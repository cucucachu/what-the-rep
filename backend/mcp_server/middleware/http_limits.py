"""HTTP-layer middleware: rate limiting, body-size cap, concurrency, and timeouts."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from threading import Lock

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mcp_server.config import HygieneSettings, ServerSettings
from mcp_server.middleware.rate_limiter import RateLimitResult, SlidingWindowRateLimiter

SendCallable = Callable[[Message], Awaitable[None]]


def client_ip_from_headers(headers: Headers, client_host: str | None) -> str:
    """Resolve the caller IP, honoring X-Forwarded-For when present."""
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if client_host:
        return client_host
    return "unknown"


def client_ip_from_scope(scope: Scope) -> str:
    headers = Headers(scope=scope)
    client = scope.get("client")
    client_host = client[0] if client else None
    return client_ip_from_headers(headers, client_host)


class BodySizeLimitMiddleware:
    """Reject requests whose bodies exceed a configured byte limit."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_body_bytes:
                    await _send_json_error(
                        send,
                        status_code=413,
                        detail="Request body too large",
                    )
                    return
            except ValueError:
                await _send_json_error(send, status_code=400, detail="Invalid Content-Length")
                return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received += len(chunk)
                if received > self.max_body_bytes:
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _send_json_error(send, status_code=413, detail="Request body too large")


class ConcurrencyLimitMiddleware:
    """Cap simultaneous in-flight requests per client IP."""

    def __init__(self, app: ASGIApp, *, max_concurrent_per_ip: int) -> None:
        self.app = app
        self.max_concurrent_per_ip = max_concurrent_per_ip
        self._active: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = client_ip_from_scope(scope)
        acquired = False
        with self._lock:
            if self._active[client_ip] >= self.max_concurrent_per_ip:
                pass
            else:
                self._active[client_ip] += 1
                acquired = True

        if not acquired:
            await _send_json_error(
                send,
                status_code=429,
                detail="Too many concurrent requests",
            )
            return

        try:
            await self.app(scope, receive, send)
        finally:
            with self._lock:
                self._active[client_ip] -= 1
                if self._active[client_ip] <= 0:
                    del self._active[client_ip]


class RequestTimeoutMiddleware:
    """Abort requests that exceed a configured wall-clock timeout."""

    def __init__(self, app: ASGIApp, *, timeout_seconds: float) -> None:
        self.app = app
        self.timeout_seconds = timeout_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await asyncio.wait_for(
                self.app(scope, receive, send),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            await _send_json_error(send, status_code=504, detail="Request timed out")


class RateLimitMiddleware:
    """Per-IP sliding-window rate limiting at the HTTP transport layer."""

    def __init__(self, app: ASGIApp, *, limiter: SlidingWindowRateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = client_ip_from_scope(scope)
        result = self.limiter.acquire(client_ip)
        if not result.allowed:
            await _send_rate_limit_response(send, result)
            return

        await self.app(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


async def _send_json_error(send: Send, *, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _send_rate_limit_response(send: Send, result: RateLimitResult) -> None:
    headers: list[tuple[bytes, bytes]] = [(b"content-type", b"application/json")]
    if result.retry_after_seconds is not None:
        retry_after = max(1, int(result.retry_after_seconds) + 1)
        headers.append((b"retry-after", str(retry_after).encode("ascii")))

    body = json.dumps(
        {
            "detail": "Rate limit exceeded",
            "retry_after_seconds": result.retry_after_seconds,
        }
    ).encode("utf-8")
    headers.append((b"content-length", str(len(body)).encode("ascii")))

    await send({"type": "http.response.start", "status": 429, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def build_hygiene_middleware(
    hygiene: HygieneSettings,
    *,
    limiter: SlidingWindowRateLimiter | None = None,
) -> list:
    """Return Starlette Middleware entries for HTTP hygiene controls."""
    from starlette.middleware import Middleware

    middleware: list[Middleware] = [
        Middleware(RequestTimeoutMiddleware, timeout_seconds=hygiene.request_timeout_seconds),
        Middleware(
            ConcurrencyLimitMiddleware,
            max_concurrent_per_ip=hygiene.max_concurrent_requests_per_ip,
        ),
        Middleware(BodySizeLimitMiddleware, max_body_bytes=hygiene.max_request_body_bytes),
    ]
    if limiter is not None:
        middleware.append(Middleware(RateLimitMiddleware, limiter=limiter))
    return middleware


def build_cors_middleware(settings: ServerSettings) -> list:
    """Return CORS middleware so browser MCP clients can call the HTTP transport."""
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware

    if not settings.cors_allow_origins:
        return []

    return [
        Middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allow_origins),
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=[
                "accept",
                "accept-language",
                "content-type",
                "mcp-protocol-version",
                "mcp-session-id",
            ],
            expose_headers=["mcp-session-id"],
        )
    ]


def build_http_middleware(
    settings: ServerSettings,
    *,
    limiter: SlidingWindowRateLimiter | None = None,
) -> list:
    """Return hygiene + CORS middleware for the Streamable HTTP app."""
    return [
        *build_cors_middleware(settings),
        *build_hygiene_middleware(settings.hygiene, limiter=limiter),
    ]

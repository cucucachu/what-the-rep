"""Integration tests for the FastMCP HTTP server and rate-limit middleware."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from mcp_server.app import create_mcp, get_http_app
from mcp_server.config import HygieneSettings, RateLimitSettings, ServerSettings
from mcp_server.middleware.rate_limiter import RateLimitWindow, SlidingWindowRateLimiter


@pytest.fixture
def tiny_limit_settings(monkeypatch: pytest.MonkeyPatch) -> ServerSettings:
    monkeypatch.setenv("RATE_LIMIT_READ_PER_MIN", "2")
    monkeypatch.setenv("RATE_LIMIT_READ_PER_DAY", "100")
    monkeypatch.setenv("MCP_MAX_REQUEST_BODY_BYTES", "1024")
    monkeypatch.setenv("MCP_MAX_CONCURRENT_REQUESTS_PER_IP", "5")
    monkeypatch.setenv("MCP_REQUEST_TIMEOUT_SECONDS", "5")
    return ServerSettings(
        rate_limit=RateLimitSettings(per_minute=2, per_day=100),
        hygiene=HygieneSettings(
            max_request_body_bytes=1024,
            max_concurrent_requests_per_ip=5,
            request_timeout_seconds=5.0,
        ),
        host="127.0.0.1",
        port=8000,
        cors_allow_origins=("http://localhost:8080",),
    )


@pytest.fixture
def tiny_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(
        windows=[RateLimitWindow(max_requests=2, window_seconds=60.0)],
    )


@asynccontextmanager
async def _http_client_for_app(app) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        asgi_transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=asgi_transport, base_url="http://test") as client:
            yield client


async def _post_mcp(
    client: httpx.AsyncClient,
    *,
    forwarded_for: str | None = None,
    body: bytes = b"{}",
) -> httpx.Response:
    headers = {"content-type": "application/json"}
    if forwarded_for is not None:
        headers["x-forwarded-for"] = forwarded_for
    return await client.post("/mcp", content=body, headers=headers)


@pytest.mark.asyncio
async def test_ping_tool_via_in_memory_client() -> None:
    mcp = create_mcp()
    async with Client(mcp) as client:
        result = await client.call_tool("ping", {})
    assert result.data == {"status": "ok"}


@pytest.mark.asyncio
async def test_ping_tool_via_streamable_http(tiny_limit_settings: ServerSettings) -> None:
    generous_limiter = SlidingWindowRateLimiter(
        windows=[RateLimitWindow(max_requests=100, window_seconds=60.0)],
    )
    mcp = create_mcp()
    app = get_http_app(
        mcp,
        settings=tiny_limit_settings,
        limiter=generous_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app):

        def factory(**kwargs):
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test",
                **kwargs,
            )

        transport = StreamableHttpTransport(
            url="http://test/mcp",
            httpx_client_factory=factory,
        )
        async with Client(transport) as client:
            result = await client.call_tool("ping", {})
    assert result.data == {"status": "ok"}


@pytest.mark.asyncio
async def test_rate_limit_returns_429_for_same_ip(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        assert (await _post_mcp(client, forwarded_for="203.0.113.10")).status_code != 429
        assert (await _post_mcp(client, forwarded_for="203.0.113.10")).status_code != 429
        blocked = await _post_mcp(client, forwarded_for="203.0.113.10")

    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") is not None
    assert blocked.json()["detail"] == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_rate_limit_does_not_block_other_ips(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        for _ in range(2):
            assert (await _post_mcp(client, forwarded_for="203.0.113.10")).status_code != 429
        assert (await _post_mcp(client, forwarded_for="203.0.113.10")).status_code == 429
        other = await _post_mcp(client, forwarded_for="198.51.100.20")

    assert other.status_code != 429


@pytest.mark.asyncio
async def test_request_body_size_limit(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        oversized = await _post_mcp(client, body=b"x" * 2048)

    assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_load_settings_reads_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "RATE_LIMIT_READ_PER_MIN",
        "RATE_LIMIT_READ_PER_DAY",
        "MCP_MAX_REQUEST_BODY_BYTES",
        "MCP_MAX_CONCURRENT_REQUESTS_PER_IP",
        "MCP_REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    from mcp_server.config import load_settings

    settings = load_settings()
    assert settings.rate_limit.per_minute == 60
    assert settings.rate_limit.per_day == 1000
    assert settings.hygiene.max_request_body_bytes == 1_048_576


@pytest.mark.asyncio
async def test_healthz_returns_200(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_preflight_allows_frontend_origin(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        response = await client.options(
            "/mcp",
            headers={
                "origin": "http://localhost:8080",
                "access-control-request-method": "POST",
                "access-control-request-headers": "content-type,mcp-session-id",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "mcp-session-id" in allow_headers


@pytest.mark.asyncio
async def test_cors_response_exposes_mcp_session_header(
    tiny_limit_settings: ServerSettings,
    tiny_limiter: SlidingWindowRateLimiter,
) -> None:
    app = get_http_app(
        settings=tiny_limit_settings,
        limiter=tiny_limiter,
        host_origin_protection=False,
    )

    async with _http_client_for_app(app) as client:
        response = await client.post(
            "/mcp",
            content=b"{}",
            headers={
                "content-type": "application/json",
                "origin": "http://localhost:8080",
            },
        )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:8080"
    expose_headers = response.headers.get("access-control-expose-headers", "").lower()
    assert "mcp-session-id" in expose_headers

"""Environment-driven configuration for the MCP HTTP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


DEFAULT_CORS_ALLOW_ORIGINS: tuple[str, ...] = (
    "http://localhost:8080",
    "http://127.0.0.1:8080",
)


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class RateLimitSettings:
    per_minute: int
    per_day: int


@dataclass(frozen=True)
class HygieneSettings:
    max_request_body_bytes: int
    max_concurrent_requests_per_ip: int
    request_timeout_seconds: float


@dataclass(frozen=True)
class ServerSettings:
    rate_limit: RateLimitSettings
    hygiene: HygieneSettings
    host: str
    port: int
    cors_allow_origins: tuple[str, ...]


def load_settings() -> ServerSettings:
    return ServerSettings(
        rate_limit=RateLimitSettings(
            per_minute=_env_int("RATE_LIMIT_READ_PER_MIN", 60),
            per_day=_env_int("RATE_LIMIT_READ_PER_DAY", 1000),
        ),
        hygiene=HygieneSettings(
            max_request_body_bytes=_env_int("MCP_MAX_REQUEST_BODY_BYTES", 1_048_576),
            max_concurrent_requests_per_ip=_env_int("MCP_MAX_CONCURRENT_REQUESTS_PER_IP", 10),
            request_timeout_seconds=_env_float("MCP_REQUEST_TIMEOUT_SECONDS", 30.0),
        ),
        host=os.environ.get("MCP_HOST", os.environ.get("FASTMCP_HOST", "127.0.0.1")),
        port=_env_int("MCP_PORT", _env_int("FASTMCP_PORT", 8000)),
        cors_allow_origins=_env_csv("MCP_CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS),
    )

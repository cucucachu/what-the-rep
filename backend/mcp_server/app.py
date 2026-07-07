"""FastMCP application factory and Streamable HTTP ASGI app."""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_server.config import ServerSettings, load_settings
from mcp_server.middleware.http_limits import build_hygiene_middleware
from mcp_server.middleware.rate_limiter import RateLimitWindow, SlidingWindowRateLimiter
from mcp_server.tools import register_home_summary_tools, register_readonly_tools
from mcp_server.ui.demo import register_debug_ui_demo_if_enabled

MCP_SERVER_NAME = "what-the-rep"


def create_mcp() -> FastMCP:
    mcp = FastMCP(MCP_SERVER_NAME)

    @mcp.tool
    def ping() -> dict[str, str]:
        """Health check — confirms the MCP server is reachable."""
        return {"status": "ok"}

    register_readonly_tools(mcp)
    register_home_summary_tools(mcp)
    register_debug_ui_demo_if_enabled(mcp)

    return mcp


def create_rate_limiter(settings: ServerSettings | None = None) -> SlidingWindowRateLimiter:
    settings = settings or load_settings()
    return SlidingWindowRateLimiter(
        windows=[
            RateLimitWindow(
                max_requests=settings.rate_limit.per_minute,
                window_seconds=60.0,
            ),
            RateLimitWindow(
                max_requests=settings.rate_limit.per_day,
                window_seconds=86_400.0,
            ),
        ]
    )


def get_http_app(
    mcp: FastMCP | None = None,
    *,
    settings: ServerSettings | None = None,
    limiter: SlidingWindowRateLimiter | None = None,
    host_origin_protection: bool = True,
):
    """Build the Streamable HTTP ASGI app with hygiene + rate-limit middleware."""
    settings = settings or load_settings()
    mcp = mcp or create_mcp()
    limiter = limiter if limiter is not None else create_rate_limiter(settings)
    middleware = build_hygiene_middleware(settings.hygiene, limiter=limiter)
    return mcp.http_app(
        transport="streamable-http",
        middleware=middleware,
        host_origin_protection=host_origin_protection,
    )


def serve() -> None:
    """Run the MCP server with Streamable HTTP transport."""
    settings = load_settings()
    mcp = create_mcp()
    limiter = create_rate_limiter(settings)
    middleware = build_hygiene_middleware(settings.hygiene, limiter=limiter)
    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        middleware=middleware,
    )

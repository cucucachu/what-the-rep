"""FastMCP application factory and Streamable HTTP ASGI app."""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp_server.config import ServerSettings, load_settings
from mcp_server.middleware.http_limits import build_http_middleware
from mcp_server.middleware.rate_limiter import RateLimitWindow, SlidingWindowRateLimiter
from mcp_server.tools import register_home_summary_tools, register_readonly_tools
from mcp_server.ui.demo import register_debug_ui_demo_if_enabled

MCP_SERVER_NAME = "what-the-rep"


async def healthz(_request: Request) -> JSONResponse:
    """Plain HTTP readiness probe for Playwright/CI (returns 200)."""
    return JSONResponse({"status": "ok"})


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
    middleware = build_http_middleware(settings, limiter=limiter)
    mcp_app = mcp.http_app(
        transport="streamable-http",
        middleware=middleware,
        host_origin_protection=host_origin_protection,
        allowed_origins=list(settings.cors_allow_origins),
    )
    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        lifespan=mcp_app.lifespan,
    )


def serve() -> None:
    """Run the MCP server with Streamable HTTP transport."""
    import uvicorn

    settings = load_settings()
    app = get_http_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port)

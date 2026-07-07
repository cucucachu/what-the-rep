"""FastMCP server package: tools, ui:// resources, and prompts."""

from mcp_server.app import create_mcp, get_http_app, serve

__all__ = ["create_mcp", "get_http_app", "serve"]

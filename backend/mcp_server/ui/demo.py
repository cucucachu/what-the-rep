"""Scaffolding MCP-UI demo tool — remove once T12–T14 real widgets land."""

from __future__ import annotations

import os

from fastmcp import FastMCP

from mcp_server.ui.helpers import register_html_ui_resource, ui_app_config

DEBUG_UI_URI = "ui://debug/demo"
DEBUG_UI_ENV = "MCP_DEBUG_UI"

_DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MCP-UI Demo</title>
</head>
<body>
  <h1>Hello from MCP-UI</h1>
  <p>What The Rep — T11 plumbing demo (scaffolding only).</p>
</body>
</html>"""


def debug_ui_enabled() -> bool:
    raw = os.environ.get(DEBUG_UI_ENV, "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def register_debug_ui_demo(mcp: FastMCP) -> None:
    """Register ``_debug_ui_demo`` and its linked ``ui://`` resource."""
    register_html_ui_resource(mcp, DEBUG_UI_URI, _DEMO_HTML)

    @mcp.tool(app=ui_app_config(DEBUG_UI_URI))
    def _debug_ui_demo() -> dict[str, str]:
        """Scaffolding: minimal MCP-UI demo for T11 plumbing (remove after T12)."""
        return {"status": "ok", "message": "MCP-UI demo tool"}


def register_debug_ui_demo_if_enabled(mcp: FastMCP) -> None:
    if debug_ui_enabled():
        register_debug_ui_demo(mcp)

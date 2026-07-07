"""MCP Apps / MCP-UI resource helpers shared by widget tools (T12–T14)."""

from mcp_server.ui.demo import (
    DEBUG_UI_URI,
    debug_ui_enabled,
    register_debug_ui_demo,
    register_debug_ui_demo_if_enabled,
)
from mcp_server.ui.helpers import (
    MCP_APP_MIME_TYPE,
    build_raw_html_ui_resource,
    html_from_ui_resource,
    register_html_ui_resource,
    tool_ui_resource_uri,
    ui_app_config,
)

__all__ = [
    "DEBUG_UI_URI",
    "MCP_APP_MIME_TYPE",
    "build_raw_html_ui_resource",
    "debug_ui_enabled",
    "html_from_ui_resource",
    "register_debug_ui_demo",
    "register_debug_ui_demo_if_enabled",
    "register_html_ui_resource",
    "tool_ui_resource_uri",
    "ui_app_config",
]

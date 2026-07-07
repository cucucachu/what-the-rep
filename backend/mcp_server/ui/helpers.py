"""Reusable MCP Apps / MCP-UI helpers for T12–T14 widget tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastmcp import FastMCP
from fastmcp.apps import AppConfig
from fastmcp.utilities.mime import UI_MIME_TYPE
from mcp_ui_server import create_ui_resource

MCP_APP_MIME_TYPE = UI_MIME_TYPE


def build_raw_html_ui_resource(uri: str, html: str) -> Any:
    """Build and validate a raw-HTML UI resource via ``mcp-ui-server``.

    Returns a ``UIResource`` suitable for legacy MCP-UI tool-result embedding.
    For MCP Apps (SEP-1865), prefer ``register_html_ui_resource`` +
    ``ui_app_config`` so hosts fetch HTML via ``resources/read``.
    """
    if not uri.startswith("ui://"):
        msg = f"UI resource URI must use the ui:// scheme, got: {uri!r}"
        raise ValueError(msg)
    return create_ui_resource(
        {
            "uri": uri,
            "content": {"type": "rawHtml", "htmlString": html},
            "encoding": "text",
        }
    )


def html_from_ui_resource(ui_resource: Any) -> str:
    """Extract plain HTML text from a ``create_ui_resource`` result."""
    text = ui_resource.resource.text
    if not isinstance(text, str) or not text.strip():
        msg = "UI resource has no HTML text content"
        raise ValueError(msg)
    return text


def ui_app_config(resource_uri: str, **kwargs: Any) -> AppConfig:
    """Return FastMCP ``AppConfig`` linking a tool to a ``ui://`` resource."""
    return AppConfig(resource_uri=resource_uri, **kwargs)


def register_html_ui_resource(
    mcp: FastMCP,
    uri: str,
    html: str | Callable[[], str],
) -> None:
    """Register a static ``ui://`` HTML resource on a FastMCP server.

    Uses ``mcp-ui-server`` to validate/build HTML, then registers the resource
    with FastMCP (which serves ``ui://`` URIs as ``text/html;profile=mcp-app``).
    """
    if callable(html):
        html_factory = html

        @mcp.resource(uri)
        def _dynamic_ui_resource() -> str:
            body = html_factory()
            return html_from_ui_resource(build_raw_html_ui_resource(uri, body))

    else:
        html_body = html_from_ui_resource(build_raw_html_ui_resource(uri, html))

        @mcp.resource(uri)
        def _static_ui_resource() -> str:
            return html_body


def tool_ui_resource_uri(tool_meta: dict[str, Any] | None) -> str | None:
    """Read ``_meta.ui.resourceUri`` from a FastMCP tool definition's ``meta``."""
    if not tool_meta:
        return None
    ui_meta = tool_meta.get("ui")
    if not isinstance(ui_meta, dict):
        return None
    resource_uri = ui_meta.get("resourceUri")
    return str(resource_uri) if resource_uri else None

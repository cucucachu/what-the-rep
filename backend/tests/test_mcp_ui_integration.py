"""Integration tests for MCP Apps / MCP-UI plumbing (T11, DB-free)."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from mcp_server.app import create_mcp
from mcp_server.ui.demo import DEBUG_UI_URI
from mcp_server.ui.helpers import MCP_APP_MIME_TYPE, tool_ui_resource_uri


@pytest.fixture
def mcp_with_debug_ui(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MCP_DEBUG_UI", "1")
    return create_mcp()


@pytest.mark.asyncio
async def test_debug_ui_tool_not_registered_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_DEBUG_UI", raising=False)
    mcp = create_mcp()

    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert "_debug_ui_demo" not in {tool.name for tool in tools}


@pytest.mark.asyncio
async def test_debug_ui_tool_links_ui_resource(mcp_with_debug_ui) -> None:
    async with Client(mcp_with_debug_ui) as client:
        tools = await client.list_tools()
        demo_tool = next(tool for tool in tools if tool.name == "_debug_ui_demo")
        resource_uri = tool_ui_resource_uri(demo_tool.meta)

        assert resource_uri == DEBUG_UI_URI
        assert resource_uri.startswith("ui://")

        result = await client.call_tool("_debug_ui_demo", {})
        assert result.data == {"status": "ok", "message": "MCP-UI demo tool"}
        # FastMCP 3.4.3 surfaces MCP Apps linkage on the tool definition (list_tools
        # meta), not on CallToolResult.meta — hosts discover the UI via tool _meta.
        assert result.meta is None

        contents = await client.read_resource(DEBUG_UI_URI)

    assert len(contents) == 1
    resource = contents[0]
    assert str(resource.uri) == DEBUG_UI_URI
    assert resource.mimeType == MCP_APP_MIME_TYPE
    assert isinstance(resource.text, str)
    assert "<h1>Hello from MCP-UI</h1>" in resource.text
    assert "<html" in resource.text.lower()

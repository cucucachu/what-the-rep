"""Integration tests for get_home_summary tool and ui://home-summary widget (T12)."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from db.client import close_client, get_client, ping
from ingestion.officials.marin_county import ingest_marin_county_supervisors
from ingestion.officials.novato import ingest_novato_council
from ingestion.pipeline.run import run_ingestion_pipeline
from ingestion.registry.marin_seed import (
    SLUG_MARIN_COUNTY,
    SLUG_NOVATO,
    seed_marin_jurisdictions,
)
from mcp_server.app import create_mcp
from mcp_server.ui.helpers import MCP_APP_MIME_TYPE, tool_ui_resource_uri
from mcp_server.ui.home_summary import HOME_SUMMARY_URI

TEST_DB_NAME = "what_the_rep_home_summary_test"


@pytest.fixture
async def seeded_db(monkeypatch: pytest.MonkeyPatch):
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    monkeypatch.setenv("MONGODB_DB_NAME", TEST_DB_NAME)
    await close_client()

    db = get_client()[TEST_DB_NAME]
    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)

    await seed_marin_jurisdictions(db)
    await ingest_novato_council(db)
    await ingest_marin_county_supervisors(db)
    await run_ingestion_pipeline(db, SLUG_NOVATO)
    await run_ingestion_pipeline(db, SLUG_MARIN_COUNTY)

    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


@pytest.fixture
def mcp_client():
    return create_mcp()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_home_summary_both_jurisdictions(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool(
            "get_home_summary",
            {"jurisdiction_slugs": ["novato-ca", "marin-county-ca"]},
        )

    data = result.data
    assert data["jurisdiction_slugs"] == ["novato-ca", "marin-county-ca"]
    assert len(data["jurisdictions"]) == 2

    novato = data["jurisdictions"][0]
    assert novato["found"] is True
    assert novato["slug"] == "novato-ca"
    assert novato["jurisdiction"]["slug"] == "novato-ca"
    assert len(novato["recent_meetings"]) >= 1
    assert novato["recent_meetings"][0]["scheduled_start"].startswith("2024-01-23")
    assert len(novato["notable_actions"]) >= 1
    novato_names = {h["person"]["full_name"] for h in novato["current_officeholders"]}
    assert any("Eklund" in name for name in novato_names)

    marin = data["jurisdictions"][1]
    assert marin["found"] is True
    assert marin["slug"] == "marin-county-ca"
    assert len(marin["recent_meetings"]) >= 1
    assert len(marin["notable_actions"]) >= 1
    marin_names = {h["person"]["full_name"] for h in marin["current_officeholders"]}
    assert any("Sackett" in name for name in marin_names)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_home_summary_links_ui_resource(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        tools = await client.list_tools()
        home_tool = next(tool for tool in tools if tool.name == "get_home_summary")
        resource_uri = tool_ui_resource_uri(home_tool.meta)

        assert resource_uri == HOME_SUMMARY_URI

        await client.call_tool(
            "get_home_summary",
            {"jurisdiction_slugs": ["novato-ca", "marin-county-ca"]},
        )
        contents = await client.read_resource(HOME_SUMMARY_URI)

    assert len(contents) == 1
    resource = contents[0]
    assert str(resource.uri) == HOME_SUMMARY_URI
    assert resource.mimeType == MCP_APP_MIME_TYPE
    assert isinstance(resource.text, str)
    assert "Government Activity Summary" in resource.text
    assert "City of Novato" in resource.text
    assert "Marin County" in resource.text
    assert "Recent Meetings" in resource.text
    assert "Recent Votes" in resource.text
    assert "Current Officeholders" in resource.text
    assert "Pat Eklund" in resource.text or "Eklund" in resource.text
    assert "Mary Sackett" in resource.text or "Sackett" in resource.text
    assert "2024-01-23" in resource.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_home_summary_unknown_jurisdiction_graceful(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool(
            "get_home_summary",
            {"jurisdiction_slugs": ["unknown-slug"]},
        )
        contents = await client.read_resource(HOME_SUMMARY_URI)

    entry = result.data["jurisdictions"][0]
    assert entry["found"] is False
    assert entry["recent_meetings"] == []
    assert entry["notable_actions"] == []
    assert entry["current_officeholders"] == []

    html = contents[0].text
    assert "Jurisdiction not found." in html

"""Integration tests for get_action vote-tally widget linkage (T13)."""

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
from mcp_server.ui.action_vote_tally import ACTION_VOTE_TALLY_URI
from mcp_server.ui.helpers import MCP_APP_MIME_TYPE, tool_ui_resource_uri

TEST_DB_NAME = "what_the_rep_action_vote_tally_test"


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
async def test_get_action_links_ui_resource_and_structured_output_unchanged(
    seeded_db,
    mcp_client,
) -> None:
    action = await seeded_db.actions.find_one({"external_id": {"$regex": "2024-011"}})
    assert action is not None

    async with Client(mcp_client) as client:
        tools = await client.list_tools()
        action_tool = next(tool for tool in tools if tool.name == "get_action")
        resource_uri = tool_ui_resource_uri(action_tool.meta)

        assert resource_uri == ACTION_VOTE_TALLY_URI

        result = await client.call_tool("get_action", {"action_id": str(action["_id"])})
        contents = await client.read_resource(ACTION_VOTE_TALLY_URI)

    data = result.data
    assert data["found"] is True
    assert data["action"]["vote_tally"]["ayes"] == 4
    assert data["action"]["vote_tally"]["noes"] == 1
    assert len(data["vote_records"]) == 5
    assert "action" in data
    assert "meeting" in data
    assert "agenda_item" in data
    assert "documents" in data

    eklund_vote = next(
        record
        for record in data["vote_records"]
        if record["person"] and "Eklund" in record["person"]["full_name"]
    )
    assert eklund_vote["vote_record"]["vote"] == "no"

    assert len(contents) == 1
    resource = contents[0]
    assert str(resource.uri) == ACTION_VOTE_TALLY_URI
    assert resource.mimeType == MCP_APP_MIME_TYPE
    html = resource.text
    assert isinstance(html, str)
    assert "passed" in html
    assert 'class="count">4</span>' in html
    assert 'class="count">1</span>' in html
    assert "Resolution 2024-011" in html or "2024-011" in html
    assert "Pat Eklund" in html
    assert "Moved by:" in html
    assert "Seconded by:" in html

    unresolved = [
        record for record in data["vote_records"] if record["person"] is None
    ]
    assert len(unresolved) >= 1
    for record in unresolved:
        external_id = record["vote_record"]["external_id"]
        raw_name = external_id.rsplit(":", 1)[-1]
        assert raw_name in html

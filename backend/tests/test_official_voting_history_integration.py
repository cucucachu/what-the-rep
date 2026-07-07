"""Integration tests for get_official voting-history widget linkage (T14)."""

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
from mcp_server.ui.official_voting_history import OFFICIAL_VOTING_HISTORY_URI

TEST_DB_NAME = "what_the_rep_official_voting_history_test"


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
async def test_get_official_links_ui_resource_and_structured_output_unchanged(
    seeded_db,
    mcp_client,
) -> None:
    person = await seeded_db.people.find_one({"full_name": {"$regex": "Eklund"}})
    assert person is not None

    async with Client(mcp_client) as client:
        tools = await client.list_tools()
        official_tool = next(tool for tool in tools if tool.name == "get_official")
        resource_uri = tool_ui_resource_uri(official_tool.meta)

        assert resource_uri == OFFICIAL_VOTING_HISTORY_URI

        result = await client.call_tool("get_official", {"person_id": str(person["_id"])})
        contents = await client.read_resource(OFFICIAL_VOTING_HISTORY_URI)

    data = result.data
    assert data["found"] is True
    assert "Eklund" in data["person"]["full_name"]
    assert len(data["tenure_history"]) >= 1
    assert data["tenure_history"][0]["office"]["title"]
    assert any(entry["vote_record"]["vote"] == "no" for entry in data["voting_record"])
    assert "person" in data
    assert "tenure_history" in data
    assert "voting_record" in data

    no_vote = next(
        entry
        for entry in data["voting_record"]
        if entry["vote_record"]["vote"] == "no"
        and (
            "2024-011" in (entry["action"].get("description") or "")
            or "2024-011" in str(entry["action"].get("external_id", ""))
        )
    )
    action_description = no_vote["action"]["description"] or ""
    assert "2024-011" in action_description or "2024-011" in str(
        no_vote["action"].get("external_id", "")
    )

    assert len(contents) == 1
    resource = contents[0]
    assert str(resource.uri) == OFFICIAL_VOTING_HISTORY_URI
    assert resource.mimeType == MCP_APP_MIME_TYPE
    html = resource.text
    assert isinstance(html, str)
    assert "Pat Eklund" in html
    assert "Tenure Timeline" in html
    assert "Voting Record" in html
    assert "2024-011" in html
    assert 'class="vote-badge no">No</span>' in html
    assert "badge-current" in html


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_official_empty_voting_record_widget_graceful(
    seeded_db,
    mcp_client,
) -> None:
    """Supervisors may have no per-person vote records in the pilot fixture."""
    person = await seeded_db.people.find_one({"full_name": {"$regex": "Sackett"}})
    if person is None:
        person = await seeded_db.people.find_one(
            {"full_name": {"$regex": "Supervisor"}},
        )
    if person is None:
        pytest.skip("No supervisor with empty voting record found in fixture")

    async with Client(mcp_client) as client:
        result = await client.call_tool("get_official", {"person_id": str(person["_id"])})
        contents = await client.read_resource(OFFICIAL_VOTING_HISTORY_URI)

    data = result.data
    assert data["found"] is True
    assert len(data["tenure_history"]) >= 1

    html = contents[0].text
    assert isinstance(html, str)
    assert data["person"]["full_name"] in html
    if not data["voting_record"]:
        assert "No recorded votes on file for this official." in html

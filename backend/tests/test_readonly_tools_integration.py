"""Integration tests for read-only structured MCP tools (T9)."""

from __future__ import annotations

import pytest
from bson import ObjectId
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

TEST_DB_NAME = "what_the_rep_readonly_tools_test"


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
async def test_get_jurisdiction_novato(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool("get_jurisdiction", {"slug": "novato-ca"})

    data = result.data
    assert data["found"] is True
    assert data["jurisdiction"]["slug"] == "novato-ca"
    assert len(data["governing_bodies"]) >= 1
    assert data["recent_activity"]["latest_meeting"] is not None
    assert data["recent_activity"]["latest_meeting"]["scheduled_start"].startswith("2024-01-23")

    names = {holder["person"]["full_name"] for holder in data["current_officeholders"]}
    assert any("Eklund" in name for name in names)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_jurisdictions_returns_seeded_hierarchy(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        all_result = await client.call_tool("list_jurisdictions", {})
        california_children = await client.call_tool(
            "list_jurisdictions",
            {"parent_slug": "california"},
        )

    slugs = {item["slug"] for item in all_result.data["jurisdictions"]}
    assert slugs == {"united-states", "california", "marin-county-ca", "novato-ca"}
    assert all_result.data["count"] == 4

    child_slugs = {item["slug"] for item in california_children.data["jurisdictions"]}
    assert child_slugs == {"marin-county-ca"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_meetings_by_jurisdiction_and_date(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool(
            "search_meetings",
            {
                "jurisdiction_slug": "novato-ca",
                "date_range": {"start": "2024-01-23", "end": "2024-01-23"},
            },
        )

    data = result.data
    assert data["count"] == 1
    meeting = data["meetings"][0]
    assert meeting["scheduled_start"].startswith("2024-01-23")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_meeting_full_payload(seeded_db, mcp_client) -> None:
    meeting = await seeded_db.meetings.find_one({"external_id": "1980"})
    assert meeting is not None

    async with Client(mcp_client) as client:
        result = await client.call_tool(
            "get_meeting",
            {"meeting_id": str(meeting["_id"])},
        )

    data = result.data
    assert data["found"] is True
    assert data["meeting"]["id"] == str(meeting["_id"])
    assert data["governing_body"]["name"] == "Novato City Council"
    assert len(data["agenda_items"]) > 0
    assert any(item["actions"] for item in data["agenda_items"])
    assert "meeting_documents" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_actions_resolution_2024_011(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool(
            "search_actions",
            {"jurisdiction_slug": "novato-ca", "query": "2024-011"},
        )

    data = result.data
    assert data["count"] >= 1
    assert any(
        "2024-011" in (action.get("description") or "")
        or "2024-011" in (action.get("external_id") or "")
        for action in data["actions"]
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_action_roll_call_4_1(seeded_db, mcp_client) -> None:
    action = await seeded_db.actions.find_one({"external_id": {"$regex": "2024-011"}})
    assert action is not None

    async with Client(mcp_client) as client:
        result = await client.call_tool("get_action", {"action_id": str(action["_id"])})

    data = result.data
    assert data["found"] is True
    assert data["action"]["vote_tally"]["ayes"] == 4
    assert data["action"]["vote_tally"]["noes"] == 1
    assert len(data["vote_records"]) == 5

    eklund_vote = next(
        record
        for record in data["vote_records"]
        if record["person"] and "Eklund" in record["person"]["full_name"]
    )
    assert eklund_vote["vote_record"]["vote"] == "no"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_official_pat_eklund(seeded_db, mcp_client) -> None:
    person = await seeded_db.people.find_one({"full_name": {"$regex": "Eklund"}})
    assert person is not None

    async with Client(mcp_client) as client:
        result = await client.call_tool("get_official", {"person_id": str(person["_id"])})

    data = result.data
    assert data["found"] is True
    assert "Eklund" in data["person"]["full_name"]
    assert len(data["tenure_history"]) >= 1
    assert data["tenure_history"][0]["office"]["title"]
    assert any(entry["vote_record"]["vote"] == "no" for entry in data["voting_record"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_meeting_not_found(seeded_db, mcp_client) -> None:
    missing_id = str(ObjectId())

    async with Client(mcp_client) as client:
        result = await client.call_tool("get_meeting", {"meeting_id": missing_id})

    data = result.data
    assert data["found"] is False
    assert data["meeting_id"] == missing_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_meeting_invalid_id(seeded_db, mcp_client) -> None:
    async with Client(mcp_client) as client:
        result = await client.call_tool("get_meeting", {"meeting_id": "not-an-object-id"})

    data = result.data
    assert data["found"] is False
    assert data["meeting_id"] == "not-an-object-id"

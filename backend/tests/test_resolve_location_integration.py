"""Integration tests for resolve_location MCP tool (T10)."""

from __future__ import annotations

import pytest
from fastmcp.client import Client

from db.client import close_client, create_indexes, get_client, ping
from ingestion.boundaries.load import load_boundaries_from_fixtures
from ingestion.registry.marin_seed import seed_marin_jurisdictions
from mcp_server.app import create_mcp
from mcp_server.tools.location import jurisdiction_stack_names

TEST_DB_NAME = "what_the_rep_resolve_location_test"

NOVATO_CITY_HALL = (38.1074, -122.5697)
POINT_REYES_AREA = (38.0700, -122.8080)
NYC = (40.7128, -74.0060)


@pytest.fixture
async def seeded_db_with_boundaries(monkeypatch: pytest.MonkeyPatch):
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    monkeypatch.setenv("MONGODB_DB_NAME", TEST_DB_NAME)
    await close_client()

    db = get_client()[TEST_DB_NAME]
    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)

    await seed_marin_jurisdictions(db)
    await create_indexes(db)
    await load_boundaries_from_fixtures(db)

    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


@pytest.fixture
def mcp_client():
    return create_mcp()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_location_novato_city_hall(
    seeded_db_with_boundaries,
    mcp_client,
) -> None:
    lat, lng = NOVATO_CITY_HALL
    async with Client(mcp_client) as client:
        result = await client.call_tool("resolve_location", {"lat": lat, "lng": lng})

    data = result.data
    assert data["covered"] is True
    assert data["lat"] == lat
    assert data["lng"] == lng
    names = jurisdiction_stack_names(data)
    assert names == ["City of Novato", "Marin County", "California", "United States"]
    slugs = [item["slug"] for item in data["jurisdictions"]]
    assert slugs == ["novato-ca", "marin-county-ca", "california", "united-states"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_location_unincorporated_marin(
    seeded_db_with_boundaries,
    mcp_client,
) -> None:
    lat, lng = POINT_REYES_AREA
    async with Client(mcp_client) as client:
        result = await client.call_tool("resolve_location", {"lat": lat, "lng": lng})

    data = result.data
    assert data["covered"] is True
    names = jurisdiction_stack_names(data)
    assert names == ["Marin County", "California", "United States"]
    slugs = [item["slug"] for item in data["jurisdictions"]]
    assert slugs == ["marin-county-ca", "california", "united-states"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolve_location_outside_pilot_coverage(
    seeded_db_with_boundaries,
    mcp_client,
) -> None:
    lat, lng = NYC
    async with Client(mcp_client) as client:
        result = await client.call_tool("resolve_location", {"lat": lat, "lng": lng})

    data = result.data
    assert data["covered"] is False
    assert data["jurisdictions"] == []
    assert "outside" in data["message"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_geo_intersects_uses_2dsphere_index(seeded_db_with_boundaries) -> None:
    db = seeded_db_with_boundaries
    explain = await db.jurisdictions.find(
        {
            "boundary": {
                "$geoIntersects": {
                    "$geometry": {"type": "Point", "coordinates": [-122.5697, 38.1074]},
                }
            }
        }
    ).explain()

    winning_plan = explain.get("queryPlanner", {}).get("winningPlan", {})
    assert _plan_uses_2dsphere(winning_plan)


def _plan_uses_2dsphere(plan: dict) -> bool:
    if plan.get("stage") == "GEO_NEAR_2DSPHERE":
        return True
    if plan.get("stage") == "IXSCAN" and plan.get("indexName") == "boundary_2dsphere":
        return True
    for key in ("inputStage", "innerStage", "shards"):
        child = plan.get(key)
        if isinstance(child, dict) and _plan_uses_2dsphere(child):
            return True
        if isinstance(child, list):
            return any(_plan_uses_2dsphere(item) for item in child if isinstance(item, dict))
    return False

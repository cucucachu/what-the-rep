"""Integration tests for officeholder ingestion (T5)."""

from __future__ import annotations

import pytest

from db.client import close_client, get_client, ping
from ingestion.officials.marin_county import (
    MARIN_BOS_NAME,
    MARIN_BOS_SOURCE_URL,
    ingest_marin_county_supervisors,
)
from ingestion.officials.novato import (
    NOVATO_COUNCIL_NAME,
    NOVATO_COUNCIL_SOURCE_URL,
    ingest_novato_council,
)
from ingestion.registry.marin_seed import SLUG_MARIN_COUNTY, SLUG_NOVATO, seed_marin_jurisdictions
from tests.test_officials_parsers import MARIN_EXPECTED, NOVATO_EXPECTED

TEST_DB_NAME = "what_the_rep_officials_test"


@pytest.fixture
async def officials_db():
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    db = get_client()[TEST_DB_NAME]
    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


async def _assert_sources(collection, expected_count: int) -> None:
    docs = await collection.find({}).to_list(length=expected_count + 10)
    assert len(docs) >= expected_count
    for doc in docs:
        assert doc.get("sources"), f"{collection.name} record missing sources: {doc.get('_id')}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_novato_council(officials_db) -> None:
    seed = await seed_marin_jurisdictions(officials_db)
    novato_id = seed.ids[SLUG_NOVATO]

    result = await ingest_novato_council(officials_db)

    body = await officials_db.governing_bodies.find_one({"_id": result.body_id})
    assert body is not None
    assert body["name"] == NOVATO_COUNCIL_NAME
    assert body["type"] == "legislative"
    assert body["jurisdiction_id"] == novato_id

    offices = await officials_db.offices.find({"jurisdiction_id": novato_id}).to_list(length=20)
    assert len(offices) == len(NOVATO_EXPECTED)
    office_titles = sorted(o["title"] for o in offices)
    assert office_titles == sorted(title for title, _, _, _ in NOVATO_EXPECTED)

    people = await officials_db.people.find({}).to_list(length=20)
    assert len(people) == 5  # Rachel Farac holds Mayor + District 2 seat

    tenures = await officials_db.office_tenures.find({"is_current": True}).to_list(length=20)
    assert len(tenures) == len(NOVATO_EXPECTED)

    for tenure in tenures:
        office = await officials_db.offices.find_one({"_id": tenure["office_id"]})
        person = await officials_db.people.find_one({"_id": tenure["person_id"]})
        assert office is not None and person is not None
        assert tenure["end_date"] is None
        assert tenure["sources"][0]["url"] == NOVATO_COUNCIL_SOURCE_URL

    await _assert_sources(officials_db.governing_bodies, 1)
    await _assert_sources(officials_db.offices, len(NOVATO_EXPECTED))
    await _assert_sources(officials_db.people, 5)
    await _assert_sources(officials_db.office_tenures, len(NOVATO_EXPECTED))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_marin_county_supervisors(officials_db) -> None:
    seed = await seed_marin_jurisdictions(officials_db)
    marin_id = seed.ids[SLUG_MARIN_COUNTY]

    result = await ingest_marin_county_supervisors(officials_db)

    body = await officials_db.governing_bodies.find_one({"_id": result.body_id})
    assert body is not None
    assert body["name"] == MARIN_BOS_NAME
    assert body["type"] == "legislative"
    assert body["jurisdiction_id"] == marin_id

    offices = await officials_db.offices.find({"jurisdiction_id": marin_id}).to_list(length=20)
    assert len(offices) == len(MARIN_EXPECTED)

    tenures = await officials_db.office_tenures.find({"is_current": True}).to_list(length=20)
    assert len(tenures) == len(MARIN_EXPECTED)

    for title, name, district in MARIN_EXPECTED:
        office = await officials_db.offices.find_one(
            {"jurisdiction_id": marin_id, "title": title, "district": district},
        )
        assert office is not None
        person = await officials_db.people.find_one({"full_name": name})
        assert person is not None
        tenure = await officials_db.office_tenures.find_one(
            {"office_id": office["_id"], "person_id": person["_id"], "is_current": True},
        )
        assert tenure is not None
        assert tenure["sources"][0]["url"] == MARIN_BOS_SOURCE_URL

    await _assert_sources(officials_db.governing_bodies, 1)
    await _assert_sources(officials_db.offices, len(MARIN_EXPECTED))
    await _assert_sources(officials_db.people, len(MARIN_EXPECTED))
    await _assert_sources(officials_db.office_tenures, len(MARIN_EXPECTED))

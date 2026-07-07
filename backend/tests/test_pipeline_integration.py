"""Integration tests for the full ingestion pipeline (T6)."""

from __future__ import annotations

import pytest

from db.client import close_client, get_client, ping
from ingestion.officials.marin_county import ingest_marin_county_supervisors
from ingestion.officials.novato import ingest_novato_council
from ingestion.pipeline.run import run_ingestion_pipeline
from ingestion.registry.marin_seed import SLUG_MARIN_COUNTY, SLUG_NOVATO, seed_marin_jurisdictions

TEST_DB_NAME = "what_the_rep_pipeline_test"


@pytest.fixture
async def pipeline_db():
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    db = get_client()[TEST_DB_NAME]
    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


async def _seed_officials(db, slug: str) -> None:
    await seed_marin_jurisdictions(db)
    if slug == SLUG_NOVATO:
        await ingest_novato_council(db)
    elif slug == SLUG_MARIN_COUNTY:
        await ingest_marin_county_supervisors(db)


async def _collection_counts(db) -> dict[str, int]:
    names = ("meetings", "agenda_items", "actions", "vote_records")
    return {name: await db[name].count_documents({}) for name in names}


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("slug", [SLUG_NOVATO, SLUG_MARIN_COUNTY])
async def test_pipeline_idempotent_two_runs(pipeline_db, slug: str) -> None:
    await _seed_officials(pipeline_db, slug)

    first = await run_ingestion_pipeline(pipeline_db, slug)
    assert first.status.value == "success"
    assert first.stats.meetings_found == 1
    assert first.stats.meetings_upserted == 1
    assert first.stats.agenda_items_upserted > 0

    counts_after_first = await _collection_counts(pipeline_db)

    second = await run_ingestion_pipeline(pipeline_db, slug)
    assert second.status.value == "success"
    assert second.stats.meetings_upserted == 0
    assert second.stats.agenda_items_upserted == 0
    assert second.stats.actions_upserted == 0

    counts_after_second = await _collection_counts(pipeline_db)
    assert counts_after_second == counts_after_first
    assert await pipeline_db.ingestion_runs.count_documents({}) == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_novato_resolution_2024_011_roll_call(pipeline_db) -> None:
    await _seed_officials(pipeline_db, SLUG_NOVATO)
    await run_ingestion_pipeline(pipeline_db, SLUG_NOVATO)

    action = await pipeline_db.actions.find_one(
        {"external_id": {"$regex": "2024-011"}},
    )
    assert action is not None
    assert action["vote_tally"]["ayes"] == 4
    assert action["vote_tally"]["noes"] == 1

    vote_records = await pipeline_db.vote_records.find({"action_id": action["_id"]}).to_list(
        length=10,
    )
    assert len(vote_records) == 5
    people = {}
    for record in vote_records:
        if record.get("person_id") is not None:
            people[record["person_id"]] = record
    eklund_record = None
    for person_id, record in people.items():
        person = await pipeline_db.people.find_one({"_id": person_id})
        assert person is not None
        if "Eklund" in person["full_name"]:
            eklund_record = record
            break
    assert eklund_record is not None
    assert eklund_record["vote"] == "no"

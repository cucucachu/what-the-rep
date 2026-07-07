"""Unit and integration tests for Marin jurisdiction seed script."""

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from db.client import close_client, get_client, ping
from ingestion.registry.marin_seed import (
    SLUG_CALIFORNIA,
    SLUG_MARIN_COUNTY,
    SLUG_NOVATO,
    SLUG_UNITED_STATES,
    build_jurisdiction_path,
    documents_equal,
    seed_marin_jurisdictions,
)

TEST_DB_NAME = "what_the_rep_marin_seed_test"


class TestBuildJurisdictionPath:
    def test_root_jurisdiction_has_empty_path(self) -> None:
        assert build_jurisdiction_path([], None) == []

    def test_child_path_appends_parent_id_root_first(self) -> None:
        us_id = ObjectId()
        ca_id = ObjectId()
        marin_id = ObjectId()

        assert build_jurisdiction_path([], us_id) == [us_id]
        assert build_jurisdiction_path([us_id], ca_id) == [us_id, ca_id]
        assert build_jurisdiction_path([us_id, ca_id], marin_id) == [us_id, ca_id, marin_id]


class TestDocumentsEqual:
    def test_ignores_updated_at(self) -> None:
        doc_id = ObjectId()
        created = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
        left = {
            "_id": doc_id,
            "slug": "novato-ca",
            "created_at": created,
            "updated_at": datetime(2026, 7, 6, 12, 0, tzinfo=UTC),
            "name": "City of Novato",
        }
        right = {
            **_left_copy(left),
            "updated_at": datetime(2026, 7, 7, 8, 30, tzinfo=UTC),
        }
        assert documents_equal(left, right)


def _left_copy(left: dict) -> dict:
    return {key: value for key, value in left.items()}


@pytest.fixture
async def seed_db():
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    db = get_client()[TEST_DB_NAME]
    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seed_marin_jurisdictions_is_idempotent(seed_db) -> None:
    first = await seed_marin_jurisdictions(seed_db)
    assert first.modified == 4

    count_after_first = await seed_db.jurisdictions.count_documents({})
    assert count_after_first == 4

    first_snapshot = await _snapshot_jurisdictions(seed_db)

    second = await seed_marin_jurisdictions(seed_db)
    assert second.modified == 0

    count_after_second = await seed_db.jurisdictions.count_documents({})
    assert count_after_second == 4

    second_snapshot = await _snapshot_jurisdictions(seed_db)
    assert second_snapshot == first_snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_seed_marin_jurisdictions_hierarchy(seed_db) -> None:
    await seed_marin_jurisdictions(seed_db)

    us = await seed_db.jurisdictions.find_one({"slug": SLUG_UNITED_STATES})
    ca = await seed_db.jurisdictions.find_one({"slug": SLUG_CALIFORNIA})
    marin = await seed_db.jurisdictions.find_one({"slug": SLUG_MARIN_COUNTY})
    novato = await seed_db.jurisdictions.find_one({"slug": SLUG_NOVATO})

    assert us is not None and us["level"] == "federal" and us["status"] == "stub"
    assert us["path"] == []
    assert us["parent_id"] is None

    assert ca is not None and ca["level"] == "state" and ca["status"] == "stub"
    assert ca["parent_id"] == us["_id"]
    assert ca["path"] == [us["_id"]]

    assert marin is not None and marin["level"] == "county" and marin["status"] == "pilot"
    assert marin["parent_id"] == ca["_id"]
    assert marin["path"] == [us["_id"], ca["_id"]]
    assert marin["population"] == 253_694
    assert marin["fips"]["geoid"] == "06041"

    assert novato is not None and novato["level"] == "city" and novato["status"] == "pilot"
    assert novato["government_type"] == "general_law"
    assert novato["parent_id"] == marin["_id"]
    assert novato["path"] == [us["_id"], ca["_id"], marin["_id"]]
    assert novato["population"] == 51_947
    assert novato["fips"]["place_fips"] == "52582"
    assert novato["incorporated_date"].year == 1960


async def _snapshot_jurisdictions(db) -> list[dict]:
    docs = []
    async for doc in db.jurisdictions.find({}).sort("slug", 1):
        docs.append(
            {key: value for key, value in doc.items() if key not in {"created_at", "updated_at"}}
        )
    return docs

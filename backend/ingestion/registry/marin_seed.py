"""Marin pilot jurisdiction seed data and idempotent upsert logic (T4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase

from db.client import get_db
from db.models.common import FipsCodes, SourceRef
from db.models.enums import (
    GovernmentType,
    JurisdictionLevel,
    JurisdictionStatus,
    SourceMethod,
)
from db.models.jurisdiction import Jurisdiction

# Fixed timestamps keep re-runs from touching updated_at when nothing changed.
SEED_RETRIEVED_AT = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
SEED_RUN_AT = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)

SLUG_UNITED_STATES = "united-states"
SLUG_CALIFORNIA = "california"
SLUG_MARIN_COUNTY = "marin-county-ca"
SLUG_NOVATO = "novato-ca"

MARIN_POPULATION = 253_694
NOVATO_POPULATION = 51_947


def build_jurisdiction_path(
    parent_path: list[ObjectId],
    parent_id: ObjectId | None,
) -> list[ObjectId]:
    """Return root-first materialized ancestor path for a child jurisdiction."""
    if parent_id is None:
        return []
    return [*parent_path, parent_id]


def _manual_source(url: str, publisher: str) -> SourceRef:
    return SourceRef(
        url=url,
        publisher=publisher,
        retrieved_at=SEED_RETRIEVED_AT,
        method=SourceMethod.MANUAL,
    )


def _build_united_states(doc_id: ObjectId, now: datetime) -> Jurisdiction:
    return Jurisdiction(
        _id=doc_id,
        slug=SLUG_UNITED_STATES,
        name="United States",
        level=JurisdictionLevel.FEDERAL,
        parent_id=None,
        path=build_jurisdiction_path([], None),
        status=JurisdictionStatus.STUB,
        sources=[
            _manual_source(
                "https://www.usa.gov/about-the-us",
                "U.S. General Services Administration",
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _build_california(doc_id: ObjectId, now: datetime, us_id: ObjectId) -> Jurisdiction:
    us_path = build_jurisdiction_path([], None)
    return Jurisdiction(
        _id=doc_id,
        slug=SLUG_CALIFORNIA,
        name="California",
        level=JurisdictionLevel.STATE,
        parent_id=us_id,
        path=build_jurisdiction_path(us_path, us_id),
        fips=FipsCodes(state_fips="06", geoid="06"),
        status=JurisdictionStatus.STUB,
        sources=[
            _manual_source("https://www.ca.gov/", "State of California"),
        ],
        created_at=now,
        updated_at=now,
    )


def _build_marin_county(
    doc_id: ObjectId,
    now: datetime,
    us_id: ObjectId,
    ca_id: ObjectId,
) -> Jurisdiction:
    ca_path = build_jurisdiction_path(build_jurisdiction_path([], None), us_id)
    return Jurisdiction(
        _id=doc_id,
        slug=SLUG_MARIN_COUNTY,
        name="Marin County",
        level=JurisdictionLevel.COUNTY,
        parent_id=ca_id,
        path=build_jurisdiction_path(ca_path, ca_id),
        fips=FipsCodes(state_fips="06", county_fips="041", geoid="06041"),
        population=MARIN_POPULATION,
        website="https://www.marincounty.org/",
        status=JurisdictionStatus.PILOT,
        sources=[
            SourceRef(
                url="https://www.marincounty.org/",
                publisher="County of Marin",
                retrieved_at=SEED_RETRIEVED_AT,
                method=SourceMethod.MANUAL,
            ),
            SourceRef(
                url="https://www.census.gov/quickfacts/fact/table/marincountycalifornia/PST045224",
                publisher="U.S. Census Bureau",
                retrieved_at=SEED_RETRIEVED_AT,
                method=SourceMethod.API,
            ),
        ],
        created_at=now,
        updated_at=now,
    )


def _build_novato(
    doc_id: ObjectId,
    now: datetime,
    us_id: ObjectId,
    ca_id: ObjectId,
    marin_id: ObjectId,
) -> Jurisdiction:
    marin_path = build_jurisdiction_path(
        build_jurisdiction_path(build_jurisdiction_path([], None), us_id),
        ca_id,
    )
    return Jurisdiction(
        _id=doc_id,
        slug=SLUG_NOVATO,
        name="City of Novato",
        level=JurisdictionLevel.CITY,
        government_type=GovernmentType.GENERAL_LAW,
        parent_id=marin_id,
        path=build_jurisdiction_path(marin_path, marin_id),
        fips=FipsCodes(
            state_fips="06",
            county_fips="041",
            place_fips="52582",
            geoid="0652582",
        ),
        population=NOVATO_POPULATION,
        website="https://www.novato.gov/",
        incorporated_date=date(1960, 1, 20),
        status=JurisdictionStatus.PILOT,
        sources=[
            SourceRef(
                url="https://www.novato.gov/government",
                publisher="City of Novato",
                retrieved_at=SEED_RETRIEVED_AT,
                method=SourceMethod.MANUAL,
            ),
            SourceRef(
                url="https://www.census.gov/quickfacts/fact/table/novatocitycalifornia/PST045224",
                publisher="U.S. Census Bureau",
                retrieved_at=SEED_RETRIEVED_AT,
                method=SourceMethod.API,
            ),
        ],
        created_at=now,
        updated_at=now,
    )


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def _document_for_compare(document: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_value(document)
    normalized.pop("updated_at", None)
    return normalized


def documents_equal(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    """Compare jurisdiction payloads, ignoring updated_at."""
    return _document_for_compare(existing) == _document_for_compare(desired)


async def ensure_jurisdiction_slug_index(db: AsyncIOMotorDatabase) -> None:
    """Create a unique slug index idempotently."""
    await db.jurisdictions.create_index("slug", unique=True)


async def upsert_jurisdiction(
    collection: AsyncIOMotorCollection,
    jurisdiction: Jurisdiction,
) -> tuple[ObjectId, bool]:
    """Upsert a jurisdiction by slug. Returns (id, was_modified)."""
    slug = jurisdiction.slug
    desired = jurisdiction.to_mongo()
    existing = await collection.find_one({"slug": slug})

    if existing is None:
        await collection.insert_one(desired)
        return desired["_id"], True

    doc_id = existing["_id"]
    desired["_id"] = doc_id
    desired["created_at"] = existing["created_at"]

    if documents_equal(existing, desired):
        return doc_id, False

    await collection.replace_one({"slug": slug}, desired)
    return doc_id, True


@dataclass(frozen=True)
class SeedResult:
    ids: dict[str, ObjectId]
    modified: int


async def seed_marin_jurisdictions(
    db: AsyncIOMotorDatabase | None = None,
    *,
    now: datetime | None = None,
) -> SeedResult:
    """Create or upsert the four Marin pilot jurisdictions in hierarchy order."""
    database = get_db() if db is None else db
    run_at = SEED_RUN_AT if now is None else now
    collection = database.jurisdictions

    await ensure_jurisdiction_slug_index(database)

    modified = 0
    ids: dict[str, ObjectId] = {}

    us_id, changed = await upsert_jurisdiction(
        collection,
        _build_united_states(await _resolve_id(collection, SLUG_UNITED_STATES), run_at),
    )
    ids[SLUG_UNITED_STATES] = us_id
    modified += int(changed)

    ca_id, changed = await upsert_jurisdiction(
        collection,
        _build_california(await _resolve_id(collection, SLUG_CALIFORNIA), run_at, us_id),
    )
    ids[SLUG_CALIFORNIA] = ca_id
    modified += int(changed)

    marin_id, changed = await upsert_jurisdiction(
        collection,
        _build_marin_county(
            await _resolve_id(collection, SLUG_MARIN_COUNTY),
            run_at,
            us_id,
            ca_id,
        ),
    )
    ids[SLUG_MARIN_COUNTY] = marin_id
    modified += int(changed)

    novato_id, changed = await upsert_jurisdiction(
        collection,
        _build_novato(
            await _resolve_id(collection, SLUG_NOVATO),
            run_at,
            us_id,
            ca_id,
            marin_id,
        ),
    )
    ids[SLUG_NOVATO] = novato_id
    modified += int(changed)

    return SeedResult(ids=ids, modified=modified)


async def _resolve_id(collection: AsyncIOMotorCollection, slug: str) -> ObjectId:
    existing = await collection.find_one({"slug": slug}, {"_id": 1})
    if existing is not None:
        return existing["_id"]
    return ObjectId()


async def main() -> None:
    result = await seed_marin_jurisdictions()
    print(
        f"Seeded {len(result.ids)} jurisdictions "
        f"({result.modified} document(s) inserted or updated)."
    )

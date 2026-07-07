"""Persist parsed officeholders to MongoDB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.common import SourceRef
from db.models.enums import GoverningBodyType, SelectionMethod
from db.models.governing_body import GoverningBody
from db.models.office import Office
from db.models.office_tenure import OfficeTenure
from db.models.person import Person
from ingestion.officials.common import ParsedOfficeholder, slugify_person_name


@dataclass(frozen=True)
class OfficialsIngestResult:
    body_id: ObjectId
    office_ids: list[ObjectId]
    person_ids: list[ObjectId]
    tenure_ids: list[ObjectId]


async def _get_jurisdiction_id(db: AsyncIOMotorDatabase, slug: str) -> ObjectId:
    doc = await db.jurisdictions.find_one({"slug": slug}, {"_id": 1})
    if doc is None:
        raise ValueError(f"Jurisdiction slug {slug!r} not found; seed jurisdictions first")
    return doc["_id"]


async def _upsert_governing_body(
    db: AsyncIOMotorDatabase,
    *,
    jurisdiction_id: ObjectId,
    name: str,
    source: SourceRef,
    now: datetime,
) -> ObjectId:
    existing = await db.governing_bodies.find_one(
        {"jurisdiction_id": jurisdiction_id, "name": name},
    )
    if existing is not None:
        return existing["_id"]

    body = GoverningBody(
        jurisdiction_id=jurisdiction_id,
        name=name,
        type=GoverningBodyType.LEGISLATIVE,
        sources=[source],
        created_at=now,
        updated_at=now,
    )
    payload = body.to_mongo()
    await db.governing_bodies.insert_one(payload)
    return payload["_id"]


async def _upsert_office(
    db: AsyncIOMotorDatabase,
    *,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    holder: ParsedOfficeholder,
    source: SourceRef,
) -> ObjectId:
    query = {
        "jurisdiction_id": jurisdiction_id,
        "title": holder.office_title,
        "district": holder.district,
    }
    existing = await db.offices.find_one(query)
    if existing is not None:
        return existing["_id"]

    office = Office(
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        title=holder.office_title,
        selection_method=holder.selection_method,
        district=holder.district,
        term_length_months=48
        if holder.selection_method == SelectionMethod.ELECTED_BY_DISTRICT
        else None,
        is_rotating_leadership=holder.is_rotating_leadership,
        sources=[source],
    )
    payload = office.to_mongo()
    await db.offices.insert_one(payload)
    return payload["_id"]


async def _upsert_person(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    source: SourceRef,
    now: datetime,
) -> ObjectId:
    slug = slugify_person_name(full_name)
    existing = await db.people.find_one({"slug": slug})
    if existing is not None:
        return existing["_id"]

    person = Person(
        full_name=full_name,
        slug=slug,
        sources=[source],
        created_at=now,
        updated_at=now,
    )
    payload = person.to_mongo()
    await db.people.insert_one(payload)
    return payload["_id"]


async def _upsert_tenure(
    db: AsyncIOMotorDatabase,
    *,
    office_id: ObjectId,
    person_id: ObjectId,
    holder: ParsedOfficeholder,
    source: SourceRef,
) -> ObjectId:
    existing = await db.office_tenures.find_one(
        {"office_id": office_id, "person_id": person_id, "is_current": True},
    )
    if existing is not None:
        return existing["_id"]

    tenure = OfficeTenure(
        office_id=office_id,
        person_id=person_id,
        start_date=holder.start_date,
        end_date=None,
        reason_ended=None,
        is_current=True,
        sources=[source],
    )
    payload = tenure.to_mongo()
    await db.office_tenures.insert_one(payload)
    return payload["_id"]


async def store_officials(
    db: AsyncIOMotorDatabase,
    *,
    jurisdiction_slug: str,
    body_name: str,
    holders: list[ParsedOfficeholder],
    source: SourceRef,
    now: datetime,
) -> OfficialsIngestResult:
    """Create governing body, offices, people, and current tenures."""
    jurisdiction_id = await _get_jurisdiction_id(db, jurisdiction_slug)
    body_id = await _upsert_governing_body(
        db,
        jurisdiction_id=jurisdiction_id,
        name=body_name,
        source=source,
        now=now,
    )

    office_ids: list[ObjectId] = []
    person_ids: list[ObjectId] = []
    tenure_ids: list[ObjectId] = []
    seen_people: set[ObjectId] = set()

    for holder in holders:
        office_id = await _upsert_office(
            db,
            jurisdiction_id=jurisdiction_id,
            body_id=body_id,
            holder=holder,
            source=source,
        )
        office_ids.append(office_id)

        person_id = await _upsert_person(
            db,
            full_name=holder.full_name,
            source=source,
            now=now,
        )
        if person_id not in seen_people:
            person_ids.append(person_id)
            seen_people.add(person_id)

        tenure_id = await _upsert_tenure(
            db,
            office_id=office_id,
            person_id=person_id,
            holder=holder,
            source=source,
        )
        tenure_ids.append(tenure_id)

    return OfficialsIngestResult(
        body_id=body_id,
        office_ids=office_ids,
        person_ids=person_ids,
        tenure_ids=tenure_ids,
    )

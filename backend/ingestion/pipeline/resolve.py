"""Resolve stage — match roll-call / mover names to office tenures (minimal MVP).

Matching strategy (T6 — T7 will harden):
- Normalize a parsed name to an uppercase token (last segment after stripping titles like
  "Councilmember", "Mayor", "Supervisor").
- Exact match against uppercase last-name tokens derived from ``people.full_name``.
- On ties or no match, leave ``office_tenure_id`` / ``person_id`` null (no crash).
"""

from __future__ import annotations

import re

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from ingestion.pipeline.types import NormalizedMeeting

_TITLE_PREFIX_RE = re.compile(
    r"^(?:Mayor Pro Tem|Mayor|Councilmember|Supervisor)\s+",
    re.IGNORECASE,
)


def _name_token(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = _TITLE_PREFIX_RE.sub("", raw.strip())
    cleaned = cleaned.replace("\ufffd", "'")
    if not cleaned:
        return None
    return cleaned.split()[-1].upper()


def _person_last_token(full_name: str) -> str:
    return full_name.split()[-1].upper()


async def _load_tenure_index(
    db: AsyncIOMotorDatabase,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
) -> dict[str, tuple[ObjectId, ObjectId]]:
    """Map uppercase last-name token → (office_tenure_id, person_id)."""
    index: dict[str, tuple[ObjectId, ObjectId]] = {}
    offices = await db.offices.find(
        {"jurisdiction_id": jurisdiction_id, "body_id": body_id}
    ).to_list(
        length=50,
    )
    office_ids = {office["_id"] for office in offices}
    tenures = await db.office_tenures.find(
        {"office_id": {"$in": list(office_ids)}, "is_current": True},
    ).to_list(length=50)

    for tenure in tenures:
        person = await db.people.find_one({"_id": tenure["person_id"]})
        if person is None:
            continue
        token = _person_last_token(person["full_name"])
        index[token] = (tenure["_id"], person["_id"])
    return index


def _resolve_name(
    raw: str | None,
    index: dict[str, tuple[ObjectId, ObjectId]],
) -> tuple[ObjectId | None, ObjectId | None]:
    token = _name_token(raw)
    if token is None:
        return None, None
    match = index.get(token)
    if match is None:
        return None, None
    return match


async def resolve_officials(
    db: AsyncIOMotorDatabase,
    meeting: NormalizedMeeting,
    *,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
) -> NormalizedMeeting:
    index = await _load_tenure_index(db, jurisdiction_id, body_id)

    for item in meeting.agenda_items:
        for action in item.actions:
            moved_tenure, moved_person = _resolve_name(action.moved_by_name, index)
            second_tenure, second_person = _resolve_name(action.seconded_by_name, index)
            action.moved_by_office_tenure_id = (
                str(moved_tenure) if moved_tenure is not None else None
            )
            action.seconded_by_office_tenure_id = (
                str(second_tenure) if second_tenure is not None else None
            )
            for record in action.vote_records:
                tenure_id, person_id = _resolve_name(record.voter_name, index)
                record.office_tenure_id = str(tenure_id) if tenure_id is not None else None
                record.person_id = str(person_id) if person_id is not None else None

    return meeting

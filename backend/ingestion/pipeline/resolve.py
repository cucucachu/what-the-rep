"""Resolve stage — match roll-call / mover names to office tenures (T7)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.common import SourceRef, prepare_for_mongo
from db.models.enums import MeetingType, ReasonEnded, SourceMethod
from db.models.office_tenure import OfficeTenure
from db.models.person import Person
from ingestion.officials.common import slugify_person_name
from ingestion.pipeline.name_match import (
    MatchOutcome,
    ParsedOfficialName,
    is_mayor_office_title,
    leadership_office_title,
    match_tokens_for_full_name,
    parse_official_name,
)
from ingestion.pipeline.types import NormalizedMeeting, NormalizedVoteRecord

logger = logging.getLogger(__name__)


@dataclass
class TenureEntry:
    tenure_id: ObjectId
    person_id: ObjectId
    office_id: ObjectId
    office_title: str
    district: str | None
    person_full_name: str
    match_tokens: frozenset[str]


@dataclass
class ResolveResult:
    meeting: NormalizedMeeting
    unresolved_names: list[str] = field(default_factory=list)


@dataclass
class _NameResolution:
    outcome: MatchOutcome
    tenure_id: ObjectId | None = None
    person_id: ObjectId | None = None


def _meeting_boundary_date(meeting: NormalizedMeeting) -> date:
    return meeting.scheduled_start.date()


def _provenance_sources(
    meeting: NormalizedMeeting,
    *,
    ingestion_run_id: ObjectId | None,
) -> list[SourceRef]:
    refs: list[SourceRef] = []
    for source in meeting.sources:
        update: dict = {}
        if ingestion_run_id is not None:
            update["ingestion_run_id"] = ingestion_run_id
        refs.append(source.model_copy(update=update) if update else source)
    if refs:
        return refs
    return [
        SourceRef(
            url=f"meeting:{meeting.external_id}",
            publisher="ingestion",
            retrieved_at=meeting.scheduled_start,
            ingestion_run_id=ingestion_run_id,
            method=SourceMethod.SCRAPE,
        ),
    ]


def _infer_reason_ended(
    meeting: NormalizedMeeting,
    *,
    office_title: str,
    raw_name: str,
) -> ReasonEnded:
    lowered = raw_name.lower()
    if "resign" in lowered:
        return ReasonEnded.RESIGNED
    if meeting.meeting_type == MeetingType.REORGANIZATION or office_title == "Mayor":
        return ReasonEnded.REORGANIZATION
    return ReasonEnded.REORGANIZATION


def _filter_candidates(
    parsed: ParsedOfficialName,
    candidates: list[TenureEntry],
) -> list[TenureEntry]:
    if not candidates:
        return []

    if is_mayor_office_title(parsed.title):
        by_office = [c for c in candidates if c.office_title == "Mayor"]
        if len(by_office) == 1:
            return by_office
        if len(by_office) > 1:
            return by_office

    if parsed.title == "councilmember" or parsed.title == "supervisor":
        if parsed.district is not None:
            by_district = [c for c in candidates if c.district == parsed.district]
            if by_district:
                return by_district

    if len(candidates) == 1:
        return candidates

    return candidates


class _TenureIndex:
    def __init__(self, entries: list[TenureEntry]) -> None:
        self._entries = list(entries)
        self._by_token: dict[str, list[TenureEntry]] = {}
        for entry in entries:
            for token in entry.match_tokens:
                self._by_token.setdefault(token, []).append(entry)

    def lookup(self, parsed: ParsedOfficialName) -> list[TenureEntry]:
        seen: set[tuple[ObjectId, ObjectId]] = set()
        matched: list[TenureEntry] = []
        for token in parsed.match_tokens:
            for entry in self._by_token.get(token, []):
                key = (entry.tenure_id, entry.person_id)
                if key not in seen:
                    seen.add(key)
                    matched.append(entry)
        return _filter_candidates(parsed, matched)

    def add(self, entry: TenureEntry) -> None:
        self._entries.append(entry)
        for token in entry.match_tokens:
            self._by_token.setdefault(token, []).append(entry)

    def current_for_office(self, office_id: ObjectId) -> TenureEntry | None:
        for entry in self._entries:
            if entry.office_id == office_id:
                return entry
        return None

    def replace_current(self, office_id: ObjectId, new_entry: TenureEntry) -> None:
        self._entries = [e for e in self._entries if e.office_id != office_id]
        self._by_token = {}
        for entry in self._entries:
            for token in entry.match_tokens:
                self._by_token.setdefault(token, []).append(entry)
        self.add(new_entry)


async def _load_tenure_index(
    db: AsyncIOMotorDatabase,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
) -> _TenureIndex:
    offices = await db.offices.find(
        {"jurisdiction_id": jurisdiction_id, "body_id": body_id},
    ).to_list(length=50)
    office_by_id = {office["_id"]: office for office in offices}
    office_ids = list(office_by_id)

    tenures = await db.office_tenures.find(
        {"office_id": {"$in": office_ids}, "is_current": True},
    ).to_list(length=50)

    entries: list[TenureEntry] = []
    for tenure in tenures:
        office = office_by_id.get(tenure["office_id"])
        person = await db.people.find_one({"_id": tenure["person_id"]})
        if office is None or person is None:
            continue
        entries.append(
            TenureEntry(
                tenure_id=tenure["_id"],
                person_id=person["_id"],
                office_id=office["_id"],
                office_title=office["title"],
                district=office.get("district"),
                person_full_name=person["full_name"],
                match_tokens=match_tokens_for_full_name(person["full_name"]),
            ),
        )
    return _TenureIndex(entries)


async def _find_office_by_title(
    db: AsyncIOMotorDatabase,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    office_title: str,
) -> dict | None:
    return await db.offices.find_one(
        {
            "jurisdiction_id": jurisdiction_id,
            "body_id": body_id,
            "title": office_title,
        },
    )


async def _find_person_in_body(
    db: AsyncIOMotorDatabase,
    index: _TenureIndex,
    parsed: ParsedOfficialName,
) -> dict | None:
    seen: set[ObjectId] = set()
    for entry in index.lookup(parsed):
        if entry.person_id in seen:
            continue
        seen.add(entry.person_id)
        person = await db.people.find_one({"_id": entry.person_id})
        if person is not None:
            return person
    return None


async def _create_person(
    db: AsyncIOMotorDatabase,
    *,
    full_name: str,
    sources: list[SourceRef],
    now: datetime,
) -> ObjectId:
    slug = slugify_person_name(full_name)
    existing = await db.people.find_one({"slug": slug})
    if existing is not None:
        return existing["_id"]

    person = Person(
        full_name=full_name,
        slug=slug,
        sources=list(sources),
        created_at=now,
        updated_at=now,
    )
    payload = person.to_mongo()
    await db.people.insert_one(payload)
    return payload["_id"]


async def _apply_leadership_change(
    db: AsyncIOMotorDatabase,
    *,
    index: _TenureIndex,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    parsed: ParsedOfficialName,
    meeting: NormalizedMeeting,
    ingestion_run_id: ObjectId | None,
    now: datetime,
) -> _NameResolution:
    target_office_title = leadership_office_title(parsed.title)
    if target_office_title is None:
        return _NameResolution(outcome=MatchOutcome.UNRESOLVED)

    office = await _find_office_by_title(db, jurisdiction_id, body_id, target_office_title)
    if office is None:
        return _NameResolution(outcome=MatchOutcome.UNRESOLVED)

    boundary = _meeting_boundary_date(meeting)
    sources = _provenance_sources(meeting, ingestion_run_id=ingestion_run_id)
    reason = _infer_reason_ended(
        meeting,
        office_title=target_office_title,
        raw_name=parsed.raw,
    )

    person = await _find_person_in_body(db, index, parsed)
    if person is None:
        person_id = await _create_person(
            db,
            full_name=parsed.name_part.title(),
            sources=sources,
            now=now,
        )
        person = await db.people.find_one({"_id": person_id})
    assert person is not None

    current = index.current_for_office(office["_id"])
    if current is not None and current.person_id == person["_id"]:
        return _NameResolution(
            outcome=MatchOutcome.MATCHED,
            tenure_id=current.tenure_id,
            person_id=current.person_id,
        )

    if current is not None:
        await db.office_tenures.update_one(
            {"_id": current.tenure_id},
            {
                "$set": {
                    "end_date": prepare_for_mongo(boundary),
                    "reason_ended": reason.value,
                    "is_current": False,
                },
                "$push": {
                    "sources": {
                        "$each": [prepare_for_mongo(s.model_dump(mode="python")) for s in sources],
                    },
                },
            },
        )

    tenure = OfficeTenure(
        office_id=office["_id"],
        person_id=person["_id"],
        start_date=boundary,
        end_date=None,
        reason_ended=None,
        is_current=True,
        sources=list(sources),
    )
    payload = tenure.to_mongo()
    await db.office_tenures.insert_one(payload)

    new_entry = TenureEntry(
        tenure_id=payload["_id"],
        person_id=person["_id"],
        office_id=office["_id"],
        office_title=office["title"],
        district=office.get("district"),
        person_full_name=person["full_name"],
        match_tokens=match_tokens_for_full_name(person["full_name"]),
    )
    index.replace_current(office["_id"], new_entry)

    logger.info(
        "Leadership change: %s now holds %s (meeting %s)",
        person["full_name"],
        target_office_title,
        meeting.external_id,
    )

    return _NameResolution(
        outcome=MatchOutcome.MATCHED,
        tenure_id=new_entry.tenure_id,
        person_id=new_entry.person_id,
    )


async def _resolve_parsed_name(
    db: AsyncIOMotorDatabase,
    *,
    index: _TenureIndex,
    parsed: ParsedOfficialName,
    meeting: NormalizedMeeting,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    ingestion_run_id: ObjectId | None,
    now: datetime,
) -> _NameResolution:
    target_office_title = leadership_office_title(parsed.title)
    candidates = index.lookup(parsed)
    if len(candidates) == 1:
        entry = candidates[0]
        if target_office_title and entry.office_title != target_office_title:
            return await _apply_leadership_change(
                db,
                index=index,
                jurisdiction_id=jurisdiction_id,
                body_id=body_id,
                parsed=parsed,
                meeting=meeting,
                ingestion_run_id=ingestion_run_id,
                now=now,
            )
        return _NameResolution(
            outcome=MatchOutcome.MATCHED,
            tenure_id=entry.tenure_id,
            person_id=entry.person_id,
        )
    if len(candidates) > 1:
        if target_office_title:
            by_office = [c for c in candidates if c.office_title == target_office_title]
            if len(by_office) == 1:
                return _NameResolution(
                    outcome=MatchOutcome.MATCHED,
                    tenure_id=by_office[0].tenure_id,
                    person_id=by_office[0].person_id,
                )
        unique_people = {c.person_id for c in candidates}
        if len(unique_people) == 1:
            non_mayor = [c for c in candidates if c.office_title != "Mayor"]
            if len(non_mayor) == 1:
                entry = non_mayor[0]
                return _NameResolution(
                    outcome=MatchOutcome.MATCHED,
                    tenure_id=entry.tenure_id,
                    person_id=entry.person_id,
                )
        return _NameResolution(outcome=MatchOutcome.UNRESOLVED)

    if is_mayor_office_title(parsed.title):
        return await _apply_leadership_change(
            db,
            index=index,
            jurisdiction_id=jurisdiction_id,
            body_id=body_id,
            parsed=parsed,
            meeting=meeting,
            ingestion_run_id=ingestion_run_id,
            now=now,
        )

    return _NameResolution(outcome=MatchOutcome.UNRESOLVED)


def _apply_resolution_to_vote_record(
    record: NormalizedVoteRecord,
    resolution: _NameResolution,
) -> None:
    if resolution.outcome == MatchOutcome.MATCHED:
        record.office_tenure_id = str(resolution.tenure_id)
        record.person_id = str(resolution.person_id)
        record.resolution_status = "matched"
        return

    record.office_tenure_id = None
    record.person_id = None
    record.resolution_status = "unresolved"


async def resolve_officials(
    db: AsyncIOMotorDatabase,
    meeting: NormalizedMeeting,
    *,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    ingestion_run_id: ObjectId | None = None,
    now: datetime | None = None,
) -> ResolveResult:
    """Match parsed names to office tenures; detect leadership changes."""
    run_at = now or meeting.scheduled_start
    index = await _load_tenure_index(db, jurisdiction_id, body_id)
    unresolved_names: list[str] = []

    for item in meeting.agenda_items:
        for action in item.actions:
            for field_name, raw in (
                ("moved_by", action.moved_by_name),
                ("seconded_by", action.seconded_by_name),
            ):
                parsed = parse_official_name(raw)
                if parsed is None:
                    continue
                resolution = await _resolve_parsed_name(
                    db,
                    index=index,
                    parsed=parsed,
                    meeting=meeting,
                    jurisdiction_id=jurisdiction_id,
                    body_id=body_id,
                    ingestion_run_id=ingestion_run_id,
                    now=run_at,
                )
                if resolution.outcome == MatchOutcome.MATCHED:
                    tenure_str = str(resolution.tenure_id)
                    if field_name == "moved_by":
                        action.moved_by_office_tenure_id = tenure_str
                    else:
                        action.seconded_by_office_tenure_id = tenure_str
                elif resolution.outcome == MatchOutcome.UNRESOLVED:
                    unresolved_names.append(parsed.raw)

            for record in action.vote_records:
                parsed = parse_official_name(record.voter_name)
                if parsed is None:
                    record.resolution_status = "unresolved"
                    if record.voter_name:
                        unresolved_names.append(record.voter_name)
                    continue

                resolution = await _resolve_parsed_name(
                    db,
                    index=index,
                    parsed=parsed,
                    meeting=meeting,
                    jurisdiction_id=jurisdiction_id,
                    body_id=body_id,
                    ingestion_run_id=ingestion_run_id,
                    now=run_at,
                )
                _apply_resolution_to_vote_record(record, resolution)
                if resolution.outcome == MatchOutcome.UNRESOLVED:
                    unresolved_names.append(parsed.raw)

    if unresolved_names:
        logger.warning(
            "Unresolved official names for meeting %s: %s",
            meeting.external_id,
            sorted(set(unresolved_names)),
        )

    return ResolveResult(meeting=meeting, unresolved_names=sorted(set(unresolved_names)))

"""Store stage — idempotent upsert keyed on external_id + content_hash."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.action import Action
from db.models.agenda_item import AgendaItem
from db.models.common import SourceRef
from db.models.enums import MeetingStatus
from db.models.meeting import Meeting
from db.models.vote_record import VoteRecord
from ingestion.pipeline.content_hash import compute_content_hash, documents_equal
from ingestion.pipeline.types import NormalizedMeeting


@dataclass
class StoreStats:
    meetings_upserted: int = 0
    agenda_items_upserted: int = 0
    actions_upserted: int = 0
    vote_records_upserted: int = 0


@dataclass
class StoreResult:
    meeting_id: ObjectId
    stats: StoreStats = field(default_factory=StoreStats)


def _with_hash(document: dict, *, now: datetime) -> dict:
    document["content_hash"] = compute_content_hash(document)
    document.setdefault("created_at", now)
    document["updated_at"] = now
    return document


async def _upsert_by_external_id(
    collection,
    *,
    jurisdiction_id: ObjectId,
    external_id: str,
    document: dict,
    now: datetime,
) -> bool:
    """Insert or replace when content changed. Returns True if write occurred."""
    desired = _with_hash(document, now=now)
    existing = await collection.find_one(
        {"jurisdiction_id": jurisdiction_id, "external_id": external_id},
    )
    if existing is not None and documents_equal(existing, desired):
        return False
    if existing is not None:
        desired["_id"] = existing["_id"]
        desired["created_at"] = existing.get("created_at", now)
        await collection.replace_one({"_id": existing["_id"]}, desired)
        return True
    await collection.insert_one(desired)
    return True


async def store_meeting_graph(
    db: AsyncIOMotorDatabase,
    meeting: NormalizedMeeting,
    *,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    ingestion_run_id: ObjectId | None = None,
    now: datetime | None = None,
) -> StoreResult:
    """Upsert meeting, agenda items, actions, and vote records without duplicates."""
    run_at = datetime.now(tz=UTC) if now is None else now
    stats = StoreStats()

    sources: list[SourceRef] = []
    for source in meeting.sources:
        payload = source.model_copy()
        if ingestion_run_id is not None:
            payload.ingestion_run_id = ingestion_run_id
        sources.append(payload)

    meeting_doc = Meeting(
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        scheduled_start=meeting.scheduled_start,
        meeting_type=meeting.meeting_type,
        status=MeetingStatus.HELD,
        video_url=meeting.video_url,
        external_id=meeting.external_id,
        sources=sources,
    ).to_mongo()
    meeting_doc["external_id"] = meeting.external_id

    if await _upsert_by_external_id(
        db.meetings,
        jurisdiction_id=jurisdiction_id,
        external_id=meeting.external_id,
        document=meeting_doc,
        now=run_at,
    ):
        stats.meetings_upserted += 1

    stored_meeting = await db.meetings.find_one(
        {"jurisdiction_id": jurisdiction_id, "external_id": meeting.external_id},
    )
    assert stored_meeting is not None
    meeting_id = stored_meeting["_id"]

    for item in meeting.agenda_items:
        item_sources = list(sources)
        agenda_doc = AgendaItem(
            meeting_id=meeting_id,
            jurisdiction_id=jurisdiction_id,
            body_id=body_id,
            item_number=item.item_number,
            section=item.section,
            title=item.title,
            description=item.description,
            sources=item_sources,
        ).to_mongo()
        agenda_doc["external_id"] = item.external_id

        if await _upsert_by_external_id(
            db.agenda_items,
            jurisdiction_id=jurisdiction_id,
            external_id=item.external_id,
            document=agenda_doc,
            now=run_at,
        ):
            stats.agenda_items_upserted += 1

        stored_item = await db.agenda_items.find_one(
            {"jurisdiction_id": jurisdiction_id, "external_id": item.external_id},
        )
        assert stored_item is not None
        agenda_item_id = stored_item["_id"]

        for action in item.actions:
            action_doc = Action(
                agenda_item_id=agenda_item_id,
                meeting_id=meeting_id,
                jurisdiction_id=jurisdiction_id,
                action_type=action.action_type,
                description=action.description,
                moved_by_office_tenure_id=(
                    ObjectId(action.moved_by_office_tenure_id)
                    if action.moved_by_office_tenure_id
                    else None
                ),
                seconded_by_office_tenure_id=(
                    ObjectId(action.seconded_by_office_tenure_id)
                    if action.seconded_by_office_tenure_id
                    else None
                ),
                outcome=action.outcome,
                vote_tally=action.vote_tally,
                sources=item_sources,
            ).to_mongo()
            action_doc["external_id"] = action.external_id

            if await _upsert_by_external_id(
                db.actions,
                jurisdiction_id=jurisdiction_id,
                external_id=action.external_id,
                document=action_doc,
                now=run_at,
            ):
                stats.actions_upserted += 1

            stored_action = await db.actions.find_one(
                {"jurisdiction_id": jurisdiction_id, "external_id": action.external_id},
            )
            assert stored_action is not None
            action_id = stored_action["_id"]

            for record in action.vote_records:
                vote_doc = VoteRecord(
                    action_id=action_id,
                    office_tenure_id=(
                        ObjectId(record.office_tenure_id) if record.office_tenure_id else None
                    ),
                    person_id=ObjectId(record.person_id) if record.person_id else None,
                    vote=record.vote,
                ).to_mongo()
                vote_doc["external_id"] = record.external_id
                vote_doc["jurisdiction_id"] = jurisdiction_id

                if await _upsert_by_external_id(
                    db.vote_records,
                    jurisdiction_id=jurisdiction_id,
                    external_id=record.external_id,
                    document=vote_doc,
                    now=run_at,
                ):
                    stats.vote_records_upserted += 1

    return StoreResult(meeting_id=meeting_id, stats=stats)

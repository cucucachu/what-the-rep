"""Parse stage — vendor extraction into intermediate representation."""

from __future__ import annotations

from datetime import UTC, datetime

from db.models.common import SourceRef
from db.models.enums import SourceMethod
from ingestion.adapters.base import RawMeetingDetail
from ingestion.adapters.granicus import GranicusAdapter, MeetingDetail, _attach_motions_to_items
from ingestion.pipeline.types import ParsedMeetingBundle


def parse_meeting_detail(
    raw: RawMeetingDetail,
    *,
    publisher: str,
    retrieved_at: datetime | None = None,
) -> ParsedMeetingBundle:
    """Parse fetched agenda/minutes into the Granicus IR."""
    adapter = GranicusAdapter()
    agenda = adapter.parse_agenda(raw.agenda_path)
    motions = ()
    meeting_type = agenda.meeting_type
    if raw.minutes_path is not None:
        minutes = adapter.parse_minutes(raw.minutes_path)
        motions = minutes.motions
        meeting_type = minutes.meeting_type or agenda.meeting_type

    items = _attach_motions_to_items(agenda.items, motions)
    detail = MeetingDetail(
        meeting_date=agenda.meeting_date,
        meeting_type=meeting_type,
        agenda_items=items,
        motions=motions,
    )
    run_at = datetime.now(tz=UTC) if retrieved_at is None else retrieved_at
    sources = [
        SourceRef(
            url=str(raw.agenda_path),
            publisher=publisher,
            retrieved_at=run_at,
            method=SourceMethod.PDF_PARSE,
        ),
    ]
    if raw.minutes_path is not None:
        sources.append(
            SourceRef(
                url=str(raw.minutes_path),
                publisher=publisher,
                retrieved_at=run_at,
                method=SourceMethod.PDF_PARSE,
            ),
        )
    return ParsedMeetingBundle(detail=detail, clip_id=raw.ref.clip_id, sources=sources)

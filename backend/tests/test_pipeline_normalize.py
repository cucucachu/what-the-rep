"""Unit tests for normalize stage (IR → pipeline models)."""

from __future__ import annotations

from datetime import datetime

from db.models.enums import ActionOutcome, ActionType, AgendaSection, Vote
from ingestion.adapters.granicus import GranicusAdapter
from ingestion.pipeline.config import get_granicus_config
from ingestion.pipeline.discover import build_ref_from_config
from ingestion.pipeline.fetch import fetch_meeting_detail
from ingestion.pipeline.normalize import normalize_meeting
from ingestion.pipeline.parse import parse_meeting_detail


def _normalized_for(slug: str):
    config = get_granicus_config(slug)
    adapter = GranicusAdapter(config)
    ref = build_ref_from_config(config)
    raw = fetch_meeting_detail(adapter, ref)
    parsed = parse_meeting_detail(raw, publisher=config.publisher)
    is_marin = slug == "marin-county-ca"
    return normalize_meeting(parsed, is_marin=is_marin)


class TestNormalizeNovato:
    def test_meeting_fields(self) -> None:
        meeting = _normalized_for("novato-ca")
        assert meeting.external_id == "1980"
        assert meeting.scheduled_start == datetime(2024, 1, 23, 18, 0)
        assert meeting.meeting_type.value == "regular"
        assert len(meeting.agenda_items) == 24

    def test_agenda_item_i1_section(self) -> None:
        meeting = _normalized_for("novato-ca")
        item = next(i for i in meeting.agenda_items if i.item_number == "I.1")
        assert item.section == AgendaSection.PUBLIC_HEARING
        assert item.external_id == "1980:I.1"

    def test_resolution_2024_011_vote(self) -> None:
        meeting = _normalized_for("novato-ca")
        item = next(i for i in meeting.agenda_items if i.item_number == "I.1")
        action = next(a for a in item.actions if "2024-011" in a.external_id)
        assert action.action_type == ActionType.RESOLUTION
        assert action.outcome == ActionOutcome.PASSED
        assert action.vote_tally is not None
        assert action.vote_tally.ayes == 4
        assert action.vote_tally.noes == 1
        votes = {r.voter_name: r.vote for r in action.vote_records}
        assert votes["EKLUND"] == Vote.NO
        assert votes["FARAC"] == Vote.AYE


class TestNormalizeMarinCounty:
    def test_meeting_fields(self) -> None:
        meeting = _normalized_for("marin-county-ca")
        assert meeting.external_id == "12654"
        assert meeting.scheduled_start == datetime(2025, 6, 10, 9, 0)
        assert meeting.meeting_type.value == "regular"
        assert len(meeting.agenda_items) > 20

    def test_consent_calendar_section(self) -> None:
        meeting = _normalized_for("marin-county-ca")
        item = next(
            i
            for i in meeting.agenda_items
            if i.item_number == "CA-1" and not i.external_id.endswith("#1")
        )
        assert item.section == AgendaSection.CONSENT_CALENDAR

    def test_marin_actions_from_minutes(self) -> None:
        meeting = _normalized_for("marin-county-ca")
        actions = [a for item in meeting.agenda_items for a in item.actions]
        assert len(actions) >= 1
        assert any(a.moved_by_name and "Supervisor" in a.moved_by_name for a in actions)

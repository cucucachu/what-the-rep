"""Normalize stage — map Granicus IR into canonical pipeline models."""

from __future__ import annotations

import re
from datetime import datetime, time

from db.models.common import VoteTally
from db.models.enums import ActionOutcome, ActionType, AgendaSection, MeetingType, Vote
from ingestion.adapters.granicus import Motion, RollCall
from ingestion.pipeline.types import (
    NormalizedAction,
    NormalizedAgendaItem,
    NormalizedMeeting,
    NormalizedVoteRecord,
    ParsedMeetingBundle,
)

_DEFAULT_MEETING_TIME = time(18, 0)
_MARIN_MEETING_TIME = time(9, 0)

_SECTION_MAP: dict[str, AgendaSection] = {
    "consent_calendar": AgendaSection.CONSENT_CALENDAR,
    "general_business": AgendaSection.GENERAL_BUSINESS,
    "public_hearing": AgendaSection.PUBLIC_HEARING,
    "ceremonial": AgendaSection.CEREMONIAL,
    "closed_session": AgendaSection.CLOSED_SESSION,
}

_MEETING_TYPE_MAP: dict[str, MeetingType] = {
    "regular": MeetingType.REGULAR,
    "special": MeetingType.SPECIAL,
    "study_session": MeetingType.STUDY_SESSION,
    "closed_session": MeetingType.CLOSED_SESSION,
    "reorganization": MeetingType.REORGANIZATION,
}

_OUTCOME_MAP: dict[str, ActionOutcome] = {
    "passed": ActionOutcome.PASSED,
    "failed": ActionOutcome.FAILED,
    "unknown": ActionOutcome.PASSED,
}


def _meeting_start(detail_date, *, is_marin: bool) -> datetime:
    meeting_time = _MARIN_MEETING_TIME if is_marin else _DEFAULT_MEETING_TIME
    return datetime.combine(detail_date, meeting_time)


def _section_for_ir(section: str | None, item_number: str) -> AgendaSection:
    if section and section in _SECTION_MAP:
        return _SECTION_MAP[section]
    if item_number.startswith(("CA-", "CB-")):
        return AgendaSection.CONSENT_CALENDAR
    if re.match(r"^CA-\d+[a-z]? - CEREMONIAL", item_number, re.IGNORECASE):
        return AgendaSection.CEREMONIAL
    if item_number.startswith("I"):
        return AgendaSection.PUBLIC_HEARING
    return AgendaSection.GENERAL_BUSINESS


def _action_type_for_motion(motion: Motion) -> ActionType:
    if motion.resolution_number:
        return ActionType.RESOLUTION
    if motion.ordinance_number:
        return ActionType.ORDINANCE
    return ActionType.MOTION


def _vote_records_from_roll_call(
    roll_call: RollCall,
    action_external_id: str,
) -> list[NormalizedVoteRecord]:
    records: list[NormalizedVoteRecord] = []
    buckets = (
        (roll_call.ayes, Vote.AYE),
        (roll_call.noes, Vote.NO),
        (roll_call.abstain, Vote.ABSTAIN),
        (roll_call.absent, Vote.ABSENT),
        (roll_call.recuse, Vote.RECUSE),
    )
    for names, vote in buckets:
        for name in names:
            records.append(
                NormalizedVoteRecord(
                    external_id=f"{action_external_id}:{name.upper()}",
                    voter_name=name,
                    vote=vote,
                ),
            )
    return records


def _normalize_action(
    motion: Motion,
    clip_id: str,
    item_number: str,
    motion_index: int,
) -> NormalizedAction:
    suffix = motion.resolution_number or motion.ordinance_number or str(motion_index)
    external_id = f"{clip_id}:{item_number}:{suffix}"
    outcome = _OUTCOME_MAP.get(motion.outcome, ActionOutcome.PASSED)
    vote_tally = VoteTally(
        ayes=motion.vote_tally.ayes,
        noes=motion.vote_tally.noes,
        abstain=motion.vote_tally.abstain,
        absent=motion.vote_tally.absent,
        recuse=motion.vote_tally.recuse,
    )
    vote_records = _vote_records_from_roll_call(motion.roll_call, external_id)
    return NormalizedAction(
        external_id=external_id,
        action_type=_action_type_for_motion(motion),
        description=motion.description,
        moved_by_name=motion.moved_by,
        seconded_by_name=motion.seconded_by,
        outcome=outcome,
        vote_tally=vote_tally,
        roll_call=motion.roll_call,
        vote_records=vote_records,
    )


def normalize_meeting(
    bundle: ParsedMeetingBundle,
    *,
    is_marin: bool = False,
    meeting_time: time | None = None,
) -> NormalizedMeeting:
    """Pure IR → normalized meeting graph (no Mongo ids, no entity resolution)."""
    detail = bundle.detail
    if meeting_time is not None:
        scheduled_start = datetime.combine(detail.meeting_date, meeting_time)
    else:
        scheduled_start = _meeting_start(detail.meeting_date, is_marin=is_marin)

    meeting_type = _MEETING_TYPE_MAP.get(detail.meeting_type, MeetingType.REGULAR)
    agenda_items: list[NormalizedAgendaItem] = []
    item_number_counts: dict[str, int] = {}

    for item in detail.agenda_items:
        occurrence = item_number_counts.get(item.item_number, 0)
        item_number_counts[item.item_number] = occurrence + 1
        suffix = f"#{occurrence}" if occurrence else ""
        item_external_id = f"{bundle.clip_id}:{item.item_number}{suffix}"
        actions = [
            _normalize_action(motion, bundle.clip_id, item.item_number, idx)
            for idx, motion in enumerate(item.motions)
        ]
        agenda_items.append(
            NormalizedAgendaItem(
                external_id=item_external_id,
                item_number=item.item_number,
                section=_section_for_ir(item.section, item.item_number),
                title=item.title,
                actions=actions,
                sources=list(bundle.sources),
            ),
        )

    attached_keys = {action.external_id for item in agenda_items for action in item.actions}
    fallback_item = next(
        (item for item in agenda_items if item.item_number in {"3", "4"}),
        agenda_items[0] if agenda_items else None,
    )
    if fallback_item is not None:
        for idx, motion in enumerate(detail.motions):
            action = _normalize_action(motion, bundle.clip_id, fallback_item.item_number, idx)
            if action.external_id not in attached_keys and not action.vote_records:
                if action.vote_tally and (action.vote_tally.ayes or action.vote_tally.noes):
                    fallback_item.actions.append(action)
                    attached_keys.add(action.external_id)

    video_url = None
    return NormalizedMeeting(
        external_id=bundle.clip_id,
        scheduled_start=scheduled_start,
        meeting_type=meeting_type,
        video_url=video_url,
        sources=list(bundle.sources),
        agenda_items=agenda_items,
    )

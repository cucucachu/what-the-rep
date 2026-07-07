"""Intermediate and normalized pipeline dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from db.models.common import SourceRef, VoteTally
from db.models.enums import ActionOutcome, ActionType, AgendaSection, MeetingType, Vote
from ingestion.adapters.granicus import MeetingDetail, RollCall


@dataclass(frozen=True)
class ParsedMeetingBundle:
    detail: MeetingDetail
    clip_id: str
    sources: list[SourceRef]


@dataclass
class NormalizedVoteRecord:
    external_id: str
    voter_name: str
    vote: Vote
    office_tenure_id: str | None = None
    person_id: str | None = None
    resolution_status: str | None = None  # "matched" | "unresolved"


@dataclass
class NormalizedAction:
    external_id: str
    action_type: ActionType
    description: str
    moved_by_name: str | None
    seconded_by_name: str | None
    outcome: ActionOutcome
    vote_tally: VoteTally | None
    roll_call: RollCall
    moved_by_office_tenure_id: str | None = None
    seconded_by_office_tenure_id: str | None = None
    vote_records: list[NormalizedVoteRecord] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class NormalizedAgendaItem:
    external_id: str
    item_number: str
    section: AgendaSection
    title: str
    description: str | None = None
    actions: list[NormalizedAction] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)


@dataclass
class NormalizedMeeting:
    external_id: str
    scheduled_start: datetime
    meeting_type: MeetingType
    video_url: str | None
    sources: list[SourceRef]
    agenda_items: list[NormalizedAgendaItem] = field(default_factory=list)

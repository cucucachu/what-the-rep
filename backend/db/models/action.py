"""Action collection model (§5)."""

from datetime import date

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId, SourceRef, VoteTally
from db.models.enums import ActionOutcome, ActionType


class Action(MongoDocument):
    agenda_item_id: PyObjectId
    meeting_id: PyObjectId
    jurisdiction_id: PyObjectId
    action_type: ActionType
    description: str
    moved_by_office_tenure_id: PyObjectId | None = None
    seconded_by_office_tenure_id: PyObjectId | None = None
    outcome: ActionOutcome
    vote_tally: VoteTally | None = None
    effective_date: date | None = None
    document_ids: list[PyObjectId] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)

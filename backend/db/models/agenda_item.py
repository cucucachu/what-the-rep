"""Agenda item collection model (§5)."""

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId, SourceRef
from db.models.enums import AgendaSection


class AgendaItem(MongoDocument):
    meeting_id: PyObjectId
    jurisdiction_id: PyObjectId
    body_id: PyObjectId
    item_number: str
    section: AgendaSection
    title: str
    description: str | None = None
    staff_contact: str | None = None
    document_ids: list[PyObjectId] = Field(default_factory=list)
    topic_ids: list[PyObjectId] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)

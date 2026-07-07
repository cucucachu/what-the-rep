"""Governing body collection model (§5)."""

from datetime import datetime

from db.models.common import MongoDocument, PyObjectId, SourceRef
from db.models.enums import GoverningBodyType


class GoverningBody(MongoDocument):
    jurisdiction_id: PyObjectId
    name: str
    type: GoverningBodyType
    parent_body_id: PyObjectId | None = None
    meeting_cadence: str | None = None
    sources: list[SourceRef]
    created_at: datetime
    updated_at: datetime

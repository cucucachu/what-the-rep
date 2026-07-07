"""Office tenure collection model (§5)."""

from datetime import date

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId, SourceRef
from db.models.enums import ReasonEnded


class OfficeTenure(MongoDocument):
    office_id: PyObjectId
    person_id: PyObjectId
    start_date: date
    end_date: date | None = None
    reason_ended: ReasonEnded | None = None
    is_current: bool
    sources: list[SourceRef] = Field(default_factory=list)

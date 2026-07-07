"""Office collection model (§5)."""

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId, SourceRef
from db.models.enums import SelectionMethod


class Office(MongoDocument):
    jurisdiction_id: PyObjectId
    body_id: PyObjectId | None = None
    title: str
    selection_method: SelectionMethod
    district: str | None = None
    term_length_months: int | None = None
    is_rotating_leadership: bool = False
    sources: list[SourceRef] = Field(default_factory=list)

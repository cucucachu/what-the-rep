"""Document collection model (§5)."""

from datetime import datetime

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId, SourceRef
from db.models.enums import DocumentType, RelatedType


class Document(MongoDocument):
    jurisdiction_id: PyObjectId
    related_type: RelatedType
    related_id: PyObjectId
    doc_type: DocumentType
    title: str
    url: str
    retrieved_at: datetime
    content_hash: str | None = None
    extracted_text_ref: str | None = None
    mime_type: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)

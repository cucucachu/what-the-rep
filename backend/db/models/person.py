"""Person collection model (§5)."""

from datetime import datetime

from pydantic import Field

from db.models.common import MongoDocument, SourceRef


class Person(MongoDocument):
    full_name: str
    slug: str
    bio: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    sources: list[SourceRef]
    created_at: datetime
    updated_at: datetime

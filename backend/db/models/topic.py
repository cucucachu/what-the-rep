"""Topic collection model (§5)."""

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId


class Topic(MongoDocument):
    slug: str
    label: str
    description: str | None = None
    embedding: list[float] = Field(default_factory=list)
    parent_topic_id: PyObjectId | None = None
    auto_generated: bool = False

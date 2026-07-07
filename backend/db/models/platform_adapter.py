"""Platform adapter collection model (§5)."""

from datetime import datetime

from pydantic import Field

from db.models.common import MongoDocument, PyObjectId
from db.models.enums import DetectedMethod, PlatformVendor


class PlatformAdapter(MongoDocument):
    vendor: PlatformVendor
    jurisdiction_id: PyObjectId
    config: dict[str, str | int | None] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)
    detected_method: DetectedMethod
    last_verified_at: datetime | None = None
    notes: str | None = None

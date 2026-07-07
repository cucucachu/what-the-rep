"""Meeting collection model (§5)."""

from datetime import datetime

from pydantic import Field

from db.models.common import MeetingLocation, MongoDocument, PyObjectId, SourceRef
from db.models.enums import MeetingStatus, MeetingType


class Meeting(MongoDocument):
    jurisdiction_id: PyObjectId
    body_id: PyObjectId
    scheduled_start: datetime
    actual_start: datetime | None = None
    location: MeetingLocation | None = None
    meeting_type: MeetingType
    status: MeetingStatus
    video_url: str | None = None
    external_id: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)

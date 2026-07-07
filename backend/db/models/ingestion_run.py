"""Ingestion run collection model (§5)."""

from datetime import datetime

from db.models.common import IngestionRunStats, MongoDocument, PyObjectId
from db.models.enums import IngestionRunStatus, IngestionTriggeredBy, PlatformVendor


class IngestionRun(MongoDocument):
    jurisdiction_id: PyObjectId
    adapter_vendor: PlatformVendor
    started_at: datetime
    finished_at: datetime | None = None
    status: IngestionRunStatus
    stats: IngestionRunStats = IngestionRunStats()
    triggered_by: IngestionTriggeredBy

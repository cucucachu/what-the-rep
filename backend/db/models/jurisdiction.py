"""Jurisdiction collection model (§5)."""

from datetime import date, datetime

from pydantic import Field

from db.models.common import (
    CivicPlatformRef,
    FipsCodes,
    GeoJsonPolygon,
    MongoDocument,
    PyObjectId,
    SourceRef,
)
from db.models.enums import GovernmentType, JurisdictionLevel, JurisdictionStatus


class Jurisdiction(MongoDocument):
    slug: str
    name: str
    level: JurisdictionLevel
    government_type: GovernmentType | None = None
    parent_id: PyObjectId | None = None
    path: list[PyObjectId] = Field(default_factory=list)
    fips: FipsCodes | None = None
    population: int | None = None
    website: str | None = None
    boundary: GeoJsonPolygon | None = None
    incorporated_date: date | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    civic_platforms: list[CivicPlatformRef] = Field(default_factory=list)
    status: JurisdictionStatus
    sources: list[SourceRef]
    created_at: datetime
    updated_at: datetime

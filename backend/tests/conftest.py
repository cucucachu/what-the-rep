"""Shared fixtures for db model and integration tests."""

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from db.models.common import (
    CivicPlatformRef,
    FipsCodes,
    GeoJsonPoint,
    GeoJsonPolygon,
    IngestionRunStats,
    MeetingLocation,
    SourceRef,
    VoteTally,
)
from db.models.enums import SourceMethod


@pytest.fixture
def oid() -> ObjectId:
    return ObjectId()


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def sample_source(now: datetime, oid: ObjectId) -> SourceRef:
    return SourceRef(
        url="https://novato.gov/agenda",
        publisher="City of Novato",
        retrieved_at=now,
        ingestion_run_id=oid,
        method=SourceMethod.SCRAPE,
        confidence=0.95,
    )


@pytest.fixture
def sample_boundary() -> GeoJsonPolygon:
    return GeoJsonPolygon(
        coordinates=[
            [
                [-122.6, 38.0],
                [-122.5, 38.0],
                [-122.5, 38.1],
                [-122.6, 38.1],
                [-122.6, 38.0],
            ]
        ]
    )


@pytest.fixture
def sample_fips() -> FipsCodes:
    return FipsCodes(state_fips="06", county_fips="041", place_fips="51102", geoid="0651102")


@pytest.fixture
def sample_civic_platform(now: datetime) -> CivicPlatformRef:
    return CivicPlatformRef(
        vendor="granicus",
        base_url="https://novato.granicus.com",
        detected_at=now,
        confidence=0.99,
    )


@pytest.fixture
def sample_location() -> MeetingLocation:
    return MeetingLocation(
        name="City Hall Council Chambers",
        address="922 Machin Ave, Novato, CA 94945",
        geo=GeoJsonPoint(coordinates=[-122.569, 38.107]),
    )


@pytest.fixture
def sample_vote_tally() -> VoteTally:
    return VoteTally(ayes=4, noes=1, abstain=0, absent=0, recuse=0)


@pytest.fixture
def sample_ingestion_stats() -> IngestionRunStats:
    return IngestionRunStats(
        meetings_found=3,
        meetings_upserted=2,
        agenda_items_upserted=42,
        actions_upserted=15,
        errors=["minor parse warning"],
    )

"""Load committed boundary GeoJSON fixtures into jurisdiction documents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from db.client import get_db
from db.models.common import GEOJSON_BOUNDARY_ADAPTER, GeoJsonBoundary
from ingestion.registry.marin_seed import SLUG_MARIN_COUNTY, SLUG_NOVATO

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "boundaries"

SLUG_TO_FIXTURE: dict[str, str] = {
    SLUG_NOVATO: "novato.geojson",
    SLUG_MARIN_COUNTY: "marin-county.geojson",
}


def load_fixture_geojson(slug: str, *, fixtures_dir: Path | None = None) -> dict[str, Any]:
    """Read a committed boundary fixture for the given jurisdiction slug."""
    base = fixtures_dir or FIXTURES_DIR
    filename = SLUG_TO_FIXTURE.get(slug)
    if filename is None:
        raise ValueError(f"No boundary fixture mapped for slug {slug!r}")
    path = base / filename
    return json.loads(path.read_text(encoding="utf-8"))


def validate_boundary_geojson(geojson: dict[str, Any]) -> GeoJsonBoundary:
    """Validate fixture GeoJSON against the jurisdiction boundary model."""
    return GEOJSON_BOUNDARY_ADAPTER.validate_python(geojson)


@dataclass(frozen=True)
class BoundaryLoadResult:
    slug: str
    updated: bool


async def load_boundary_for_slug(
    db: AsyncIOMotorDatabase,
    slug: str,
    *,
    fixtures_dir: Path | None = None,
    now: datetime | None = None,
) -> BoundaryLoadResult:
    """Update only the boundary + updated_at fields for one jurisdiction."""
    geojson = load_fixture_geojson(slug, fixtures_dir=fixtures_dir)
    boundary = validate_boundary_geojson(geojson)
    run_at = datetime.now(tz=UTC) if now is None else now

    result = await db.jurisdictions.update_one(
        {"slug": slug},
        {
            "$set": {
                "boundary": boundary.model_dump(mode="python"),
                "updated_at": run_at,
            }
        },
    )
    if result.matched_count == 0:
        raise ValueError(f"Jurisdiction {slug!r} not found; seed jurisdictions first")
    return BoundaryLoadResult(slug=slug, updated=result.modified_count > 0)


async def load_boundaries_from_fixtures(
    db: AsyncIOMotorDatabase | None = None,
    *,
    fixtures_dir: Path | None = None,
    now: datetime | None = None,
) -> list[BoundaryLoadResult]:
    """Load Novato + Marin County boundaries from committed GeoJSON fixtures."""
    database = get_db() if db is None else db
    results: list[BoundaryLoadResult] = []
    for slug in SLUG_TO_FIXTURE:
        results.append(
            await load_boundary_for_slug(
                database,
                slug,
                fixtures_dir=fixtures_dir,
                now=now,
            )
        )
    return results

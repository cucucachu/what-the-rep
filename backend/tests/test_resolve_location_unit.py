"""Unit tests for point-in-polygon logic using committed boundary fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Point, shape

from ingestion.boundaries.load import load_fixture_geojson
from mcp_server.tools.location import (
    jurisdiction_specificity,
    pick_most_specific_jurisdiction,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "boundaries"

NOVATO_CITY_HALL = (38.1074, -122.5697)
POINT_REYES_AREA = (38.0700, -122.8080)
NYC = (40.7128, -74.0060)


@pytest.fixture
def novato_geojson() -> dict:
    return load_fixture_geojson("novato-ca", fixtures_dir=FIXTURES_DIR)


@pytest.fixture
def marin_geojson() -> dict:
    return load_fixture_geojson("marin-county-ca", fixtures_dir=FIXTURES_DIR)


def _contains(geojson: dict, lat: float, lng: float) -> bool:
    return shape(geojson).contains(Point(lng, lat))


def test_novato_city_hall_inside_novato_and_marin(
    novato_geojson: dict,
    marin_geojson: dict,
) -> None:
    lat, lng = NOVATO_CITY_HALL
    assert _contains(novato_geojson, lat, lng)
    assert _contains(marin_geojson, lat, lng)


def test_point_reyes_inside_marin_not_novato(
    novato_geojson: dict,
    marin_geojson: dict,
) -> None:
    lat, lng = POINT_REYES_AREA
    assert not _contains(novato_geojson, lat, lng)
    assert _contains(marin_geojson, lat, lng)


def test_nyc_outside_pilot_boundaries(
    novato_geojson: dict,
    marin_geojson: dict,
) -> None:
    lat, lng = NYC
    assert not _contains(novato_geojson, lat, lng)
    assert not _contains(marin_geojson, lat, lng)


def test_pick_most_specific_jurisdiction_prefers_city() -> None:
    matches = [
        {"slug": "marin-county-ca", "level": "county", "path": []},
        {"slug": "novato-ca", "level": "city", "path": []},
    ]
    picked = pick_most_specific_jurisdiction(matches)
    assert picked["slug"] == "novato-ca"


def test_jurisdiction_specificity_ordering() -> None:
    assert jurisdiction_specificity("city") > jurisdiction_specificity("county")
    assert jurisdiction_specificity("county") > jurisdiction_specificity("state")


def test_fixture_geojson_is_valid_and_reasonably_small() -> None:
    for filename in ("novato.geojson", "marin-county.geojson"):
        path = FIXTURES_DIR / filename
        geojson = json.loads(path.read_text(encoding="utf-8"))
        assert geojson["type"] in {"Polygon", "MultiPolygon"}
        assert path.stat().st_size < 100_000

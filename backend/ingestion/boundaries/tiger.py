"""US Census TIGER/Line shapefile download and GeoJSON conversion."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

import shapefile
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import orient

TIGER_YEAR = 2024
CA_STATE_FIPS = "06"
NOVATO_PLACE_GEOID = "0652582"
MARIN_COUNTY_GEOID = "06041"

TIGER_PLACE_URL = f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/PLACE/tl_{TIGER_YEAR}_{CA_STATE_FIPS}_place.zip"
TIGER_COUNTY_URL = (
    f"https://www2.census.gov/geo/tiger/TIGER{TIGER_YEAR}/COUNTY/tl_{TIGER_YEAR}_us_county.zip"
)

# ~11 m at Marin latitude; keeps fixtures small while preserving point-in-polygon accuracy.
SIMPLIFY_TOLERANCE = 0.0001

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "boundaries"


def _download_zip(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / url.rsplit("/", maxsplit=1)[-1]
    if not zip_path.exists():
        urlretrieve(url, zip_path)
    return zip_path


def _extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    extract_dir = dest_dir / zip_path.stem
    if not extract_dir.exists():
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)
    shp_files = list(extract_dir.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"No shapefile found in {extract_dir}")
    return shp_files[0]


def _record_to_geometry(record: shapefile.Shape) -> BaseGeometry:
    return shape(record.__geo_interface__)


def _find_geometry_by_geoid(shp_path: Path, geoid: str) -> BaseGeometry:
    reader = shapefile.Reader(str(shp_path))
    geoid_field = next((field[0] for field in reader.fields if field[0] == "GEOID"), None)
    if geoid_field is None:
        raise ValueError(f"GEOID field not found in {shp_path}")

    for shape_record in reader.iterShapeRecords():
        if str(shape_record.record[geoid_field]).strip() == geoid:
            return _record_to_geometry(shape_record.shape)
    raise ValueError(f"GEOID {geoid} not found in {shp_path}")


def geometry_to_geojson(geometry: BaseGeometry, *, simplify: bool = True) -> dict[str, Any]:
    """Convert a shapely geometry to MongoDB-compatible GeoJSON."""
    geom = geometry
    if simplify:
        geom = geom.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    geom = orient(geom, sign=1.0)
    geojson = mapping(geom)
    if geojson["type"] == "Polygon":
        geojson["coordinates"] = _ensure_ccw_rings(geojson["coordinates"])
    elif geojson["type"] == "MultiPolygon":
        geojson["coordinates"] = [_ensure_ccw_rings(polygon) for polygon in geojson["coordinates"]]
    return geojson


def _ensure_ccw_rings(polygon_coords: list[list[list[float]]]) -> list[list[list[float]]]:
    from shapely.geometry import LinearRing

    rings: list[list[list[float]]] = []
    for index, ring_coords in enumerate(polygon_coords):
        ring = LinearRing(ring_coords)
        is_exterior = index == 0
        if is_exterior and not ring.is_ccw:
            rings.append(list(reversed(ring_coords)))
        elif not is_exterior and ring.is_ccw:
            rings.append(list(reversed(ring_coords)))
        else:
            rings.append(ring_coords)
    return rings


def fetch_tiger_boundaries(
    *,
    cache_dir: Path | None = None,
    simplify: bool = True,
) -> dict[str, dict[str, Any]]:
    """Download TIGER/Line shapefiles and return GeoJSON for Novato + Marin County."""
    cache_root = cache_dir or Path(tempfile.gettempdir()) / "wtr_tiger_cache"
    place_zip = _download_zip(TIGER_PLACE_URL, cache_root)
    county_zip = _download_zip(TIGER_COUNTY_URL, cache_root)
    place_shp = _extract_zip(place_zip, cache_root)
    county_shp = _extract_zip(county_zip, cache_root)

    novato_geom = _find_geometry_by_geoid(place_shp, NOVATO_PLACE_GEOID)
    marin_geom = _find_geometry_by_geoid(county_shp, MARIN_COUNTY_GEOID)

    return {
        "novato-ca": geometry_to_geojson(novato_geom, simplify=simplify),
        "marin-county-ca": geometry_to_geojson(marin_geom, simplify=simplify),
    }


def extract_boundary_geojson(
    *,
    output_dir: Path | None = None,
    cache_dir: Path | None = None,
    simplify: bool = True,
) -> dict[str, Path]:
    """Fetch TIGER boundaries and write committed fixture GeoJSON files."""
    output = output_dir or FIXTURES_DIR
    output.mkdir(parents=True, exist_ok=True)
    boundaries = fetch_tiger_boundaries(cache_dir=cache_dir, simplify=simplify)

    written: dict[str, Path] = {}
    for slug, geojson in boundaries.items():
        filename = "novato.geojson" if slug == "novato-ca" else "marin-county.geojson"
        path = output / filename
        path.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
        written[slug] = path
    return written

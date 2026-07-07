"""Point-in-polygon jurisdiction resolution against stored boundaries."""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.enums import JurisdictionLevel
from mcp_server.tools.serialize import serialize_docs

PILOT_COVERAGE_MESSAGE = (
    "This location is outside the Marin County pilot coverage area "
    "(Novato and Marin County boundaries only)."
)

LEVEL_SPECIFICITY: dict[JurisdictionLevel, int] = {
    JurisdictionLevel.CITY: 40,
    JurisdictionLevel.TOWN: 40,
    JurisdictionLevel.COUNTY: 30,
    JurisdictionLevel.SPECIAL_DISTRICT: 25,
    JurisdictionLevel.SCHOOL_DISTRICT: 25,
    JurisdictionLevel.TRIBAL_NATION: 25,
    JurisdictionLevel.JOINT_POWERS_AUTHORITY: 25,
    JurisdictionLevel.STATE: 20,
    JurisdictionLevel.FEDERAL: 10,
}


def build_point_geometry(lat: float, lng: float) -> dict[str, Any]:
    """Return a GeoJSON Point for MongoDB geospatial queries (lng, lat order)."""
    return {"type": "Point", "coordinates": [lng, lat]}


def jurisdiction_specificity(level: str) -> int:
    try:
        return LEVEL_SPECIFICITY[JurisdictionLevel(level)]
    except ValueError:
        return 0


def pick_most_specific_jurisdiction(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the deepest matching jurisdiction when multiple boundaries overlap."""
    return max(
        matches,
        key=lambda doc: (jurisdiction_specificity(doc["level"]), len(doc.get("path", []))),
    )


async def find_boundary_matches(
    db: AsyncIOMotorDatabase,
    lat: float,
    lng: float,
) -> list[dict[str, Any]]:
    """Return jurisdictions whose stored boundary contains the point."""
    point = build_point_geometry(lat, lng)
    return await db.jurisdictions.find(
        {
            "boundary": {
                "$geoIntersects": {
                    "$geometry": point,
                }
            }
        }
    ).to_list(length=20)


async def fetch_jurisdiction_stack(
    db: AsyncIOMotorDatabase,
    matched: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build leaf-first stack: matched jurisdiction followed by ancestors."""
    ancestor_ids: list[ObjectId] = list(reversed(matched.get("path", [])))
    ancestors = (
        await db.jurisdictions.find({"_id": {"$in": ancestor_ids}}).to_list(length=20)
        if ancestor_ids
        else []
    )
    ancestors_by_id = {doc["_id"]: doc for doc in ancestors}
    ordered_ancestors = [
        ancestors_by_id[doc_id] for doc_id in ancestor_ids if doc_id in ancestors_by_id
    ]
    return [matched, *ordered_ancestors]


async def resolve_location_at_point(
    db: AsyncIOMotorDatabase,
    lat: float,
    lng: float,
) -> dict[str, Any]:
    """Resolve the jurisdiction stack for a latitude/longitude pair."""
    matches = await find_boundary_matches(db, lat, lng)
    if not matches:
        return {
            "covered": False,
            "lat": lat,
            "lng": lng,
            "message": PILOT_COVERAGE_MESSAGE,
            "jurisdictions": [],
        }

    matched = pick_most_specific_jurisdiction(matches)
    stack = await fetch_jurisdiction_stack(db, matched)
    return {
        "covered": True,
        "lat": lat,
        "lng": lng,
        "jurisdictions": serialize_docs(stack),
    }


def jurisdiction_stack_names(result: dict[str, Any]) -> list[str]:
    """Return jurisdiction names from a resolve_location result."""
    return [item["name"] for item in result.get("jurisdictions", [])]

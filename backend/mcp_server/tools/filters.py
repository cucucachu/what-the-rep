"""Shared query-filter helpers for read-only MCP tools."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def parse_object_id(value: str) -> ObjectId | None:
    if not ObjectId.is_valid(value):
        return None
    return ObjectId(value)


def id_lookup_filter(value: str) -> dict[str, Any] | None:
    """Build an ``_id`` filter that matches string or ObjectId storage."""
    if not ObjectId.is_valid(value):
        return None
    return {"_id": {"$in": [value, ObjectId(value)]}}


def ref_lookup_filter(field: str, value: str) -> dict[str, Any]:
    """Build a foreign-key filter that matches string or ObjectId storage."""
    if not ObjectId.is_valid(value):
        return {field: value}
    return {field: {"$in": [value, ObjectId(value)]}}


def ref_lookup_values(values: set[ObjectId] | set[str] | list) -> dict[str, Any]:
    """Build an ``$in`` filter covering both string and ObjectId reference forms."""
    expanded: list[Any] = []
    for value in values:
        expanded.append(value)
        if isinstance(value, str) and ObjectId.is_valid(value):
            expanded.append(ObjectId(value))
        elif isinstance(value, ObjectId):
            expanded.append(str(value))
    return {"$in": expanded}


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_date_range_filter(
    field: str,
    date_range: dict[str, str] | None,
) -> dict[str, Any]:
    """Build a MongoDB range filter from ``{"start": "YYYY-MM-DD", "end": "..."}``."""
    if not date_range:
        return {}

    bounds: dict[str, Any] = {}
    start = date_range.get("start")
    end = date_range.get("end")
    if start:
        parsed_start = parse_iso_date(start)
        if parsed_start is not None:
            bounds["$gte"] = datetime.combine(parsed_start, datetime.min.time(), tzinfo=UTC)
    if end:
        parsed_end = parse_iso_date(end)
        if parsed_end is not None:
            bounds["$lte"] = datetime.combine(parsed_end, datetime.max.time(), tzinfo=UTC)

    if not bounds:
        return {}
    return {field: bounds}


def build_effective_date_filter(date_range: dict[str, str] | None) -> dict[str, Any]:
    if not date_range:
        return {}

    bounds: dict[str, Any] = {}
    start = date_range.get("start")
    end = date_range.get("end")
    if start:
        parsed_start = parse_iso_date(start)
        if parsed_start is not None:
            bounds["$gte"] = datetime.combine(parsed_start, datetime.min.time())
    if end:
        parsed_end = parse_iso_date(end)
        if parsed_end is not None:
            bounds["$lte"] = datetime.combine(parsed_end, datetime.max.time())

    if not bounds:
        return {}
    return {"effective_date": bounds}


def regex_query_filter(query: str | None) -> re.Pattern[str] | None:
    if not query or not query.strip():
        return None
    return re.compile(re.escape(query.strip()), re.IGNORECASE)


async def resolve_jurisdiction_id(
    db: AsyncIOMotorDatabase,
    slug: str | None,
) -> ObjectId | None:
    if not slug:
        return None
    jurisdiction = await db.jurisdictions.find_one({"slug": slug}, {"_id": 1})
    if jurisdiction is None:
        return None
    return jurisdiction["_id"]


async def resolve_body_id(
    db: AsyncIOMotorDatabase,
    *,
    jurisdiction_id: ObjectId,
    body_name: str,
) -> ObjectId | None:
    body = await db.governing_bodies.find_one(
        {"jurisdiction_id": jurisdiction_id, "name": body_name},
        {"_id": 1},
    )
    if body is None:
        return None
    return body["_id"]

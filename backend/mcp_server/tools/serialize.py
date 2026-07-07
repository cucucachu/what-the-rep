"""BSON → JSON-serializable conversion for MCP structured output."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from bson import ObjectId


def serialize_value(value: Any) -> Any:
    """Recursively convert MongoDB values to JSON-safe forms."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    return value


def serialize_doc(document: dict[str, Any] | None) -> dict[str, Any] | None:
    """Serialize a MongoDB document, exposing ``id`` instead of ``_id``."""
    if document is None:
        return None
    serialized = serialize_value(document)
    if "_id" in serialized:
        serialized["id"] = serialized.pop("_id")
    return serialized


def serialize_docs(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [doc for doc in (serialize_doc(item) for item in documents) if doc is not None]

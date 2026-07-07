"""Content-hash helpers for idempotent Mongo upserts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

_EXCLUDED_KEYS = frozenset({"_id", "content_hash", "updated_at", "created_at", "retrieved_at"})


_HASH_IGNORED_KEYS = frozenset({"ingestion_run_id", "retrieved_at"})


def _normalize_for_hash(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in sorted(value.items()):
            if key in _HASH_IGNORED_KEYS:
                continue
            normalized[key] = _normalize_for_hash(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_for_hash(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def compute_content_hash(document: dict[str, Any]) -> str:
    """SHA-256 of canonical document content (excluding identity/timestamp fields)."""
    payload = {
        key: _normalize_for_hash(value)
        for key, value in document.items()
        if key not in _EXCLUDED_KEYS
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def documents_equal(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    """Return True when stored content_hash matches desired payload."""
    existing_hash = existing.get("content_hash")
    if existing_hash is None:
        return False
    return existing_hash == compute_content_hash(desired)

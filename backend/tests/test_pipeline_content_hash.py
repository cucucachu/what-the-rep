"""Unit tests for content-hash idempotency helpers."""

from __future__ import annotations

from ingestion.pipeline.content_hash import compute_content_hash, documents_equal


def test_content_hash_stable_for_same_payload() -> None:
    doc = {
        "_id": "aaa",
        "external_id": "1980",
        "title": "Regular Meeting",
        "content_hash": "old",
        "updated_at": "2026-01-01",
    }
    h1 = compute_content_hash(doc)
    h2 = compute_content_hash({**doc, "updated_at": "2026-06-01"})
    assert h1 == h2


def test_documents_equal_uses_content_hash() -> None:
    existing = {
        "_id": "aaa",
        "external_id": "1980",
        "title": "Regular Meeting",
        "content_hash": compute_content_hash(
            {"external_id": "1980", "title": "Regular Meeting"},
        ),
    }
    desired = {"external_id": "1980", "title": "Regular Meeting"}
    assert documents_equal(existing, desired) is True

    changed = {"external_id": "1980", "title": "Changed title"}
    assert documents_equal(existing, changed) is False

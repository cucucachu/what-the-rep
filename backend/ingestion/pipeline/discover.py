"""Discover stage — list meetings to ingest."""

from __future__ import annotations

import json
from datetime import date

from ingestion.adapters.base import PlatformAdapter, RawMeetingRef
from ingestion.pipeline.config import GranicusJurisdictionConfig, get_granicus_config


def _load_fixture_metadata(config: GranicusJurisdictionConfig) -> dict:
    metadata_path = config.fixture_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing fixture metadata: {metadata_path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def discover_meetings(
    adapter: PlatformAdapter,
    jurisdiction_slug: str,
    since: date | None = None,
) -> list[RawMeetingRef]:
    """Return meeting refs from the adapter (fixture metadata for MVP)."""
    return adapter.discover_meetings(jurisdiction_slug, since)


def build_ref_from_config(config: GranicusJurisdictionConfig) -> RawMeetingRef:
    """Build a RawMeetingRef from captured fixture metadata + config."""
    metadata = _load_fixture_metadata(config)
    meeting_date = date.fromisoformat(metadata["meeting_date"])
    return RawMeetingRef(
        clip_id=str(metadata["clip_id"]),
        view_id=int(metadata.get("view_id", config.view_id)),
        meeting_date=meeting_date,
        base_url=config.base_url,
        fixture_dir=config.fixture_dir,
        agenda_filename=metadata.get("agenda_filename", config.agenda_filename),
        minutes_filename=metadata.get("minutes_filename", config.minutes_filename),
        body_name=metadata.get("body", config.body_name),
    )


def discover_fixture_meeting(jurisdiction_slug: str) -> RawMeetingRef:
    """Convenience helper for fixture-backed MVP runs."""
    config = get_granicus_config(jurisdiction_slug)
    return build_ref_from_config(config)

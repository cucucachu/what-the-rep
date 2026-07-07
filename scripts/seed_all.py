#!/usr/bin/env python3
"""Idempotent full-database seed for local dev and Docker Compose."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
DOCKER_APP_ROOT = Path("/app")


def _backend_root() -> Path:
    """Return the backend package root (repo layout or Docker /app)."""
    for candidate in (DOCKER_APP_ROOT, BACKEND_ROOT):
        if (candidate / "db").is_dir():
            return candidate
    return BACKEND_ROOT


sys.path.insert(0, str(_backend_root()))

from db.client import close_client, create_indexes, get_db, ping  # noqa: E402
from ingestion.boundaries.load import load_boundaries_from_fixtures  # noqa: E402
from ingestion.officials.marin_county import ingest_marin_county_supervisors  # noqa: E402
from ingestion.officials.novato import ingest_novato_council  # noqa: E402
from ingestion.pipeline.run import run_ingestion_pipeline  # noqa: E402
from ingestion.registry.marin_seed import (  # noqa: E402
    SLUG_MARIN_COUNTY,
    SLUG_NOVATO,
    seed_marin_jurisdictions,
)


async def main() -> None:
    if not await ping():
        print("MongoDB is not reachable", file=sys.stderr)
        raise SystemExit(1)

    db = get_db()

    await create_indexes(db)
    print("Indexes ensured.")

    seed_result = await seed_marin_jurisdictions(db)
    print(
        f"Jurisdictions: {len(seed_result.ids)} "
        f"({seed_result.modified} inserted or updated)."
    )

    boundary_results = await load_boundaries_from_fixtures(db)
    updated = sum(int(result.updated) for result in boundary_results)
    print(f"Boundaries: {len(boundary_results)} loaded ({updated} updated).")

    novato_result = await ingest_novato_council(db)
    print(
        f"Novato officials: {len(novato_result.person_ids)} people, "
        f"{len(novato_result.office_ids)} offices."
    )

    marin_result = await ingest_marin_county_supervisors(db)
    print(
        f"Marin supervisors: {len(marin_result.person_ids)} people, "
        f"{len(marin_result.office_ids)} offices."
    )

    for slug in (SLUG_NOVATO, SLUG_MARIN_COUNTY):
        pipeline_result = await run_ingestion_pipeline(db, slug)
        print(f"Pipeline {slug}: {pipeline_result.status.value}")

    jurisdiction_count = await db.jurisdictions.count_documents({})
    meeting_count = await db.meetings.count_documents({})
    print(f"Seed complete — {jurisdiction_count} jurisdictions, {meeting_count} meetings.")

    await close_client()


if __name__ == "__main__":
    asyncio.run(main())

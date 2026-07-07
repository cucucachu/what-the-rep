#!/usr/bin/env python3
"""Load committed boundary GeoJSON fixtures into MongoDB jurisdiction documents."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from db.client import close_client  # noqa: E402
from ingestion.boundaries.load import load_boundaries_from_fixtures  # noqa: E402
from ingestion.registry.marin_seed import seed_marin_jurisdictions  # noqa: E402


async def main() -> None:
    await seed_marin_jurisdictions()
    results = await load_boundaries_from_fixtures()
    updated = sum(int(result.updated) for result in results)
    print(f"Loaded {len(results)} boundaries ({updated} document(s) updated).")
    await close_client()


if __name__ == "__main__":
    asyncio.run(main())

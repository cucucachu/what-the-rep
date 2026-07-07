#!/usr/bin/env python3
"""Extract Novato + Marin County boundaries from Census TIGER/Line into test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from ingestion.boundaries.tiger import extract_boundary_geojson  # noqa: E402


def main() -> None:
    written = extract_boundary_geojson()
    for slug, path in written.items():
        size_kb = path.stat().st_size / 1024
        print(f"Wrote {slug} -> {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

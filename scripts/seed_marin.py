#!/usr/bin/env python3
"""Bootstrap Marin pilot jurisdiction hierarchy (US, CA, Marin County, Novato)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from ingestion.registry.marin_seed import main  # noqa: E402


if __name__ == "__main__":
    asyncio.run(main())

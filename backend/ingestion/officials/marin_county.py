"""Marin County Board of Supervisors roster parser and store routine."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.enums import SelectionMethod
from ingestion.officials.common import ParsedOfficeholder, build_source
from ingestion.officials.store import OfficialsIngestResult, store_officials
from ingestion.registry.marin_seed import SLUG_MARIN_COUNTY

MARIN_BOS_NAME = "Marin County Board of Supervisors"
MARIN_BOS_SOURCE_URL = "https://www.marincounty.gov/departments/board/about-board-supervisors"
MARIN_PUBLISHER = "County of Marin"

# Page does not list individual term start dates; use Jan 3 after the most recent
# staggered election cycle as an approximate current-term start.
APPROXIMATE_SUPERVISOR_TERM_START = date(2023, 1, 3)

_DISTRICT_LINE = re.compile(
    r"District\s+(\d+):\s*Supervisor\s+(.+?)(?:\s*\(|$)",
    flags=re.IGNORECASE,
)
_CARD_TITLE = re.compile(r"District\s+(\d+)\s+—\s+(.+)", flags=re.IGNORECASE)


def parse_marin_county_supervisors(html: str) -> list[ParsedOfficeholder]:
    """Parse Marin BOS roster HTML into current supervisors."""
    soup = BeautifulSoup(html, "html.parser")
    by_district: dict[str, ParsedOfficeholder] = {}

    for li in soup.select("li"):
        text = li.get_text(" ", strip=True)
        match = _DISTRICT_LINE.match(text)
        if not match:
            continue
        district, name = match.group(1), match.group(2).strip()
        by_district[district] = ParsedOfficeholder(
            full_name=name,
            office_title=f"District {district} Supervisor",
            district=district,
            selection_method=SelectionMethod.ELECTED_BY_DISTRICT,
            is_rotating_leadership=False,
            start_date=APPROXIMATE_SUPERVISOR_TERM_START,
        )

    for strong in soup.select("strong"):
        text = strong.get_text(" ", strip=True)
        match = _CARD_TITLE.match(text)
        if not match:
            continue
        district, name = match.group(1), match.group(2).strip()
        by_district.setdefault(
            district,
            ParsedOfficeholder(
                full_name=name,
                office_title=f"District {district} Supervisor",
                district=district,
                selection_method=SelectionMethod.ELECTED_BY_DISTRICT,
                is_rotating_leadership=False,
                start_date=APPROXIMATE_SUPERVISOR_TERM_START,
            ),
        )

    if len(by_district) != 5:
        raise ValueError(f"Expected 5 Marin supervisors, found {len(by_district)}")

    return [by_district[str(d)] for d in sorted(by_district, key=int)]


def parse_marin_county_supervisors_fixture(
    fixture_path: Path | None = None,
) -> list[ParsedOfficeholder]:
    path = (
        fixture_path
        or Path(__file__).parents[2] / "tests/fixtures/officials/marin-county/bos_roster.html"
    )
    return parse_marin_county_supervisors(path.read_text(encoding="utf-8"))


async def ingest_marin_county_supervisors(
    db: AsyncIOMotorDatabase,
    *,
    html: str | None = None,
    now: datetime | None = None,
) -> OfficialsIngestResult:
    """Parse and store Marin County Board of Supervisors officeholders."""
    source = build_source(MARIN_BOS_SOURCE_URL, MARIN_PUBLISHER)
    parsed = (
        parse_marin_county_supervisors(html)
        if html is not None
        else parse_marin_county_supervisors_fixture()
    )
    run_at = datetime.now(tz=UTC) if now is None else now
    return await store_officials(
        db,
        jurisdiction_slug=SLUG_MARIN_COUNTY,
        body_name=MARIN_BOS_NAME,
        holders=parsed,
        source=source,
        now=run_at,
    )

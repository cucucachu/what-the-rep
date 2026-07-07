"""Novato City Council roster parser and store routine."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorDatabase

from db.models.enums import SelectionMethod
from ingestion.officials.common import (
    CAPTURED_AT,
    ParsedOfficeholder,
    build_source,
    district_from_text,
    parse_month_year,
)
from ingestion.officials.store import OfficialsIngestResult, store_officials
from ingestion.registry.marin_seed import SLUG_NOVATO

NOVATO_COUNCIL_NAME = "Novato City Council"
NOVATO_COUNCIL_SOURCE_URL = "https://www.novato.gov/government/city-council"
NOVATO_PUBLISHER = "City of Novato"

_ACCORDION_HEADING = re.compile(
    r"^(Mayor Pro Tem|Mayor|Councilmember)\s+(.+)$",
    flags=re.IGNORECASE,
)


def _term_start_date(term_text: str) -> date:
    elections = re.findall(
        r"elected(?: for a 4-year term)?(?: to City Council)?(?: in)? November (\d{4})",
        term_text,
        flags=re.IGNORECASE,
    )
    if elections:
        return date(int(elections[-1]), 12, 3)

    appointed = re.search(
        r"Appointed[^.]*\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}",
        term_text,
        flags=re.IGNORECASE,
    )
    if appointed:
        parsed = parse_month_year(appointed.group(0))
        if parsed is not None:
            return parsed

    return date(2022, 12, 3)


def _mayor_term_start() -> date:
    """Mayor is selected each December; use prior December for the current term."""
    return date(CAPTURED_AT.year - 1, 12, 1)


def parse_novato_council(html: str) -> list[ParsedOfficeholder]:
    """Parse Novato council roster HTML into current officeholders."""
    soup = BeautifulSoup(html, "html.parser")
    holders: list[ParsedOfficeholder] = []
    mayor_found = False

    for item in soup.select("div.accordion-item"):
        title_el = item.select_one(".accordion-heading .title")
        if title_el is None:
            continue
        heading = " ".join(title_el.get_text(" ", strip=True).split())
        match = _ACCORDION_HEADING.match(heading)
        if not match:
            continue

        role, full_name = match.group(1), match.group(2).strip()
        content_el = item.select_one(".accordion-content")
        block = content_el.get_text("\n", strip=True) if content_el else ""
        district = district_from_text(block)
        term_match = re.search(r"Term [Ii]nformation:\s*(.+?)(?:\n|$)", block)
        term_text = term_match.group(1).strip() if term_match else ""
        start_date = _term_start_date(term_text)

        if role.lower() == "mayor":
            mayor_found = True
            holders.append(
                ParsedOfficeholder(
                    full_name=full_name,
                    office_title="Mayor",
                    district=None,
                    selection_method=SelectionMethod.ANNUALLY_SELECTED_BY_BODY,
                    is_rotating_leadership=True,
                    start_date=_mayor_term_start(),
                    is_mayor=True,
                )
            )
        elif role.lower() == "mayor pro tem":
            pass

        if district is None:
            continue

        holders.append(
            ParsedOfficeholder(
                full_name=full_name,
                office_title=f"District {district} Councilmember",
                district=district,
                selection_method=SelectionMethod.ELECTED_BY_DISTRICT,
                is_rotating_leadership=False,
                start_date=start_date,
            )
        )

    if not mayor_found:
        raise ValueError("Novato council roster did not include a Mayor accordion item")

    def _sort_key(holder: ParsedOfficeholder) -> tuple[int, str]:
        if holder.office_title == "Mayor":
            return (0, holder.full_name)
        district_num = int(holder.district or "99")
        return (1, f"{district_num:02d}")

    return sorted(holders, key=_sort_key)


def parse_novato_council_fixture(fixture_path: Path | None = None) -> list[ParsedOfficeholder]:
    path = (
        fixture_path
        or Path(__file__).parents[2] / "tests/fixtures/officials/novato/council_roster.html"
    )
    return parse_novato_council(path.read_text(encoding="utf-8"))


async def ingest_novato_council(
    db: AsyncIOMotorDatabase,
    *,
    html: str | None = None,
    now: datetime | None = None,
) -> OfficialsIngestResult:
    """Parse and store Novato City Council officeholders."""
    source = build_source(NOVATO_COUNCIL_SOURCE_URL, NOVATO_PUBLISHER)
    parsed = parse_novato_council(html) if html is not None else parse_novato_council_fixture()
    run_at = datetime.now(tz=UTC) if now is None else now
    return await store_officials(
        db,
        jurisdiction_slug=SLUG_NOVATO,
        body_name=NOVATO_COUNCIL_NAME,
        holders=parsed,
        source=source,
        now=run_at,
    )

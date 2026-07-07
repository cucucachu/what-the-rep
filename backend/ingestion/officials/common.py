"""Shared helpers for officeholder ingestion."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime

from db.models.common import SourceRef
from db.models.enums import SelectionMethod

CAPTURED_AT = datetime(2026, 7, 6, 22, 36, tzinfo=UTC)


@dataclass(frozen=True)
class ParsedOfficeholder:
    """Intermediate representation of one current officeholder."""

    full_name: str
    office_title: str
    district: str | None
    selection_method: SelectionMethod
    is_rotating_leadership: bool
    start_date: date
    is_mayor: bool = False


def slugify_person_name(full_name: str) -> str:
    """Build a stable person slug from a display name."""
    normalized = unicodedata.normalize("NFKD", full_name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "unknown"


def build_source(
    url: str,
    publisher: str,
    *,
    retrieved_at: datetime | None = None,
) -> SourceRef:
    from db.models.enums import SourceMethod

    return SourceRef(
        url=url,
        publisher=publisher,
        retrieved_at=CAPTURED_AT if retrieved_at is None else retrieved_at,
        method=SourceMethod.SCRAPE,
    )


def parse_month_year(text: str) -> date | None:
    """Parse 'November 2024' style election dates."""
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        month_name, day, year = match.groups()
        month = datetime.strptime(month_name[:3], "%b").month
        return date(int(year), month, int(day))

    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+(\d{4})\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        month_name, year = match.groups()
        month = datetime.strptime(month_name[:3], "%b").month
        # Municipal terms typically begin in early December after November elections.
        return date(int(year), 12, 3) if month == 11 else date(int(year), month, 1)
    return None


def district_from_text(text: str) -> str | None:
    match = re.search(r"District:\s*(\d+)", text, flags=re.IGNORECASE)
    return match.group(1) if match else None

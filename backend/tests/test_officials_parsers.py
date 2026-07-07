"""Unit tests for officeholder parsers (T5)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ingestion.officials.marin_county import parse_marin_county_supervisors
from ingestion.officials.novato import parse_novato_council

FIXTURES = Path(__file__).parent / "fixtures" / "officials"

# Captured 2026-07-06 from https://www.novato.gov/government/city-council
# (live fetch blocked by Akamai; HTML archived via Wayback 2026-06-01 snapshot).
NOVATO_EXPECTED = [
    ("Mayor", "Rachel Farac", None, date(2025, 12, 1)),
    ("District 1 Councilmember", "Kevin Jacobs", "1", date(2024, 12, 3)),
    ("District 2 Councilmember", "Rachel Farac", "2", date(2022, 12, 3)),
    ("District 3 Councilmember", "Tim O'Connor", "3", date(2024, 12, 3)),
    ("District 4 Councilmember", "Pat Eklund", "4", date(2022, 12, 3)),
    ("District 5 Councilmember", "Sandeep Karkal", "5", date(2025, 12, 3)),
]

# Captured 2026-07-06 from https://www.marincounty.gov/departments/board/about-board-supervisors
MARIN_EXPECTED = [
    ("District 1 Supervisor", "Mary Sackett", "1"),
    ("District 2 Supervisor", "Brian Colbert", "2"),
    ("District 3 Supervisor", "Stephanie Moulton-Peters", "3"),
    ("District 4 Supervisor", "Dennis Rodoni", "4"),
    ("District 5 Supervisor", "Eric Lucan", "5"),
]


class TestParseNovatoCouncil:
    def test_extracts_full_roster_from_fixture(self) -> None:
        html = (FIXTURES / "novato" / "council_roster.html").read_text(encoding="utf-8")
        parsed = parse_novato_council(html)

        assert len(parsed) == len(NOVATO_EXPECTED)
        actual = [(h.office_title, h.full_name, h.district, h.start_date) for h in parsed]
        assert actual == NOVATO_EXPECTED

    def test_mayor_is_rotating_leadership(self) -> None:
        html = (FIXTURES / "novato" / "council_roster.html").read_text(encoding="utf-8")
        mayor = next(h for h in parse_novato_council(html) if h.office_title == "Mayor")
        assert mayor.is_rotating_leadership is True
        assert mayor.selection_method.value == "annually_selected_by_body"


class TestParseMarinCountySupervisors:
    def test_extracts_full_roster_from_fixture(self) -> None:
        html = (FIXTURES / "marin-county" / "bos_roster.html").read_text(encoding="utf-8")
        parsed = parse_marin_county_supervisors(html)

        assert len(parsed) == len(MARIN_EXPECTED)
        actual = [(h.office_title, h.full_name, h.district) for h in parsed]
        assert actual == MARIN_EXPECTED

    def test_all_supervisors_elected_by_district(self) -> None:
        html = (FIXTURES / "marin-county" / "bos_roster.html").read_text(encoding="utf-8")
        for holder in parse_marin_county_supervisors(html):
            assert holder.selection_method.value == "elected_by_district"
            assert holder.district is not None

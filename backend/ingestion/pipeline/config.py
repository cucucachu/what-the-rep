"""Jurisdiction-specific Granicus adapter configuration (no code branching)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parents[2] / "tests" / "fixtures" / "granicus"


@dataclass(frozen=True)
class GranicusJurisdictionConfig:
    jurisdiction_slug: str
    base_url: str
    view_id: int
    fixture_dir: Path
    body_name: str
    publisher: str
    agenda_filename: str = "agenda.pdf"
    minutes_filename: str = "minutes.pdf"


GRANICUS_CONFIGS: dict[str, GranicusJurisdictionConfig] = {
    "novato-ca": GranicusJurisdictionConfig(
        jurisdiction_slug="novato-ca",
        base_url="https://novato.granicus.com",
        view_id=7,
        fixture_dir=FIXTURES_ROOT / "novato",
        body_name="Novato City Council",
        publisher="City of Novato",
    ),
    "marin-county-ca": GranicusJurisdictionConfig(
        jurisdiction_slug="marin-county-ca",
        base_url="https://marin.granicus.com",
        view_id=33,
        fixture_dir=FIXTURES_ROOT / "marin-county",
        body_name="Marin County Board of Supervisors",
        publisher="County of Marin",
        agenda_filename="agenda.html",
        minutes_filename="minutes.html",
    ),
}


def get_granicus_config(jurisdiction_slug: str) -> GranicusJurisdictionConfig:
    try:
        return GRANICUS_CONFIGS[jurisdiction_slug]
    except KeyError as exc:
        raise ValueError(f"No Granicus config for jurisdiction {jurisdiction_slug!r}") from exc

"""Unit tests for the Granicus adapter spike (T2) against Novato fixtures."""

from datetime import date
from pathlib import Path

import pytest

from ingestion.adapters.granicus import GranicusAdapter

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "granicus" / "novato"

EXPECTED_AGENDA_ITEM_NUMBERS = (
    "A",
    "B",
    "C",
    "C.1",
    "D",
    "E",
    "F",
    "G",
    "G.1",
    "G.2",
    "G.3",
    "G.4",
    "G.5",
    "G.6",
    "H",
    "I",
    "I.1",
    "I.2",
    "J",
    "J.1",
    "J.2",
    "K",
    "L",
    "M",
)

RESOLUTION_2024_011_MOTION = {
    "description_prefix": (
        "adopt a resolution finding the proposed General Plan Land Use Map and Text "
        "Amendments and Combined Master Plan, Precise Development Plan and Design Review "
        "addressing Residential Redevelopment of the former Fireman's Fund Office Campus"
    ),
    "moved_by": "Mayor Pro Tem O'Connor",
    "seconded_by": "Councilmember Wernick",
    "outcome": "passed",
    "vote_tally": {"ayes": 4, "noes": 1, "abstain": 0, "absent": 0, "recuse": 0},
    "roll_call": {
        "ayes": ("FARAC", "WERNICK", "O'CONNOR", "MILBERG"),
        "noes": ("EKLUND",),
        "abstain": (),
        "absent": (),
        "recuse": (),
    },
    "resolution_number": "2024-011",
}


@pytest.fixture
def adapter() -> GranicusAdapter:
    return GranicusAdapter()


@pytest.fixture
def meeting_detail(adapter: GranicusAdapter):
    return adapter.parse_fixture_dir(FIXTURE_DIR)


def test_meeting_metadata(meeting_detail) -> None:
    assert meeting_detail.meeting_date == date(2024, 1, 23)
    assert meeting_detail.meeting_type == "regular"


def test_agenda_item_count_and_order(meeting_detail) -> None:
    numbers = tuple(item.item_number for item in meeting_detail.agenda_items)
    assert numbers == EXPECTED_AGENDA_ITEM_NUMBERS


def test_agenda_item_i1_title(meeting_detail) -> None:
    item = next(i for i in meeting_detail.agenda_items if i.item_number == "I.1")
    assert item.title.startswith("773, 775, & 777 San Marin Drive")
    assert item.section == "public_hearing"


def test_non_unanimous_roll_call_on_resolution_2024_011(meeting_detail) -> None:
    motion = next(m for m in meeting_detail.motions if m.resolution_number == "2024-011")
    expected = RESOLUTION_2024_011_MOTION

    assert expected["description_prefix"] in motion.description
    assert motion.moved_by == expected["moved_by"]
    assert motion.seconded_by == expected["seconded_by"]
    assert motion.outcome == expected["outcome"]
    assert motion.vote_tally.ayes == expected["vote_tally"]["ayes"]
    assert motion.vote_tally.noes == expected["vote_tally"]["noes"]
    assert motion.vote_tally.abstain == expected["vote_tally"]["abstain"]
    assert motion.vote_tally.absent == expected["vote_tally"]["absent"]
    assert motion.vote_tally.recuse == expected["vote_tally"]["recuse"]
    assert motion.roll_call.ayes == expected["roll_call"]["ayes"]
    assert motion.roll_call.noes == expected["roll_call"]["noes"]
    assert motion.roll_call.abstain == expected["roll_call"]["abstain"]
    assert motion.roll_call.absent == expected["roll_call"]["absent"]
    assert motion.roll_call.recuse == expected["roll_call"]["recuse"]


def test_non_unanimous_motion_attached_to_agenda_item_i1(meeting_detail) -> None:
    item = next(i for i in meeting_detail.agenda_items if i.item_number == "I.1")
    resolution_numbers = {m.resolution_number for m in item.motions}
    assert "2024-011" in resolution_numbers
    assert "2024-012" in resolution_numbers


def test_fetch_minutes_returns_motions(adapter: GranicusAdapter) -> None:
    minutes = adapter.parse_minutes(FIXTURE_DIR / "minutes.pdf")
    assert minutes.meeting_date == date(2024, 1, 23)
    non_unanimous = [m for m in minutes.motions if m.roll_call.noes]
    assert len(non_unanimous) >= 1
    assert non_unanimous[0].roll_call.noes == ("EKLUND",)

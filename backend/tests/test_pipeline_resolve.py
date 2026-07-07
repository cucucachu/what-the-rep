"""Unit and integration tests for entity resolution (T7)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from bson import ObjectId

from db.client import close_client, get_client, ping
from db.models.common import SourceRef
from db.models.enums import (
    ActionOutcome,
    ActionType,
    AgendaSection,
    GoverningBodyType,
    MeetingType,
    SelectionMethod,
    SourceMethod,
    Vote,
)
from db.models.governing_body import GoverningBody
from db.models.office import Office
from db.models.office_tenure import OfficeTenure
from db.models.person import Person
from ingestion.adapters.granicus import RollCall
from ingestion.pipeline.name_match import (
    last_name_token,
    match_tokens_for_full_name,
    parse_official_name,
)
from ingestion.pipeline.resolve import resolve_officials
from ingestion.pipeline.types import (
    NormalizedAction,
    NormalizedAgendaItem,
    NormalizedMeeting,
    NormalizedVoteRecord,
)

TEST_DB_NAME = "what_the_rep_resolve_test"
NOW = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
MEETING_SOURCE = SourceRef(
    url="https://example.gov/meeting/123",
    publisher="Test City",
    retrieved_at=NOW,
    method=SourceMethod.SCRAPE,
)


@pytest.fixture
async def resolve_db():
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    db = get_client()[TEST_DB_NAME]
    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


class TestNameMatchHelpers:
    def test_parse_roll_call_last_name(self) -> None:
        parsed = parse_official_name("EKLUND")
        assert parsed is not None
        assert parsed.last_token == "EKLUND"
        assert "EKLUND" in parsed.match_tokens

    def test_parse_apostrophe_roll_call(self) -> None:
        parsed = parse_official_name("O'CONNOR")
        assert parsed is not None
        assert "OCONNOR" in parsed.match_tokens

    def test_parse_title_and_suffix(self) -> None:
        parsed = parse_official_name("Mayor Pro Tem O'Connor")
        assert parsed is not None
        assert parsed.title == "mayor pro tem"
        assert parsed.last_token == "O'CONNOR"

    def test_person_token_matches_roll_call(self) -> None:
        person_tokens = match_tokens_for_full_name("Tim O'Connor")
        parsed = parse_official_name("O'CONNOR")
        assert parsed is not None
        assert person_tokens & parsed.match_tokens

    def test_suffix_stripped_from_full_name(self) -> None:
        assert last_name_token("Pat Eklund Jr.") == "EKLUND"


async def _seed_body(
    db,
) -> tuple[ObjectId, ObjectId]:
    jurisdiction_id = ObjectId()
    body_id = ObjectId()
    source = MEETING_SOURCE

    body_doc = GoverningBody(
        _id=body_id,
        jurisdiction_id=jurisdiction_id,
        name="City Council",
        type=GoverningBodyType.LEGISLATIVE,
        sources=[source],
        created_at=NOW,
        updated_at=NOW,
    ).to_mongo()
    await db.governing_bodies.insert_one(body_doc)
    return body_doc["jurisdiction_id"], body_doc["_id"]


async def _insert_office_holder(
    db,
    *,
    jurisdiction_id: ObjectId,
    body_id: ObjectId,
    office_title: str,
    full_name: str,
    district: str | None = None,
    selection_method: SelectionMethod = SelectionMethod.ELECTED_BY_DISTRICT,
    is_rotating: bool = False,
    tenure_id: ObjectId | None = None,
) -> tuple[ObjectId, ObjectId, ObjectId]:
    source = MEETING_SOURCE
    office_id = ObjectId()
    person_id = ObjectId()
    tenure_id = tenure_id or ObjectId()

    await db.offices.insert_one(
        Office(
            _id=office_id,
            jurisdiction_id=jurisdiction_id,
            body_id=body_id,
            title=office_title,
            selection_method=selection_method,
            district=district,
            is_rotating_leadership=is_rotating,
            sources=[source],
        ).to_mongo(),
    )
    person_doc = Person(
        _id=person_id,
        full_name=full_name,
        slug=full_name.lower().replace(" ", "-").replace("'", ""),
        sources=[source],
        created_at=NOW,
        updated_at=NOW,
    ).to_mongo()
    await db.people.insert_one(person_doc)
    tenure_doc = OfficeTenure(
        _id=tenure_id,
        office_id=office_id,
        person_id=person_id,
        start_date=date(2022, 12, 3),
        is_current=True,
        sources=[source],
    ).to_mongo()
    await db.office_tenures.insert_one(tenure_doc)
    return tenure_doc["office_id"], tenure_doc["person_id"], tenure_doc["_id"]


def _sample_meeting(
    *,
    meeting_type: MeetingType = MeetingType.REGULAR,
    voter_names: tuple[str, ...] = ("EKLUND",),
    moved_by: str | None = None,
    scheduled_start: datetime | None = None,
) -> NormalizedMeeting:
    vote_records = [
        NormalizedVoteRecord(
            external_id=f"action:{name}",
            voter_name=name,
            vote=Vote.AYE,
        )
        for name in voter_names
    ]
    action = NormalizedAction(
        external_id="clip:I.1:2024-011",
        action_type=ActionType.RESOLUTION,
        description="Test action",
        moved_by_name=moved_by,
        seconded_by_name=None,
        outcome=ActionOutcome.PASSED,
        vote_tally=None,
        roll_call=RollCall(),
        vote_records=vote_records,
    )
    return NormalizedMeeting(
        external_id="clip-123",
        scheduled_start=scheduled_start or datetime(2024, 1, 23, 18, 0, tzinfo=UTC),
        meeting_type=meeting_type,
        video_url=None,
        sources=[MEETING_SOURCE],
        agenda_items=[
            NormalizedAgendaItem(
                external_id="clip:I.1",
                item_number="I.1",
                section=AgendaSection.PUBLIC_HEARING,
                title="Test item",
                actions=[action],
            ),
        ],
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_exact_roll_call_match_links_tenure(resolve_db) -> None:
    jurisdiction_id, body_id = await _seed_body(resolve_db)
    _, _, tenure_id = await _insert_office_holder(
        resolve_db,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        office_title="District 4 Councilmember",
        full_name="Pat Eklund",
        district="4",
    )
    meeting = _sample_meeting(voter_names=("EKLUND",))

    result = await resolve_officials(
        resolve_db,
        meeting,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
    )

    record = result.meeting.agenda_items[0].actions[0].vote_records[0]
    assert record.resolution_status == "matched"
    assert record.office_tenure_id == str(tenure_id)
    assert result.unresolved_names == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reorganization_creates_mayor_tenure_and_ends_prior(resolve_db) -> None:
    jurisdiction_id, body_id = await _seed_body(resolve_db)
    mayor_office_id, _farac_id, farac_mayor_tenure_id = await _insert_office_holder(
        resolve_db,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        office_title="Mayor",
        full_name="Rachel Farac",
        selection_method=SelectionMethod.ANNUALLY_SELECTED_BY_BODY,
        is_rotating=True,
    )
    await _insert_office_holder(
        resolve_db,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        office_title="District 3 Councilmember",
        full_name="Tim O'Connor",
        district="3",
    )
    meeting = _sample_meeting(
        meeting_type=MeetingType.REORGANIZATION,
        voter_names=(),
        moved_by="Mayor O'Connor",
        scheduled_start=datetime(2024, 12, 3, 18, 0, tzinfo=UTC),
    )

    result = await resolve_officials(
        resolve_db,
        meeting,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
    )

    action = result.meeting.agenda_items[0].actions[0]
    assert action.moved_by_office_tenure_id is not None
    assert action.moved_by_office_tenure_id != str(farac_mayor_tenure_id)

    ended = await resolve_db.office_tenures.find_one({"_id": farac_mayor_tenure_id})
    assert ended is not None
    assert ended["is_current"] is False
    assert ended["end_date"] == datetime(2024, 12, 3)
    assert ended["reason_ended"] == "reorganization"
    assert any(s["url"] == MEETING_SOURCE.url for s in ended["sources"])

    new_mayor = await resolve_db.office_tenures.find_one(
        {"office_id": mayor_office_id, "is_current": True},
    )
    assert new_mayor is not None
    assert (
        new_mayor["person_id"]
        == (await resolve_db.people.find_one({"full_name": "Tim O'Connor"}))["_id"]
    )
    assert new_mayor["start_date"] == datetime(2024, 12, 3)
    assert any(s["url"] == MEETING_SOURCE.url for s in new_mayor["sources"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unresolvable_name_is_flagged_not_guessed(resolve_db) -> None:
    jurisdiction_id, body_id = await _seed_body(resolve_db)
    await _insert_office_holder(
        resolve_db,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        office_title="District 1 Councilmember",
        full_name="Kevin Jacobs",
        district="1",
    )
    meeting = _sample_meeting(voter_names=("XYZZYUNKNOWN",))

    result = await resolve_officials(
        resolve_db,
        meeting,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
    )

    record = result.meeting.agenda_items[0].actions[0].vote_records[0]
    assert record.resolution_status == "unresolved"
    assert record.office_tenure_id is None
    assert record.person_id is None
    assert "XYZZYUNKNOWN" in result.unresolved_names


def test_unresolvable_name_without_db() -> None:
    """Pure matcher: unknown token has no parse failure but would not match."""
    parsed = parse_official_name("XYZZYUNKNOWN")
    assert parsed is not None
    assert parsed.last_token == "XYZZYUNKNOWN"

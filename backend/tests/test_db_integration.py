"""Integration tests against a real MongoDB instance."""

from datetime import UTC, date, datetime

import pytest
from bson import ObjectId

from db.client import close_client, create_indexes, get_client, ping
from db.models.action import Action
from db.models.agenda_item import AgendaItem
from db.models.common import SourceRef
from db.models.document import Document
from db.models.enums import (
    ActionOutcome,
    ActionType,
    AgendaSection,
    DetectedMethod,
    DocumentType,
    GoverningBodyType,
    GovernmentType,
    IngestionRunStatus,
    IngestionTriggeredBy,
    JurisdictionLevel,
    JurisdictionStatus,
    MeetingStatus,
    MeetingType,
    PlatformVendor,
    RelatedType,
    SelectionMethod,
    SourceMethod,
    Vote,
)
from db.models.governing_body import GoverningBody
from db.models.ingestion_run import IngestionRun
from db.models.jurisdiction import Jurisdiction
from db.models.meeting import Meeting
from db.models.office import Office
from db.models.office_tenure import OfficeTenure
from db.models.person import Person
from db.models.platform_adapter import PlatformAdapter
from db.models.topic import Topic
from db.models.vote_record import VoteRecord

pytestmark = pytest.mark.integration

TEST_DB_NAME = "what_the_rep_integration_test"


@pytest.fixture
async def mongo_db():
    if not await ping():
        pytest.skip("MongoDB is not reachable")

    db = get_client()[TEST_DB_NAME]
    yield db

    for collection_name in await db.list_collection_names():
        await db.drop_collection(collection_name)
    await close_client()


def _source(now: datetime, run_id: ObjectId) -> SourceRef:
    return SourceRef(
        url="https://novato.gov/agenda",
        publisher="City of Novato",
        retrieved_at=now,
        ingestion_run_id=run_id,
        method=SourceMethod.SCRAPE,
        confidence=0.95,
    )


def _assert_values_equal(original, round_tripped) -> None:
    if isinstance(original, datetime) and isinstance(round_tripped, datetime):
        assert original.replace(tzinfo=None) == round_tripped.replace(tzinfo=None)
    elif isinstance(original, date) and isinstance(round_tripped, date):
        assert original == round_tripped
    elif isinstance(original, dict) and isinstance(round_tripped, dict):
        assert original.keys() == round_tripped.keys()
        for key in original:
            _assert_values_equal(original[key], round_tripped[key])
    elif isinstance(original, list) and isinstance(round_tripped, list):
        assert len(original) == len(round_tripped)
        for left, right in zip(original, round_tripped, strict=True):
            _assert_values_equal(left, right)
    else:
        assert original == round_tripped


async def _round_trip(db, collection: str, model):
    payload = model.to_mongo()
    await db[collection].insert_one(payload)
    stored = await db[collection].find_one({"_id": payload["_id"]})
    assert stored is not None
    round_tripped = type(model).model_validate(stored)
    _assert_values_equal(
        model.model_dump(by_alias=True, mode="python"),
        round_tripped.model_dump(by_alias=True, mode="python"),
    )


@pytest.mark.asyncio
async def test_create_indexes_is_idempotent(mongo_db) -> None:
    await create_indexes(mongo_db)
    await create_indexes(mongo_db)

    index_names = await mongo_db.jurisdictions.index_information()
    assert "path_1" in index_names
    assert "parent_id_1" in index_names
    assert "boundary_2dsphere" in index_names

    meeting_indexes = await mongo_db.meetings.index_information()
    assert "jurisdiction_id_1_scheduled_start_1" in meeting_indexes

    action_indexes = await mongo_db.actions.index_information()
    assert "jurisdiction_id_1_effective_date_1" in action_indexes


@pytest.mark.asyncio
async def test_all_collections_round_trip(
    mongo_db,
    sample_boundary,
    sample_fips,
    sample_civic_platform,
    sample_location,
    sample_vote_tally,
    sample_ingestion_stats,
) -> None:
    now = datetime(2026, 7, 6, 12, 0, tzinfo=UTC)
    run_id = ObjectId()
    source = _source(now, run_id)

    jurisdiction_id = ObjectId()
    body_id = ObjectId()
    office_id = ObjectId()
    person_id = ObjectId()
    tenure_id = ObjectId()
    meeting_id = ObjectId()
    agenda_item_id = ObjectId()
    action_id = ObjectId()
    document_id = ObjectId()
    topic_id = ObjectId()

    jurisdiction = Jurisdiction(
        _id=jurisdiction_id,
        slug="novato-ca",
        name="City of Novato",
        level=JurisdictionLevel.CITY,
        government_type=GovernmentType.GENERAL_LAW,
        parent_id=ObjectId(),
        path=[ObjectId()],
        fips=sample_fips,
        boundary=sample_boundary,
        status=JurisdictionStatus.PILOT,
        civic_platforms=[sample_civic_platform],
        sources=[source],
        created_at=now,
        updated_at=now,
    )
    governing_body = GoverningBody(
        _id=body_id,
        jurisdiction_id=jurisdiction_id,
        name="City Council",
        type=GoverningBodyType.LEGISLATIVE,
        sources=[source],
        created_at=now,
        updated_at=now,
    )
    office = Office(
        _id=office_id,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        title="District 1 Councilmember",
        selection_method=SelectionMethod.ELECTED_BY_DISTRICT,
        district="1",
        sources=[source],
    )
    person = Person(
        _id=person_id,
        full_name="Jane Doe",
        slug="jane-doe",
        sources=[source],
        created_at=now,
        updated_at=now,
    )
    tenure = OfficeTenure(
        _id=tenure_id,
        office_id=office_id,
        person_id=person_id,
        start_date=date(2024, 1, 1),
        is_current=True,
        sources=[source],
    )
    meeting = Meeting(
        _id=meeting_id,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        scheduled_start=now,
        location=sample_location,
        meeting_type=MeetingType.REGULAR,
        status=MeetingStatus.HELD,
        external_id="granicus-123",
        sources=[source],
    )
    agenda_item = AgendaItem(
        _id=agenda_item_id,
        meeting_id=meeting_id,
        jurisdiction_id=jurisdiction_id,
        body_id=body_id,
        item_number="G.2",
        section=AgendaSection.PUBLIC_HEARING,
        title="Costco gas station appeal",
        document_ids=[document_id],
        topic_ids=[topic_id],
        sources=[source],
    )
    action = Action(
        _id=action_id,
        agenda_item_id=agenda_item_id,
        meeting_id=meeting_id,
        jurisdiction_id=jurisdiction_id,
        action_type=ActionType.RESOLUTION,
        description="Adopt resolution 2024-011",
        moved_by_office_tenure_id=tenure_id,
        outcome=ActionOutcome.PASSED,
        vote_tally=sample_vote_tally,
        effective_date=date(2024, 3, 5),
        document_ids=[document_id],
        sources=[source],
    )
    vote_record = VoteRecord(
        _id=ObjectId(),
        action_id=action_id,
        office_tenure_id=tenure_id,
        person_id=person_id,
        vote=Vote.AYE,
    )
    document = Document(
        _id=document_id,
        jurisdiction_id=jurisdiction_id,
        related_type=RelatedType.MEETING,
        related_id=meeting_id,
        doc_type=DocumentType.AGENDA,
        title="March 5, 2024 Agenda",
        url="https://novato.gov/agenda.pdf",
        retrieved_at=now,
        sources=[source],
    )
    topic = Topic(
        _id=topic_id,
        slug="housing",
        label="Housing",
        embedding=[0.1, 0.2],
        auto_generated=False,
    )
    platform_adapter = PlatformAdapter(
        _id=ObjectId(),
        vendor=PlatformVendor.GRANICUS,
        jurisdiction_id=jurisdiction_id,
        config={"base_url": "https://novato.granicus.com"},
        capabilities=["agendas", "minutes"],
        detected_method=DetectedMethod.AUTO_FINGERPRINT,
        last_verified_at=now,
    )
    ingestion_run = IngestionRun(
        _id=run_id,
        jurisdiction_id=jurisdiction_id,
        adapter_vendor=PlatformVendor.GRANICUS,
        started_at=now,
        finished_at=now,
        status=IngestionRunStatus.SUCCESS,
        stats=sample_ingestion_stats,
        triggered_by=IngestionTriggeredBy.SCHEDULED,
    )

    round_trips = [
        ("jurisdictions", jurisdiction),
        ("governing_bodies", governing_body),
        ("offices", office),
        ("people", person),
        ("office_tenures", tenure),
        ("meetings", meeting),
        ("agenda_items", agenda_item),
        ("actions", action),
        ("vote_records", vote_record),
        ("documents", document),
        ("topics", topic),
        ("platform_adapters", platform_adapter),
        ("ingestion_runs", ingestion_run),
    ]

    for collection, model in round_trips:
        await _round_trip(mongo_db, collection, model)

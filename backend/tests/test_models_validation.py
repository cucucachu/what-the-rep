"""Unit tests for Pydantic model validation (no database)."""

from datetime import date, datetime

import pytest
from bson import ObjectId
from pydantic import ValidationError

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


def test_source_ref_valid(now: datetime) -> None:
    ref = SourceRef(
        url="https://example.gov",
        publisher="Example Gov",
        retrieved_at=now,
        method=SourceMethod.API,
    )
    assert ref.method == SourceMethod.API


def test_source_ref_invalid_method(now: datetime) -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            url="https://example.gov",
            publisher="Example Gov",
            retrieved_at=now,
            method="telepathy",
        )


def test_jurisdiction_valid(
    sample_source: SourceRef,
    sample_fips,
    sample_boundary,
    sample_civic_platform,
    now: datetime,
    oid: ObjectId,
) -> None:
    doc = Jurisdiction(
        _id=oid,
        slug="novato-ca",
        name="City of Novato",
        level=JurisdictionLevel.CITY,
        government_type=GovernmentType.GENERAL_LAW,
        parent_id=ObjectId(),
        path=[ObjectId()],
        fips=sample_fips,
        population=52000,
        website="https://novato.gov",
        boundary=sample_boundary,
        incorporated_date=date(1960, 1, 14),
        external_ids={"wikipedia": "Novato,_California"},
        civic_platforms=[sample_civic_platform],
        status=JurisdictionStatus.PILOT,
        sources=[sample_source],
        created_at=now,
        updated_at=now,
    )
    assert doc.level == JurisdictionLevel.CITY


def test_jurisdiction_invalid_level(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Jurisdiction(
            _id=oid,
            slug="novato-ca",
            name="City of Novato",
            level="village",
            status=JurisdictionStatus.PILOT,
            sources=[sample_source],
            created_at=now,
            updated_at=now,
        )


def test_governing_body_valid(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    doc = GoverningBody(
        _id=oid,
        jurisdiction_id=ObjectId(),
        name="City Council",
        type=GoverningBodyType.LEGISLATIVE,
        meeting_cadence="2nd/4th Tuesday 6:00pm",
        sources=[sample_source],
        created_at=now,
        updated_at=now,
    )
    assert doc.type == GoverningBodyType.LEGISLATIVE


def test_governing_body_missing_required(now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        GoverningBody(
            _id=oid,
            jurisdiction_id=ObjectId(),
            name="City Council",
            created_at=now,
            updated_at=now,
        )


def test_office_valid(sample_source: SourceRef, oid: ObjectId) -> None:
    doc = Office(
        _id=oid,
        jurisdiction_id=ObjectId(),
        body_id=ObjectId(),
        title="District 1 Councilmember",
        selection_method=SelectionMethod.ELECTED_BY_DISTRICT,
        district="1",
        term_length_months=48,
        is_rotating_leadership=False,
        sources=[sample_source],
    )
    assert doc.selection_method == SelectionMethod.ELECTED_BY_DISTRICT


def test_office_invalid_selection_method(sample_source: SourceRef, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Office(
            _id=oid,
            jurisdiction_id=ObjectId(),
            title="Mayor",
            selection_method="inherited",
            sources=[sample_source],
        )


def test_person_valid(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    doc = Person(
        _id=oid,
        full_name="Jane Doe",
        slug="jane-doe",
        bio="Councilmember",
        external_ids={"ballotpedia": "Jane_Doe"},
        sources=[sample_source],
        created_at=now,
        updated_at=now,
    )
    assert doc.slug == "jane-doe"


def test_person_missing_required(now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Person(
            _id=oid,
            full_name="Jane Doe",
            created_at=now,
            updated_at=now,
        )


def test_office_tenure_valid(sample_source: SourceRef, oid: ObjectId) -> None:
    doc = OfficeTenure(
        _id=oid,
        office_id=ObjectId(),
        person_id=ObjectId(),
        start_date=date(2024, 1, 1),
        end_date=None,
        reason_ended=None,
        is_current=True,
        sources=[sample_source],
    )
    assert doc.is_current is True


def test_office_tenure_invalid_reason_ended(sample_source: SourceRef, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        OfficeTenure(
            _id=oid,
            office_id=ObjectId(),
            person_id=ObjectId(),
            start_date=date(2024, 1, 1),
            reason_ended="promoted",
            is_current=True,
            sources=[sample_source],
        )


def test_meeting_valid(
    sample_source: SourceRef,
    sample_location,
    now: datetime,
    oid: ObjectId,
) -> None:
    doc = Meeting(
        _id=oid,
        jurisdiction_id=ObjectId(),
        body_id=ObjectId(),
        scheduled_start=now,
        location=sample_location,
        meeting_type=MeetingType.REGULAR,
        status=MeetingStatus.SCHEDULED,
        external_id="granicus-123",
        sources=[sample_source],
    )
    assert doc.meeting_type == MeetingType.REGULAR


def test_meeting_invalid_status(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Meeting(
            _id=oid,
            jurisdiction_id=ObjectId(),
            body_id=ObjectId(),
            scheduled_start=now,
            meeting_type=MeetingType.REGULAR,
            status="postponed_forever",
            sources=[sample_source],
        )


def test_agenda_item_valid(sample_source: SourceRef, oid: ObjectId) -> None:
    doc = AgendaItem(
        _id=oid,
        meeting_id=ObjectId(),
        jurisdiction_id=ObjectId(),
        body_id=ObjectId(),
        item_number="G.2",
        section=AgendaSection.PUBLIC_HEARING,
        title="Costco gas station appeal",
        description="Appeal of use permit",
        sources=[sample_source],
    )
    assert doc.section == AgendaSection.PUBLIC_HEARING


def test_agenda_item_invalid_section(sample_source: SourceRef, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        AgendaItem(
            _id=oid,
            meeting_id=ObjectId(),
            jurisdiction_id=ObjectId(),
            body_id=ObjectId(),
            item_number="G.2",
            section="executive_session",
            title="Closed item",
            sources=[sample_source],
        )


def test_action_valid(
    sample_source: SourceRef,
    sample_vote_tally,
    oid: ObjectId,
) -> None:
    doc = Action(
        _id=oid,
        agenda_item_id=ObjectId(),
        meeting_id=ObjectId(),
        jurisdiction_id=ObjectId(),
        action_type=ActionType.RESOLUTION,
        description="Adopt resolution 2024-011",
        outcome=ActionOutcome.PASSED,
        vote_tally=sample_vote_tally,
        effective_date=date(2024, 3, 5),
        sources=[sample_source],
    )
    assert doc.outcome == ActionOutcome.PASSED


def test_action_invalid_action_type(sample_source: SourceRef, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Action(
            _id=oid,
            agenda_item_id=ObjectId(),
            meeting_id=ObjectId(),
            jurisdiction_id=ObjectId(),
            action_type="decree",
            description="Invalid action",
            outcome=ActionOutcome.PASSED,
            sources=[sample_source],
        )


def test_vote_record_valid(oid: ObjectId) -> None:
    doc = VoteRecord(
        _id=oid,
        action_id=ObjectId(),
        office_tenure_id=ObjectId(),
        person_id=ObjectId(),
        vote=Vote.AYE,
    )
    assert doc.vote == Vote.AYE


def test_vote_record_invalid_vote(oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        VoteRecord(
            _id=oid,
            action_id=ObjectId(),
            office_tenure_id=ObjectId(),
            person_id=ObjectId(),
            vote="maybe",
        )


def test_document_valid(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    doc = Document(
        _id=oid,
        jurisdiction_id=ObjectId(),
        related_type=RelatedType.MEETING,
        related_id=ObjectId(),
        doc_type=DocumentType.AGENDA,
        title="March 5, 2024 Agenda",
        url="https://novato.gov/agenda.pdf",
        retrieved_at=now,
        content_hash="abc123",
        mime_type="application/pdf",
        sources=[sample_source],
    )
    assert doc.doc_type == DocumentType.AGENDA


def test_document_invalid_doc_type(sample_source: SourceRef, now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Document(
            _id=oid,
            jurisdiction_id=ObjectId(),
            related_type=RelatedType.MEETING,
            related_id=ObjectId(),
            doc_type="newsletter",
            title="Bad doc",
            url="https://example.gov",
            retrieved_at=now,
            sources=[sample_source],
        )


def test_topic_valid(oid: ObjectId) -> None:
    doc = Topic(
        _id=oid,
        slug="housing",
        label="Housing",
        description="Land use and housing policy",
        embedding=[0.1, 0.2, 0.3],
        auto_generated=False,
    )
    assert doc.slug == "housing"


def test_topic_missing_required(oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        Topic(_id=oid, slug="housing")


def test_platform_adapter_valid(now: datetime, oid: ObjectId) -> None:
    doc = PlatformAdapter(
        _id=oid,
        vendor=PlatformVendor.GRANICUS,
        jurisdiction_id=ObjectId(),
        config={"base_url": "https://novato.granicus.com", "view_id": "2"},
        capabilities=["agendas", "minutes", "video"],
        detected_method=DetectedMethod.AUTO_FINGERPRINT,
        last_verified_at=now,
    )
    assert doc.vendor == PlatformVendor.GRANICUS


def test_platform_adapter_invalid_vendor(now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        PlatformAdapter(
            _id=oid,
            vendor="salesforce",
            jurisdiction_id=ObjectId(),
            detected_method=DetectedMethod.MANUAL,
        )


def test_ingestion_run_valid(sample_ingestion_stats, now: datetime, oid: ObjectId) -> None:
    doc = IngestionRun(
        _id=oid,
        jurisdiction_id=ObjectId(),
        adapter_vendor=PlatformVendor.GRANICUS,
        started_at=now,
        finished_at=now,
        status=IngestionRunStatus.SUCCESS,
        stats=sample_ingestion_stats,
        triggered_by=IngestionTriggeredBy.SCHEDULED,
    )
    assert doc.status == IngestionRunStatus.SUCCESS


def test_ingestion_run_invalid_triggered_by(now: datetime, oid: ObjectId) -> None:
    with pytest.raises(ValidationError):
        IngestionRun(
            _id=oid,
            jurisdiction_id=ObjectId(),
            adapter_vendor=PlatformVendor.GRANICUS,
            started_at=now,
            status=IngestionRunStatus.FAILED,
            triggered_by="cron_daemon",
        )

"""Enumerations for MASTER_PLAN §5 schema fields."""

from enum import StrEnum


class JurisdictionLevel(StrEnum):
    CITY = "city"
    TOWN = "town"
    COUNTY = "county"
    STATE = "state"
    FEDERAL = "federal"
    SPECIAL_DISTRICT = "special_district"
    SCHOOL_DISTRICT = "school_district"
    TRIBAL_NATION = "tribal_nation"
    JOINT_POWERS_AUTHORITY = "joint_powers_authority"


class GovernmentType(StrEnum):
    GENERAL_LAW = "general_law"
    CHARTER = "charter"
    HOME_RULE = "home_rule"


class JurisdictionStatus(StrEnum):
    ACTIVE = "active"
    PILOT = "pilot"
    PLANNED = "planned"
    STUB = "stub"


class GoverningBodyType(StrEnum):
    LEGISLATIVE = "legislative"
    EXECUTIVE = "executive"
    JUDICIAL = "judicial"
    ADVISORY = "advisory"
    COMMISSION = "commission"


class SelectionMethod(StrEnum):
    ELECTED_BY_DISTRICT = "elected_by_district"
    ELECTED_AT_LARGE = "elected_at_large"
    APPOINTED = "appointed"
    ANNUALLY_SELECTED_BY_BODY = "annually_selected_by_body"


class ReasonEnded(StrEnum):
    TERM_EXPIRED = "term_expired"
    RESIGNED = "resigned"
    RECALLED = "recalled"
    DIED = "died"
    REORGANIZATION = "reorganization"


class MeetingType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"
    STUDY_SESSION = "study_session"
    CLOSED_SESSION = "closed_session"
    REORGANIZATION = "reorganization"


class MeetingStatus(StrEnum):
    SCHEDULED = "scheduled"
    HELD = "held"
    CANCELLED = "cancelled"
    CONTINUED = "continued"


class AgendaSection(StrEnum):
    CONSENT_CALENDAR = "consent_calendar"
    GENERAL_BUSINESS = "general_business"
    PUBLIC_HEARING = "public_hearing"
    CEREMONIAL = "ceremonial"
    CLOSED_SESSION = "closed_session"


class ActionType(StrEnum):
    MOTION = "motion"
    RESOLUTION = "resolution"
    ORDINANCE = "ordinance"
    PROCLAMATION = "proclamation"
    APPOINTMENT = "appointment"
    MINUTE_ORDER = "minute_order"


class ActionOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    TABLED = "tabled"
    CONTINUED = "continued"
    WITHDRAWN = "withdrawn"


class Vote(StrEnum):
    AYE = "aye"
    NO = "no"
    ABSTAIN = "abstain"
    ABSENT = "absent"
    RECUSE = "recuse"


class DocumentType(StrEnum):
    AGENDA = "agenda"
    MINUTES = "minutes"
    STAFF_REPORT = "staff_report"
    RESOLUTION = "resolution"
    ORDINANCE = "ordinance"
    TRANSCRIPT = "transcript"
    VIDEO = "video"
    OTHER = "other"


class RelatedType(StrEnum):
    MEETING = "meeting"
    AGENDA_ITEM = "agenda_item"
    ACTION = "action"


class PlatformVendor(StrEnum):
    GRANICUS = "granicus"
    LEGISTAR = "legistar"
    CIVICCLERK = "civicclerk"
    CIVICPLUS = "civicplus"
    PRIMEGOV = "primegov"
    NOVUSAGENDA = "novusagenda"
    CUSTOM_HTML = "custom_html"


class SourceMethod(StrEnum):
    API = "api"
    SCRAPE = "scrape"
    PDF_PARSE = "pdf_parse"
    MANUAL = "manual"


class DetectedMethod(StrEnum):
    MANUAL = "manual"
    AUTO_FINGERPRINT = "auto_fingerprint"


class IngestionRunStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class IngestionTriggeredBy(StrEnum):
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    AGENT_TOOL = "agent_tool"


class EmbeddingSourceType(StrEnum):
    AGENDA_ITEM = "agenda_item"
    DOCUMENT = "document"
    MEETING_SUMMARY = "meeting_summary"

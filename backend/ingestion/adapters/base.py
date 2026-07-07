"""Platform adapter ABC (MASTER_PLAN §6)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class DetectionResult:
    vendor: str
    confidence: float
    notes: str | None = None


@dataclass(frozen=True)
class RawMeetingRef:
    """Vendor-native meeting pointer — fixture-backed for MVP offline tests."""

    clip_id: str
    view_id: int
    meeting_date: date
    base_url: str
    fixture_dir: Path | None = None
    agenda_filename: str = "agenda.pdf"
    minutes_filename: str = "minutes.pdf"
    body_name: str | None = None


@dataclass(frozen=True)
class RawMeetingDetail:
    ref: RawMeetingRef
    agenda_path: Path
    minutes_path: Path | None


@dataclass(frozen=True)
class RawMinutes:
    ref: RawMeetingRef
    minutes_path: Path


class PlatformAdapter(ABC):
    """Common interface for civic-platform ingestion adapters."""

    vendor: str

    @abstractmethod
    def detect(self, jurisdiction_website: str) -> DetectionResult | None: ...

    @abstractmethod
    def discover_meetings(
        self,
        jurisdiction_slug: str,
        since: date | None = None,
    ) -> list[RawMeetingRef]: ...

    @abstractmethod
    def fetch_meeting_detail(self, ref: RawMeetingRef) -> RawMeetingDetail: ...

    @abstractmethod
    def fetch_minutes(self, ref: RawMeetingRef) -> RawMinutes: ...

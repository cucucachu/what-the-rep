"""Fetch stage — load raw agenda/minutes from adapter."""

from __future__ import annotations

from ingestion.adapters.base import PlatformAdapter, RawMeetingDetail, RawMeetingRef, RawMinutes


def fetch_meeting_detail(adapter: PlatformAdapter, ref: RawMeetingRef) -> RawMeetingDetail:
    return adapter.fetch_meeting_detail(ref)


def fetch_minutes(adapter: PlatformAdapter, ref: RawMeetingRef) -> RawMinutes:
    return adapter.fetch_minutes(ref)

"""In-memory per-key sliding-window rate limiter (v1 single-instance).

When the deployment moves to multiple backend instances (Phase 7+), replace this
in-memory store with a shared store such as Redis so limits are consistent
across instances (MASTER_PLAN §9).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Deque


@dataclass(frozen=True)
class RateLimitWindow:
    max_requests: int
    window_seconds: float


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float | None = None
    window_seconds: float | None = None


class SlidingWindowRateLimiter:
    """Per-key sliding-window limiter with multiple independent windows."""

    def __init__(
        self,
        windows: list[RateLimitWindow],
        *,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        if not windows:
            raise ValueError("At least one rate-limit window is required")
        self._windows = windows
        self._time_fn = time_fn or time.monotonic
        self._events: dict[str, list[Deque[float]]] = defaultdict(
            lambda: [deque() for _ in windows]
        )
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> None:
        key_events = self._events[key]
        for window, events in zip(self._windows, key_events, strict=True):
            cutoff = now - window.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

    def check(self, key: str) -> RateLimitResult:
        """Return whether a request for *key* is allowed without recording it."""
        now = self._time_fn()
        with self._lock:
            self._prune(key, now)
            key_events = self._events[key]
            for window, events in zip(self._windows, key_events, strict=True):
                if len(events) >= window.max_requests:
                    retry_after = window.window_seconds - (now - events[0])
                    return RateLimitResult(
                        allowed=False,
                        retry_after_seconds=max(0.0, retry_after),
                        window_seconds=window.window_seconds,
                    )
        return RateLimitResult(allowed=True)

    def acquire(self, key: str) -> RateLimitResult:
        """Check and, if allowed, record one request for *key*."""
        now = self._time_fn()
        with self._lock:
            self._prune(key, now)
            key_events = self._events[key]
            for window, events in zip(self._windows, key_events, strict=True):
                if len(events) >= window.max_requests:
                    retry_after = window.window_seconds - (now - events[0])
                    return RateLimitResult(
                        allowed=False,
                        retry_after_seconds=max(0.0, retry_after),
                        window_seconds=window.window_seconds,
                    )
            for events in key_events:
                events.append(now)
        return RateLimitResult(allowed=True)

    def reset(self, key: str | None = None) -> None:
        """Clear recorded events for one key or all keys (testing helper)."""
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)

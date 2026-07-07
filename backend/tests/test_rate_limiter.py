"""Unit tests for the sliding-window rate limiter."""

from __future__ import annotations

import pytest

from mcp_server.middleware.rate_limiter import RateLimitWindow, SlidingWindowRateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def limiter(clock: FakeClock) -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(
        windows=[RateLimitWindow(max_requests=3, window_seconds=60.0)],
        time_fn=clock,
    )


def test_allows_requests_under_limit(limiter: SlidingWindowRateLimiter) -> None:
    for _ in range(3):
        assert limiter.acquire("10.0.0.1").allowed is True


def test_rejects_requests_over_limit(limiter: SlidingWindowRateLimiter) -> None:
    for _ in range(3):
        limiter.acquire("10.0.0.1")

    result = limiter.acquire("10.0.0.1")
    assert result.allowed is False
    assert result.retry_after_seconds is not None
    assert result.retry_after_seconds > 0


def test_resets_after_window_elapses(limiter: SlidingWindowRateLimiter, clock: FakeClock) -> None:
    for _ in range(3):
        limiter.acquire("10.0.0.1")
    assert limiter.acquire("10.0.0.1").allowed is False

    clock.advance(60.0)
    assert limiter.acquire("10.0.0.1").allowed is True


def test_isolates_limits_per_key(limiter: SlidingWindowRateLimiter) -> None:
    for _ in range(3):
        limiter.acquire("10.0.0.1")

    assert limiter.acquire("10.0.0.1").allowed is False
    assert limiter.acquire("10.0.0.2").allowed is True


def test_short_window_resets_while_long_window_still_counts(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(
        windows=[
            RateLimitWindow(max_requests=2, window_seconds=10.0),
            RateLimitWindow(max_requests=5, window_seconds=100.0),
        ],
        time_fn=clock,
    )

    for _ in range(2):
        assert limiter.acquire("client-a").allowed is True
    assert limiter.acquire("client-a").allowed is False

    clock.advance(10.0)
    assert limiter.acquire("client-a").allowed is True

    for _ in range(4):
        limiter.acquire("client-a")
    assert limiter.acquire("client-a").allowed is False

    clock.advance(100.0)
    assert limiter.acquire("client-a").allowed is True

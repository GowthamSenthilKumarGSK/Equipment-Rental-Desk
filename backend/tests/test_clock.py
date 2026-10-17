from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.clock import FixedClock, SystemClock

IST = timezone(timedelta(hours=5, minutes=30))


def test_fixed_clock_does_not_move_until_advanced():
    clock = FixedClock(datetime(2026, 10, 12, 10, 0, tzinfo=UTC))

    assert clock.now() == clock.now() == datetime(2026, 10, 12, 10, 0, tzinfo=UTC)

    clock.advance(timedelta(hours=48))

    assert clock.now() == datetime(2026, 10, 14, 10, 0, tzinfo=UTC)


def test_fixed_clock_normalises_to_utc():
    clock = FixedClock(datetime(2026, 10, 12, 15, 30, tzinfo=IST))

    assert clock.now() == datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    assert clock.now().tzinfo is UTC


def test_fixed_clock_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 10, 12, 10, 0))


def test_system_clock_returns_aware_utc():
    assert SystemClock().now().tzinfo is UTC

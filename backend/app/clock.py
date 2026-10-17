"""Injectable clock so time-based rules can be tested without waiting."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Protocol

# India has no daylight saving, so a fixed offset is exact (and needs no timezone database).
IST = timezone(timedelta(hours=5, minutes=30), "IST")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock that only moves when told to. The reviewer test clock (M3) builds on this."""

    def __init__(self, start: datetime):
        if start.tzinfo is None:
            raise ValueError("FixedClock needs a timezone-aware datetime")
        self._now = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta

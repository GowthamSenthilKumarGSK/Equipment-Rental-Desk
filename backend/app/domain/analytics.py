"""Pure reporting rules for the analytics dashboard: windows, IST buckets, ratios and overdue aging.

Nothing here touches a database or a clock; callers pass `now` in. All timestamps are
timezone-aware UTC instants, and every reporting day is an Asia/Kolkata (IST) calendar day. Money is
integer paise.

Reporting window. A report covers the last `days` IST calendar days **including today**: it starts
at IST midnight `days - 1` days ago and ends (exclusive) at the next IST midnight. It is compared
with the `days` days immediately before it. Today is still going on, so the current period is only
"so far": the comparison counts the previous period up to the same elapsed time
(`comparison_period`) rather than all of it, and callers ignore events after `now`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from app.clock import IST
from app.domain.policy import BLOCKING_OVERDUE

MAX_REPORT_DAYS = 366
DEFAULT_REPORT_DAYS = 30

# A loan more than this many (rounded-up) days overdue blocks its member: same number as the policy.
BLOCKING_DAYS = BLOCKING_OVERDUE.days


class Bucket(StrEnum):
    DAY = "day"
    WEEK = "week"  # Monday to Sunday, IST


@dataclass(frozen=True)
class Period:
    """A half-open range of UTC instants: `start` is included, `end` is not."""

    start: datetime
    end: datetime

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end

    @property
    def first_day(self) -> date:
        """The first IST calendar day of the period."""
        return ist_date(self.start)

    @property
    def last_day(self) -> date:
        """The last IST calendar day of the period (inclusive)."""
        return ist_date(self.end - timedelta(microseconds=1))


def _require_aware(moment: datetime, name: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def ist_date(moment: datetime) -> date:
    """The IST calendar date on which this instant falls."""
    _require_aware(moment, "moment")
    return moment.astimezone(IST).date()


def ist_midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=IST)


def reporting_periods(now: datetime, days: int) -> tuple[Period, Period]:
    """The current period (the last `days` IST days including today) and the one before it.

    Both are half-open and exactly `days` IST days long, so a moment at IST midnight belongs to the
    day that starts there. `days` must be a whole number from 1 to MAX_REPORT_DAYS.
    """
    _require_aware(now, "now")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_REPORT_DAYS:
        raise ValueError(f"days must be a whole number from 1 to {MAX_REPORT_DAYS}")
    today = ist_date(now)
    first_day = today - timedelta(days=days - 1)
    start = ist_midnight(first_day)
    end = ist_midnight(today + timedelta(days=1))
    previous_start = ist_midnight(first_day - timedelta(days=days))
    return (
        Period(start=start, end=end),
        Period(start=previous_start, end=start),
    )


def comparison_period(current: Period, previous: Period, now: datetime) -> Period:
    """The part of `previous` that matches how much of `current` has happened by `now`.

    The current period ends at the next IST midnight, so at 15:30 it is missing the rest of today.
    Counting all of `previous` against that would make every figure look like a drop. This returns
    `previous` cut after the same elapsed time, `now` itself included (`current` counts events up
    to and including `now`, so the comparison does too). Its last instant is exactly
    `now - days`, because the two periods are `days` IST days apart.
    """
    _require_aware(now, "now")
    if not current.contains(now):
        raise ValueError("now must fall inside the current period")
    elapsed = now - current.start
    return Period(start=previous.start, end=previous.start + elapsed + timedelta(microseconds=1))


def overlap(start: datetime, end: datetime, period: Period) -> timedelta:
    """How much of [start, end) lies inside the period (zero if they do not meet).

    Used to count the time something was in use during a report window, e.g. a loan that began
    before the window and is still open (pass `now` as `end`).
    """
    _require_aware(start, "start")
    _require_aware(end, "end")
    if end < start:
        raise ValueError("end must not be before start")
    clipped_start = max(start, period.start)
    clipped_end = min(end, period.end)
    return max(clipped_end - clipped_start, timedelta(0))


def bucket_start(day: date, bucket: Bucket) -> date:
    """The first day of the bucket that contains `day` (weeks begin on Monday)."""
    if bucket is Bucket.WEEK:
        return day - timedelta(days=day.weekday())
    return day


def bucket_starts(period: Period, bucket: Bucket) -> list[date]:
    """Every bucket start from the one holding the period's first day to the one holding its last.

    With weekly buckets the first and last bucket can reach beyond the period; only events inside
    the period are counted in them.
    """
    step = timedelta(days=7 if bucket is Bucket.WEEK else 1)
    current = bucket_start(period.first_day, bucket)
    last = bucket_start(period.last_day, bucket)
    starts = []
    while current <= last:
        starts.append(current)
        current += step
    return starts


@dataclass(frozen=True)
class BucketTotal:
    """One bucket's totals and which of its days the report really covers.

    `covered_from`/`covered_to` are the first and last IST day of the bucket that lie inside the
    period. `partial` is true when the bucket is not a whole day or week of finished days: a weekly
    bucket cut off by the start of the period, or the last bucket, which holds today.
    """

    start: date
    total: int
    count: int
    covered_from: date
    covered_to: date
    partial: bool


def bucketize(
    entries: Iterable[tuple[datetime, int]], period: Period, bucket: Bucket
) -> list[BucketTotal]:
    """Sum (instant, amount) entries into IST buckets; empty buckets are present with zeros.

    Entries outside the period are ignored. Amounts are integers (paise). The period's last day
    is today (see `reporting_periods`), which is not over yet, so the bucket holding it is partial.
    """
    totals = {start: [0, 0] for start in bucket_starts(period, bucket)}
    for moment, amount in entries:
        if not period.contains(moment):
            continue
        slot = totals[bucket_start(ist_date(moment), bucket)]
        slot[0] += amount
        slot[1] += 1
    length = timedelta(days=6 if bucket is Bucket.WEEK else 0)
    slots = []
    for start, (total, count) in totals.items():
        last = start + length
        covered_from = max(start, period.first_day)
        slots.append(
            BucketTotal(
                start=start,
                total=total,
                count=count,
                covered_from=covered_from,
                covered_to=min(last, period.last_day),
                partial=covered_from != start or last >= period.last_day,
            )
        )
    return slots


def _half_up_tenths(numerator: int, denominator: int) -> int:
    """numerator / denominator, in tenths, rounded half up, using integers only."""
    return (numerator * 20 + denominator) // (2 * denominator)


def ratio_pct(numerator: int, denominator: int) -> float | None:
    """numerator / denominator as a percentage, one decimal, half up; None without a denominator."""
    if denominator == 0:
        return None
    return _half_up_tenths(numerator * 100, denominator) / 10


def change_pct(current: int, previous: int) -> float | None:
    """How much `current` differs from `previous`, in percent, one decimal; None if previous is 0.

    A fall gives a negative number. Rounding is half away from zero.
    """
    if previous == 0:
        return None
    difference = current - previous
    tenths = _half_up_tenths(abs(difference) * 100, abs(previous))
    return (tenths if difference >= 0 else -tenths) / 10


def average_1dp(total: int, count: int) -> float | None:
    """total / count with one decimal (half up); None for an empty set."""
    if count == 0:
        return None
    return _half_up_tenths(total, count) / 10


def average_paise(total_paise: int, count: int) -> int | None:
    """A mean amount in whole paise (half up); None for an empty set."""
    if count == 0:
        return None
    return (total_paise * 2 + count) // (2 * count)


@dataclass(frozen=True)
class AgingBand:
    label: str
    min_days: int
    max_days: int | None  # None = no upper limit


AGING_BANDS: tuple[AgingBand, ...] = (
    AgingBand("1–3 days", 1, 3),
    AgingBand("4–7 days", 4, 7),
    AgingBand(f"8–{BLOCKING_DAYS} days", 8, BLOCKING_DAYS),
    # More than BLOCKING_DAYS days overdue is what blocks a member from reserving and checking out.
    AgingBand(f"{BLOCKING_DAYS + 1}+ days", BLOCKING_DAYS + 1, None),
)


def aging_band_index(days_overdue: int) -> int:
    """Which band a loan belongs to. `days_overdue` is the rounded-up late days (at least 1)."""
    if days_overdue < 1:
        raise ValueError("a loan in the aging report is at least one day overdue")
    for index, band in enumerate(AGING_BANDS):
        if band.max_days is None or days_overdue <= band.max_days:
            return index
    raise AssertionError("the last band has no upper limit")  # pragma: no cover


def blocks_member(days_overdue: int) -> bool:
    """True if a loan this late blocks its member (overdue by more than 14 days)."""
    return days_overdue > BLOCKING_DAYS

"""Pure rules for the utilization and demand reports.

Utilization is time, not counts: for a stretch of the report, the checked-out item-days divided by
the item-days the whole fleet could have been out. Only time that has actually passed counts, so the
measured stretch of the current period runs from its first IST midnight up to `now`, and the
previous period is measured over the same length (`observed_periods`) so the two are comparable.

An item is "checked out" from `checked_out_at` until `returned_at` (or `now`, while it is still
out), overdue time included. Time spent reserved is not utilization: the item is on the shelf.

The fleet is the items that exist now, for the whole measured stretch: the database keeps no history
of when items were added and, above all, none of when they were under maintenance (only the
current `items.status`). Nothing here invents those intervals.
"""

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from app.domain.analytics import (
    Bucket,
    Period,
    bucket_starts,
    ist_midnight,
    overlap,
)
from app.domain.rules import is_reservation_expired

MICROSECOND = timedelta(microseconds=1)
_ONE_DAY = timedelta(days=1)


def observed_periods(current: Period, previous: Period, now: datetime) -> tuple[Period, Period]:
    """The stretches of time actually lived through: the current period up to `now`, and the same
    length from the start of the previous period.

    Utilization is time-weighted, so unlike the counts it compares exact lengths of time:
    `[current.start, now)` against `[previous.start, previous.start + (now - current.start))`.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if not current.contains(now):
        raise ValueError("now must fall inside the current period")
    elapsed = now - current.start
    return Period(current.start, now), Period(previous.start, previous.start + elapsed)


def duration_microseconds(span: timedelta) -> int:
    """A length of time as a whole number of microseconds, for exact integer ratios."""
    return span // MICROSECOND


def busy_time(intervals: Iterable[tuple[datetime, datetime]], period: Period) -> timedelta:
    """Total time the (start, end) intervals spend inside the period. Intervals may cross the
    period's edges (that is what `overlap` clips); the loans of one item never overlap."""
    total = timedelta(0)
    for start, end in intervals:
        total += overlap(start, end, period)
    return total


def item_days(span: timedelta) -> float:
    """A length of time in days with two decimals, rounded half up with integer arithmetic."""
    micro_per_day = duration_microseconds(_ONE_DAY)
    return ((duration_microseconds(span) * 200 + micro_per_day) // (2 * micro_per_day)) / 100


def change_in_points(current: float | None, previous: float | None) -> float | None:
    """The difference of two one-decimal percentages, in percentage points (none if either is)."""
    if current is None or previous is None:
        return None
    return (round(current * 10) - round(previous * 10)) / 10


@dataclass(frozen=True)
class BucketWindow:
    """One bucket of the utilization series: which days it covers, whether it is cut short, and the
    stretch of time that was actually measured in it (never past `now`)."""

    start: date
    covered_from: date
    covered_to: date
    partial: bool
    period: Period


def bucket_windows(current: Period, observed: Period, bucket: Bucket) -> list[BucketWindow]:
    """Cut the measured stretch into IST day or Monday-to-Sunday week buckets.

    The buckets are the same as the payments series (`bucket_starts`) and are contiguous. A
    bucket's measured time is its IST days clipped to the start of the report and to `now`, so the
    first weekly bucket may be shorter and the last bucket holds today so far; both are `partial`.
    """
    length = timedelta(days=6 if bucket is Bucket.WEEK else 0)
    windows = []
    for start in bucket_starts(current, bucket):
        last = start + length
        begins = max(ist_midnight(start), observed.start)
        ends = min(ist_midnight(last + timedelta(days=1)), observed.end)
        covered_from = max(start, current.first_day)
        windows.append(
            BucketWindow(
                start=start,
                covered_from=covered_from,
                covered_to=min(last, current.last_day),
                partial=covered_from != start or last >= current.last_day,
                period=Period(begins, max(begins, ends)),
            )
        )
    return windows


def busy_by_window(
    intervals: Iterable[tuple[datetime, datetime]], windows: Sequence[Period]
) -> list[timedelta]:
    """Time the intervals spend inside each of several contiguous, ordered windows.

    Each interval is only compared with the windows it reaches, so the cost grows with the number
    of intervals plus the windows they cross, not with intervals times windows.
    """
    totals = [timedelta(0)] * len(windows)
    starts = [window.start for window in windows]
    for start, end in intervals:
        index = max(bisect_right(starts, start) - 1, 0)
        while index < len(windows) and windows[index].start < end:
            totals[index] += overlap(start, end, windows[index])
            index += 1
    return totals


class Outcome(StrEnum):
    """What became of a reservation, as of `now`."""

    CONVERTED = "converted"  # the item was handed over
    CANCELLED = "cancelled"
    EXPIRED = "expired"  # the 48-hour hold ran out
    HELD = "held"  # still waiting, hold not run out


def reservation_outcome(
    *,
    reserved_at: datetime,
    checked_out_at: datetime | None,
    cancelled_at: datetime | None,
    now: datetime,
) -> Outcome:
    """The reservation's outcome judged at `now`, from its own timestamps.

    Only what had happened by `now` counts, like every other figure of the report. A hold that has
    run out is EXPIRED whether or not a write has saved that yet (the same rule as
    `effective_loan_status`, so it is judged from `reserved_at`, not from the stored status).
    A reservation cancelled because its item went into maintenance looks like any other
    cancellation: the database does not record why.
    """
    if checked_out_at is not None and checked_out_at <= now:
        return Outcome.CONVERTED
    if cancelled_at is not None and cancelled_at <= now:
        return Outcome.CANCELLED
    if is_reservation_expired(reserved_at, now):
        return Outcome.EXPIRED
    return Outcome.HELD

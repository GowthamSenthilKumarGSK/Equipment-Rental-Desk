"""Utilization time arithmetic, bucket windows and reservation outcomes."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.analytics import Bucket, Period, reporting_periods
from app.domain.utilization import (
    Outcome,
    bucket_windows,
    busy_by_window,
    busy_time,
    change_in_points,
    duration_microseconds,
    item_days,
    observed_periods,
    reservation_outcome,
)

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
MICRO = timedelta(microseconds=1)
# 12 Oct 2026 10:00 UTC is 15:30 IST on Monday 12 Oct.
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)


def utc(*parts) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def measured(now: datetime, days: int) -> tuple[Period, Period, Period]:
    current, previous = reporting_periods(now, days)
    return current, *observed_periods(current, previous, now)


# --- the measured stretch of time --------------------------------------------------------------


def test_the_measured_time_is_the_current_period_so_far_and_the_same_length_before():
    current, now_part, before_part = measured(NOW, 7)

    assert now_part.start == current.start and now_part.end == NOW
    assert now_part.end - now_part.start == timedelta(days=6, hours=15, minutes=30)
    assert before_part.end - before_part.start == now_part.end - now_part.start
    assert before_part.start == current.start - 7 * DAY


@pytest.mark.parametrize("days", [1, 7, 30, 366])
def test_both_stretches_have_the_same_length_for_any_period(days):
    _, now_part, before_part = measured(NOW, days)

    assert now_part.end - now_part.start == before_part.end - before_part.start


def test_at_ist_midnight_nothing_has_been_measured_yet():
    midnight = utc(2026, 10, 12, 18, 30)

    _, now_part, before_part = measured(midnight, 1)

    assert now_part.end == now_part.start == midnight
    assert before_part.end == before_part.start


def test_a_microsecond_before_ist_midnight_almost_the_whole_day_is_measured():
    last = utc(2026, 10, 12, 18, 29, 59, 999999)

    _, now_part, _ = measured(last, 1)

    assert now_part.end - now_part.start == DAY - MICRO


def test_observed_periods_need_an_aware_moment_inside_the_current_period():
    current, previous = reporting_periods(NOW, 7)

    with pytest.raises(ValueError):
        observed_periods(current, previous, datetime(2026, 10, 12, 10))
    for outside in (current.start - MICRO, current.end):
        with pytest.raises(ValueError):
            observed_periods(current, previous, outside)


def test_a_loan_starting_at_previous_through_adds_nothing_but_one_microsecond_earlier_does():
    _, _, before = measured(NOW, 7)
    edge = before.end

    assert edge == NOW - 7 * DAY
    assert busy_time([(edge, edge + 10 * HOUR)], before) == timedelta(0)
    assert busy_time([(edge - MICRO, edge + 10 * HOUR)], before) == MICRO
    assert busy_time([(edge - 8 * HOUR, edge)], before) == 8 * HOUR  # ending there counts fully


# --- time spent inside a period ----------------------------------------------------------------

WINDOW = Period(utc(2026, 10, 10), utc(2026, 10, 12))


@pytest.mark.parametrize(
    ("intervals", "expected_hours"),
    [
        ([], 0),
        ([(utc(2026, 10, 10, 6), utc(2026, 10, 10, 18))], 12),  # inside
        ([(utc(2026, 10, 9), utc(2026, 10, 10, 6))], 6),  # starts before
        ([(utc(2026, 10, 11, 12), utc(2026, 10, 13))], 12),  # ends after
        ([(utc(2026, 10, 1), utc(2026, 10, 30))], 48),  # covers the whole period
        ([(utc(2026, 10, 9), utc(2026, 10, 10))], 0),  # ends exactly where it starts
        ([(utc(2026, 10, 12), utc(2026, 10, 13))], 0),  # starts exactly where it ends
        ([(utc(2026, 10, 10, 6), utc(2026, 10, 10, 6))], 0),  # no length
        (
            [(utc(2026, 10, 10), utc(2026, 10, 10, 6)), (utc(2026, 10, 11), utc(2026, 10, 11, 6))],
            12,
        ),
    ],
)
def test_busy_time_counts_only_the_part_inside_the_period(intervals, expected_hours):
    assert busy_time(intervals, WINDOW) == expected_hours * HOUR


def test_busy_time_keeps_sub_second_precision():
    interval = (utc(2026, 10, 9, 23, 59, 59, 500000), utc(2026, 10, 10, 0, 0, 0, 250000))

    assert busy_time([interval], WINDOW) == timedelta(microseconds=250000)


# --- days with two decimals --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("span", "expected"),
    [
        (timedelta(0), 0.0),
        (DAY, 1.0),
        (36 * HOUR, 1.5),
        (timedelta(seconds=1), 0.0),
        (timedelta(seconds=431), 0.0),
        (timedelta(seconds=432), 0.01),  # 0.005 of a day rounds up
        (timedelta(hours=15, minutes=30), 0.65),  # 0.64583...
        (timedelta(days=366, hours=12), 366.5),
    ],
)
def test_item_days_have_two_decimals_rounded_half_up(span, expected):
    assert item_days(span) == expected


def test_durations_become_exact_integers():
    assert duration_microseconds(timedelta(seconds=1, microseconds=5)) == 1_000_005
    assert type(duration_microseconds(DAY)) is int


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (41.1, 34.7, 6.4),
        (10.0, 10.0, 0.0),
        (0.0, 12.5, -12.5),
        (None, 5.0, None),
        (5.0, None, None),
    ],
)
def test_change_in_points_is_exact_to_one_decimal(current, previous, expected):
    assert change_in_points(current, previous) == expected


# --- buckets -----------------------------------------------------------------------------------


def test_daily_windows_split_the_measured_time_at_ist_midnight():
    current, now_part, _ = measured(NOW, 3)  # 10, 11, 12 Oct IST

    windows = bucket_windows(current, now_part, Bucket.DAY)

    assert [w.start for w in windows] == [
        date(2026, 10, 10),
        date(2026, 10, 11),
        date(2026, 10, 12),
    ]
    assert [w.period.end - w.period.start for w in windows] == [
        DAY,
        DAY,
        timedelta(hours=15, minutes=30),  # today so far
    ]
    assert [w.partial for w in windows] == [False, False, True]


def test_the_windows_are_contiguous_and_add_up_to_the_measured_time():
    for bucket in Bucket:
        current, now_part, _ = measured(NOW, 10)

        windows = bucket_windows(current, now_part, bucket)

        assert windows[0].period.start == now_part.start
        assert windows[-1].period.end == now_part.end
        for earlier, later in zip(windows, windows[1:], strict=False):
            assert earlier.period.end == later.period.start
        assert sum((w.period.end - w.period.start for w in windows), timedelta(0)) == (
            now_part.end - now_part.start
        )


def test_weekly_windows_are_cut_by_the_period_start_and_by_now():
    current, now_part, _ = measured(NOW, 10)  # Sat 3 Oct .. Mon 12 Oct

    windows = bucket_windows(current, now_part, Bucket.WEEK)

    assert [
        (w.start, w.covered_from, w.covered_to, w.partial, w.period.end - w.period.start)
        for w in windows
    ] == [
        (date(2026, 9, 28), date(2026, 10, 3), date(2026, 10, 4), True, 2 * DAY),
        (date(2026, 10, 5), date(2026, 10, 5), date(2026, 10, 11), False, 7 * DAY),
        (date(2026, 10, 12), date(2026, 10, 12), date(2026, 10, 12), True, timedelta(hours=15.5)),
    ]


def test_at_ist_midnight_the_new_day_bucket_exists_but_has_no_measured_time():
    midnight = utc(2026, 10, 12, 18, 30)
    current, now_part, _ = measured(midnight, 2)  # 12 and 13 Oct IST

    windows = bucket_windows(current, now_part, Bucket.DAY)

    assert [w.start for w in windows] == [date(2026, 10, 12), date(2026, 10, 13)]
    assert windows[-1].period.end == windows[-1].period.start
    assert windows[-1].partial


def test_busy_by_window_splits_an_interval_at_the_window_edges():
    current, now_part, _ = measured(NOW, 3)
    windows = [w.period for w in bucket_windows(current, now_part, Bucket.DAY)]
    across_midnight = (utc(2026, 10, 11, 18), utc(2026, 10, 11, 19))  # 23:30 .. 00:30 IST

    assert busy_by_window([across_midnight], windows) == [
        timedelta(0),
        timedelta(minutes=30),
        timedelta(minutes=30),
    ]


def test_busy_by_window_adds_up_to_the_busy_time_of_the_whole_period():
    current, now_part, _ = measured(NOW, 10)
    windows = [w.period for w in bucket_windows(current, now_part, Bucket.WEEK)]
    intervals = [
        (utc(2026, 9, 1), utc(2026, 10, 4, 5)),  # starts long before, ends inside the first week
        (utc(2026, 10, 6), utc(2026, 10, 8, 3)),
        (utc(2026, 10, 11, 20), NOW + 5 * DAY),  # reaches past now
        (utc(2026, 10, 20), utc(2026, 10, 21)),  # entirely in the future
    ]

    per_window = busy_by_window(intervals, windows)

    assert sum(per_window, timedelta(0)) == busy_time(intervals, now_part)


# --- what became of a reservation --------------------------------------------------------------

RESERVED = NOW - 10 * HOUR


def outcome(*, checked_out=None, cancelled=None, now=NOW, reserved=RESERVED):
    return reservation_outcome(
        reserved_at=reserved, checked_out_at=checked_out, cancelled_at=cancelled, now=now
    )


def test_a_reservation_that_was_handed_over_is_converted_whatever_else_is_true():
    assert outcome(checked_out=RESERVED + HOUR) is Outcome.CONVERTED
    # Even if the 48 hours have long run out by now, the item was handed over in time.
    assert outcome(checked_out=RESERVED + HOUR, now=NOW + 100 * DAY) is Outcome.CONVERTED


def test_only_what_has_happened_by_now_counts():
    assert outcome(checked_out=NOW) is Outcome.CONVERTED  # at now counts
    assert outcome(checked_out=NOW + MICRO) is Outcome.HELD  # a moment later does not
    assert outcome(cancelled=NOW) is Outcome.CANCELLED
    assert outcome(cancelled=NOW + MICRO) is Outcome.HELD


def test_a_hold_expires_at_exactly_48_hours():
    reserved = NOW - timedelta(hours=48)

    assert outcome(reserved=reserved + MICRO) is Outcome.HELD
    assert outcome(reserved=reserved) is Outcome.EXPIRED
    assert outcome(reserved=reserved - MICRO) is Outcome.EXPIRED


def test_a_cancellation_before_the_hold_ran_out_is_a_cancellation_not_an_expiry():
    assert outcome(cancelled=RESERVED + HOUR, now=NOW + 100 * DAY) is Outcome.CANCELLED


def test_an_unsettled_young_reservation_is_held():
    assert outcome() is Outcome.HELD


def test_a_naive_moment_is_rejected():
    with pytest.raises(ValueError):
        reservation_outcome(
            reserved_at=datetime(2026, 10, 12), checked_out_at=None, cancelled_at=None, now=NOW
        )

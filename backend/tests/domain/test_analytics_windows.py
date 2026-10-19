"""Reporting windows: the last N IST calendar days including today, and the N days before them."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.analytics import (
    MAX_REPORT_DAYS,
    Period,
    comparison_period,
    ist_date,
    overlap,
    reporting_periods,
)

# 12 Oct 2026 10:00 UTC is 15:30 IST on Monday 12 Oct.
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
MICRO = timedelta(microseconds=1)


def utc(*parts) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def test_a_seven_day_window_starts_at_ist_midnight_six_days_ago_and_ends_at_the_next_ist_midnight():
    current, previous = reporting_periods(NOW, 7)

    assert current.start == utc(2026, 10, 5, 18, 30)  # 6 Oct 00:00 IST
    assert current.end == utc(2026, 10, 12, 18, 30)  # 13 Oct 00:00 IST
    assert (current.first_day, current.last_day) == (date(2026, 10, 6), date(2026, 10, 12))
    assert previous.start == utc(2026, 9, 28, 18, 30)  # 29 Sep 00:00 IST
    assert previous.end == current.start
    assert (previous.first_day, previous.last_day) == (date(2026, 9, 29), date(2026, 10, 5))


def test_a_one_day_window_is_today_in_india():
    current, previous = reporting_periods(NOW, 1)

    assert (current.start, current.end) == (utc(2026, 10, 11, 18, 30), utc(2026, 10, 12, 18, 30))
    assert current.first_day == current.last_day == date(2026, 10, 12)
    assert (previous.first_day, previous.last_day) == (date(2026, 10, 11), date(2026, 10, 11))


def test_the_day_changes_exactly_at_ist_midnight_not_at_utc_midnight():
    just_before = utc(2026, 10, 12, 18, 29, 59, 999999)  # 23:59:59.999999 IST on 12 Oct
    at_midnight = utc(2026, 10, 12, 18, 30)  # 00:00 IST on 13 Oct

    assert reporting_periods(just_before, 1)[0].last_day == date(2026, 10, 12)
    assert reporting_periods(at_midnight, 1)[0].last_day == date(2026, 10, 13)
    # UTC midnight is 05:30 IST, the middle of an Indian morning: nothing changes there.
    assert reporting_periods(utc(2026, 10, 12, 0, 0), 1)[0].last_day == date(2026, 10, 12)
    assert reporting_periods(utc(2026, 10, 11, 23, 59, 59), 1)[0].last_day == date(2026, 10, 12)


def test_a_moment_is_in_a_period_from_its_first_instant_until_its_last_but_not_the_end():
    current, previous = reporting_periods(NOW, 7)

    assert current.contains(current.start)
    assert not current.contains(current.start - MICRO)
    assert current.contains(current.end - MICRO)
    assert not current.contains(current.end)
    # The two periods never overlap and leave no gap.
    assert previous.contains(current.start - MICRO)
    assert not previous.contains(current.start)


@pytest.mark.parametrize("days", [1, 2, 7, 30, 90, 365, MAX_REPORT_DAYS])
def test_both_periods_are_exactly_n_days_long_and_adjacent(days):
    current, previous = reporting_periods(NOW, days)

    assert current.end - current.start == timedelta(days=days)
    assert previous.end - previous.start == timedelta(days=days)
    assert previous.end == current.start
    assert current.last_day == date(2026, 10, 12)
    assert (current.last_day - current.first_day).days == days - 1


@pytest.mark.parametrize("days", [0, -1, MAX_REPORT_DAYS + 1, 7.0, "7", None, True])
def test_days_must_be_a_whole_number_from_1_to_366(days):
    with pytest.raises(ValueError):
        reporting_periods(NOW, days)


def test_a_naive_moment_is_a_bug_not_a_guess():
    with pytest.raises(ValueError):
        reporting_periods(datetime(2026, 10, 12, 10, 0), 7)
    with pytest.raises(ValueError):
        ist_date(datetime(2026, 10, 12, 10, 0))


def test_ist_date_follows_the_indian_calendar():
    assert ist_date(utc(2026, 10, 12, 18, 29, 59, 999999)) == date(2026, 10, 12)
    assert ist_date(utc(2026, 10, 12, 18, 30)) == date(2026, 10, 13)
    assert ist_date(utc(2026, 1, 1, 0, 0)) == date(2026, 1, 1)


# --- clipping an interval to a window ----------------------------------------------------------

WINDOW = Period(start=utc(2026, 10, 10), end=utc(2026, 10, 20))


@pytest.mark.parametrize(
    ("start", "end", "expected_days"),
    [
        (utc(2026, 10, 12), utc(2026, 10, 15), 3),  # inside
        (utc(2026, 10, 1), utc(2026, 10, 5), 0),  # before
        (utc(2026, 10, 25), utc(2026, 10, 30), 0),  # after
        (utc(2026, 10, 5), utc(2026, 10, 12), 2),  # starts before, ends inside
        (utc(2026, 10, 18), utc(2026, 10, 30), 2),  # starts inside, ends after
        (utc(2026, 10, 1), utc(2026, 10, 30), 10),  # covers the whole window
        (utc(2026, 10, 5), utc(2026, 10, 10), 0),  # ends exactly where the window starts
        (utc(2026, 10, 20), utc(2026, 10, 25), 0),  # starts exactly where the window ends
        (utc(2026, 10, 12), utc(2026, 10, 12), 0),  # no length
    ],
)
def test_overlap_counts_only_the_part_inside_the_window(start, end, expected_days):
    assert overlap(start, end, WINDOW) == timedelta(days=expected_days)


def test_overlap_keeps_sub_day_precision():
    assert overlap(utc(2026, 10, 9, 23), utc(2026, 10, 10, 1, 30), WINDOW) == timedelta(
        hours=1, minutes=30
    )


def test_overlap_rejects_an_interval_that_ends_before_it_starts_and_naive_moments():
    with pytest.raises(ValueError):
        overlap(utc(2026, 10, 15), utc(2026, 10, 14), WINDOW)
    with pytest.raises(ValueError):
        overlap(datetime(2026, 10, 12), utc(2026, 10, 14), WINDOW)


# --- comparing like with like ------------------------------------------------------------------


def compared(now: datetime, days: int) -> Period:
    current, previous = reporting_periods(now, days)
    return comparison_period(current, previous, now)


@pytest.mark.parametrize("days", [1, 2, 7, 30, 366])
def test_the_comparison_ends_exactly_days_before_now_and_includes_that_instant(days):
    period = compared(NOW, days)

    assert period.contains(NOW - timedelta(days=days))
    assert not period.contains(NOW - timedelta(days=days) + MICRO)
    assert period.end - MICRO == NOW - timedelta(days=days)


def test_the_comparison_starts_with_the_previous_period_and_never_outgrows_it():
    current, previous = reporting_periods(NOW, 7)
    period = comparison_period(current, previous, NOW)

    assert period.start == previous.start
    assert period.end <= previous.end
    # 6 days and 15.5 hours of the current week have passed; the same amount of the last one counts.
    assert period.end - MICRO == utc(2026, 10, 5, 10, 0)  # Mon 5 Oct 15:30 IST
    assert (period.first_day, period.last_day) == (date(2026, 9, 29), date(2026, 10, 5))


def test_just_after_ist_midnight_only_the_first_instants_of_the_previous_day_are_compared():
    just_after = utc(2026, 10, 12, 18, 30, 0, 500)  # 00:00:00.0005 IST on 13 Oct
    current, previous = reporting_periods(just_after, 1)
    period = comparison_period(current, previous, just_after)

    assert current.start == just_after - timedelta(microseconds=500)
    assert period.start == previous.start
    assert period.end - previous.start == timedelta(microseconds=501)  # 500 µs plus `now` itself
    assert period.last_day == date(2026, 10, 12)


def test_exactly_at_ist_midnight_the_comparison_still_holds_the_matching_instant():
    midnight = utc(2026, 10, 12, 18, 30)
    current, previous = reporting_periods(midnight, 1)
    period = comparison_period(current, previous, midnight)

    assert period.contains(previous.start)
    assert not period.contains(previous.start + MICRO)


def test_the_last_instant_before_midnight_compares_with_the_whole_previous_period():
    last = utc(2026, 10, 12, 18, 29, 59, 999999)
    current, previous = reporting_periods(last, 7)

    assert comparison_period(current, previous, last) == previous


def test_the_comparison_needs_a_moment_inside_the_current_period():
    current, previous = reporting_periods(NOW, 7)

    for outside in (current.start - MICRO, current.end):
        with pytest.raises(ValueError):
            comparison_period(current, previous, outside)
    with pytest.raises(ValueError):
        comparison_period(current, previous, datetime(2026, 10, 12, 10))

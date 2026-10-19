"""Daily and weekly IST buckets."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.clock import IST
from app.domain.analytics import (
    Bucket,
    BucketTotal,
    bucket_start,
    bucket_starts,
    bucketize,
    reporting_periods,
)


def utc(*parts) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def ist(*parts) -> datetime:
    return datetime(*parts, tzinfo=IST)


def period(now: datetime, days: int):
    return reporting_periods(now, days)[0]


# Monday 12 Oct 2026 is a Monday; Sunday 18 Oct is the last day of that week.
def test_a_week_starts_on_monday():
    assert date(2026, 10, 12).weekday() == 0
    assert bucket_start(date(2026, 10, 12), Bucket.WEEK) == date(2026, 10, 12)  # Monday
    assert bucket_start(date(2026, 10, 18), Bucket.WEEK) == date(2026, 10, 12)  # Sunday
    assert bucket_start(date(2026, 10, 19), Bucket.WEEK) == date(2026, 10, 19)  # next Monday
    assert bucket_start(date(2026, 10, 14), Bucket.DAY) == date(2026, 10, 14)


@pytest.mark.parametrize("days", [1, 7, 30, 366])
def test_there_is_one_daily_bucket_per_day_of_the_period(days):
    window = period(utc(2026, 10, 12, 10), days)

    starts = bucket_starts(window, Bucket.DAY)

    assert len(starts) == days
    assert starts[0] == window.first_day and starts[-1] == window.last_day
    assert all(b - a == timedelta(days=1) for a, b in zip(starts, starts[1:], strict=False))


def test_weekly_buckets_cover_the_period_and_may_start_before_it():
    window = period(utc(2026, 10, 15, 10), 10)  # Tue 6 Oct .. Thu 15 Oct

    assert bucket_starts(window, Bucket.WEEK) == [date(2026, 10, 5), date(2026, 10, 12)]


def test_a_period_of_exactly_one_calendar_week_has_one_weekly_bucket():
    window = period(utc(2026, 10, 18, 10), 7)  # Mon 12 Oct .. Sun 18 Oct

    assert bucket_starts(window, Bucket.WEEK) == [date(2026, 10, 12)]


def test_empty_buckets_are_present_with_zeros():
    window = period(utc(2026, 10, 12, 10), 3)

    assert bucketize([], window, Bucket.DAY) == [
        BucketTotal(date(2026, 10, 10), 0, 0, date(2026, 10, 10), date(2026, 10, 10), False),
        BucketTotal(date(2026, 10, 11), 0, 0, date(2026, 10, 11), date(2026, 10, 11), False),
        BucketTotal(date(2026, 10, 12), 0, 0, date(2026, 10, 12), date(2026, 10, 12), True),
    ]


def covered(window, bucket):
    return [
        (s.start, s.covered_from, s.covered_to, s.partial) for s in bucketize([], window, bucket)
    ]


def test_only_the_daily_bucket_holding_today_is_partial():
    window = period(utc(2026, 10, 12, 10), 5)  # 8 .. 12 Oct

    assert [slot.partial for slot in bucketize([], window, Bucket.DAY)] == [
        False, False, False, False, True,
    ]  # fmt: skip


def test_a_weekly_bucket_cut_off_by_the_period_start_is_partial_and_says_which_days_it_covers():
    window = period(utc(2026, 10, 15, 10), 10)  # Tue 6 Oct .. Thu 15 Oct

    assert covered(window, Bucket.WEEK) == [
        (date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 11), True),  # Monday 5th is missing
        (date(2026, 10, 12), date(2026, 10, 12), date(2026, 10, 15), True),  # week not over yet
    ]


def test_a_weekly_bucket_in_the_middle_of_the_period_is_whole():
    window = period(utc(2026, 10, 20, 10), 21)  # Tue 30 Sep .. Tue 20 Oct

    assert covered(window, Bucket.WEEK) == [
        (date(2026, 9, 28), date(2026, 9, 30), date(2026, 10, 4), True),
        (date(2026, 10, 5), date(2026, 10, 5), date(2026, 10, 11), False),
        (date(2026, 10, 12), date(2026, 10, 12), date(2026, 10, 18), False),
        (date(2026, 10, 19), date(2026, 10, 19), date(2026, 10, 20), True),
    ]


def test_a_period_of_whole_weeks_ending_on_sunday_still_has_a_partial_last_bucket():
    # Sunday is the last day of the week but it is today, and today is not over.
    window = period(utc(2026, 10, 18, 10), 7)  # Mon 12 Oct .. Sun 18 Oct

    assert covered(window, Bucket.WEEK) == [
        (date(2026, 10, 12), date(2026, 10, 12), date(2026, 10, 18), True)
    ]


def test_an_entry_belongs_to_the_ist_day_it_happened_on():
    window = period(utc(2026, 10, 13, 10), 3)  # 11, 12, 13 Oct IST
    entries = [
        (utc(2026, 10, 12, 18, 29, 59, 999999), 100),  # 23:59:59.999999 IST on 12 Oct
        (utc(2026, 10, 12, 18, 30), 200),  # 00:00 IST on 13 Oct
        (utc(2026, 10, 11, 0, 0), 5),  # 05:30 IST on 11 Oct
    ]

    totals = {
        slot.start: (slot.total, slot.count) for slot in bucketize(entries, window, Bucket.DAY)
    }

    assert totals == {
        date(2026, 10, 11): (5, 1),
        date(2026, 10, 12): (100, 1),
        date(2026, 10, 13): (200, 1),
    }


def test_entries_outside_the_period_are_ignored():
    window = period(utc(2026, 10, 12, 10), 2)  # 11 and 12 Oct IST
    entries = [
        (window.start - timedelta(microseconds=1), 1),  # just before
        (window.start, 10),  # first instant: counted
        (window.end - timedelta(microseconds=1), 100),  # last instant: counted
        (window.end, 1000),  # end is exclusive
    ]

    slots = bucketize(entries, window, Bucket.DAY)

    assert [(s.start, s.total, s.count) for s in slots] == [
        (date(2026, 10, 11), 10, 1),
        (date(2026, 10, 12), 100, 1),
    ]


def test_several_entries_in_one_bucket_are_summed_and_counted():
    window = period(utc(2026, 10, 12, 10), 1)

    [slot] = bucketize(
        [(ist(2026, 10, 12, 9), 250), (ist(2026, 10, 12, 20), 750)], window, Bucket.DAY
    )

    assert (slot.total, slot.count) == (1000, 2)


def test_weekly_buckets_split_at_monday_ist_midnight():
    window = period(utc(2026, 10, 15, 10), 10)  # Tue 6 Oct .. Thu 15 Oct
    entries = [
        (ist(2026, 10, 5, 12), 1),  # Monday before the period starts: ignored
        (ist(2026, 10, 6, 0, 0), 10),  # first instant of the period: week of 5 Oct
        (ist(2026, 10, 11, 23, 59, 59), 100),  # Sunday night: still the week of 5 Oct
        (ist(2026, 10, 12, 0, 0), 1000),  # Monday 00:00 IST: week of 12 Oct
        (utc(2026, 10, 15, 10), 10000),  # now: week of 12 Oct
    ]

    slots = bucketize(entries, window, Bucket.WEEK)

    assert [(s.start, s.total, s.count) for s in slots] == [
        (date(2026, 10, 5), 110, 2),
        (date(2026, 10, 12), 11000, 2),
    ]


def test_the_totals_are_integers_so_money_is_never_a_float():
    window = period(utc(2026, 10, 12, 10), 1)

    [slot] = bucketize([(utc(2026, 10, 12, 9), 12_345)], window, Bucket.DAY)

    assert type(slot.total) is int and type(slot.count) is int

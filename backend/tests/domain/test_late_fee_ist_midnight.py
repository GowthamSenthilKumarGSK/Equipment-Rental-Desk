"""Assumption A5: "calendar days, rounded up" means elapsed 24-hour periods, rounded up.

So the fee never depends on the time zone or on where IST midnight falls: crossing midnight does not
start a new chargeable day by itself, and the same two instants cost the same however they are
written. These tests pin that interpretation around IST midnight (UTC+05:30, no daylight saving).
"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.rules import calculate_late_fee_paise, late_fee_days

IST = timezone(timedelta(hours=5, minutes=30))
BIG_VALUE = 100_000 * 100


def ist(day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, second, tzinfo=IST)


@pytest.mark.parametrize(
    ("due", "returned", "expected_days"),
    [
        # Crossing IST midnight by two minutes: only two minutes late, so one day.
        (ist(19, 23, 59), ist(20, 0, 1), 1),
        # Same IST calendar day, eight hours late: one day, not zero.
        (ist(19, 10), ist(19, 18), 1),
        # Due at IST midnight, returned the second before the next IST midnight: one day.
        (ist(19, 0), ist(19, 23, 59, 59), 1),
        # Exactly 24 hours after an IST-midnight due time: still one day.
        (ist(19, 0), ist(20, 0), 1),
        # One second later it is two days.
        (ist(19, 0), ist(20, 0, 0, 1), 2),
        # Crossing IST midnight but under 24 hours elapsed: one day.
        (ist(19, 12), ist(20, 11, 59, 59), 1),
        (ist(19, 12), ist(20, 12), 1),
        (ist(19, 12), ist(20, 12, 0, 1), 2),
        # Returned exactly at an IST-midnight due time: on time.
        (ist(19, 0), ist(19, 0), 0),
        # One second before an IST-midnight due time: on time.
        (ist(19, 0), ist(18, 23, 59, 59), 0),
        # Two midnights crossed, 24h01m elapsed: two days.
        (ist(19, 23, 59), ist(21, 0, 0), 2),
    ],
)
def test_late_days_do_not_depend_on_ist_midnight(due, returned, expected_days):
    assert late_fee_days(due, returned) == expected_days


@pytest.mark.parametrize("due_hour", [0, 5, 6, 12, 18, 23])
@pytest.mark.parametrize(
    ("late_by", "expected_days"),
    [
        (timedelta(hours=1), 1),
        (timedelta(hours=23, minutes=59, seconds=59), 1),
        (timedelta(hours=24), 1),
        (timedelta(hours=24, seconds=1), 2),
        (timedelta(hours=30), 2),
        (timedelta(hours=48), 2),
        (timedelta(hours=48, seconds=1), 3),
    ],
)
def test_same_lateness_costs_the_same_at_any_time_of_day(due_hour, late_by, expected_days):
    due = ist(19, due_hour)

    assert late_fee_days(due, due + late_by) == expected_days


def test_the_same_instants_cost_the_same_in_ist_and_utc():
    due_ist, returned_ist = ist(19, 23, 30), ist(21, 0, 15)

    in_ist = calculate_late_fee_paise(due_ist, returned_ist, BIG_VALUE)
    in_utc = calculate_late_fee_paise(
        due_ist.astimezone(UTC), returned_ist.astimezone(UTC), BIG_VALUE
    )

    assert in_ist == in_utc == 2 * 1_000  # 24h45m late: two days

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.rules import calculate_late_fee_paise, late_fee_days
from tests.markers import awaiting_m2

pytestmark = awaiting_m2

DUE_AT = datetime(2026, 10, 19, 10, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
DAY = timedelta(days=1)
RUPEE = 100  # paise
BIG_VALUE = 100_000 * RUPEE  # replacement value that never limits the fee


@pytest.mark.parametrize(
    ("late_by", "expected_days"),
    [
        (-DAY, 0),  # returned early
        (timedelta(0), 0),  # returned exactly on time
        (SECOND, 1),  # one second late already costs a day (rounded up): A5
        (timedelta(hours=23, minutes=59), 1),
        (DAY, 1),
        (DAY + SECOND, 2),
        (2 * DAY, 2),
        (timedelta(days=6, hours=1), 7),
    ],
)
def test_late_days_are_rounded_up(late_by, expected_days):
    assert late_fee_days(DUE_AT, DUE_AT + late_by) == expected_days


@pytest.mark.parametrize(
    ("late_by", "expected_paise"),
    [
        (-DAY, 0),
        (timedelta(0), 0),
        (SECOND, 10 * RUPEE),
        (DAY, 10 * RUPEE),
        (DAY + SECOND, 20 * RUPEE),
        (19 * DAY, 190 * RUPEE),
        (20 * DAY - SECOND, 200 * RUPEE),
        (20 * DAY, 200 * RUPEE),  # exactly reaches the cap
        (20 * DAY + SECOND, 200 * RUPEE),  # 21 days would be ₹210, capped at ₹200
        (365 * DAY, 200 * RUPEE),
    ],
)
def test_late_fee_is_10_rupees_per_day_capped_at_200(late_by, expected_paise):
    fee = calculate_late_fee_paise(DUE_AT, DUE_AT + late_by, BIG_VALUE)

    assert fee == expected_paise
    assert type(fee) is int


@pytest.mark.parametrize(
    ("late_by", "replacement_paise", "expected_paise"),
    [
        (DAY, 15 * RUPEE, 10 * RUPEE),  # fee below the value: unchanged
        (2 * DAY, 15 * RUPEE, 15 * RUPEE),  # ₹20 would exceed the ₹15 item: limited to ₹15
        (2 * DAY, 20 * RUPEE, 20 * RUPEE),  # fee exactly equals the value
        (2 * DAY, 20 * RUPEE - 1, 20 * RUPEE - 1),  # one paisa below the fee
        (2 * DAY, 20 * RUPEE + 1, 20 * RUPEE),  # one paisa above the fee
        (16 * DAY, 150 * RUPEE, 150 * RUPEE),  # ₹160 limited to a ₹150 item
        (30 * DAY, 300 * RUPEE, 200 * RUPEE),  # item worth more than the cap: cap wins
        (30 * DAY, 200 * RUPEE, 200 * RUPEE),  # value and cap are equal
        (SECOND, 5 * RUPEE, 5 * RUPEE),  # even one day is limited by a ₹5 item
    ],
)
def test_late_fee_never_exceeds_replacement_value(late_by, replacement_paise, expected_paise):
    assert calculate_late_fee_paise(DUE_AT, DUE_AT + late_by, replacement_paise) == expected_paise

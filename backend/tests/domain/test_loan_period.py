from datetime import UTC, datetime, timedelta

import pytest

from app.domain.rules import is_overdue, loan_due_at
from tests.markers import awaiting_m2

pytestmark = awaiting_m2

CHECKED_OUT_AT = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
DUE_AT = CHECKED_OUT_AT + timedelta(days=7)


def test_loan_is_due_seven_days_after_checkout():
    assert loan_due_at(CHECKED_OUT_AT) == DUE_AT


@pytest.mark.parametrize(
    ("offset_from_due", "expected_overdue"),
    [
        (timedelta(days=-7), False),
        (timedelta(seconds=-1), False),
        (timedelta(0), False),  # still on time at exactly due_at: assumption A6
        (timedelta(seconds=1), True),
        (timedelta(days=3), True),
    ],
)
def test_overdue_boundary(offset_from_due, expected_overdue):
    assert is_overdue(DUE_AT, DUE_AT + offset_from_due) is expected_overdue

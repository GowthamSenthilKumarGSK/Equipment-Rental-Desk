from datetime import UTC, datetime, timedelta

import pytest

from app.domain.rules import is_reservation_expired, reservation_expires_at

RESERVED_AT = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)


def test_reservation_holds_for_48_hours():
    assert reservation_expires_at(RESERVED_AT) == RESERVED_AT + timedelta(hours=48)


@pytest.mark.parametrize(
    ("elapsed", "expected_expired"),
    [
        (timedelta(0), False),
        (timedelta(hours=47, minutes=59), False),
        (timedelta(hours=47, minutes=59, seconds=59), False),
        (timedelta(hours=48), True),  # boundary is exclusive: assumption A2
        (timedelta(hours=48, minutes=1), True),
        (timedelta(days=30), True),
    ],
)
def test_reservation_expiry_boundary(elapsed, expected_expired):
    assert is_reservation_expired(RESERVED_AT, RESERVED_AT + elapsed) is expected_expired


def test_naive_datetimes_are_rejected():
    naive = datetime(2026, 10, 12, 10, 0)

    with pytest.raises(ValueError, match="timezone"):
        is_reservation_expired(naive, RESERVED_AT)

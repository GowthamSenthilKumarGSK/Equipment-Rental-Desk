from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import LoanStatus
from app.domain.rules import effective_loan_status

RESERVED_AT = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(0), LoanStatus.RESERVED),
        (timedelta(hours=47, minutes=59), LoanStatus.RESERVED),
        (timedelta(hours=48), LoanStatus.EXPIRED),  # same boundary as everywhere else (A2)
        (timedelta(days=30), LoanStatus.EXPIRED),
    ],
)
def test_a_reserved_loan_reads_as_expired_once_the_hold_lapses(elapsed, expected):
    status = effective_loan_status(
        LoanStatus.RESERVED, reserved_at=RESERVED_AT, now=RESERVED_AT + elapsed
    )

    assert status is expected


@pytest.mark.parametrize(
    "status",
    [LoanStatus.CHECKED_OUT, LoanStatus.RETURNED, LoanStatus.CANCELLED, LoanStatus.EXPIRED],
)
def test_other_statuses_never_change_with_time(status):
    later = RESERVED_AT + timedelta(days=365)

    assert effective_loan_status(status, reserved_at=RESERVED_AT, now=later) is status


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        effective_loan_status(
            LoanStatus.RESERVED, reserved_at=RESERVED_AT.replace(tzinfo=None), now=RESERVED_AT
        )

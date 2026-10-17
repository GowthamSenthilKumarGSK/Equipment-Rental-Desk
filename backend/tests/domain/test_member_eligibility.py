from datetime import timedelta

import pytest

from app.domain.enums import BlockReason, MemberStatus
from app.domain.errors import LoanLimitExceeded, MemberBlocked
from app.domain.rules import (
    ensure_member_can_transact,
    ensure_within_loan_limit,
    member_block_reasons,
)

ACTIVE = MemberStatus.ACTIVE
SUSPENDED = MemberStatus.SUSPENDED


def reasons(*, status=ACTIVE, balance_paise=0, longest_overdue=None):
    return member_block_reasons(
        status=status, balance_paise=balance_paise, longest_overdue=longest_overdue
    )


def test_member_in_good_standing_is_not_blocked():
    assert reasons() == []


@pytest.mark.parametrize(
    ("balance_paise", "blocked"),
    [
        (0, False),
        (9_999, False),  # ₹99.99
        (10_000, False),  # exactly ₹100 is still allowed
        (10_001, True),  # ₹100.01
        (50_000, True),
    ],
)
def test_unpaid_fee_threshold(balance_paise, blocked):
    expected = [BlockReason.UNPAID_FEES] if blocked else []

    assert reasons(balance_paise=balance_paise) == expected


@pytest.mark.parametrize(
    ("overdue_by", "blocked"),
    [
        (None, False),  # no overdue loan
        (timedelta(days=1), False),
        (timedelta(days=13, hours=23), False),
        (timedelta(days=14), False),  # exactly 14 days is still allowed
        (timedelta(days=14, seconds=1), True),
        (timedelta(days=30), True),
    ],
)
def test_long_overdue_threshold(overdue_by, blocked):
    expected = [BlockReason.LONG_OVERDUE] if blocked else []

    assert reasons(longest_overdue=overdue_by) == expected


def test_suspended_member_is_blocked_even_with_clean_record():
    assert reasons(status=SUSPENDED) == [BlockReason.SUSPENDED]


def test_every_applicable_reason_is_reported():
    result = reasons(status=SUSPENDED, balance_paise=10_001, longest_overdue=timedelta(days=15))

    assert set(result) == {
        BlockReason.SUSPENDED,
        BlockReason.UNPAID_FEES,
        BlockReason.LONG_OVERDUE,
    }


def test_blocked_member_raises_with_the_reasons():
    with pytest.raises(MemberBlocked) as caught:
        ensure_member_can_transact(status=ACTIVE, balance_paise=10_001, longest_overdue=None)

    assert caught.value.reasons == (BlockReason.UNPAID_FEES,)


def test_member_at_exactly_100_rupees_may_transact():
    ensure_member_can_transact(status=ACTIVE, balance_paise=10_000, longest_overdue=None)


@pytest.mark.parametrize("active_loans", [0, 1, 2])
def test_member_below_three_active_loans_may_take_another(active_loans):
    ensure_within_loan_limit(active_loans)


@pytest.mark.parametrize("active_loans", [3, 4])
def test_member_with_three_active_loans_cannot_take_another(active_loans):
    with pytest.raises(LoanLimitExceeded):
        ensure_within_loan_limit(active_loans)

"""The rules refuse inputs that would silently produce wrong money or wrong times."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.enums import ItemAction, ItemStatus, LoanAction, LoanStatus, MemberStatus
from app.domain.errors import InvalidTransition
from app.domain.rules import (
    calculate_late_fee_paise,
    effective_item_status,
    is_overdue,
    late_fee_days,
    loan_due_at,
    member_block_reasons,
    next_item_status,
    next_loan_status,
    reservation_expires_at,
    validate_payment,
)

AWARE = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
NAIVE = datetime(2026, 10, 12, 10, 0)


@pytest.mark.parametrize("bad_amount", [10.5, 1e3, "1000", None, True])
def test_money_must_be_integer_paise(bad_amount):
    with pytest.raises(TypeError, match="integer"):
        validate_payment(bad_amount, 12_000)
    with pytest.raises(TypeError, match="integer"):
        validate_payment(1_000, bad_amount)
    with pytest.raises(TypeError, match="integer"):
        calculate_late_fee_paise(AWARE, AWARE + timedelta(days=1), bad_amount)
    with pytest.raises(TypeError, match="integer"):
        member_block_reasons(
            status=MemberStatus.ACTIVE, balance_paise=bad_amount, longest_overdue=None
        )


@pytest.mark.parametrize(
    "call",
    [
        lambda: reservation_expires_at(NAIVE),
        lambda: loan_due_at(NAIVE),
        lambda: is_overdue(NAIVE, AWARE),
        lambda: is_overdue(AWARE, NAIVE),
        lambda: late_fee_days(NAIVE, AWARE),
        lambda: late_fee_days(AWARE, NAIVE),
        lambda: calculate_late_fee_paise(AWARE, NAIVE, 10_000),
        lambda: effective_item_status(ItemStatus.AVAILABLE, now=NAIVE),
    ],
)
def test_naive_datetimes_are_rejected_everywhere(call):
    with pytest.raises(ValueError, match="timezone-aware"):
        call()


def test_a_reserved_item_without_its_reservation_time_is_reported_not_guessed():
    with pytest.raises(ValueError, match="reserved_at"):
        effective_item_status(ItemStatus.RESERVED, now=AWARE)


def test_a_checked_out_item_without_its_due_date_is_reported_not_guessed():
    with pytest.raises(ValueError, match="due_at"):
        effective_item_status(ItemStatus.CHECKED_OUT, now=AWARE)


def test_transition_errors_say_what_was_attempted_and_from_where():
    with pytest.raises(InvalidTransition, match="Cannot return an item that is available"):
        next_item_status(ItemStatus.AVAILABLE, ItemAction.RETURN)
    with pytest.raises(InvalidTransition, match="Cannot return a loan that is returned"):
        next_loan_status(LoanStatus.RETURNED, LoanAction.RETURN)
    with pytest.raises(InvalidTransition, match="Cannot check out an item that is checked out"):
        next_item_status(ItemStatus.CHECKED_OUT, ItemAction.CHECK_OUT)

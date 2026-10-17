from datetime import timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import InvalidTransition
from app.models import Item, Loan
from tests.builders import NOW

SECOND = timedelta(seconds=1)
DAY = timedelta(days=1)
LOAN_PERIOD = timedelta(days=7)


def test_returning_on_time_costs_nothing_and_frees_the_item(db, loans, members, clock, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD)  # returned exactly at the due time

    loan = loans.return_item(item_id=item_id)

    stored = db.get(Loan, loan.id)
    assert stored.status is LoanStatus.RETURNED
    assert stored.returned_at == NOW + LOAN_PERIOD
    assert stored.fee_charged_paise == 0
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE
    assert members.balance_paise(member_id) == 0


@pytest.mark.parametrize(
    ("late_by", "expected_fee"),
    [
        (SECOND, 1_000),
        (DAY, 1_000),
        (DAY + SECOND, 2_000),
        (19 * DAY, 19_000),
        (20 * DAY - SECOND, 20_000),
        (20 * DAY, 20_000),  # reaches the ₹200 cap exactly
        (20 * DAY + SECOND, 20_000),  # 21 days would be ₹210
        (60 * DAY, 20_000),
    ],
)
def test_late_return_charges_the_fee_to_the_member(
    db, loans, members, clock, rent, late_by, expected_fee
):
    member_id, item_id = db.member(), db.item(replacement_value_paise=650_000)
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + late_by)

    loan = loans.return_item(item_id=item_id)

    assert db.get(Loan, loan.id).fee_charged_paise == expected_fee
    assert members.balance_paise(member_id) == expected_fee


@pytest.mark.parametrize(
    ("late_by", "replacement_paise", "expected_fee"),
    [
        (2 * DAY, 1_500, 1_500),  # ₹20 would exceed a ₹15 item
        (2 * DAY, 2_000, 2_000),  # fee equals the replacement value
        (2 * DAY, 1_999, 1_999),
        (2 * DAY, 2_001, 2_000),
        (16 * DAY, 15_000, 15_000),  # ₹160 limited to a ₹150 item
        (30 * DAY, 30_000, 20_000),  # item worth more than the cap: the ₹200 cap applies
    ],
)
def test_fee_is_never_more_than_the_replacement_value(
    db, loans, clock, rent, late_by, replacement_paise, expected_fee
):
    member_id, item_id = db.member(), db.item(replacement_value_paise=replacement_paise)
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + late_by)

    assert loans.return_item(item_id=item_id).fee_charged_paise == expected_fee


def test_returning_an_overdue_item_works_and_it_is_overdue_until_then(
    db, loans, items, clock, rent
):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + DAY)
    assert items.item_status(item_id) is ItemStatus.OVERDUE

    loans.return_item(item_id=item_id)

    assert items.item_status(item_id) is ItemStatus.AVAILABLE


def test_a_member_blocked_for_being_long_overdue_can_still_return(db, loans, members, clock, rent):
    member_id, item_id = db.member(), db.item(replacement_value_paise=650_000)
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + timedelta(days=20))
    members.suspend(member_id=member_id)

    loan = loans.return_item(item_id=item_id)

    assert loan.fee_charged_paise == 20_000


# --- returning something that is not checked out -------------------------------------------


def test_double_return_is_an_error_and_charges_nothing_more(db, loans, members, clock, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + 3 * DAY)
    loans.return_item(item_id=item_id)
    balance_after_first = members.balance_paise(member_id)

    with pytest.raises(InvalidTransition, match="not checked out"):
        loans.return_item(item_id=item_id)

    assert members.balance_paise(member_id) == balance_after_first == 3_000
    assert len(db.loans_of_item(item_id)) == 1


def test_an_available_item_cannot_be_returned(db, loans):
    item_id = db.item()

    with pytest.raises(InvalidTransition, match="not checked out"):
        loans.return_item(item_id=item_id)


def test_a_reserved_item_cannot_be_returned(db, loans):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)

    with pytest.raises(InvalidTransition, match="Cannot return a loan that is reserved"):
        loans.return_item(item_id=item_id)

    assert db.get(Item, item_id).status is ItemStatus.RESERVED


def test_an_item_under_maintenance_with_no_loan_cannot_be_returned(db, loans):
    item_id = db.item(status=ItemStatus.UNDER_MAINTENANCE)

    with pytest.raises(InvalidTransition, match="not checked out"):
        loans.return_item(item_id=item_id)

    assert db.get(Item, item_id).status is ItemStatus.UNDER_MAINTENANCE


# --- failures leave nothing behind ---------------------------------------------------------


def test_failure_while_returning_rolls_back_the_loan_fee_and_item(
    db, loans, members, clock, rent, monkeypatch
):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + 5 * DAY)

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated failure while updating the item")

    monkeypatch.setattr("app.services.loans.items_repo.set_status", explode)
    with pytest.raises(RuntimeError, match="simulated failure"):
        loans.return_item(item_id=item_id)

    stored = db.loans_of_item(item_id)[0]
    assert stored.status is LoanStatus.CHECKED_OUT
    assert stored.returned_at is None and stored.fee_charged_paise == 0
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT
    assert members.balance_paise(member_id) == 0


def test_clock_moved_before_check_out_is_refused_cleanly(db, loans, clock, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(-timedelta(hours=1))

    with pytest.raises(InvalidTransition, match="earlier than"):
        loans.return_item(item_id=item_id)

    assert db.loans_of_item(item_id)[0].status is LoanStatus.CHECKED_OUT

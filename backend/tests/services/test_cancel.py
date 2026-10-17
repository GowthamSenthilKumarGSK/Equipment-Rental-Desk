from datetime import timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import InvalidTransition, ReservationExpired
from app.models import Item, Loan
from tests.builders import NOW


def test_cancelling_frees_the_item_and_keeps_the_loan_as_history(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(timedelta(hours=5))

    cancelled = loans.cancel_reservation(item_id=item_id)

    assert cancelled.id == reserved.id
    stored = db.get(Loan, reserved.id)
    assert stored.status is LoanStatus.CANCELLED
    assert stored.cancelled_at == NOW + timedelta(hours=5)
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE


def test_a_cancelled_item_can_be_reserved_again(db, loans):
    first, second = db.member(), db.member(name="Second")
    item_id = db.item()
    loans.reserve_item(member_id=first, item_id=item_id)
    loans.cancel_reservation(item_id=item_id)

    loans.reserve_item(member_id=second, item_id=item_id)

    statuses = [loan.status for loan in db.loans_of_item(item_id)]
    assert statuses == [LoanStatus.CANCELLED, LoanStatus.RESERVED]


def test_cancelling_at_47h59m_works(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(timedelta(hours=47, minutes=59))

    assert loans.cancel_reservation(item_id=item_id).status is LoanStatus.CANCELLED


@pytest.mark.parametrize("elapsed", [timedelta(hours=48), timedelta(hours=48, minutes=1)])
def test_cancelling_after_the_hold_lapsed_reports_expiry_and_keeps_it(db, loans, clock, elapsed):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(elapsed)

    with pytest.raises(ReservationExpired):
        loans.cancel_reservation(item_id=item_id)

    assert db.get(Loan, reserved.id).status is LoanStatus.EXPIRED
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE


def test_only_a_reserved_loan_can_be_cancelled(db, loans, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)

    with pytest.raises(InvalidTransition, match="Cannot cancel a loan that is checked out"):
        loans.cancel_reservation(item_id=item_id)

    assert db.loans_of_item(item_id)[0].status is LoanStatus.CHECKED_OUT
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT


def test_cancelling_when_nothing_is_reserved_is_an_error(db, loans):
    item_id = db.item()

    with pytest.raises(InvalidTransition, match="no reservation to cancel"):
        loans.cancel_reservation(item_id=item_id)


def test_cancelling_twice_is_an_error(db, loans):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    loans.cancel_reservation(item_id=item_id)

    with pytest.raises(InvalidTransition, match="no reservation to cancel"):
        loans.cancel_reservation(item_id=item_id)


def test_a_returned_item_has_nothing_to_cancel(db, loans, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    loans.return_item(item_id=item_id)

    with pytest.raises(InvalidTransition, match="no reservation to cancel"):
        loans.cancel_reservation(item_id=item_id)

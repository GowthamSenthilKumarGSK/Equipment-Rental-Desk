"""Maintenance is allowed from any state (A3) but never makes an item available by accident (A4)."""

from datetime import timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import EntityNotFound, InvalidTransition
from app.models import Item, Loan
from tests.builders import NOW

LOAN_PERIOD = timedelta(days=7)


def test_an_available_item_can_go_to_maintenance_and_come_back(db, items):
    item_id = db.item()

    assert items.start_maintenance(item_id=item_id).status is ItemStatus.UNDER_MAINTENANCE
    assert items.finish_maintenance(item_id=item_id).status is ItemStatus.AVAILABLE


def test_unknown_item_is_not_found(items):
    with pytest.raises(EntityNotFound):
        items.start_maintenance(item_id=999)
    with pytest.raises(EntityNotFound):
        items.finish_maintenance(item_id=999)


def test_starting_maintenance_twice_is_an_error(db, items):
    item_id = db.item()
    items.start_maintenance(item_id=item_id)

    with pytest.raises(InvalidTransition, match="Cannot start maintenance on an item that is"):
        items.start_maintenance(item_id=item_id)


def test_finishing_maintenance_on_a_working_item_is_an_error(db, items):
    item_id = db.item()

    with pytest.raises(InvalidTransition, match="Cannot finish maintenance"):
        items.finish_maintenance(item_id=item_id)


def test_a_reservation_is_cancelled_but_kept_as_history(db, loans, items):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)

    items.start_maintenance(item_id=item_id)

    stored = db.get(Loan, reserved.id)
    assert stored.status is LoanStatus.CANCELLED
    assert stored.cancelled_at == NOW
    assert db.get(Item, item_id).status is ItemStatus.UNDER_MAINTENANCE
    # and the member is free to reserve something else straight away
    assert loans.reserve_item(member_id=member_id, item_id=db.item(name="Other")).id


def test_an_expired_reservation_is_cleared_first_and_not_reported_as_cancelled(
    db, loans, items, clock
):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(timedelta(hours=48))

    items.start_maintenance(item_id=item_id)

    assert db.get(Loan, reserved.id).status is LoanStatus.EXPIRED
    assert db.get(Item, item_id).status is ItemStatus.UNDER_MAINTENANCE


def test_a_checked_out_item_goes_to_maintenance_with_the_loan_still_open(db, loans, items, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)

    item = items.start_maintenance(item_id=item_id)

    assert item.status is ItemStatus.UNDER_MAINTENANCE
    assert db.loans_of_item(item_id)[0].status is LoanStatus.CHECKED_OUT


def test_maintenance_cannot_end_while_the_item_is_still_on_loan(db, items, rent):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    items.start_maintenance(item_id=item_id)

    with pytest.raises(InvalidTransition, match="still on loan"):
        items.finish_maintenance(item_id=item_id)

    assert db.get(Item, item_id).status is ItemStatus.UNDER_MAINTENANCE


def test_returning_an_item_that_went_to_maintenance_does_not_make_it_available(
    db, loans, items, members, clock, rent
):
    member_id, item_id = db.member(), db.item(replacement_value_paise=650_000)
    rent(member_id, item_id)
    items.start_maintenance(item_id=item_id)
    clock.advance(LOAN_PERIOD + timedelta(days=2))

    returned = loans.return_item(item_id=item_id)

    assert returned.status is LoanStatus.RETURNED
    assert returned.fee_charged_paise == 2_000  # late fees still apply
    assert members.balance_paise(member_id) == 2_000
    assert db.get(Item, item_id).status is ItemStatus.UNDER_MAINTENANCE
    assert items.item_status(item_id) is ItemStatus.UNDER_MAINTENANCE
    # only staff can release it, and now they can
    assert items.finish_maintenance(item_id=item_id).status is ItemStatus.AVAILABLE


def test_an_overdue_loan_on_an_item_in_maintenance_still_counts_against_the_member(
    db, items, members, rent, clock
):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    items.start_maintenance(item_id=item_id)
    clock.advance(LOAN_PERIOD + timedelta(days=15))

    standing = members.standing(member_id)

    assert standing.longest_overdue > timedelta(days=14)
    assert standing.active_loan_count == 1


def test_an_item_under_maintenance_cannot_be_reserved(db, loans, items):
    member_id, item_id = db.member(), db.item()
    items.start_maintenance(item_id=item_id)

    with pytest.raises(InvalidTransition, match="Cannot reserve an item that is under maintenance"):
        loans.reserve_item(member_id=member_id, item_id=item_id)

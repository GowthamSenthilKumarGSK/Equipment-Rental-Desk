from datetime import timedelta

import pytest

from app.domain.enums import BlockReason, ItemStatus, LoanStatus
from app.domain.errors import EntityNotFound, InvalidTransition, MemberBlocked, ReservationExpired
from app.models import Item, Loan
from tests.builders import NOW

HOUR = timedelta(hours=1)


def test_check_out_sets_the_due_date_seven_days_later(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(HOUR)

    loan = loans.check_out(item_id=item_id)

    stored = db.get(Loan, loan.id)
    assert stored.status is LoanStatus.CHECKED_OUT
    assert stored.checked_out_at == NOW + HOUR
    assert stored.due_at == NOW + HOUR + timedelta(days=7)
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT


def test_unknown_item_is_not_found(loans):
    with pytest.raises(EntityNotFound, match="Item 999"):
        loans.check_out(item_id=999)


@pytest.mark.parametrize(
    ("elapsed", "allowed"),
    [
        (timedelta(0), True),
        (timedelta(hours=47, minutes=59), True),
        (timedelta(hours=47, minutes=59, seconds=59), True),
        (timedelta(hours=48), False),  # assumption A2: the hold is over at exactly 48h
        (timedelta(hours=48, minutes=1), False),
    ],
)
def test_reservation_expiry_boundary_at_check_out(db, loans, clock, elapsed, allowed):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(elapsed)

    if allowed:
        assert loans.check_out(item_id=item_id).status is LoanStatus.CHECKED_OUT
        return

    with pytest.raises(ReservationExpired, match="expired"):
        loans.check_out(item_id=item_id)
    # The expiry itself is kept even though the check-out was refused.
    assert db.get(Loan, reserved.id).status is LoanStatus.EXPIRED
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE


def test_expired_reservation_error_is_also_an_invalid_transition(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(timedelta(hours=49))

    with pytest.raises(InvalidTransition):
        loans.check_out(item_id=item_id)


def test_an_item_cannot_be_checked_out_without_a_reservation(db, loans):
    item_id = db.item()

    with pytest.raises(InvalidTransition, match="no active reservation"):
        loans.check_out(item_id=item_id)

    assert db.count(Loan) == 0


def test_item_under_maintenance_cannot_be_checked_out(db, loans):
    item_id = db.item(status=ItemStatus.UNDER_MAINTENANCE)

    with pytest.raises(InvalidTransition, match="no active reservation"):
        loans.check_out(item_id=item_id)


def test_double_check_out_is_rejected_and_changes_nothing(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    first = loans.check_out(item_id=item_id)
    clock.advance(timedelta(days=1))

    with pytest.raises(InvalidTransition, match="Cannot check out a loan that is checked out"):
        loans.check_out(item_id=item_id)

    stored = db.get(Loan, first.id)
    assert stored.checked_out_at == first.checked_out_at
    assert stored.due_at == first.due_at
    assert len(db.loans_of_item(item_id)) == 1


def test_the_reservation_itself_counts_so_a_third_loan_can_still_be_checked_out(db, loans, rent):
    member_id = db.member()
    rent(member_id, db.item(name="One"))
    loans.reserve_item(member_id=member_id, item_id=db.item(name="Two"))
    third = db.item(name="Three")
    loans.reserve_item(member_id=member_id, item_id=third)

    assert loans.check_out(item_id=third).status is LoanStatus.CHECKED_OUT


# --- the member's standing is checked again at check-out -------------------------------------


def test_member_suspended_after_reserving_cannot_check_out(db, loans, members):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    members.suspend(member_id=member_id, reason="test")

    with pytest.raises(MemberBlocked) as caught:
        loans.check_out(item_id=item_id)

    assert caught.value.reasons == (BlockReason.SUSPENDED,)
    assert db.get(Item, item_id).status is ItemStatus.RESERVED
    assert db.loans_of_item(item_id)[0].status is LoanStatus.RESERVED


@pytest.mark.parametrize(("owed_paise", "allowed"), [(10_000, True), (10_001, False)])
def test_balance_of_100_rupees_versus_100_rupees_1_paisa_at_check_out(
    db, loans, owed_paise, allowed
):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    db.owing(member_id, owed_paise)

    if allowed:
        assert loans.check_out(item_id=item_id).status is LoanStatus.CHECKED_OUT
    else:
        with pytest.raises(MemberBlocked) as caught:
            loans.check_out(item_id=item_id)
        assert caught.value.reasons == (BlockReason.UNPAID_FEES,)


@pytest.mark.parametrize(
    ("overdue_by", "allowed"),
    [(timedelta(days=14), True), (timedelta(days=14, seconds=1), False)],
)
def test_14_days_overdue_versus_14_days_and_a_second_at_check_out(db, loans, overdue_by, allowed):
    member_id, item_id, held = db.member(), db.item(), db.item(name="Held")
    loans.reserve_item(member_id=member_id, item_id=item_id)
    db.checked_out(member_id, held, due_at=NOW - overdue_by)

    if allowed:
        assert loans.check_out(item_id=item_id).status is LoanStatus.CHECKED_OUT
    else:
        with pytest.raises(MemberBlocked) as caught:
            loans.check_out(item_id=item_id)
        assert caught.value.reasons == (BlockReason.LONG_OVERDUE,)


# --- failures leave nothing behind ---------------------------------------------------------


def test_failure_while_checking_out_rolls_the_loan_and_item_back(db, loans, monkeypatch):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated failure while updating the item")

    monkeypatch.setattr("app.services.loans.items_repo.set_status", explode)
    with pytest.raises(RuntimeError, match="simulated failure"):
        loans.check_out(item_id=item_id)

    stored = db.loans_of_item(item_id)[0]
    assert stored.status is LoanStatus.RESERVED
    assert stored.checked_out_at is None and stored.due_at is None
    assert db.get(Item, item_id).status is ItemStatus.RESERVED


def test_clock_moved_before_the_reservation_is_refused_cleanly(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(-HOUR)

    with pytest.raises(InvalidTransition, match="earlier than"):
        loans.check_out(item_id=item_id)

    assert db.loans_of_item(item_id)[0].status is LoanStatus.RESERVED

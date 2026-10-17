from datetime import timedelta

import pytest

from app.domain.enums import BlockReason, ItemStatus, LoanStatus, MemberStatus
from app.domain.errors import (
    ConflictError,
    EntityNotFound,
    InvalidTransition,
    LoanLimitExceeded,
    MemberBlocked,
)
from app.models import Item, Loan
from tests.builders import NOW

HOUR = timedelta(hours=1)


def test_reserving_holds_the_item_for_the_member(db, loans):
    member_id, item_id = db.member(), db.item()

    loan = loans.reserve_item(member_id=member_id, item_id=item_id)

    stored = db.get(Loan, loan.id)
    assert (stored.member_id, stored.item_id) == (member_id, item_id)
    assert stored.status is LoanStatus.RESERVED
    assert stored.reserved_at == NOW
    assert db.get(Item, item_id).status is ItemStatus.RESERVED


def test_unknown_member_or_item_is_not_found(db, loans):
    member_id, item_id = db.member(), db.item()

    with pytest.raises(EntityNotFound, match="Member 999"):
        loans.reserve_item(member_id=999, item_id=item_id)
    with pytest.raises(EntityNotFound, match="Item 999"):
        loans.reserve_item(member_id=member_id, item_id=999)
    assert db.count(Loan) == 0


@pytest.mark.parametrize("taken_by", ["reservation", "checkout", "maintenance"])
def test_only_an_available_item_can_be_reserved(db, loans, taken_by):
    borrower, other = db.member(), db.member(name="Other")
    item_id = db.item()
    if taken_by == "reservation":
        db.reserved(other, item_id)
    elif taken_by == "checkout":
        db.checked_out(other, item_id, due_at=NOW + timedelta(days=3))
    else:
        item_id = db.item(status=ItemStatus.UNDER_MAINTENANCE)

    loans_before = db.count(Loan)
    with pytest.raises(InvalidTransition, match="Cannot reserve an item that is"):
        loans.reserve_item(member_id=borrower, item_id=item_id)
    assert db.count(Loan) == loans_before


def test_overdue_item_cannot_be_reserved(db, loans):
    borrower, other = db.member(), db.member(name="Other")
    item_id = db.item()
    db.checked_out(other, item_id, due_at=NOW - timedelta(days=2))

    with pytest.raises(InvalidTransition, match="overdue"):
        loans.reserve_item(member_id=borrower, item_id=item_id)


# --- who may reserve -----------------------------------------------------------------------


def test_suspended_member_cannot_reserve(db, loans):
    member_id = db.member(status=MemberStatus.SUSPENDED)
    item_id = db.item()

    with pytest.raises(MemberBlocked) as caught:
        loans.reserve_item(member_id=member_id, item_id=item_id)

    assert caught.value.reasons == (BlockReason.SUSPENDED,)
    assert db.count(Loan) == 0
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE


@pytest.mark.parametrize(
    ("owed_paise", "blocked"),
    [(9_999, False), (10_000, False), (10_001, True), (50_000, True)],
)
def test_balance_over_100_rupees_blocks_reserving(db, loans, owed_paise, blocked):
    member_id, item_id = db.member(), db.item()
    db.owing(member_id, owed_paise)

    if blocked:
        with pytest.raises(MemberBlocked) as caught:
            loans.reserve_item(member_id=member_id, item_id=item_id)
        assert caught.value.reasons == (BlockReason.UNPAID_FEES,)
        assert db.count(Loan) == 1  # only the past returned loan used to set up the balance
    else:
        assert (
            loans.reserve_item(member_id=member_id, item_id=item_id).status is LoanStatus.RESERVED
        )


@pytest.mark.parametrize(
    ("overdue_by", "blocked"),
    [
        (timedelta(days=1), False),
        (timedelta(days=14) - timedelta(seconds=1), False),
        (timedelta(days=14), False),
        (timedelta(days=14, seconds=1), True),
        (timedelta(days=30), True),
    ],
)
def test_loan_overdue_by_more_than_14_days_blocks_reserving(db, loans, overdue_by, blocked):
    member_id, held, wanted = db.member(), db.item(name="Held"), db.item(name="Wanted")
    db.checked_out(member_id, held, due_at=NOW - overdue_by)

    if blocked:
        with pytest.raises(MemberBlocked) as caught:
            loans.reserve_item(member_id=member_id, item_id=wanted)
        assert caught.value.reasons == (BlockReason.LONG_OVERDUE,)
    else:
        assert loans.reserve_item(member_id=member_id, item_id=wanted).status is LoanStatus.RESERVED


def test_every_reason_is_reported_together(db, loans):
    member_id, held, wanted = db.member(status=MemberStatus.SUSPENDED), db.item(), db.item()
    db.checked_out(member_id, held, due_at=NOW - timedelta(days=20))
    db.owing(member_id, 20_000)

    with pytest.raises(MemberBlocked) as caught:
        loans.reserve_item(member_id=member_id, item_id=wanted)

    assert set(caught.value.reasons) == set(BlockReason)


# --- the limit of three active loans -------------------------------------------------------


def make_active_loans(db, member_id, kinds):
    for kind in kinds:
        item_id = db.item(name=f"Item {kind}")
        if kind == "reserved":
            db.reserved(member_id, item_id)
        elif kind == "checked_out":
            db.checked_out(member_id, item_id, due_at=NOW + timedelta(days=3))
        else:  # overdue, but by less than the 14 days that would block the member outright
            db.checked_out(member_id, item_id, due_at=NOW - timedelta(days=2))


def test_third_active_loan_is_allowed(db, loans):
    member_id = db.member()
    make_active_loans(db, member_id, ["reserved", "checked_out"])

    loan = loans.reserve_item(member_id=member_id, item_id=db.item(name="Third"))

    assert loan.status is LoanStatus.RESERVED


@pytest.mark.parametrize(
    "kinds",
    [
        ["reserved", "reserved", "reserved"],
        ["checked_out", "checked_out", "checked_out"],
        ["reserved", "checked_out", "overdue"],
        ["overdue", "overdue", "overdue"],
    ],
)
def test_fourth_active_loan_is_rejected_whatever_mix_of_states(db, loans, kinds):
    member_id = db.member()
    make_active_loans(db, member_id, kinds)
    fourth = db.item(name="Fourth")
    loans_before = db.count(Loan)

    with pytest.raises(LoanLimitExceeded, match="3 active loans"):
        loans.reserve_item(member_id=member_id, item_id=fourth)

    assert db.count(Loan) == loans_before
    assert db.get(Item, fourth).status is ItemStatus.AVAILABLE


def test_finished_loans_do_not_count_towards_the_limit(db, loans):
    member_id = db.member()
    for _ in range(3):
        db.owing(member_id, 0)  # three returned loans with no fee
    make_active_loans(db, member_id, ["reserved", "checked_out"])

    assert loans.reserve_item(member_id=member_id, item_id=db.item(name="Next")).id


@pytest.mark.parametrize(
    ("age", "still_counts"),
    [
        (timedelta(hours=47, minutes=59), True),
        (timedelta(hours=48), False),  # the hold has run out, so it no longer counts
        (timedelta(hours=48, minutes=1), False),
    ],
)
def test_a_lapsed_reservation_stops_counting_towards_the_limit(db, loans, age, still_counts):
    member_id = db.member()
    make_active_loans(db, member_id, ["reserved", "checked_out"])
    db.reserved(member_id, db.item(name="Old hold"), reserved_at=NOW - age)
    wanted = db.item(name="Wanted")

    if still_counts:
        with pytest.raises(LoanLimitExceeded):
            loans.reserve_item(member_id=member_id, item_id=wanted)
    else:
        assert loans.reserve_item(member_id=member_id, item_id=wanted).status is LoanStatus.RESERVED


# --- reservation expiry is enforced when an item is written --------------------------------


@pytest.mark.parametrize(
    ("elapsed", "second_member_succeeds"),
    [
        (timedelta(hours=47, minutes=59), False),
        (timedelta(hours=48), True),
        (timedelta(hours=48, minutes=1), True),
    ],
)
def test_a_lapsed_reservation_frees_the_item_for_someone_else(
    db, loans, clock, elapsed, second_member_succeeds
):
    first, second = db.member(), db.member(name="Second")
    item_id = db.item()
    first_loan = loans.reserve_item(member_id=first, item_id=item_id)
    clock.advance(elapsed)

    if not second_member_succeeds:
        with pytest.raises(InvalidTransition):
            loans.reserve_item(member_id=second, item_id=item_id)
        assert db.get(Loan, first_loan.id).status is LoanStatus.RESERVED
        return

    second_loan = loans.reserve_item(member_id=second, item_id=item_id)

    assert db.get(Loan, first_loan.id).status is LoanStatus.EXPIRED
    assert db.get(Loan, second_loan.id).status is LoanStatus.RESERVED
    assert db.get(Item, item_id).status is ItemStatus.RESERVED
    assert [loan.member_id for loan in db.loans_of_item(item_id)] == [first, second]


def test_the_same_member_can_reserve_again_after_their_hold_lapses(db, loans, clock):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(timedelta(hours=48))

    loans.reserve_item(member_id=member_id, item_id=item_id)

    statuses = [loan.status for loan in db.loans_of_item(item_id)]
    assert statuses == [LoanStatus.EXPIRED, LoanStatus.RESERVED]


# --- failures leave nothing behind ---------------------------------------------------------


def test_database_conflict_is_reported_as_a_conflict_not_a_crash(db, loans, session_factory):
    """If item and loan ever disagree, the unique index is the backstop and the error is clean."""
    holder, other = db.member(), db.member(name="Other")
    item_id = db.item()
    db.reserved(holder, item_id)
    with session_factory() as session, session.begin():
        session.get(Item, item_id).status = ItemStatus.AVAILABLE  # item wrongly says "available"

    with pytest.raises(ConflictError):
        loans.reserve_item(member_id=other, item_id=item_id)

    assert db.count(Loan) == 1


def test_failure_after_the_loan_is_written_rolls_everything_back(db, loans, monkeypatch):
    member_id, item_id = db.member(), db.item()

    def explode(*_args, **_kwargs):
        raise RuntimeError("simulated failure while updating the item")

    monkeypatch.setattr("app.services.loans.items_repo.set_status", explode)

    with pytest.raises(RuntimeError, match="simulated failure"):
        loans.reserve_item(member_id=member_id, item_id=item_id)

    assert db.count(Loan) == 0
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE

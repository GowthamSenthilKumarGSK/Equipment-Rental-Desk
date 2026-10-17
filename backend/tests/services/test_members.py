"""Suspension: reversible, history kept, and it blocks only reserving and checking out."""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from app.domain.enums import BlockReason, ItemStatus, LoanStatus, MemberStatus
from app.domain.errors import EntityNotFound, InvalidTransition, MemberBlocked
from app.models import Item, Member, MemberSuspension
from tests.builders import NOW


def suspensions_of(session_factory, member_id):
    with session_factory() as session:
        statement = (
            sa.select(MemberSuspension)
            .where(MemberSuspension.member_id == member_id)
            .order_by(MemberSuspension.id)
        )
        return list(session.scalars(statement))


def test_suspending_records_when_and_why(db, members, session_factory, clock):
    member_id = db.member()
    clock.advance(timedelta(hours=2))

    member = members.suspend(member_id=member_id, reason="Tool returned damaged")

    assert db.get(Member, member_id).status is MemberStatus.SUSPENDED
    assert member.status is MemberStatus.SUSPENDED
    [row] = suspensions_of(session_factory, member_id)
    assert row.suspended_at == NOW + timedelta(hours=2)
    assert row.lifted_at is None
    assert row.reason == "Tool returned damaged"


def test_reinstating_lifts_the_suspension_and_keeps_the_history(
    db, members, session_factory, clock
):
    member_id = db.member()
    members.suspend(member_id=member_id, reason="First")
    clock.advance(timedelta(days=3))

    members.reinstate(member_id=member_id)
    clock.advance(timedelta(days=1))
    members.suspend(member_id=member_id, reason="Second")

    first, second = suspensions_of(session_factory, member_id)
    assert (first.reason, first.suspended_at, first.lifted_at) == (
        "First",
        NOW,
        NOW + timedelta(days=3),
    )
    assert (second.reason, second.lifted_at) == ("Second", None)
    assert db.get(Member, member_id).status is MemberStatus.SUSPENDED


def test_suspending_twice_or_reinstating_an_active_member_is_an_error(db, members):
    member_id = db.member()

    with pytest.raises(InvalidTransition, match="not suspended"):
        members.reinstate(member_id=member_id)

    members.suspend(member_id=member_id)
    with pytest.raises(InvalidTransition, match="already suspended"):
        members.suspend(member_id=member_id)


def test_unknown_member_is_not_found(members):
    for action in (members.suspend, members.reinstate):
        with pytest.raises(EntityNotFound):
            action(member_id=999)
    for read in (members.standing, members.block_reasons):
        with pytest.raises(EntityNotFound):
            read(999)


def test_suspended_members_cannot_reserve_but_reinstated_members_can(db, loans, members):
    member_id, item_id = db.member(), db.item()
    members.suspend(member_id=member_id)

    with pytest.raises(MemberBlocked) as caught:
        loans.reserve_item(member_id=member_id, item_id=item_id)
    assert caught.value.reasons == (BlockReason.SUSPENDED,)

    members.reinstate(member_id=member_id)
    assert loans.reserve_item(member_id=member_id, item_id=item_id).status is LoanStatus.RESERVED


def test_suspension_does_not_touch_existing_loans_and_returns_still_work(db, loans, members, rent):
    member_id, held, reserved = db.member(), db.item(name="Held"), db.item(name="Reserved")
    rent(member_id, held)
    loans.reserve_item(member_id=member_id, item_id=reserved)

    members.suspend(member_id=member_id)

    assert db.get(Item, held).status is ItemStatus.CHECKED_OUT
    assert db.get(Item, reserved).status is ItemStatus.RESERVED
    assert loans.return_item(item_id=held).status is LoanStatus.RETURNED
    assert loans.cancel_reservation(item_id=reserved).status is LoanStatus.CANCELLED


def test_block_reasons_explain_why_a_member_cannot_borrow(db, members, rent, clock):
    member_id = db.member()
    assert members.block_reasons(member_id) == []

    db.owing(member_id, 10_001)
    members.suspend(member_id=member_id)
    rent_item = db.item()
    db.checked_out(member_id, rent_item, due_at=NOW - timedelta(days=15))

    assert set(members.block_reasons(member_id)) == set(BlockReason)


def test_standing_counts_reserved_and_checked_out_but_not_lapsed_reservations(
    db, loans, members, clock, rent
):
    member_id = db.member()
    rent(member_id, db.item(name="Out"))
    loans.reserve_item(member_id=member_id, item_id=db.item(name="Held"))
    assert members.standing(member_id).active_loan_count == 2

    clock.advance(timedelta(hours=48))  # the reservation lapses; the check-out does not

    standing = members.standing(member_id)
    assert standing.active_loan_count == 1
    assert standing.longest_overdue is None

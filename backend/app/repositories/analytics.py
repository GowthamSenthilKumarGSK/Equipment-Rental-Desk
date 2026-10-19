"""Read-only queries for the analytics dashboard.

Every function here is a plain SELECT that returns small tuples, never ORM objects that a session
could later flush. Nothing is written and nothing is expired: lapsed reservations are left as they
are and the service judges them with the domain rules. The SQL avoids date functions (PostgreSQL and
SQLite disagree on them); the service buckets instants into IST days in Python.

`upto` is "now": events stamped after it (possible only after a request made under a pretend clock)
are not reported, in the period figures and in the running balances alike.
"""

from datetime import datetime
from typing import NamedTuple

import sqlalchemy as sa
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.domain.enums import LoanStatus, MemberStatus
from app.models import Item, Loan, Member, Payment


class ActiveLoanRow(NamedTuple):
    status: LoanStatus
    reserved_at: datetime
    due_at: datetime | None


class OverdueRow(NamedTuple):
    loan_id: int
    member_id: int
    member_name: str
    item_id: int
    item_name: str
    due_at: datetime
    replacement_value_paise: int


class ReturnedRow(NamedTuple):
    due_at: datetime
    returned_at: datetime
    fee_charged_paise: int


class UsageRow(NamedTuple):
    """When an item was handed out and, if it has come back, when."""

    item_id: int
    checked_out_at: datetime
    returned_at: datetime | None


class ReservationRow(NamedTuple):
    item_id: int
    reserved_at: datetime
    checked_out_at: datetime | None
    cancelled_at: datetime | None
    returned_at: datetime | None


class MemberRow(NamedTuple):
    member_id: int
    name: str
    status: MemberStatus


def active_loans(session: Session) -> list[ActiveLoanRow]:
    """Every reserved or checked-out loan (a reserved one may have lapsed without being saved)."""
    statement = sa.select(Loan.status, Loan.reserved_at, Loan.due_at).where(
        Loan.status.in_((LoanStatus.RESERVED, LoanStatus.CHECKED_OUT))
    )
    return [ActiveLoanRow(*row) for row in session.execute(statement)]


def overdue_loans(session: Session, now: datetime) -> list[OverdueRow]:
    """All checked-out loans past their due time, most overdue first. `due_at < now` matches
    `rules.is_overdue` and the overdue list: exactly at the due time is still on time."""
    statement = (
        sa.select(
            Loan.id,
            Loan.member_id,
            Member.name,
            Loan.item_id,
            Item.name,
            Loan.due_at,
            Item.replacement_value_paise,
        )
        .join(Member, Member.id == Loan.member_id)
        .join(Item, Item.id == Loan.item_id)
        .where(Loan.status == LoanStatus.CHECKED_OUT, Loan.due_at < now)
        .order_by(Loan.due_at, Loan.id)
    )
    return [OverdueRow(*row) for row in session.execute(statement)]


def loan_instants(
    session: Session,
    column: InstrumentedAttribute[datetime | None],
    start: datetime,
    end: datetime,
    upto: datetime,
) -> list[datetime]:
    """Values of one loan timestamp column that fall in [start, end) and are not after `upto`."""
    statement = sa.select(column).where(column >= start, column < end, column <= upto)
    return [value for (value,) in session.execute(statement)]


def returned_loans(
    session: Session, start: datetime, end: datetime, upto: datetime
) -> list[ReturnedRow]:
    """Loans returned in [start, end) (not after `upto`) with their due time and the fee charged."""
    statement = sa.select(Loan.due_at, Loan.returned_at, Loan.fee_charged_paise).where(
        Loan.returned_at >= start, Loan.returned_at < end, Loan.returned_at <= upto
    )
    return [ReturnedRow(*row) for row in session.execute(statement)]


def payments_between(
    session: Session, start: datetime, end: datetime, upto: datetime
) -> list[tuple[datetime, int]]:
    """(paid_at, amount in paise) for payments in [start, end), not after `upto`."""
    statement = sa.select(Payment.paid_at, Payment.amount_paise).where(
        Payment.paid_at >= start, Payment.paid_at < end, Payment.paid_at <= upto
    )
    return [(paid_at, amount) for paid_at, amount in session.execute(statement)]


def members(session: Session) -> list[MemberRow]:
    statement = sa.select(Member.id, Member.name, Member.status).order_by(Member.id)
    return [MemberRow(*row) for row in session.execute(statement)]


def fees_by_member(session: Session, upto: datetime) -> dict[int, int]:
    """Total late fees charged to each member by `upto` (a fee is charged when the loan returns)."""
    statement = (
        sa.select(Loan.member_id, sa.func.sum(Loan.fee_charged_paise))
        .where(Loan.returned_at <= upto)
        .group_by(Loan.member_id)
    )
    return {member_id: int(total or 0) for member_id, total in session.execute(statement)}


def payments_by_member(session: Session, upto: datetime) -> dict[int, int]:
    """Total payments received from each member by `upto` (only members who paid appear)."""
    statement = (
        sa.select(Payment.member_id, sa.func.sum(Payment.amount_paise))
        .where(Payment.paid_at <= upto)
        .group_by(Payment.member_id)
    )
    return {member_id: int(total or 0) for member_id, total in session.execute(statement)}


def oldest_due_by_member(session: Session, now: datetime) -> dict[int, datetime]:
    """For each member with an overdue loan, the due time of their most overdue one."""
    statement = (
        sa.select(Loan.member_id, sa.func.min(Loan.due_at))
        .where(Loan.status == LoanStatus.CHECKED_OUT, Loan.due_at < now)
        .group_by(Loan.member_id)
    )
    return {member_id: due_at for member_id, due_at in session.execute(statement)}


def loan_usage(session: Session, start: datetime, end: datetime) -> list[UsageRow]:
    """Every loan that was checked out at some point in [start, end): handed out before `end` and
    not returned until after `start` (or not returned yet). The caller clips them to the periods."""
    statement = sa.select(Loan.item_id, Loan.checked_out_at, Loan.returned_at).where(
        Loan.checked_out_at.is_not(None),
        Loan.checked_out_at < end,
        sa.or_(Loan.returned_at.is_(None), Loan.returned_at > start),
    )
    return [UsageRow(*row) for row in session.execute(statement)]


def reservations_between(
    session: Session, start: datetime, end: datetime, upto: datetime
) -> list[ReservationRow]:
    """Every reservation made in [start, end) and not after `upto`, whatever became of it."""
    statement = sa.select(
        Loan.item_id, Loan.reserved_at, Loan.checked_out_at, Loan.cancelled_at, Loan.returned_at
    ).where(Loan.reserved_at >= start, Loan.reserved_at < end, Loan.reserved_at <= upto)
    return [ReservationRow(*row) for row in session.execute(statement)]


def category_keys(session: Session) -> dict[int, str]:
    """Each item's category folded to lower case by the database's own `lower()`.

    This is the expression the `category` filter of `GET /items` applies to the column, so items
    share a key here exactly when that filter's database side cannot tell them apart. (SQLite
    folds only ASCII letters; PostgreSQL folds by its locale.)
    """
    statement = sa.select(Item.id, sa.func.lower(Item.category))
    return {item_id: key for item_id, key in session.execute(statement)}

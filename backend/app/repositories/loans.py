from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import ACTIVE_LOAN_STATUSES, LoanStatus
from app.models import Loan


def add(session: Session, loan: Loan) -> None:
    session.add(loan)
    session.flush()


def active_for_item(session: Session, item_id: int) -> Loan | None:
    """The item's reserved or checked-out loan. The partial unique index allows at most one.

    The row is always re-read: if the session loaded this loan earlier (before taking a lock),
    `populate_existing` replaces that cached copy with what is in the database now, so a change a
    competing request committed in the meantime is not hidden by stale in-memory state.
    """
    statement = (
        sa.select(Loan)
        .where(Loan.item_id == item_id, Loan.status.in_(ACTIVE_LOAN_STATUSES))
        .execution_options(populate_existing=True)
    )
    return session.scalars(statement).one_or_none()


def active_for_member(session: Session, member_id: int) -> list[Loan]:
    """The member's reserved and checked-out loans (a reserved one may have lapsed unnoticed)."""
    statement = sa.select(Loan).where(
        Loan.member_id == member_id, Loan.status.in_(ACTIVE_LOAN_STATUSES)
    )
    return list(session.scalars(statement))


def reserved_before(session: Session, cutoff: datetime, item_id: int | None = None) -> list[Loan]:
    """Reserved loans made at or before `cutoff` (i.e. whose hold has run out)."""
    statement = sa.select(Loan).where(
        Loan.status == LoanStatus.RESERVED, Loan.reserved_at <= cutoff
    )
    if item_id is not None:
        statement = statement.where(Loan.item_id == item_id)
    return list(session.scalars(statement))


def for_member(session: Session, member_id: int) -> list[Loan]:
    """Every loan the member has had, newest first, with the item loaded."""
    statement = (
        sa.select(Loan)
        .where(Loan.member_id == member_id)
        .options(joinedload(Loan.item))
        .order_by(Loan.reserved_at.desc(), Loan.id.desc())
    )
    return list(session.scalars(statement))


def overdue(session: Session, now: datetime, limit: int, offset: int) -> tuple[list[Loan], int]:
    """One page of checked-out loans past their due time (oldest due first) and the total.

    `due_at < now` is the same test as `rules.is_overdue`: exactly at the due time is still on time.
    """
    condition = sa.and_(Loan.status == LoanStatus.CHECKED_OUT, Loan.due_at < now)
    total = session.scalar(sa.select(sa.func.count()).select_from(Loan).where(condition))
    page = (
        sa.select(Loan)
        .where(condition)
        .options(joinedload(Loan.member), joinedload(Loan.item))
        .order_by(Loan.due_at, Loan.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(page).unique()), total

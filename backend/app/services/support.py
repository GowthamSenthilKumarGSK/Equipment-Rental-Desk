"""Helpers shared by the use cases: locked lookups, reservation expiry, and a member's standing."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.enums import ItemAction, ItemStatus, LoanAction, LoanStatus
from app.domain.errors import EntityNotFound, InvalidTransition
from app.domain.policy import RESERVATION_HOLD
from app.domain.rules import (
    effective_item_status,
    is_overdue,
    is_reservation_expired,
    next_item_status,
    next_loan_status,
)
from app.models import Item, Loan, Member
from app.repositories import items as items_repo
from app.repositories import loans as loans_repo
from app.repositories import members as members_repo


@dataclass(frozen=True)
class MemberStanding:
    """What the rules need to know about a member at one moment."""

    balance_paise: int
    active_loan_count: int  # reserved (unexpired) + checked out, which includes overdue
    longest_overdue: timedelta | None  # how far past due the most overdue loan is


def locked_member(session: Session, member_id: int) -> Member:
    member = members_repo.get_for_update(session, member_id)
    if member is None:
        raise EntityNotFound(f"Member {member_id} not found")
    return member


def locked_item(session: Session, item_id: int) -> Item:
    item = items_repo.get_for_update(session, item_id)
    if item is None:
        raise EntityNotFound(f"Item {item_id} not found")
    return item


def current_item_status(item: Item, active_loan: Loan | None, now: datetime) -> ItemStatus:
    """The item's status at `now`: a lapsed reservation is available, a late loan is overdue."""
    return effective_item_status(
        item.status,
        now=now,
        reserved_at=active_loan.reserved_at if active_loan else None,
        due_at=active_loan.due_at if active_loan else None,
    )


def member_standing(session: Session, member_id: int, now: datetime) -> MemberStanding:
    """Balance, active loans and worst overdue for a member. Reads only; never writes."""
    active = loans_repo.active_for_member(session, member_id)
    counted = [
        loan
        for loan in active
        if loan.status is LoanStatus.CHECKED_OUT
        or not is_reservation_expired(loan.reserved_at, now)
    ]
    overdue_by = [
        now - loan.due_at
        for loan in active
        if loan.status is LoanStatus.CHECKED_OUT and is_overdue(loan.due_at, now)
    ]
    return MemberStanding(
        balance_paise=members_repo.balance_paise(session, member_id),
        active_loan_count=len(counted),
        longest_overdue=max(overdue_by, default=None),
    )


def expire_stale_reservations(session: Session, now: datetime, item_id: int | None = None) -> int:
    """Persist expiry: lapsed reservations become EXPIRED and their items AVAILABLE again.

    With `item_id` only that item is looked at (the cheap case used before every write on an item);
    without it, every lapsed reservation is. Each item is locked first and re-checked, so a
    reservation that was checked out a moment ago is never expired by mistake. Returns the count.
    """
    candidates = loans_repo.reserved_before(session, now - RESERVATION_HOLD, item_id)
    expired = 0
    for candidate_item_id in sorted({loan.item_id for loan in candidates}):
        item = locked_item(session, candidate_item_id)
        loan = loans_repo.active_for_item(session, candidate_item_id)
        if loan is None or loan.status is not LoanStatus.RESERVED:
            continue
        if not is_reservation_expired(loan.reserved_at, now):
            continue
        loan.status = next_loan_status(loan.status, LoanAction.EXPIRE)
        if item.status is ItemStatus.RESERVED:
            new_status = next_item_status(item.status, ItemAction.EXPIRE_RESERVATION)
            items_repo.set_status(session, item, new_status)
        session.flush()
        expired += 1
    return expired


def active_loan_after_expiry(
    session: Session, item_id: int, now: datetime
) -> tuple[Loan | None, bool]:
    """The item's active loan once lapsed reservations are cleared, and whether one just lapsed.

    The item must already be locked. When the second value is True the item's reservation ran out
    and has now been marked expired; callers keep that change and then report ReservationExpired.
    """
    before = loans_repo.active_for_item(session, item_id)
    expire_stale_reservations(session, now, item_id)
    after = loans_repo.active_for_item(session, item_id)
    lapsed = before is not None and after is None and before.status is LoanStatus.EXPIRED
    return after, lapsed


def require_not_before(now: datetime, earlier: datetime, action: str) -> None:
    """Reject a clock reading from before the event it follows (e.g. a test clock moved back)."""
    if now < earlier:
        raise InvalidTransition(
            f"Cannot {action}: the current time {now.isoformat()} is earlier than "
            f"{earlier.isoformat()}"
        )

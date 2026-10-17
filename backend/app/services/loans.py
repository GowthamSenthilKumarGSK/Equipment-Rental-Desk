"""Use cases that move a loan and its item together: reserve, check out, return, cancel.

Every public method is one database transaction. It locks the rows it changes (member, then item,
always in that order), clears lapsed reservations, checks the rules, and writes the loan and the
item together, so either both change or neither does.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db import transaction
from app.domain.enums import ItemAction, LoanAction, LoanStatus
from app.domain.errors import (
    ConflictError,
    EntityNotFound,
    InvalidTransition,
    ReservationExpired,
)
from app.domain.rules import (
    calculate_late_fee_paise,
    ensure_member_can_transact,
    ensure_within_loan_limit,
    late_fee_days,
    loan_due_at,
    next_item_status,
    next_loan_status,
)
from app.models import Loan
from app.repositories import items as items_repo
from app.repositories import loans as loans_repo
from app.services.support import (
    active_loan_after_expiry,
    current_item_status,
    expire_stale_reservations,
    locked_item,
    locked_member,
    member_standing,
    require_not_before,
)
from app.services.views import OverdueLoan, Page


def _is_active_loan_conflict(error: IntegrityError) -> bool:
    """True if the database refused a second active loan for one item (PostgreSQL or SQLite)."""
    message = str(error.orig)
    return (
        "uq_loans_one_active_per_item" in message
        or "UNIQUE constraint failed: loans.item_id" in message
    )


class LoanService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

    def reserve_item(self, *, member_id: int, item_id: int) -> Loan:
        """Hold an available item for a member for 48 hours."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = locked_member(session, member_id)
            item = locked_item(session, item_id)
            active_loan, _ = active_loan_after_expiry(session, item_id, now)

            standing = member_standing(session, member_id, now)
            ensure_member_can_transact(
                status=member.status,
                balance_paise=standing.balance_paise,
                longest_overdue=standing.longest_overdue,
            )
            ensure_within_loan_limit(standing.active_loan_count)
            new_item_status = next_item_status(
                current_item_status(item, active_loan, now), ItemAction.RESERVE
            )

            loan = Loan(
                member_id=member.id, item_id=item.id, status=LoanStatus.RESERVED, reserved_at=now
            )
            try:
                loans_repo.add(session, loan)
            except IntegrityError as error:
                if _is_active_loan_conflict(error):
                    raise ConflictError(
                        f"Item {item_id} was reserved by another request"
                    ) from error
                raise
            items_repo.set_status(session, item, new_item_status)
            return loan

    def check_out(self, *, item_id: int) -> Loan:
        """Hand over a reserved item. The due date is seven days from now."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            loan = self._check_out(session, item_id, now)
        if loan is None:
            raise ReservationExpired(f"The reservation on item {item_id} has expired")
        return loan

    def _check_out(self, session: Session, item_id: int, now) -> Loan | None:
        """Returns the loan, or None if the reservation had lapsed (the expiry is still saved)."""
        if items_repo.get(session, item_id) is None:
            raise EntityNotFound(f"Item {item_id} not found")
        # Lock order is member, then item. The member is only known from the loan, so read it
        # first without a lock and check again once both rows are held.
        seen = loans_repo.active_for_item(session, item_id)
        member = locked_member(session, seen.member_id) if seen else None
        item = locked_item(session, item_id)
        loan, lapsed = active_loan_after_expiry(session, item_id, now)

        if lapsed:
            return None
        if loan is None:
            raise InvalidTransition(
                f"Item {item_id} cannot be checked out: it has no active reservation "
                f"(status: {item.status.value})"
            )
        if member is None or loan.member_id != member.id:
            raise ConflictError(f"The reservation on item {item_id} changed; please retry")

        new_loan_status = next_loan_status(loan.status, LoanAction.CHECK_OUT)
        require_not_before(now, loan.reserved_at, "check out")
        standing = member_standing(session, member.id, now)
        ensure_member_can_transact(
            status=member.status,
            balance_paise=standing.balance_paise,
            longest_overdue=standing.longest_overdue,
        )
        new_item_status = next_item_status(
            current_item_status(item, loan, now), ItemAction.CHECK_OUT
        )

        loan.status = new_loan_status
        loan.checked_out_at = now
        loan.due_at = loan_due_at(now)
        items_repo.set_status(session, item, new_item_status)
        return loan

    def return_item(self, *, item_id: int) -> Loan:
        """Take back a checked-out item and charge any late fee to the member's balance."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item = locked_item(session, item_id)
            loan, _ = active_loan_after_expiry(session, item_id, now)
            if loan is None:
                raise InvalidTransition(
                    f"Item {item_id} is not checked out (status: {item.status.value})"
                )

            new_loan_status = next_loan_status(loan.status, LoanAction.RETURN)
            require_not_before(now, loan.checked_out_at, "return")
            fee = calculate_late_fee_paise(loan.due_at, now, item.replacement_value_paise)
            new_item_status = next_item_status(
                current_item_status(item, loan, now), ItemAction.RETURN
            )

            loan.status = new_loan_status
            loan.returned_at = now
            loan.fee_charged_paise = fee
            items_repo.set_status(session, item, new_item_status)
            return loan

    def cancel_reservation(self, *, item_id: int) -> Loan:
        """Give up a reservation before collecting the item. Only valid for a reserved loan."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            loan = self._cancel(session, item_id, now)
        if loan is None:
            raise ReservationExpired(f"The reservation on item {item_id} has expired")
        return loan

    def _cancel(self, session: Session, item_id: int, now) -> Loan | None:
        """Returns the cancelled loan, or None if it had already lapsed (the expiry is saved)."""
        item = locked_item(session, item_id)
        loan, lapsed = active_loan_after_expiry(session, item_id, now)
        if lapsed:
            return None
        if loan is None:
            raise InvalidTransition(
                f"Item {item_id} has no reservation to cancel (status: {item.status.value})"
            )

        new_loan_status = next_loan_status(loan.status, LoanAction.CANCEL)
        require_not_before(now, loan.reserved_at, "cancel")
        new_item_status = next_item_status(
            current_item_status(item, loan, now), ItemAction.CANCEL_RESERVATION
        )

        loan.status = new_loan_status
        loan.cancelled_at = now
        items_repo.set_status(session, item, new_item_status)
        return loan

    def overdue_loans(self, *, limit: int, offset: int) -> Page[OverdueLoan]:
        """Checked-out loans past their due time, longest overdue first, with the fee so far."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            loans, total = loans_repo.overdue(session, now, limit, offset)
            rows = [
                OverdueLoan(
                    loan=loan,
                    member_name=loan.member.name,
                    member_phone=loan.member.phone,
                    item_name=loan.item.name,
                    days_overdue=late_fee_days(loan.due_at, now),
                    fee_if_returned_now_paise=calculate_late_fee_paise(
                        loan.due_at, now, loan.item.replacement_value_paise
                    ),
                )
                for loan in loans
            ]
            return Page(items=rows, total=total)

    def expire_stale_reservations(self) -> int:
        """Save the expiry of every lapsed reservation now (writes on an item also do this)."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            return expire_stale_reservations(session, now)

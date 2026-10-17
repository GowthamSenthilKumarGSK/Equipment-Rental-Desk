"""Member use cases: catalogue, suspension, payments, statement, and "why can't they borrow?"."""

from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.clock import IST, Clock
from app.db import transaction
from app.domain.enums import BlockReason, LoanStatus, MemberStatus
from app.domain.errors import DeletionBlocked, EntityNotFound, InvalidTransition
from app.domain.rules import (
    effective_loan_status,
    has_reached_loan_limit,
    is_overdue,
    late_fee_days,
    member_block_reasons,
    validate_payment,
)
from app.models import Member, MemberSuspension, Payment
from app.repositories import loans as loans_repo
from app.repositories import members as members_repo
from app.repositories import payments as payments_repo
from app.services.support import MemberStanding, locked_member, member_standing, require_not_before
from app.services.views import MemberView, Page, Statement, StatementLoan


class MemberService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

    # --- catalogue ---------------------------------------------------------------------------

    def create_member(self, *, name: str, phone: str, join_date: date | None = None) -> Member:
        """Register a member. They start out active; the join date defaults to today in IST."""
        today = self._clock.now().astimezone(IST).date()
        with transaction(self._session_factory) as session:
            member = Member(
                name=name,
                phone=phone,
                join_date=join_date or today,
                status=MemberStatus.ACTIVE,
            )
            members_repo.add(session, member)
            return member

    def get_member(self, member_id: int) -> MemberView:
        """A member with their balance, active-loan count and any reasons they are blocked."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = members_repo.get(session, member_id)
            if member is None:
                raise EntityNotFound(f"Member {member_id} not found")
            return self._view(session, member, now)

    def list_members(
        self,
        *,
        status: MemberStatus | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> Page[Member]:
        with transaction(self._session_factory) as session:
            members, total = members_repo.find(
                session, status=status, search=search, limit=limit, offset=offset
            )
            return Page(items=members, total=total)

    def update_member(
        self, *, member_id: int, name: str | None = None, phone: str | None = None
    ) -> Member:
        """Change a member's name or phone. Only the arguments given (not None) are changed.

        Status changes go through suspend and reinstate, which keep the suspension history.
        """
        with transaction(self._session_factory) as session:
            member = locked_member(session, member_id)
            if name is not None:
                member.name = name
            if phone is not None:
                member.phone = phone
            session.flush()
            return member

    def delete_member(self, *, member_id: int) -> None:
        """Remove a member who has no loans, payments or suspensions. Others must be kept."""
        with transaction(self._session_factory) as session:
            member = locked_member(session, member_id)
            if members_repo.has_history(session, member_id):
                raise DeletionBlocked(
                    f"Member {member_id} has history and cannot be deleted; suspend them instead"
                )
            members_repo.delete(session, member)

    # --- suspension --------------------------------------------------------------------------

    def suspend(self, *, member_id: int, reason: str | None = None) -> Member:
        """Stop a member reserving or checking out. Their loans and history are kept."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = locked_member(session, member_id)
            if member.status is MemberStatus.SUSPENDED:
                raise InvalidTransition(f"Member {member_id} is already suspended")
            member.status = MemberStatus.SUSPENDED
            session.add(MemberSuspension(member_id=member.id, suspended_at=now, reason=reason))
            session.flush()
            return member

    def reinstate(self, *, member_id: int) -> Member:
        """Lift a suspension. The suspension row stays as history, marked as lifted."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = locked_member(session, member_id)
            if member.status is not MemberStatus.SUSPENDED:
                raise InvalidTransition(f"Member {member_id} is not suspended")
            suspension = members_repo.open_suspension(session, member_id)
            if suspension is not None:
                require_not_before(now, suspension.suspended_at, "reinstate")
                suspension.lifted_at = now
            member.status = MemberStatus.ACTIVE
            session.flush()
            return member

    # --- money -------------------------------------------------------------------------------

    def record_payment(
        self, *, member_id: int, amount_paise: int, note: str | None = None
    ) -> Payment:
        """Record money received towards fees. Overpayment is rejected, not kept as credit."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            locked_member(session, member_id)  # serialises payments, so two cannot overpay together
            validate_payment(amount_paise, members_repo.balance_paise(session, member_id))
            payment = Payment(
                member_id=member_id, amount_paise=amount_paise, paid_at=now, note=note
            )
            payments_repo.add(session, payment)
            return payment

    def balance_paise(self, member_id: int) -> int:
        """Outstanding fees: charged at return, minus payments."""
        with transaction(self._session_factory) as session:
            if members_repo.get(session, member_id) is None:
                raise EntityNotFound(f"Member {member_id} not found")
            return members_repo.balance_paise(session, member_id)

    def statement(self, member_id: int) -> Statement:
        """Everything about a member's account: loans, fees, payments and the balance."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = members_repo.get(session, member_id)
            if member is None:
                raise EntityNotFound(f"Member {member_id} not found")
            standing = member_standing(session, member_id, now)
            loans = loans_repo.for_member(session, member_id)
            payments = payments_repo.for_member(session, member_id)

            statement_loans = []
            for loan in loans:
                overdue = loan.status is LoanStatus.CHECKED_OUT and is_overdue(loan.due_at, now)
                statement_loans.append(
                    StatementLoan(
                        loan=loan,
                        item_name=loan.item.name,
                        status=effective_loan_status(
                            loan.status, reserved_at=loan.reserved_at, now=now
                        ),
                        is_overdue=overdue,
                        days_overdue=late_fee_days(loan.due_at, now) if overdue else 0,
                    )
                )
            return Statement(
                member=member,
                balance_paise=standing.balance_paise,
                total_fees_paise=sum(loan.fee_charged_paise for loan in loans),
                total_payments_paise=sum(payment.amount_paise for payment in payments),
                active_loan_count=standing.active_loan_count,
                longest_overdue=standing.longest_overdue,
                block_reasons=self._block_reasons(member, standing),
                at_loan_limit=has_reached_loan_limit(standing.active_loan_count),
                loans=statement_loans,
                payments=payments,
            )

    def standing(self, member_id: int) -> MemberStanding:
        """Balance, active loans and worst overdue, as the rules see them right now."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            if members_repo.get(session, member_id) is None:
                raise EntityNotFound(f"Member {member_id} not found")
            return member_standing(session, member_id, now)

    def block_reasons(self, member_id: int) -> list[BlockReason]:
        """Why this member cannot reserve or check out right now (empty if they can)."""
        return self.get_member(member_id).block_reasons

    # --- helpers -----------------------------------------------------------------------------

    @staticmethod
    def _block_reasons(member: Member, standing: MemberStanding) -> list[BlockReason]:
        return member_block_reasons(
            status=member.status,
            balance_paise=standing.balance_paise,
            longest_overdue=standing.longest_overdue,
        )

    def _view(self, session: Session, member: Member, now) -> MemberView:
        standing = member_standing(session, member.id, now)
        return MemberView(
            member=member,
            balance_paise=standing.balance_paise,
            active_loan_count=standing.active_loan_count,
            block_reasons=self._block_reasons(member, standing),
            at_loan_limit=has_reached_loan_limit(standing.active_loan_count),
        )

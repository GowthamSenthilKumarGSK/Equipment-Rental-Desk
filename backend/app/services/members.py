"""Member use cases: suspension, payments, and the facts behind "why can't they borrow?"."""

from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db import transaction
from app.domain.enums import BlockReason, MemberStatus
from app.domain.errors import EntityNotFound, InvalidTransition
from app.domain.rules import member_block_reasons, validate_payment
from app.models import Member, MemberSuspension, Payment
from app.repositories import members as members_repo
from app.repositories import payments as payments_repo
from app.services.support import MemberStanding, locked_member, member_standing, require_not_before


class MemberService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

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

    def standing(self, member_id: int) -> MemberStanding:
        """Balance, active loans and worst overdue, as the rules see them right now."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            if members_repo.get(session, member_id) is None:
                raise EntityNotFound(f"Member {member_id} not found")
            return member_standing(session, member_id, now)

    def block_reasons(self, member_id: int) -> list[BlockReason]:
        """Why this member cannot reserve or check out right now (empty if they can)."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            member = members_repo.get(session, member_id)
            if member is None:
                raise EntityNotFound(f"Member {member_id} not found")
            standing = member_standing(session, member_id, now)
            return member_block_reasons(
                status=member.status,
                balance_paise=standing.balance_paise,
                longest_overdue=standing.longest_overdue,
            )

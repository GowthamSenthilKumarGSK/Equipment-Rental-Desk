"""Fixtures for service tests: real services on a real database, driven by a fixed clock."""

from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa

from app.clock import FixedClock
from app.domain.enums import ItemStatus, LoanStatus
from app.domain.policy import LOAN_PERIOD
from app.models import Item, Loan, Member, Payment
from app.services.items import ItemService
from app.services.loans import LoanService
from app.services.members import MemberService
from tests.builders import NOW, add_item, add_loan, add_member, add_payment


class Db:
    """Arrange and inspect database state around the services, each call in its own transaction."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _create(self, build) -> int:
        with self.session_factory() as session, session.begin():
            return build(session).id

    def member(self, **fields) -> int:
        return self._create(lambda s: add_member(s, **fields))

    def item(self, **fields) -> int:
        return self._create(lambda s: add_item(s, **fields))

    def reserved(self, member_id: int, item_id: int, reserved_at: datetime = NOW) -> int:
        """An existing reservation (loan and item both marked reserved)."""

        def build(session):
            item = session.get(Item, item_id)
            item.status = ItemStatus.RESERVED
            return add_loan(
                session,
                session.get(Member, member_id),
                item,
                LoanStatus.RESERVED,
                reserved_at=reserved_at,
            )

        return self._create(build)

    def checked_out(self, member_id: int, item_id: int, due_at: datetime) -> int:
        """An existing check-out that is due at `due_at` (overdue if that is in the past)."""

        def build(session):
            item = session.get(Item, item_id)
            item.status = ItemStatus.CHECKED_OUT
            checked_out_at = due_at - LOAN_PERIOD
            return add_loan(
                session,
                session.get(Member, member_id),
                item,
                LoanStatus.CHECKED_OUT,
                reserved_at=checked_out_at - timedelta(hours=1),
                checked_out_at=checked_out_at,
                due_at=due_at,
            )

        return self._create(build)

    def owing(self, member_id: int, paise: int) -> int:
        """Give the member an outstanding balance, via a past returned loan that charged a fee."""

        def build(session):
            item = add_item(session, name="Past loan item")
            return add_loan(
                session,
                session.get(Member, member_id),
                item,
                LoanStatus.RETURNED,
                reserved_at=NOW - timedelta(days=60),
                checked_out_at=NOW - timedelta(days=59),
                due_at=NOW - timedelta(days=52),
                returned_at=NOW - timedelta(days=50),
                fee_charged_paise=paise,
            )

        return self._create(build)

    def payment(self, member_id: int, amount_paise: int) -> int:
        return self._create(lambda s: add_payment(s, s.get(Member, member_id), amount_paise))

    def get(self, model, row_id: int):
        with self.session_factory() as session:
            return session.get(model, row_id)

    def loans_of_item(self, item_id: int) -> list[Loan]:
        with self.session_factory() as session:
            statement = sa.select(Loan).where(Loan.item_id == item_id).order_by(Loan.id)
            return list(session.scalars(statement))

    def count(self, model) -> int:
        with self.session_factory() as session:
            return session.scalar(sa.select(sa.func.count()).select_from(model))

    def payments_of(self, member_id: int) -> list[Payment]:
        with self.session_factory() as session:
            statement = sa.select(Payment).where(Payment.member_id == member_id)
            return list(session.scalars(statement))


@pytest.fixture
def clock():
    return FixedClock(NOW)


@pytest.fixture
def db(session_factory):
    return Db(session_factory)


@pytest.fixture
def loans(session_factory, clock):
    return LoanService(session_factory, clock)


@pytest.fixture
def items(session_factory, clock):
    return ItemService(session_factory, clock)


@pytest.fixture
def members(session_factory, clock):
    return MemberService(session_factory, clock)


@pytest.fixture
def rent(loans):
    """Reserve and check out an item through the real services, at the clock's current time."""

    def _rent(member_id: int, item_id: int) -> Loan:
        loans.reserve_item(member_id=member_id, item_id=item_id)
        return loans.check_out(item_id=item_id)

    return _rent

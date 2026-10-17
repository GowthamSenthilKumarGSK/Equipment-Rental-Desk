import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Loan, Member, MemberSuspension, Payment


def get(session: Session, member_id: int) -> Member | None:
    return session.get(Member, member_id)


def get_for_update(session: Session, member_id: int) -> Member | None:
    """Load the member and lock the row until the transaction ends (PostgreSQL).

    SQLite ignores FOR UPDATE; app.db makes its transactions exclusive instead.
    """
    statement = (
        sa.select(Member)
        .where(Member.id == member_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return session.scalars(statement).one_or_none()


def balance_paise(session: Session, member_id: int) -> int:
    """Outstanding balance: fees charged on returned loans minus payments received."""
    fees = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Loan.fee_charged_paise), 0)).where(
            Loan.member_id == member_id
        )
    )
    paid = session.scalar(
        sa.select(sa.func.coalesce(sa.func.sum(Payment.amount_paise), 0)).where(
            Payment.member_id == member_id
        )
    )
    return fees - paid


def open_suspension(session: Session, member_id: int) -> MemberSuspension | None:
    statement = sa.select(MemberSuspension).where(
        MemberSuspension.member_id == member_id, MemberSuspension.lifted_at.is_(None)
    )
    return session.scalars(statement).one_or_none()

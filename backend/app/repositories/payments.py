import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Payment


def add(session: Session, payment: Payment) -> None:
    session.add(payment)
    session.flush()


def for_member(session: Session, member_id: int) -> list[Payment]:
    """Every payment the member has made, newest first."""
    statement = (
        sa.select(Payment)
        .where(Payment.member_id == member_id)
        .order_by(Payment.paid_at.desc(), Payment.id.desc())
    )
    return list(session.scalars(statement))

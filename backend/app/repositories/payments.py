from sqlalchemy.orm import Session

from app.models import Payment


def add(session: Session, payment: Payment) -> None:
    session.add(payment)
    session.flush()

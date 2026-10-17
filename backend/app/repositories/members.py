import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domain.enums import MemberStatus
from app.models import Loan, Member, MemberSuspension, Payment


def add(session: Session, member: Member) -> None:
    session.add(member)
    session.flush()


def delete(session: Session, member: Member) -> None:
    session.delete(member)
    session.flush()


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


def find(
    session: Session,
    *,
    status: MemberStatus | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Member], int]:
    """One page of members (by name) and the total number that match the filters."""
    conditions = []
    if status is not None:
        conditions.append(Member.status == status)
    if search:
        conditions.append(
            sa.or_(
                Member.name.icontains(search, autoescape=True),
                Member.phone.icontains(search, autoescape=True),
            )
        )
    total = session.scalar(sa.select(sa.func.count()).select_from(Member).where(*conditions))
    page = (
        sa.select(Member)
        .where(*conditions)
        .order_by(Member.name, Member.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(page)), total


def has_history(session: Session, member_id: int) -> bool:
    """True if the member has any loan, payment or suspension, which must never be lost."""
    return any(
        session.scalar(sa.select(sa.exists().where(model.member_id == member_id)))
        for model in (Loan, Payment, MemberSuspension)
    )


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

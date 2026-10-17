from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import MemberStatus
from app.models.base import Base, enum_column, in_list_sql
from app.models.types import UtcDateTime


class Member(Base):
    """A registered borrower.

    The fee balance is not stored: it is derived as SUM(loans.fee_charged_paise) minus
    SUM(payments.amount_paise), so it can never drift from the ledger rows.
    `status` is the current state; every suspension is also kept in `member_suspensions`.
    """

    __tablename__ = "members"
    __table_args__ = (
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint(in_list_sql("status", tuple(MemberStatus)), name="status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    phone: Mapped[str] = mapped_column(sa.String(20))
    join_date: Mapped[date]
    status: Mapped[MemberStatus] = mapped_column(
        enum_column(MemberStatus),
        default=MemberStatus.ACTIVE,
        server_default=MemberStatus.ACTIVE.value,
    )

    loans = relationship("Loan", back_populates="member")
    payments = relationship("Payment", back_populates="member")
    suspensions = relationship("MemberSuspension", back_populates="member")


class MemberSuspension(Base):
    """One row per suspension; `lifted_at` is NULL while the suspension is in force."""

    __tablename__ = "member_suspensions"
    __table_args__ = (
        sa.CheckConstraint(
            "lifted_at IS NULL OR lifted_at >= suspended_at", name="lifted_after_suspended"
        ),
        # At most one open suspension per member.
        sa.Index(
            "uq_member_suspensions_one_open",
            "member_id",
            unique=True,
            postgresql_where=sa.text("lifted_at IS NULL"),
            sqlite_where=sa.text("lifted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(sa.ForeignKey("members.id", ondelete="RESTRICT"))
    suspended_at: Mapped[datetime] = mapped_column(UtcDateTime)
    lifted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    reason: Mapped[str | None] = mapped_column(sa.String(200))

    member = relationship("Member", back_populates="suspensions")

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ACTIVE_LOAN_STATUSES, LoanStatus
from app.models.base import Base, enum_column, in_list_sql
from app.models.types import UtcDateTime

_ACTIVE = in_list_sql("status", ACTIVE_LOAN_STATUSES)

# Which timestamps must be set (and which must be empty) in each lifecycle status.
_STATUS_TIMESTAMPS = (
    "(status = 'reserved' AND checked_out_at IS NULL AND due_at IS NULL"
    " AND returned_at IS NULL AND cancelled_at IS NULL)"
    " OR (status = 'checked_out' AND checked_out_at IS NOT NULL AND due_at IS NOT NULL"
    " AND returned_at IS NULL AND cancelled_at IS NULL)"
    " OR (status = 'returned' AND checked_out_at IS NOT NULL AND due_at IS NOT NULL"
    " AND returned_at IS NOT NULL AND cancelled_at IS NULL)"
    " OR (status = 'cancelled' AND checked_out_at IS NULL AND due_at IS NULL"
    " AND returned_at IS NULL AND cancelled_at IS NOT NULL)"
    " OR (status = 'expired' AND checked_out_at IS NULL AND due_at IS NULL"
    " AND returned_at IS NULL AND cancelled_at IS NULL)"
)


class Loan(Base):
    """One reservation-to-return lifecycle of an item for a member.

    There is no OVERDUE status: a loan is overdue when status = 'checked_out' and now > due_at.
    An expired reservation keeps status 'reserved' until a write marks it 'expired'; its real
    expiry time is reserved_at + 48h, so readers must not trust 'reserved' alone.
    `fee_charged_paise` is 0 until the loan is returned.
    """

    __tablename__ = "loans"
    __table_args__ = (
        sa.CheckConstraint(in_list_sql("status", tuple(LoanStatus)), name="status_valid"),
        sa.CheckConstraint(_STATUS_TIMESTAMPS, name="status_matches_timestamps"),
        sa.CheckConstraint("due_at IS NULL OR due_at > checked_out_at", name="due_after_checkout"),
        sa.CheckConstraint(
            "returned_at IS NULL OR returned_at >= checked_out_at", name="return_after_checkout"
        ),
        sa.CheckConstraint(
            "checked_out_at IS NULL OR checked_out_at >= reserved_at",
            name="checkout_after_reservation",
        ),
        sa.CheckConstraint("fee_charged_paise >= 0", name="fee_not_negative"),
        sa.CheckConstraint(
            "fee_charged_paise = 0 OR status = 'returned'", name="fee_only_when_returned"
        ),
        # One open reservation or check-out per item. A partial unique index is supported by both
        # PostgreSQL and SQLite; see README "Database notes" for how concurrency differs.
        sa.Index(
            "uq_loans_one_active_per_item",
            "item_id",
            unique=True,
            postgresql_where=sa.text(_ACTIVE),
            sqlite_where=sa.text(_ACTIVE),
        ),
        sa.Index("ix_loans_member_status", "member_id", "status"),
        sa.Index("ix_loans_item_id", "item_id"),
        # Overdue dashboard: checked-out loans ordered by due date.
        sa.Index(
            "ix_loans_checked_out_due_at",
            "due_at",
            postgresql_where=sa.text("status = 'checked_out'"),
            sqlite_where=sa.text("status = 'checked_out'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(sa.ForeignKey("members.id", ondelete="RESTRICT"))
    item_id: Mapped[int] = mapped_column(sa.ForeignKey("items.id", ondelete="RESTRICT"))
    status: Mapped[LoanStatus] = mapped_column(enum_column(LoanStatus))
    reserved_at: Mapped[datetime] = mapped_column(UtcDateTime)
    checked_out_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    due_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    returned_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    fee_charged_paise: Mapped[int] = mapped_column(default=0, server_default="0")

    member = relationship("Member", back_populates="loans")
    item = relationship("Item", back_populates="loans")

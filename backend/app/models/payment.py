from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import UtcDateTime


class Payment(Base):
    """Money received from a member to clear fees. Rows are never updated or deleted."""

    __tablename__ = "payments"
    __table_args__ = (
        sa.CheckConstraint("amount_paise > 0", name="amount_positive"),
        sa.Index("ix_payments_member_paid_at", "member_id", "paid_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(sa.ForeignKey("members.id", ondelete="RESTRICT"))
    amount_paise: Mapped[int]
    paid_at: Mapped[datetime] = mapped_column(UtcDateTime)
    note: Mapped[str | None] = mapped_column(sa.String(200))

    member = relationship("Member", back_populates="payments")

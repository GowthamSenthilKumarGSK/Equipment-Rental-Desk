import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import STORED_ITEM_STATUSES, ItemStatus
from app.models.base import Base, enum_column, in_list_sql


class Item(Base):
    """A piece of equipment.

    `status` holds only persisted states. OVERDUE is derived from the open loan's due_at and is
    rejected by the CHECK constraint. A RESERVED item whose 48h hold has lapsed may still say
    RESERVED here until the next write cleans it up; readers must use effective_item_status.
    """

    __tablename__ = "items"
    __table_args__ = (
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("replacement_value_paise > 0", name="replacement_value_positive"),
        sa.CheckConstraint(in_list_sql("status", STORED_ITEM_STATUSES), name="status_valid"),
        sa.Index("ix_items_status", "status"),
        sa.Index("ix_items_category", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    category: Mapped[str] = mapped_column(sa.String(50))
    replacement_value_paise: Mapped[int]
    condition_note: Mapped[str] = mapped_column(sa.Text, default="", server_default="")
    status: Mapped[ItemStatus] = mapped_column(
        enum_column(ItemStatus),
        default=ItemStatus.AVAILABLE,
        server_default=ItemStatus.AVAILABLE.value,
    )

    loans = relationship("Loan", back_populates="item")

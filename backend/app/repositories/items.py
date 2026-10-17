import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domain.enums import ItemStatus
from app.models import Item


def get(session: Session, item_id: int) -> Item | None:
    return session.get(Item, item_id)


def get_for_update(session: Session, item_id: int) -> Item | None:
    """Load the item and lock the row until the transaction ends (PostgreSQL).

    SQLite ignores FOR UPDATE; app.db makes its transactions exclusive instead.
    """
    statement = (
        sa.select(Item)
        .where(Item.id == item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return session.scalars(statement).one_or_none()


def set_status(session: Session, item: Item, status: ItemStatus) -> None:
    item.status = status
    session.flush()

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domain.enums import ACTIVE_LOAN_STATUSES, ItemStatus
from app.models import Item, Loan


def add(session: Session, item: Item) -> None:
    session.add(item)
    session.flush()


def delete(session: Session, item: Item) -> None:
    session.delete(item)
    session.flush()


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


def find_with_active_loan(
    session: Session, *, category: str | None, search: str | None
) -> list[tuple[Item, Loan | None]]:
    """Items (by name) with their reserved or checked-out loan, if any.

    The status filter is not applied here: an item's status depends on the clock, so the service
    works it out with the domain rule instead of repeating that rule in SQL.
    """
    statement = (
        sa.select(Item, Loan)
        .outerjoin(Loan, sa.and_(Loan.item_id == Item.id, Loan.status.in_(ACTIVE_LOAN_STATUSES)))
        .order_by(Item.name, Item.id)
    )
    if category:
        statement = statement.where(sa.func.lower(Item.category) == category.lower())
    if search:
        statement = statement.where(Item.name.icontains(search, autoescape=True))
    return [(item, loan) for item, loan in session.execute(statement)]


def has_loans(session: Session, item_id: int) -> bool:
    """True if the item has ever been reserved or lent; that history must never be lost."""
    return bool(session.scalar(sa.select(sa.exists().where(Loan.item_id == item_id))))


def set_status(session: Session, item: Item, status: ItemStatus) -> None:
    item.status = status
    session.flush()

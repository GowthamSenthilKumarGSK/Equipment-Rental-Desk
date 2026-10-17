"""Item use cases that are not loans: catalogue (create, read, update, delete) and maintenance."""

from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db import transaction
from app.domain.enums import ItemAction, ItemStatus, LoanAction, LoanStatus
from app.domain.errors import DeletionBlocked, EntityNotFound
from app.domain.rules import next_item_status, next_loan_status
from app.models import Item
from app.repositories import items as items_repo
from app.repositories import loans as loans_repo
from app.services.support import (
    active_loan_after_expiry,
    current_item_status,
    locked_item,
    require_not_before,
)
from app.services.views import ItemView, Page


class ItemService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

    # --- catalogue ---------------------------------------------------------------------------

    def create_item(
        self, *, name: str, category: str, replacement_value_paise: int, condition_note: str = ""
    ) -> ItemView:
        """Add an item to the library. It starts out available."""
        with transaction(self._session_factory) as session:
            item = Item(
                name=name,
                category=category,
                replacement_value_paise=replacement_value_paise,
                condition_note=condition_note,
                status=ItemStatus.AVAILABLE,
            )
            items_repo.add(session, item)
            return ItemView(item=item, status=ItemStatus.AVAILABLE, current_loan=None)

    def get_item(self, item_id: int) -> ItemView:
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item = items_repo.get(session, item_id)
            if item is None:
                raise EntityNotFound(f"Item {item_id} not found")
            loan = loans_repo.active_for_item(session, item_id)
            return ItemView(item, current_item_status(item, loan, now), loan)

    def list_items(
        self,
        *,
        status: ItemStatus | None = None,
        category: str | None = None,
        search: str | None = None,
        limit: int,
        offset: int,
    ) -> Page[ItemView]:
        """One page of items. `status` is the status as of now, so it can be OVERDUE.

        The status filter is applied here with the domain rule rather than in SQL, so a lapsed
        reservation or a late loan is judged exactly as everywhere else. That means filtering by
        status reads every item matching the other filters; fine for a library, not for millions.
        """
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            rows = items_repo.find_with_active_loan(session, category=category, search=search)
            views = [
                ItemView(item, current_item_status(item, loan, now), loan) for item, loan in rows
            ]
            if status is not None:
                views = [view for view in views if view.status is status]
            return Page(items=views[offset : offset + limit], total=len(views))

    def update_item(
        self,
        *,
        item_id: int,
        name: str | None = None,
        category: str | None = None,
        replacement_value_paise: int | None = None,
        condition_note: str | None = None,
    ) -> ItemView:
        """Change an item's details. Only the arguments given (not None) are changed.

        The item's state is not editable here; it moves only through reserve, check out, return
        and maintenance.
        """
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item = locked_item(session, item_id)
            changes = {
                "name": name,
                "category": category,
                "replacement_value_paise": replacement_value_paise,
                "condition_note": condition_note,
            }
            for field, value in changes.items():
                if value is not None:
                    setattr(item, field, value)
            session.flush()
            loan = loans_repo.active_for_item(session, item_id)
            return ItemView(item, current_item_status(item, loan, now), loan)

    def delete_item(self, *, item_id: int) -> None:
        """Remove an item that has never been reserved or lent. Items with history cannot go."""
        with transaction(self._session_factory) as session:
            item = locked_item(session, item_id)
            if items_repo.has_loans(session, item_id):
                raise DeletionBlocked(
                    f"Item {item_id} has loan history and cannot be deleted; "
                    "put it under maintenance to take it out of use"
                )
            items_repo.delete(session, item)

    # --- status and maintenance --------------------------------------------------------------

    def item_status(self, item_id: int) -> ItemStatus:
        """The status to show now: a lapsed reservation reads as available, a late loan as overdue.

        This only reads; the database row is left as it is until the next write on the item.
        """
        return self.get_item(item_id).status

    def start_maintenance(self, *, item_id: int) -> Item:
        """Take an item out of circulation, from any state except already under maintenance.

        A reservation is cancelled (its loan is kept as history). A checked-out loan stays open so
        it can still be returned and charged; the item then stays under maintenance.
        """
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item = locked_item(session, item_id)
            loan, _ = active_loan_after_expiry(session, item_id, now)
            new_item_status = next_item_status(
                current_item_status(item, loan, now), ItemAction.START_MAINTENANCE
            )
            if loan is not None and loan.status is LoanStatus.RESERVED:
                loan.status = next_loan_status(loan.status, LoanAction.CANCEL)
                require_not_before(now, loan.reserved_at, "start maintenance")
                loan.cancelled_at = now
            items_repo.set_status(session, item, new_item_status)
            return item

    def finish_maintenance(self, *, item_id: int) -> Item:
        """Put a repaired item back in circulation. Refused while a member still has it on loan."""
        with transaction(self._session_factory) as session:
            item = locked_item(session, item_id)
            open_loan = loans_repo.active_for_item(session, item_id)
            new_item_status = next_item_status(
                item.status, ItemAction.FINISH_MAINTENANCE, has_open_loan=open_loan is not None
            )
            items_repo.set_status(session, item, new_item_status)
            return item

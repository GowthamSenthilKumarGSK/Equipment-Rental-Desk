"""Item use cases that are not loans: reading the live status, and maintenance."""

from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db import transaction
from app.domain.enums import ItemAction, ItemStatus, LoanAction, LoanStatus
from app.domain.errors import EntityNotFound
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


class ItemService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

    def item_status(self, item_id: int) -> ItemStatus:
        """The status to show now: a lapsed reservation reads as available, a late loan as overdue.

        This only reads; the database row is left as it is until the next write on the item.
        """
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item = items_repo.get(session, item_id)
            if item is None:
                raise EntityNotFound(f"Item {item_id} not found")
            return current_item_status(item, loans_repo.active_for_item(session, item_id), now)

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

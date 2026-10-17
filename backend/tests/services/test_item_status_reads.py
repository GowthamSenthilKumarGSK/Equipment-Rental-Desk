"""Reading an item's status applies expiry and overdue at the time of the read, without writing."""

from datetime import timedelta

import pytest

from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import EntityNotFound
from app.models import Item, Loan
from tests.builders import NOW

LOAN_PERIOD = timedelta(days=7)


def test_unknown_item_is_not_found(items):
    with pytest.raises(EntityNotFound):
        items.item_status(999)


def test_available_stays_available(db, items, clock):
    item_id = db.item()
    clock.advance(timedelta(days=100))

    assert items.item_status(item_id) is ItemStatus.AVAILABLE


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(0), ItemStatus.RESERVED),
        (timedelta(hours=47, minutes=59), ItemStatus.RESERVED),
        (timedelta(hours=48), ItemStatus.AVAILABLE),
        (timedelta(hours=48, minutes=1), ItemStatus.AVAILABLE),
    ],
)
def test_a_lapsed_reservation_reads_as_available_without_any_job_running(
    db, loans, items, clock, elapsed, expected
):
    member_id, item_id = db.member(), db.item()
    reserved = loans.reserve_item(member_id=member_id, item_id=item_id)
    clock.advance(elapsed)

    assert items.item_status(item_id) is expected
    # Reading did not write: the stored rows still say "reserved".
    assert db.get(Item, item_id).status is ItemStatus.RESERVED
    assert db.get(Loan, reserved.id).status is LoanStatus.RESERVED


@pytest.mark.parametrize(
    ("offset_from_due", "expected"),
    [
        (-timedelta(seconds=1), ItemStatus.CHECKED_OUT),
        (timedelta(0), ItemStatus.CHECKED_OUT),
        (timedelta(seconds=1), ItemStatus.OVERDUE),
        (timedelta(days=30), ItemStatus.OVERDUE),
    ],
)
def test_a_checked_out_item_becomes_overdue_only_after_its_due_time(
    db, items, clock, rent, offset_from_due, expected
):
    member_id, item_id = db.member(), db.item()
    rent(member_id, item_id)
    clock.advance(LOAN_PERIOD + offset_from_due)

    assert items.item_status(item_id) is expected
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT  # overdue is never stored


def test_the_sweep_saves_every_lapsed_reservation_at_once(db, loans, clock):
    member_id = db.member()
    items_held = [db.item(name=f"Item {n}") for n in range(3)]
    for item_id in items_held:
        loans.reserve_item(member_id=member_id, item_id=item_id)
        clock.advance(timedelta(hours=10))
    # reserved at NOW, NOW+10h, NOW+20h; now it is NOW+30h
    clock.advance(timedelta(hours=18))  # NOW+48h: only the first has lapsed

    assert loans.expire_stale_reservations() == 1
    assert loans.expire_stale_reservations() == 0  # nothing left to do

    first, second, third = (db.loans_of_item(i)[0] for i in items_held)
    assert (first.status, second.status, third.status) == (
        LoanStatus.EXPIRED,
        LoanStatus.RESERVED,
        LoanStatus.RESERVED,
    )
    assert db.get(Item, items_held[0]).status is ItemStatus.AVAILABLE
    assert db.get(Item, items_held[1]).status is ItemStatus.RESERVED
    assert NOW  # the fixed clock started at NOW

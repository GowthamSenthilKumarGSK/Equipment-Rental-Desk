"""Deterministic replays of races where one request waits and another commits in the meantime.

A request that waits for a row lock has already read some rows by the time it gets the lock. These
tests replay that order of events exactly, with no threads and no timing: a hook runs the
competing request to completion just before the waiting request takes its lock.

What they show: after the locks are held the services act on the *current* rows, not on copies the
session cached earlier, so the loser gets a clean domain error and nothing is overwritten.

What they do not show: that PostgreSQL's `SELECT ... FOR UPDATE` really blocks and releases the way
this assumes. On SQLite `FOR UPDATE` is ignored, and the services here use plain deferred
transactions (no `BEGIN IMMEDIATE`) so the competing request can commit mid-way. On PostgreSQL the
same replay runs, but only a real concurrent run there would exercise the locks themselves.
"""

from datetime import timedelta

import pytest
import sqlalchemy as sa

import app.services.loans as loans_module
import app.services.support as support_module
from app.clock import FixedClock
from app.db import make_session_factory
from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import InvalidTransition
from app.models import Item
from app.services.loans import LoanService
from tests.builders import NOW


@pytest.fixture
def deferred_factory(database_url):
    """Sessions whose transactions start lazily, so another request can commit during one."""
    engine = sa.create_engine(database_url)
    yield make_session_factory(engine)
    engine.dispose()


def run_rival_before_first_call(monkeypatch, module, function_name, rival):
    """Make `rival()` run to completion just before `module.function_name` is first called."""
    real = getattr(module, function_name)
    fired = []

    def wrapper(*args, **kwargs):
        if not fired:
            fired.append(True)
            rival()
        return real(*args, **kwargs)

    monkeypatch.setattr(module, function_name, wrapper)
    return fired


def test_second_check_out_that_waited_for_the_lock_gets_a_clean_domain_error(
    db, deferred_factory, monkeypatch
):
    member_id, item_id = db.member(), db.item()
    LoanService(deferred_factory, FixedClock(NOW)).reserve_item(
        member_id=member_id, item_id=item_id
    )
    rival_time = NOW + timedelta(hours=1)
    waiting = LoanService(deferred_factory, FixedClock(NOW + timedelta(hours=2)))
    rival = LoanService(deferred_factory, FixedClock(rival_time))
    fired = run_rival_before_first_call(
        monkeypatch,
        loans_module,
        "locked_member",  # the waiting request has read the reserved loan, but not locked yet
        lambda: rival.check_out(item_id=item_id),
    )

    with pytest.raises(InvalidTransition, match="Cannot check out a loan that is checked out"):
        waiting.check_out(item_id=item_id)

    assert fired, "the rival never ran, so this test did not exercise the interleaving"
    [loan] = db.loans_of_item(item_id)
    assert loan.status is LoanStatus.CHECKED_OUT
    assert loan.checked_out_at == rival_time  # not overwritten by the loser's later time
    assert loan.due_at == rival_time + timedelta(days=7)
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT


def test_expiry_sweep_that_loaded_a_reservation_does_not_expire_it_after_it_was_checked_out(
    db, deferred_factory, monkeypatch
):
    """The sweep reads lapsed reservations first and locks each item afterwards.

    A check-out that committed in between (made at 47h59m, before the hold lapsed) must be seen as
    it is now: still checked out, not expired.
    """
    member_id, item_id = db.member(), db.item()
    LoanService(deferred_factory, FixedClock(NOW)).reserve_item(
        member_id=member_id, item_id=item_id
    )
    checked_out_at = NOW + timedelta(hours=47, minutes=59)
    rival = LoanService(deferred_factory, FixedClock(checked_out_at))
    sweeper = LoanService(deferred_factory, FixedClock(NOW + timedelta(hours=48)))
    fired = run_rival_before_first_call(
        monkeypatch,
        support_module,
        "locked_item",  # the sweep has listed the lapsed reservation, but not locked its item yet
        lambda: rival.check_out(item_id=item_id),
    )

    expired = sweeper.expire_stale_reservations()

    assert fired, "the rival never ran, so this test did not exercise the interleaving"
    assert expired == 0
    [loan] = db.loans_of_item(item_id)
    assert loan.status is LoanStatus.CHECKED_OUT
    assert loan.checked_out_at == checked_out_at
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT

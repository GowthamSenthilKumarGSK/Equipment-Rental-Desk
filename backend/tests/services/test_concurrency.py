"""Several requests hitting the services at the same instant, from separate threads.

Each call opens its own database connection and transaction. What protects the data differs by
database (see README "Database notes"):
- PostgreSQL: row locks (`SELECT ... FOR UPDATE`) on the member and item, plus the partial unique
  index as a backstop. Callers that lose wait for the winner and then see the new state.
- SQLite: every transaction takes the database write lock first, so they run one after another.
The assertions below are the same for both; only the mechanism differs.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from app.domain.enums import ItemStatus, LoanStatus
from app.domain.errors import (
    ConflictError,
    InvalidTransition,
    LoanLimitExceeded,
    PaymentExceedsBalance,
)
from app.models import Item, Loan
from tests.builders import NOW

CONTENDERS = 4


def run_together(calls):
    """Start every call at the same moment; return each result or the exception it raised."""
    barrier = threading.Barrier(len(calls))

    def run(call):
        barrier.wait()
        try:
            return call()
        except Exception as error:  # reported to the test, which asserts on the types
            return error

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        futures = [pool.submit(run, call) for call in calls]
        return [future.result() for future in futures]


def split(outcomes, success_type):
    winners = [o for o in outcomes if isinstance(o, success_type)]
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(winners) + len(losers) == len(outcomes), outcomes
    return winners, losers


def test_two_check_outs_of_the_same_item_at_once_only_one_succeeds(db, loans):
    member_id, item_id = db.member(), db.item()
    loans.reserve_item(member_id=member_id, item_id=item_id)

    outcomes = run_together([lambda: loans.check_out(item_id=item_id)] * CONTENDERS)

    winners, losers = split(outcomes, Loan)
    assert len(winners) == 1
    assert all(isinstance(error, (InvalidTransition, ConflictError)) for error in losers), losers
    [stored] = db.loans_of_item(item_id)
    assert stored.status is LoanStatus.CHECKED_OUT
    assert stored.due_at == stored.checked_out_at + timedelta(days=7)
    assert db.get(Item, item_id).status is ItemStatus.CHECKED_OUT


def test_two_members_reserving_the_same_item_at_once_only_one_gets_it(db, loans):
    member_ids = [db.member(name=f"Member {n}") for n in range(CONTENDERS)]
    item_id = db.item()

    outcomes = run_together(
        [lambda m=m: loans.reserve_item(member_id=m, item_id=item_id) for m in member_ids]
    )

    winners, losers = split(outcomes, Loan)
    assert len(winners) == 1
    assert all(isinstance(error, (InvalidTransition, ConflictError)) for error in losers), losers
    active = [loan for loan in db.loans_of_item(item_id) if loan.status is LoanStatus.RESERVED]
    assert [loan.member_id for loan in active] == [winners[0].member_id]
    assert db.get(Item, item_id).status is ItemStatus.RESERVED


def test_one_member_cannot_slip_past_the_three_loan_limit_by_reserving_in_parallel(db, loans):
    member_id = db.member()
    for n in range(2):
        db.reserved(member_id, db.item(name=f"Held {n}"))
    wanted = [db.item(name=f"Wanted {n}") for n in range(CONTENDERS)]

    outcomes = run_together(
        [lambda i=i: loans.reserve_item(member_id=member_id, item_id=i) for i in wanted]
    )

    winners, losers = split(outcomes, Loan)
    assert len(winners) == 1  # only one slot was left
    assert all(isinstance(error, LoanLimitExceeded) for error in losers), losers
    reserved_total = sum(
        loan.status is LoanStatus.RESERVED
        for item_id in wanted
        for loan in db.loans_of_item(item_id)
    )
    assert reserved_total == 1


def test_two_returns_of_the_same_item_at_once_charge_the_fee_once(db, loans, members, clock, rent):
    member_id, item_id = db.member(), db.item(replacement_value_paise=650_000)
    rent(member_id, item_id)
    clock.advance(timedelta(days=7, hours=30))  # 2 late days

    outcomes = run_together([lambda: loans.return_item(item_id=item_id)] * CONTENDERS)

    winners, losers = split(outcomes, Loan)
    assert len(winners) == 1
    assert all(isinstance(error, InvalidTransition) for error in losers), losers
    assert members.balance_paise(member_id) == 2_000
    assert db.get(Item, item_id).status is ItemStatus.AVAILABLE


def test_parallel_payments_cannot_together_pay_more_than_is_owed(db, members):
    member_id = db.member()
    db.owing(member_id, 10_000)

    outcomes = run_together(
        [lambda: members.record_payment(member_id=member_id, amount_paise=10_000)] * CONTENDERS
    )

    paid = [o for o in outcomes if not isinstance(o, Exception)]
    errors = [o for o in outcomes if isinstance(o, Exception)]
    assert len(paid) == 1
    assert all(isinstance(error, PaymentExceedsBalance) for error in errors), errors
    assert len(db.payments_of(member_id)) == 1
    assert members.balance_paise(member_id) == 0


def test_reservation_that_lapses_at_the_same_moment_is_handed_to_exactly_one_member(
    db, loans, clock
):
    first = db.member(name="First")
    challengers = [db.member(name=f"Challenger {n}") for n in range(CONTENDERS)]
    item_id = db.item()
    loans.reserve_item(member_id=first, item_id=item_id)
    clock.advance(timedelta(hours=48))  # the first hold is over at exactly this moment

    outcomes = run_together(
        [lambda m=m: loans.reserve_item(member_id=m, item_id=item_id) for m in challengers]
    )

    winners, losers = split(outcomes, Loan)
    assert len(winners) == 1
    assert all(isinstance(error, (InvalidTransition, ConflictError)) for error in losers), losers
    statuses = [loan.status for loan in db.loans_of_item(item_id)]
    assert statuses == [LoanStatus.EXPIRED, LoanStatus.RESERVED]
    assert NOW  # the fixed clock started at NOW

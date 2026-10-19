"""Helpers for the analytics tests: insert history directly, call the endpoints, watch the database.

History (returned loans months ago, payments on exact boundaries) is inserted straight into the
database, because the API only ever writes "now". The endpoints under test are always called through
HTTP, like a client would.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta

import sqlalchemy as sa

from app.domain.enums import ItemStatus, LoanStatus, MemberStatus
from app.models import Item, Member
from tests.api.conftest import LOAN_PERIOD
from tests.builders import NOW, add_item, add_loan, add_member, add_payment

TABLES = ("members", "items", "loans", "payments", "member_suspensions")


def fetch(api, name: str, at: datetime | None = NOW, **params) -> dict:
    """GET /analytics/<name> and return the JSON, insisting on a 200."""
    query = "&".join(f"{key}={value}" for key, value in params.items())
    response = api.get(f"/analytics/{name}" + (f"?{query}" if query else ""), at=at)
    assert response.status_code == 200, response.text
    return response.json()


def run(session_factory, build):
    """Run `build(session)` in its own transaction and return what it returns."""
    with session_factory() as session, session.begin():
        return build(session)


def new_member(session_factory, **fields) -> int:
    return run(session_factory, lambda s: add_member(s, **fields).id)


def new_item(session_factory, **fields) -> int:
    return run(session_factory, lambda s: add_item(s, **fields).id)


def checked_out_loan(
    session_factory,
    member_id: int,
    item_id: int,
    due_at: datetime,
    item_status: ItemStatus = ItemStatus.CHECKED_OUT,
) -> int:
    """A loan checked out a loan period before `due_at` (overdue if `due_at` is in the past)."""
    checked_out_at = due_at - LOAN_PERIOD

    def build(session):
        item = session.get(Item, item_id)
        item.status = item_status
        return add_loan(
            session,
            session.get(Member, member_id),
            item,
            LoanStatus.CHECKED_OUT,
            reserved_at=checked_out_at - timedelta(hours=1),
            checked_out_at=checked_out_at,
            due_at=due_at,
        ).id

    return run(session_factory, build)


def returned_loan(
    session_factory,
    member_id: int,
    item_id: int,
    *,
    due_at: datetime,
    returned_at: datetime,
    fee_paise: int = 0,
    checked_out_at: datetime | None = None,
) -> int:
    checked_out_at = checked_out_at or due_at - LOAN_PERIOD

    def build(session):
        return add_loan(
            session,
            session.get(Member, member_id),
            session.get(Item, item_id),
            LoanStatus.RETURNED,
            reserved_at=checked_out_at - timedelta(hours=1),
            checked_out_at=checked_out_at,
            due_at=due_at,
            returned_at=returned_at,
            fee_charged_paise=fee_paise,
        ).id

    return run(session_factory, build)


def reservation(
    session_factory,
    member_id: int,
    item_id: int,
    reserved_at: datetime,
    status: LoanStatus = LoanStatus.RESERVED,
) -> int:
    """A reservation row; for RESERVED the item is marked reserved too, like the services do.
    A CANCELLED one was cancelled an hour after it was made."""

    def build(session):
        item = session.get(Item, item_id)
        if status is LoanStatus.RESERVED:
            item.status = ItemStatus.RESERVED
        extra = (
            {"cancelled_at": reserved_at + timedelta(hours=1)}
            if status is LoanStatus.CANCELLED
            else {}
        )
        return add_loan(
            session, session.get(Member, member_id), item, status, reserved_at=reserved_at, **extra
        ).id

    return run(session_factory, build)


def payment(session_factory, member_id: int, paid_at: datetime, amount_paise: int) -> int:
    return run(
        session_factory,
        lambda s: add_payment(s, s.get(Member, member_id), amount_paise, paid_at=paid_at).id,
    )


def suspended_member(session_factory, **fields) -> int:
    return new_member(session_factory, status=MemberStatus.SUSPENDED, **fields)


def snapshot(session_factory) -> dict[str, list[tuple]]:
    """Every row of every table, to prove that a request changed nothing."""
    with session_factory() as session:
        return {
            table: [
                tuple(row) for row in session.execute(sa.text(f"SELECT * FROM {table} ORDER BY 1"))
            ]
            for table in TABLES
        }


@contextmanager
def captured_sql(session_factory):
    """Collect every SQL statement sent to the database while the block runs."""
    engine = session_factory.kw["bind"]
    statements: list[str] = []

    def listener(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", listener)
    try:
        yield statements
    finally:
        sa.event.remove(engine, "before_cursor_execute", listener)


def api_member_view(api, member_id: int, at: datetime = NOW) -> dict:
    response = api.get(f"/members/{member_id}", at=at)
    assert response.status_code == 200, response.text
    return response.json()


def api_statement(api, member_id: int, at: datetime = NOW) -> dict:
    response = api.get(f"/members/{member_id}/statement", at=at)
    assert response.status_code == 200, response.text
    return response.json()

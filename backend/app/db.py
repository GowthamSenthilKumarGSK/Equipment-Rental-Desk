"""Engine, session and transaction helpers.

Repositories receive a Session; only services decide where a transaction starts and ends.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def make_engine(url: str | None = None) -> sa.Engine:
    # hide_parameters keeps bound values (names, phone numbers) out of database error messages.
    engine = sa.create_engine(
        url or get_settings().sqlalchemy_url, pool_pre_ping=True, hide_parameters=True
    )
    if engine.dialect.name == "sqlite":
        sa.event.listen(engine, "connect", _configure_sqlite_connection)
        sa.event.listen(engine, "begin", _begin_sqlite_immediately)
    return engine


def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
    # Stop the driver from guessing when to BEGIN; _begin_sqlite_immediately does it explicitly.
    dbapi_connection.isolation_level = None
    # SQLite ignores foreign keys unless asked, per connection. PostgreSQL always enforces them.
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


def _begin_sqlite_immediately(connection) -> None:
    """Every SQLite transaction takes the database's write lock when it starts.

    SQLite has no row locks (`SELECT ... FOR UPDATE` is ignored), so concurrent use cases are
    serialised whole instead: a second transaction waits (up to the driver's busy timeout) until the
    first commits. Without this, two transactions could both read "available" and then both write.
    """
    connection.exec_driver_sql("BEGIN IMMEDIATE")


def make_session_factory(engine: sa.Engine) -> sessionmaker[Session]:
    # expire_on_commit=False keeps returned objects readable after the service's transaction ends.
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """One unit of work: commit when the block ends, roll back if it raises."""
    with session_factory() as session, session.begin():
        yield session


@contextmanager
def session_scope(engine: sa.Engine) -> Iterator[Session]:
    """One transaction: commit on success, roll back on any exception."""
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

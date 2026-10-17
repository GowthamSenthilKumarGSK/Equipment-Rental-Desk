"""Engine and session helpers. Repositories and services receive a Session; they never build one."""

from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.config import get_settings


def make_engine(url: str | None = None) -> sa.Engine:
    engine = sa.create_engine(url or get_settings().sqlalchemy_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked, per connection. PostgreSQL always enforces them.
        sa.event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


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

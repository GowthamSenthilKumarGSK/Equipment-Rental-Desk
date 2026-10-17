"""Database fixtures.

By default the DB tests run on a throwaway SQLite file, so `pytest` works with nothing installed.
Set TEST_DATABASE_URL to a PostgreSQL database whose name contains "test" to run the same tests
against PostgreSQL (CI does both). The schema always comes from the Alembic migration, never from
`create_all`, so the migration itself is what gets tested.
"""

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.config import to_sqlalchemy_url
from app.db import make_engine
from app.models import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def alembic_config(url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def drop_everything(engine: sa.Engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture(scope="session")
def database_url(tmp_path_factory) -> str:
    configured = os.environ.get("TEST_DATABASE_URL")
    if not configured:
        return f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.sqlite3'}"
    url = to_sqlalchemy_url(configured)
    database_name = sa.engine.make_url(url).database or ""
    if "test" not in database_name:
        # The fixtures drop every table, so refuse anything that is not obviously a test database.
        pytest.exit(
            f"TEST_DATABASE_URL must point at a database whose name contains 'test' "
            f"(got '{database_name}')",
            returncode=2,
        )
    return url


@pytest.fixture(scope="session")
def migrated_engine(database_url):
    engine = make_engine(database_url)
    drop_everything(engine)
    command.upgrade(alembic_config(database_url), "head")
    yield engine
    drop_everything(engine)
    engine.dispose()


@pytest.fixture
def session(migrated_engine):
    """A session on the migrated schema; every table is emptied again after the test."""
    with Session(migrated_engine) as db_session:
        yield db_session
        db_session.rollback()
    with migrated_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())

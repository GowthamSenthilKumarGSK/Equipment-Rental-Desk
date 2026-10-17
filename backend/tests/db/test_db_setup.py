"""The repeatable `python -m app.db_setup` workflow, run against its own throwaway SQLite file."""

import pytest
import sqlalchemy as sa

from app import db_setup
from app.config import get_settings


@pytest.fixture
def setup_database_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'setup.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def run(monkeypatch, *args: str) -> None:
    monkeypatch.setattr("sys.argv", ["db_setup", *args])
    db_setup.main()


def counts(url: str) -> dict[str, int]:
    engine = sa.create_engine(url)
    with engine.connect() as connection:
        result = {
            table: connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}"))
            for table in ("members", "items", "loans", "payments")
        }
    engine.dispose()
    return result


def test_first_run_migrates_and_seeds(setup_database_url, monkeypatch):
    run(monkeypatch)

    assert counts(setup_database_url) == {"members": 10, "items": 13, "loans": 15, "payments": 2}


def test_running_again_changes_nothing(setup_database_url, monkeypatch):
    run(monkeypatch)
    first = counts(setup_database_url)

    run(monkeypatch)

    assert counts(setup_database_url) == first


def test_reset_wipes_and_reseeds(setup_database_url, monkeypatch):
    run(monkeypatch)
    engine = sa.create_engine(setup_database_url)
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM payments"))
    engine.dispose()

    run(monkeypatch, "--reset")

    assert counts(setup_database_url)["payments"] == 2

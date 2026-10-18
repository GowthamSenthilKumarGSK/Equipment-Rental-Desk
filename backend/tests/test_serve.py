"""Container start-up: wait for the database, migrate, seed only an empty one, then serve.

The steps run against a throwaway SQLite file. What they cannot show is PostgreSQL behaviour (the
CI container job runs the real image against PostgreSQL) or Docker itself.
"""

import logging

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from app import db_setup, serve
from app.config import get_settings


@pytest.fixture
def database_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'serve.sqlite3'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    yield url
    get_settings.cache_clear()


def counts(url: str) -> dict[str, int]:
    engine = sa.create_engine(url)
    with engine.connect() as connection:
        result = {
            table: connection.scalar(sa.text(f"SELECT COUNT(*) FROM {table}"))
            for table in ("members", "items", "loans", "payments")
        }
    engine.dispose()
    return result


def execute(url: str, statement: str) -> None:
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text(statement))
    engine.dispose()


def scalars(url: str, statement: str) -> list:
    engine = sa.create_engine(url)
    with engine.connect() as connection:
        values = list(connection.scalars(sa.text(statement)))
    engine.dispose()
    return values


SEEDED = {"members": 10, "items": 13, "loans": 15, "payments": 2}
EMPTY = {"members": 0, "items": 0, "loans": 0, "payments": 0}


# --- preparing the database -------------------------------------------------------------------


def test_an_empty_database_is_migrated_and_seeded(database_url):
    serve.prepare_database(seed=True)

    assert counts(database_url) == SEEDED


def test_with_seeding_off_the_schema_is_created_and_no_rows_are(database_url):
    serve.prepare_database(seed=False)

    assert counts(database_url) == EMPTY


def test_every_restart_is_safe_and_changes_nothing(database_url):
    serve.prepare_database(seed=True)
    first = counts(database_url)

    for _ in range(3):
        serve.prepare_database(seed=True)

    assert counts(database_url) == first


def test_a_restart_never_overwrites_or_restores_existing_data(database_url):
    serve.prepare_database(seed=True)
    execute(database_url, "UPDATE members SET name = 'Edited By A Reviewer' WHERE id = 1")
    execute(database_url, "DELETE FROM payments")
    execute(
        database_url,
        "INSERT INTO payments (member_id, amount_paise, paid_at, note) "
        "VALUES (1, 100, '2026-10-12 10:00:00', 'new')",
    )

    serve.prepare_database(seed=True)

    assert scalars(database_url, "SELECT name FROM members WHERE id = 1") == [
        "Edited By A Reviewer"
    ]
    assert scalars(database_url, "SELECT note FROM payments") == ["new"]  # seed payments not back


def test_a_database_that_has_other_data_is_not_seeded_over(database_url):
    serve.prepare_database(seed=False)
    execute(
        database_url,
        "INSERT INTO items (name, category, replacement_value_paise, condition_note, status) "
        "VALUES ('Mine', 'Tools', 1000, '', 'available')",
    )

    serve.prepare_database(seed=True)

    assert counts(database_url) == {"members": 0, "items": 1, "loans": 0, "payments": 0}


def test_start_up_never_resets_the_database(database_url, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("start-up must never reset the database")

    monkeypatch.setattr(db_setup, "reset_and_seed", refuse)
    monkeypatch.setattr(db_setup, "delete_all_rows", refuse)

    serve.prepare_database(seed=True)
    serve.prepare_database(seed=True)


def test_the_manual_reset_command_still_works(database_url, monkeypatch):
    serve.prepare_database(seed=True)
    execute(database_url, "DELETE FROM payments")
    monkeypatch.setattr("sys.argv", ["db_setup", "--reset"])

    db_setup.main()

    assert counts(database_url) == SEEDED


# --- main(): the order of things ---------------------------------------------------------------


def test_main_prepares_the_database_before_it_starts_listening(monkeypatch):
    events = []
    monkeypatch.setattr(serve, "prepare_database", lambda *, seed: events.append(("prepare", seed)))
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: events.append(("run", a, k)))
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("SEED_ON_START", "true")
    get_settings.cache_clear()

    serve.main()
    get_settings.cache_clear()

    assert events == [
        ("prepare", True),
        ("run", ("app.main:app",), {"host": "0.0.0.0", "port": 10000}),
    ]


def test_main_does_not_seed_unless_asked(monkeypatch):
    seen = []
    monkeypatch.setattr(serve, "prepare_database", lambda *, seed: seen.append(seed))
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: None)
    monkeypatch.setenv("SEED_ON_START", "false")
    get_settings.cache_clear()

    serve.main()
    get_settings.cache_clear()

    assert seen == [False]


def test_the_api_is_not_started_if_preparing_the_database_fails(monkeypatch):
    started = []

    def fail(*, seed):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(serve, "prepare_database", fail)
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: started.append(True))

    with pytest.raises(RuntimeError):
        serve.main()

    assert started == []


# --- waiting for the database ------------------------------------------------------------------


class WorkingConnection:
    """What `engine.connect()` returns once the database answers: usable in a `with` block."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, statement):
        return None


class FlakyEngine:
    """Refuses connections `failures` times, then works. Counts how often it was disposed."""

    def __init__(self, state):
        self.state = state

    def connect(self):
        self.state["calls"] += 1
        if self.state["calls"] <= self.state["failures"]:
            raise OperationalError(
                "SELECT 1", {}, Exception("could not connect to server at db.example.test")
            )
        return WorkingConnection()

    def dispose(self):
        self.state["disposed"] += 1


def flaky(monkeypatch, failures):
    state = {"calls": 0, "failures": failures, "disposed": 0}
    monkeypatch.setattr(serve, "make_engine", lambda: FlakyEngine(state))
    return state


def test_it_waits_and_retries_until_the_database_answers(monkeypatch):
    state = flaky(monkeypatch, failures=2)
    sleeps = []

    serve.wait_for_database(attempts=5, delay=1.5, sleep=sleeps.append)

    assert state["calls"] == 3
    assert sleeps == [1.5, 1.5]
    assert state["disposed"] == 3  # every attempt's engine is cleaned up


def test_it_gives_up_after_the_last_attempt_without_a_pointless_wait(monkeypatch):
    state = flaky(monkeypatch, failures=99)
    sleeps = []

    with pytest.raises(OperationalError):
        serve.wait_for_database(attempts=3, delay=1.0, sleep=sleeps.append)

    assert state["calls"] == 3
    assert sleeps == [1.0, 1.0]


def test_the_wait_logs_the_error_class_but_not_its_text(monkeypatch, caplog):
    flaky(monkeypatch, failures=1)

    with caplog.at_level(logging.WARNING, logger="app.serve"):
        serve.wait_for_database(attempts=2, delay=0, sleep=lambda _: None)

    assert "OperationalError" in caplog.text
    assert "db.example.test" not in caplog.text  # connection errors can carry the host and user

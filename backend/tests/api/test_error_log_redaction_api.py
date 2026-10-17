"""Server logs say what failed and where, but never carry an exception's message.

On PostgreSQL the message of a database error can contain whole rows (the `DETAIL` line of a
CHECK or unique violation), and the message of any exception can contain submitted values. So
unexpected failures are logged as: exception class, the chain it came from, a stack of
file/line/function, and for database errors the SQLSTATE and the constraint, table and column
names. These tests plant a fake name and phone number everywhere an exception could carry them and
prove they never reach the client or the logs.
"""

import json
import logging
import traceback
from pathlib import Path

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from app.api.errors import _frame_location, safe_exception_fields
from app.db import transaction
from app.logging_config import JsonFormatter
from app.schemas.members import MemberRead
from app.services.members import MemberService
from tests.api.conftest import error_code

BACKEND_DIR = Path(__file__).resolve().parents[2]
NAME = "Zebedee Quux"
PHONE = "+91 77777 77777"
PERSONAL = (NAME, "Zebedee", PHONE, "77777")


def make_raise(error):
    def raiser(*_args, **_kwargs):
        raise error

    return raiser


def log_lines(caplog) -> list[str]:
    formatter = JsonFormatter()
    return [formatter.format(record) for record in caplog.records]


def assert_no_personal_data(response, caplog, *extra_forbidden: str):
    forbidden = (*PERSONAL, *extra_forbidden)
    for leaked in forbidden:
        assert leaked not in response.text, f"{leaked!r} reached the client"
        for line in log_lines(caplog):
            assert leaked not in line, f"{leaked!r} reached the log: {line}"


@pytest.fixture
def captured(caplog):
    caplog.set_level(logging.DEBUG, logger="app")
    return caplog


class FakeDiagnostics:
    """What psycopg exposes in `.diag`: schema names, not data."""

    constraint_name = "ck_members_name_not_blank"
    table_name = "members"
    column_name = None


class FakeCheckViolation(Exception):
    """Stands in for psycopg's CheckViolation, whose message holds the failing row."""

    sqlstate = "23514"
    diag = FakeDiagnostics()


def postgres_style_error() -> sa.exc.IntegrityError:
    message = (
        'new row for relation "members" violates check constraint "ck_members_name_not_blank"\n'
        f"DETAIL:  Failing row contains (7, {NAME}, {PHONE}, 2026-10-12, active)."
    )
    return sa.exc.IntegrityError(
        "INSERT INTO members (name, phone) VALUES (%(name)s, %(phone)s)",
        {"name": NAME, "phone": PHONE},
        FakeCheckViolation(message),
    )


# --- database errors -------------------------------------------------------------------------


def test_a_database_error_with_a_name_and_phone_in_it_is_not_logged(api, monkeypatch, captured):
    error = postgres_style_error()
    assert NAME in str(error) and PHONE in str(error)  # the planted data really is in the error
    monkeypatch.setattr(MemberService, "get_member", make_raise(error))

    response = api.get("/members/1")

    assert response.status_code == 500
    assert error_code(response) == "internal_error"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert_no_personal_data(response, captured, "Failing row", "INSERT INTO", "violates")


def test_a_database_error_is_still_diagnosable_from_its_log_line(api, monkeypatch, captured):
    monkeypatch.setattr(MemberService, "get_member", make_raise(postgres_style_error()))

    response = api.get("/members/1")

    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "database_error"]
    assert record.levelno == logging.ERROR
    assert record.request_id == response.headers["X-Request-ID"]
    assert record.exc_info is None
    assert (record.method, record.path, record.status) == ("GET", "/members/1", 500)
    assert record.exception_type == "sqlalchemy.exc.IntegrityError"
    assert record.db_error_type.endswith("FakeCheckViolation")
    assert record.db_error_code == "23514"  # PostgreSQL's SQLSTATE for a CHECK violation
    assert record.db_constraint == "ck_members_name_not_blank"
    assert record.db_table == "members"
    assert not hasattr(record, "db_column")  # not reported by the driver, so not logged
    assert record.where.startswith("app/api/members.py") and record.where.endswith("in get_member")
    assert any(frame.startswith("app/api/members.py") for frame in record.stack)
    entry = json.loads(JsonFormatter().format(record))
    assert "exception" not in entry  # no formatted traceback, whose last line is the message


def test_a_real_database_error_with_personal_data_in_its_parameters(api, monkeypatch, captured):
    """A genuine constraint failure through the real session, with the data bound as parameters."""

    def insert_invalid_member(self, _member_id):
        with transaction(self._session_factory) as session:
            session.execute(
                sa.text(
                    "INSERT INTO members (name, phone, join_date, status) "
                    "VALUES (:name, :phone, '2026-01-01', 'not-a-status')"
                ),
                {"name": NAME, "phone": PHONE},
            )

    monkeypatch.setattr(MemberService, "get_member", insert_invalid_member)

    response = api.get("/members/1")

    assert (response.status_code, error_code(response)) == (500, "internal_error")
    assert_no_personal_data(response, captured, "INSERT INTO")
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "database_error"]
    assert record.exception_type == "sqlalchemy.exc.IntegrityError"
    # The driver differs by database; both report a CHECK violation.
    assert record.db_error_type in ("sqlite3.IntegrityError", "psycopg.errors.CheckViolation")
    assert record.db_error_code in ("SQLITE_CONSTRAINT_CHECK", "23514")


# --- unexpected errors that are not database errors ------------------------------------------


def chained_error():
    try:
        raise KeyError(PHONE)
    except KeyError as cause:
        raise ValueError(f"cannot read {NAME}") from cause


def validation_error_holding_the_phone():
    try:
        MemberRead.model_validate(
            {"id": 1, "name": "x", "phone": "y", "join_date": PHONE, "status": "active"}
        )
    except ValidationError as error:
        assert PHONE in str(error)  # pydantic quotes the offending input in its message
        raise


@pytest.mark.parametrize(
    ("make_error", "exception_type"),
    [
        (lambda: RuntimeError(f"could not process {NAME} / {PHONE}"), "builtins.RuntimeError"),
        (lambda: KeyError(NAME), "builtins.KeyError"),
        (lambda: LookupError(f"{NAME}\n{PHONE}\n"), "builtins.LookupError"),
    ],
)
def test_unexpected_errors_are_logged_without_their_message(
    api, monkeypatch, captured, make_error, exception_type
):
    monkeypatch.setattr(MemberService, "get_member", make_raise(make_error()))

    response = api.get("/members/1")

    assert (response.status_code, error_code(response)) == (500, "internal_error")
    assert_no_personal_data(response, captured)
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "internal_error"]
    assert record.levelno == logging.ERROR
    assert record.exc_info is None
    assert record.exception_type == exception_type
    assert record.request_id == response.headers["X-Request-ID"]
    assert record.where.startswith("app/api/members.py")  # enough to find the failing code


@pytest.mark.parametrize(
    ("raiser", "exception_type", "causes"),
    [
        (chained_error, "builtins.ValueError", ["builtins.KeyError"]),
        (validation_error_holding_the_phone, "pydantic_core._pydantic_core.ValidationError", None),
    ],
)
def test_chained_and_validation_errors_are_logged_by_class_only(
    api, monkeypatch, captured, raiser, exception_type, causes
):
    monkeypatch.setattr(MemberService, "get_member", lambda *_args, **_kwargs: raiser())

    response = api.get("/members/1")

    assert (response.status_code, error_code(response)) == (500, "internal_error")
    assert_no_personal_data(response, captured, "input_value", "cannot read")
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "internal_error"]
    assert record.exception_type == exception_type
    assert getattr(record, "caused_by", None) == causes  # None when there is no chain


# --- the helper on its own -------------------------------------------------------------------


def test_the_fields_never_contain_the_message_or_parameters():
    error = postgres_style_error()

    fields = safe_exception_fields(error)

    serialised = json.dumps(fields)
    for secret in (*PERSONAL, "Failing row", "INSERT", "violates"):
        assert secret not in serialised


def test_an_exception_that_was_never_raised_has_no_stack_but_is_still_described():
    fields = safe_exception_fields(RuntimeError("never raised"))

    assert fields == {"exception_type": "builtins.RuntimeError", "where": None, "stack": []}


def test_a_driver_error_without_diagnostics_adds_only_its_class():
    error = sa.exc.OperationalError("SELECT 1", {}, ValueError("connection lost"))

    fields = safe_exception_fields(error)

    assert fields["exception_type"] == "sqlalchemy.exc.OperationalError"
    assert fields["db_error_type"] == "builtins.ValueError"
    assert not {"db_error_code", "db_constraint", "db_table", "db_column"} & set(fields)


def test_library_frames_are_shown_by_their_last_path_segments_and_ours_by_package_path():
    def fail():
        sa.text("x").bindparams(1)  # raises inside SQLAlchemy

    with pytest.raises(Exception) as caught:  # any failure inside the library will do
        fail()

    stack = safe_exception_fields(caught.value)["stack"]
    assert stack[0].startswith("tests/api/test_error_log_redaction_api.py")
    assert any(frame.startswith("sqlalchemy/") or "/sqlalchemy/" in frame for frame in stack[1:])


def test_frames_outside_the_project_are_shown_by_their_last_path_segments():
    library_frame = traceback.FrameSummary(
        "/usr/lib/python3.12/site-packages/sqlalchemy/engine/base.py", 1963, "_execute_context"
    )
    own_frame = traceback.FrameSummary(str(BACKEND_DIR / "app" / "services" / "loans.py"), 97, "x")

    assert _frame_location(library_frame) == "sqlalchemy/engine/base.py:1963 in _execute_context"
    assert _frame_location(own_frame) == "app/services/loans.py:97 in x"


def test_a_long_chain_of_causes_is_cut_off():
    error = None
    for _ in range(12):
        try:
            raise ValueError("link") from error
        except ValueError as raised:
            error = raised

    assert len(safe_exception_fields(error)["caused_by"]) == 5

"""One error shape for everything, nothing internal leaks, and logs hold no personal data."""

import io
import json
import logging

import pytest
import sqlalchemy as sa

from app.api.errors import DOMAIN_ERROR_STATUS
from app.db import make_engine
from app.domain import errors as domain
from app.domain.enums import BlockReason
from app.logging_config import JsonFormatter, configure_logging, request_id_var
from app.services.members import MemberService
from tests.api.conftest import error_code


def make_raise(error):
    def raiser(*_args, **_kwargs):
        raise error

    return raiser


def log_text(caplog) -> str:
    formatter = JsonFormatter()
    return "\n".join(formatter.format(record) for record in caplog.records)


@pytest.fixture
def captured(caplog):
    caplog.set_level(logging.DEBUG, logger="app")
    return caplog


# --- every domain error has a status and a code ----------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (domain.EntityNotFound("Member 1 not found"), 404, "not_found"),
        (domain.InvalidTransition("nope"), 409, "invalid_transition"),
        (domain.ReservationExpired("late"), 409, "reservation_expired"),
        (domain.ConflictError("changed"), 409, "conflict"),
        (domain.DeletionBlocked("has history"), 409, "deletion_blocked"),
        (domain.MemberBlocked([BlockReason.SUSPENDED]), 403, "member_blocked"),
        (domain.LoanLimitExceeded("3 loans"), 403, "loan_limit_exceeded"),
        (domain.PaymentExceedsBalance("too much"), 422, "payment_exceeds_balance"),
        (domain.InvalidPaymentAmount("zero"), 422, "invalid_payment_amount"),
        (domain.DomainError("anything else"), 422, "rule_violation"),
    ],
)
def test_domain_errors_map_to_a_status_and_code(api, monkeypatch, error, status, code):
    monkeypatch.setattr(MemberService, "get_member", make_raise(error))

    response = api.get("/members/1")

    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id", "details"}
    assert body["error"]["code"] == code
    assert body["error"]["message"] == str(error)
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


def test_member_blocked_lists_every_reason(api, monkeypatch):
    reasons = [BlockReason.SUSPENDED, BlockReason.UNPAID_FEES, BlockReason.LONG_OVERDUE]
    monkeypatch.setattr(MemberService, "get_member", make_raise(domain.MemberBlocked(reasons)))

    response = api.get("/members/1")

    assert response.json()["error"]["details"] == {
        "reasons": ["suspended", "unpaid_fees", "long_overdue"]
    }


def test_every_domain_error_type_is_covered_by_the_mapping():
    mapped = {error_type for error_type, _, _ in DOMAIN_ERROR_STATUS}
    all_errors = {
        value
        for value in vars(domain).values()
        if isinstance(value, type)
        and issubclass(value, domain.DomainError)
        and value is not domain.DomainError
    }
    assert all_errors == mapped, f"unmapped: {all_errors - mapped}"


# --- unexpected failures never leak ----------------------------------------------------------


def test_unexpected_error_is_a_generic_500_with_a_request_id(api, monkeypatch, captured):
    secret = "db password hunter2 at internal-host.local"
    monkeypatch.setattr(MemberService, "get_member", make_raise(RuntimeError(secret)))

    response = api.get("/members/1")

    assert response.status_code == 500
    assert error_code(response) == "internal_error"
    assert secret not in response.text and "hunter2" not in response.text
    assert "Traceback" not in response.text and "RuntimeError" not in response.text
    request_id = response.headers["X-Request-ID"]
    assert response.json()["error"]["request_id"] == request_id
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "internal_error"]
    assert record.levelno == logging.ERROR
    # Logged as what and where, never as a traceback whose last line is the exception's message.
    assert record.exc_info is None
    assert record.exception_type == "builtins.RuntimeError"
    assert record.where.startswith("app/api/members.py")
    assert record.request_id == request_id
    assert "hunter2" not in log_text(captured)


def test_database_errors_are_hidden_from_the_client(api, monkeypatch, captured):
    database_error = sa.exc.OperationalError(
        "SELECT secret_column FROM members WHERE phone = :phone",
        {"phone": "+91 99999 99999"},
        Exception("connection to server at db.internal.example failed"),
    )
    monkeypatch.setattr(MemberService, "get_member", make_raise(database_error))

    response = api.get("/members/1")

    assert response.status_code == 500
    assert error_code(response) == "internal_error"
    for leaked in ("secret_column", "99999", "db.internal", "SELECT", "OperationalError"):
        assert leaked not in response.text
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "database_error"]
    assert record.levelno == logging.ERROR and record.exc_info is None
    assert record.exception_type == "sqlalchemy.exc.OperationalError"


def test_integrity_errors_are_hidden_too(api, monkeypatch):
    error = sa.exc.IntegrityError(
        "INSERT INTO members ...", {"name": "Zed"}, Exception("UNIQUE failed")
    )
    monkeypatch.setattr(MemberService, "get_member", make_raise(error))

    response = api.get("/members/1")

    assert (response.status_code, error_code(response)) == (500, "internal_error")
    assert "UNIQUE" not in response.text and "INSERT" not in response.text


def test_database_parameters_are_hidden_in_error_messages():
    engine = make_engine("sqlite://")
    try:
        with engine.connect() as connection:
            connection.execute(
                sa.text("INSERT INTO no_such_table (a) VALUES (:a)"), {"a": "secret-phone"}
            )
    except sa.exc.SQLAlchemyError as error:
        assert "secret-phone" not in str(error)
    else:
        pytest.fail("expected a database error")
    finally:
        engine.dispose()


def test_unknown_routes_and_methods_use_the_same_shape(api):
    missing = api.get("/nope")
    wrong_method = api.call("PUT", "/members")

    assert (missing.status_code, error_code(missing)) == (404, "route_not_found")
    assert (wrong_method.status_code, error_code(wrong_method)) == (405, "method_not_allowed")
    assert missing.json()["error"]["request_id"] == missing.headers["X-Request-ID"]


# --- request ids -----------------------------------------------------------------------------


def test_every_response_has_a_request_id(api):
    ok = api.get("/health")
    not_found = api.get("/members/999")

    for response in (ok, not_found):
        assert len(response.headers["X-Request-ID"]) == 32
    assert ok.headers["X-Request-ID"] != not_found.headers["X-Request-ID"]


def test_a_sane_incoming_request_id_is_kept_and_a_bad_one_replaced(api):
    kept = api.get("/health", headers={"X-Request-ID": "reviewer-run.42_a"})
    replaced = api.get("/health", headers={"X-Request-ID": "bad id with spaces & <tags>"})
    too_long = api.get("/health", headers={"X-Request-ID": "x" * 65})

    assert kept.headers["X-Request-ID"] == "reviewer-run.42_a"
    assert len(replaced.headers["X-Request-ID"]) == 32
    assert len(too_long.headers["X-Request-ID"]) == 32


def test_the_request_id_is_readable_by_browsers_across_origins(api):
    response = api.get("/health", headers={"Origin": "http://localhost:5173"})

    assert "x-request-id" in response.headers["access-control-expose-headers"].lower()


# --- logging: context yes, personal data no --------------------------------------------------


def test_each_request_logs_one_access_line_without_the_query_string(api, captured):
    api.get("/members?q=Zebedee&limit=5")

    [line] = [r for r in captured.records if r.getMessage() == "request"]
    assert (line.method, line.path, line.status) == ("GET", "/members", 200)
    assert line.duration_ms >= 0
    assert line.levelno == logging.INFO
    assert "Zebedee" not in log_text(captured)


def test_health_checks_do_not_flood_the_info_log(api, captured):
    api.get("/health")

    lines = [r for r in captured.records if r.getMessage() == "request"]
    assert [r.levelno for r in lines] == [logging.DEBUG]


def test_rule_violations_are_logged_at_warning_with_context_but_no_personal_data(api, captured):
    member = api.make_member(name="Zebedee Quux", phone="+91 00000 77777")
    item = api.make_item(name="Zebedee's Secret Drill")
    api.post(f"/members/{member['id']}/suspension", json={"reason": "Zebedee broke the thing"})
    captured.clear()

    response = api.reserve(item["id"], member["id"])

    assert response.status_code == 403
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "member_blocked"]
    assert record.levelno == logging.WARNING
    assert (record.status, record.method, record.path) == (
        403,
        "POST",
        f"/items/{item['id']}/reservation",
    )
    assert record.request_id == response.headers["X-Request-ID"]
    text = log_text(captured)
    for personal in ("Zebedee", "77777", "Secret Drill", "broke the thing"):
        assert personal not in text


def test_validation_failures_log_the_fields_but_never_the_values(api, captured):
    response = api.post("/members", json={"name": "Asha", "phone": "SECRET-VALUE-123"})

    assert response.status_code == 422
    assert "SECRET-VALUE-123" not in response.text
    [record] = [r for r in captured.records if getattr(r, "error_code", None) == "validation_error"]
    assert record.fields == ["body.phone"]
    assert "SECRET-VALUE-123" not in log_text(captured)


def test_malformed_json_is_logged_without_the_body(api, captured):
    api.post(
        "/members", content='{"name": "Hidden Name', headers={"Content-Type": "application/json"}
    )

    assert any(getattr(r, "error_code", None) == "malformed_json" for r in captured.records)
    assert "Hidden Name" not in log_text(captured)


def test_test_clock_rejections_are_logged_as_warnings(api, captured):
    api.get("/items", headers={"X-Test-Clock": "garbage"}, at=None)

    [record] = [
        r for r in captured.records if getattr(r, "error_code", None) == "invalid_test_clock"
    ]
    assert record.levelno == logging.WARNING


# --- the log format itself -------------------------------------------------------------------


def json_log_line(log_call) -> dict:
    """Run `log_call(logger)` through the real logging setup and return the JSON line it wrote."""
    configure_logging("INFO")  # also installs the record factory that stamps the request id
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app.test_json_formatter")
    logger.addHandler(handler)
    try:
        log_call(logger)
    finally:
        logger.removeHandler(handler)
    return json.loads(stream.getvalue())


def test_json_formatter_outputs_one_json_object_with_context():
    token = request_id_var.set("abc123")
    try:
        entry = json_log_line(
            lambda logger: logger.warning(
                "something %s", "happened", extra={"error_code": "demo", "status": 409}
            )
        )
    finally:
        request_id_var.reset(token)

    assert entry["level"] == "WARNING"
    assert entry["message"] == "something happened"
    assert entry["logger"] == "app.test_json_formatter"
    assert entry["error_code"] == "demo" and entry["status"] == 409
    assert entry["request_id"] == "abc123"
    assert entry["timestamp"].endswith("+00:00")


def test_json_formatter_includes_the_traceback():
    def log_failure(logger):
        try:
            raise ValueError("boom")
        except ValueError:
            logger.exception("failed")

    entry = json_log_line(log_failure)

    assert entry["level"] == "ERROR"
    assert "ValueError: boom" in entry["exception"]
    assert entry["request_id"] is None  # logged outside any request


def test_configuring_logging_twice_does_not_duplicate_output():
    for _ in range(3):
        configure_logging("INFO")

    marked = [
        h
        for h in logging.getLogger("app").handlers
        if getattr(h, "_rental_desk_json_handler", False)
    ]
    assert len(marked) == 1

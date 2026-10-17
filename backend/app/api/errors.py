"""One error shape for every failure, and the mapping from rule violations to HTTP statuses.

    {"error": {"code": "invalid_transition", "message": "...", "request_id": "...", "details": ...}}

`code` is stable and meant for programs; `message` is meant for people. Clients never see a
traceback, a SQL statement or a database error text: unexpected failures are logged on the server
(see `safe_exception_fields`: what happened and where, never the exception's message) and reported
as `internal_error` with the request id to quote.
"""

import logging
import traceback
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import errors as domain
from app.logging_config import request_id_var

logger = logging.getLogger("app.api.errors")


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """An error raised by the API layer itself (not by a business rule)."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


# Most specific first: the first isinstance match wins.
DOMAIN_ERROR_STATUS: list[tuple[type[domain.DomainError], int, str]] = [
    (domain.EntityNotFound, 404, "not_found"),
    (domain.ReservationExpired, 409, "reservation_expired"),
    (domain.InvalidTransition, 409, "invalid_transition"),
    (domain.ConflictError, 409, "conflict"),
    (domain.DeletionBlocked, 409, "deletion_blocked"),
    (domain.MemberBlocked, 403, "member_blocked"),
    (domain.LoanLimitExceeded, 403, "loan_limit_exceeded"),
    (domain.PaymentExceedsBalance, 422, "payment_exceeds_balance"),
    (domain.InvalidPaymentAmount, 422, "invalid_payment_amount"),
]

# For OpenAPI: the error responses a route can produce.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorResponse, "description": text}
    for code, text in {
        400: "Malformed JSON or invalid X-Test-Clock header",
        403: "Member is blocked or at the loan limit",
        404: "Member, item or route not found",
        409: "Action not allowed in the current state, or a concurrent change",
        422: "Validation failed",
        500: "Unexpected server error",
    }.items()
}


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body = ErrorBody(code=code, message=message, request_id=request_id_var.get(), details=details)
    return JSONResponse(status_code=status_code, content={"error": body.model_dump(mode="json")})


def unexpected_error_response() -> JSONResponse:
    return error_response(
        500,
        "internal_error",
        "An unexpected error occurred. Quote the request id if you report this.",
    )


async def handle_domain_error(request: Request, error: domain.DomainError) -> JSONResponse:
    status_code, code = 422, "rule_violation"
    for error_type, mapped_status, mapped_code in DOMAIN_ERROR_STATUS:
        if isinstance(error, error_type):
            status_code, code = mapped_status, mapped_code
            break
    details = None
    if isinstance(error, domain.MemberBlocked):
        details = {"reasons": [reason.value for reason in error.reasons]}
    logger.warning(
        "request refused by a business rule",
        extra={
            "error_code": code,
            "error_type": type(error).__name__,
            "status": status_code,
            "method": request.method,
            "path": request.url.path,
            "reason": str(
                error
            ),  # rule messages contain ids and amounts only, never names or phones
        },
    )
    return error_response(status_code, code, str(error), details)


async def handle_api_error(request: Request, error: ApiError) -> JSONResponse:
    logger.warning(
        "request rejected",
        extra={
            "error_code": error.code,
            "status": error.status_code,
            "method": request.method,
            "path": request.url.path,
        },
    )
    return error_response(error.status_code, error.code, error.message, error.details)


async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    problems = error.errors()
    if any(problem["type"] == "json_invalid" for problem in problems):
        logger.warning(
            "malformed JSON body",
            extra={
                "error_code": "malformed_json",
                "status": 400,
                "method": request.method,
                "path": request.url.path,
            },
        )
        return error_response(400, "malformed_json", "The request body is not valid JSON")

    # Report where each problem is and what is wrong, never the submitted value.
    details = [
        {
            "field": ".".join(str(part) for part in problem["loc"]),
            "message": problem["msg"],
            "type": problem["type"],
        }
        for problem in problems
    ]
    logger.warning(
        "request failed validation",
        extra={
            "error_code": "validation_error",
            "status": 422,
            "method": request.method,
            "path": request.url.path,
            "fields": [detail["field"] for detail in details],
        },
    )
    return error_response(422, "validation_error", "The request is invalid", details)


async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    codes = {404: "route_not_found", 405: "method_not_allowed"}
    code = codes.get(error.status_code, "http_error")
    message = {404: "No such route", 405: "Method not allowed for this route"}.get(
        error.status_code, "The request could not be processed"
    )
    logger.warning(
        "http error",
        extra={
            "error_code": code,
            "status": error.status_code,
            "method": request.method,
            "path": request.url.path,
        },
    )
    return error_response(error.status_code, code, message)


_BACKEND_DIR = Path(__file__).resolve().parents[2]  # so our own files read "app/services/x.py"
_MAX_STACK_FRAMES = 40
_MAX_CAUSES = 5


def _qualified_name(error_type: type) -> str:
    return f"{error_type.__module__}.{error_type.__qualname__}"


def _frame_location(frame: traceback.FrameSummary) -> str:
    path = Path(frame.filename)
    try:
        shown = path.resolve().relative_to(_BACKEND_DIR).as_posix()
    except (ValueError, OSError):
        shown = "/".join(path.parts[-3:])  # library code: enough to recognise it
    return f"{shown}:{frame.lineno} in {frame.name}"


def safe_exception_fields(error: BaseException) -> dict[str, Any]:
    """What may be logged about an unexpected exception: what it was and where, never its message.

    The text of an exception can contain submitted values, and a database driver's message can
    contain whole rows (PostgreSQL's `DETAIL` line lists the failing row or key). So neither the
    message, the SQL parameters, nor a formatted traceback (whose last line is the message) are
    logged. Instead:

    - `exception_type`, and `caused_by` for the exceptions it was raised from or during;
    - `where` (the innermost frame in our own code) and `stack` (file, line, function per frame);
    - for database errors, the driver's exception class and its structural diagnostics: the SQLSTATE
      (PostgreSQL) or error name (SQLite), and the constraint, table and column names, which are
      schema identifiers and not data.
    """
    frames = traceback.extract_tb(error.__traceback__)[-_MAX_STACK_FRAMES:]
    stack = [_frame_location(frame) for frame in frames]
    own_frames = [location for location in stack if location.startswith("app/")]
    fields: dict[str, Any] = {
        "exception_type": _qualified_name(type(error)),
        "where": (own_frames or stack or [None])[-1],
        "stack": stack,
    }

    causes = []
    link = error.__cause__ or error.__context__
    while link is not None and len(causes) < _MAX_CAUSES:
        causes.append(_qualified_name(type(link)))
        link = link.__cause__ or link.__context__
    if causes:
        fields["caused_by"] = causes

    driver_error = getattr(error, "orig", None)  # SQLAlchemy wraps the driver's own exception
    if driver_error is not None:
        fields["db_error_type"] = _qualified_name(type(driver_error))
        code = (
            getattr(driver_error, "sqlstate", None)  # psycopg
            or getattr(driver_error, "pgcode", None)
            or getattr(driver_error, "sqlite_errorname", None)  # sqlite3
        )
        if code:
            fields["db_error_code"] = str(code)[:40]
        diagnostics = getattr(driver_error, "diag", None)  # psycopg: schema names only
        for field, attribute in (
            ("db_constraint", "constraint_name"),
            ("db_table", "table_name"),
            ("db_column", "column_name"),
        ):
            value = getattr(diagnostics, attribute, None)
            if value:
                fields[field] = str(value)[:100]
    return fields


async def handle_database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "database error",
        extra={
            "error_code": "database_error",
            "status": 500,
            "method": request.method,
            "path": request.url.path,
            **safe_exception_fields(error),
        },
    )
    return unexpected_error_response()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(domain.DomainError, handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(ApiError, handle_api_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, handle_http_error)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, handle_database_error)  # type: ignore[arg-type]

"""Structured (JSON) logging with a request id on every line.

Rules for what gets logged: ids, error codes, status codes and timings, never request bodies, query
strings, names, phone numbers or notes. Database errors are logged without bound parameters
(see `hide_parameters` in app.db).
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else on a record was passed as `extra=` and is output.
_STANDARD_ATTRIBUTES = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}
_HANDLER_MARK = "_rental_desk_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send everything under the `app` logger to stdout as JSON. Safe to call more than once."""
    _install_request_id_record_factory()
    logger = logging.getLogger("app")
    logger.setLevel(level.upper())
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)


def _install_request_id_record_factory() -> None:
    current = logging.getLogRecordFactory()
    if getattr(current, "_adds_request_id", False):
        return

    def factory(*args, **kwargs):
        record = current(*args, **kwargs)
        record.request_id = request_id_var.get()
        return record

    factory._adds_request_id = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)

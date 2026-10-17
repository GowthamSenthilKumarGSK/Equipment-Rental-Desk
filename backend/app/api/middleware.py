"""Request id, access log, and the last-resort handler for unexpected exceptions."""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import safe_exception_fields, unexpected_error_response
from app.logging_config import request_id_var

logger = logging.getLogger("app.api.request")

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Gives every request an id (kept if the caller sent a sane one) and logs one line per request.

    It also catches anything the exception handlers did not, logs what it was and where (never the
    exception's message, which can hold submitted values), and sends a generic 500 so the client
    never sees internals. The query string and body are never logged.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = supplied if _VALID_REQUEST_ID.match(supplied) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = {"code": None}

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_request_id)
            except Exception as error:
                logger.error(
                    "unhandled exception",
                    extra={
                        "error_code": "internal_error",
                        "status": 500,
                        "method": scope["method"],
                        "path": scope["path"],
                        **safe_exception_fields(error),
                    },
                )
                if status["code"] is not None:  # response already started: cannot replace it
                    raise
                await unexpected_error_response()(scope, receive, send_with_request_id)
        finally:
            level = logging.DEBUG if scope["path"] == "/health" else logging.INFO
            logger.log(
                level,
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status["code"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)

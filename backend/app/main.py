"""FastAPI entry point: builds the app, wires middleware, error handlers and routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api import analytics, health, items, loans, members, root
from app.api.errors import register_error_handlers
from app.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.logging_config import configure_logging

DESCRIPTION = """
Rules for a community tool library: reservations (48-hour hold), check-out (7 days), late fees,
loan limits and blocked members. All rules are enforced here, not in the UI.

**Reviewer test clock.** Send `X-Test-Clock: 2026-10-20T10:00:00+05:30` (ISO-8601 with a UTC offset)
on any request to make it run as if it were that moment, so expiry and overdue can be tried without
waiting. Without the header the real time is used. Money is always whole paise; timestamps are UTC.
"""


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Build the app. Tests pass their own `session_factory`; otherwise it uses DATABASE_URL."""
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = None if session_factory else make_engine()
    if engine is not None:
        session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="Equipment Rental Desk API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory

    # Added first = innermost. CORS wraps the request-context middleware so even its error
    # responses carry the CORS headers.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    register_error_handlers(app)

    app.include_router(root.router)
    app.include_router(health.router)
    app.include_router(members.router)
    app.include_router(items.router)
    app.include_router(loans.router)
    app.include_router(analytics.router)
    return app


app = create_app()

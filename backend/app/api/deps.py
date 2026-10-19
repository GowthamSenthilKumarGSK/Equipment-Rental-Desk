"""Dependencies shared by the routers: database sessions, the clock, and the services."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, Path, Query, Request
from sqlalchemy.orm import Session, sessionmaker

from app.api.errors import ApiError
from app.clock import Clock, FixedClock, SystemClock
from app.config import Settings, get_settings
from app.services.analytics import AnalyticsService
from app.services.items import ItemService
from app.services.loans import LoanService
from app.services.members import MemberService

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

# Ids and offsets are 32-bit in the database; anything bigger would crash the driver, so it is
# refused as invalid input instead.
MAX_DB_INT = 2_147_483_647
MemberId = Annotated[int, Path(ge=1, le=MAX_DB_INT, description="Member id")]
ItemId = Annotated[int, Path(ge=1, le=MAX_DB_INT, description="Item id")]

TEST_CLOCK_EXAMPLE = "2026-10-20T10:00:00+05:30"
# The accepted range for X-Test-Clock. Far enough either way for any scenario a reviewer needs, and
# far from the limits of `datetime` (years 1 to 9999), so adding or subtracting a few days to an
# accepted time can never overflow. Outside it, a stored reservation could break every later read.
TEST_CLOCK_MIN = datetime(2000, 1, 1, tzinfo=UTC)
TEST_CLOCK_MAX = datetime(2200, 1, 1, tzinfo=UTC)


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_clock(
    settings: Annotated[Settings, Depends(get_settings)],
    x_test_clock: Annotated[
        str | None,
        Header(
            description=(
                "Reviewer aid: pretend it is this moment. An ISO-8601 timestamp with a UTC "
                f"offset, e.g. {TEST_CLOCK_EXAMPLE} or 2026-10-20T04:30:00Z, between "
                "2000-01-01 and 2200-01-01 (UTC). Without the header the real time is used. "
                "Applies to this request only. Anything written keeps the pretend time."
            ),
            examples=[TEST_CLOCK_EXAMPLE],
        ),
    ] = None,
) -> Clock:
    """The real clock, or a fixed one when the reviewer sends X-Test-Clock.

    The value is validated first (format, a UTC offset, and the accepted range) and only then
    converted to UTC, like every timestamp inside the application. A rejected value never reaches a
    service, so nothing is written.
    """
    if x_test_clock is None:
        return SystemClock()
    if not settings.allow_test_clock:
        raise ApiError(400, "test_clock_disabled", "The X-Test-Clock header is disabled here")
    try:
        moment = datetime.fromisoformat(x_test_clock.strip())
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise ApiError(
            400,
            "invalid_test_clock",
            "X-Test-Clock must be an ISO-8601 timestamp with a UTC offset, "
            f"e.g. {TEST_CLOCK_EXAMPLE}",
        )
    # Comparing two aware datetimes compares the instants they stand for; it converts nothing, so
    # it cannot overflow however extreme the value or its offset is.
    if not TEST_CLOCK_MIN <= moment <= TEST_CLOCK_MAX:
        raise ApiError(
            400,
            "invalid_test_clock",
            "X-Test-Clock must be between 2000-01-01 and 2200-01-01 (UTC)",
        )
    return FixedClock(moment.astimezone(UTC))


SessionFactoryDep = Annotated[sessionmaker[Session], Depends(get_session_factory)]
ClockDep = Annotated[Clock, Depends(get_clock)]


def get_loan_service(factory: SessionFactoryDep, clock: ClockDep) -> LoanService:
    return LoanService(factory, clock)


def get_item_service(factory: SessionFactoryDep, clock: ClockDep) -> ItemService:
    return ItemService(factory, clock)


def get_member_service(factory: SessionFactoryDep, clock: ClockDep) -> MemberService:
    return MemberService(factory, clock)


def get_analytics_service(factory: SessionFactoryDep, clock: ClockDep) -> AnalyticsService:
    return AnalyticsService(factory, clock)


LoanServiceDep = Annotated[LoanService, Depends(get_loan_service)]
ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
MemberServiceDep = Annotated[MemberService, Depends(get_member_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


@dataclass(frozen=True)
class PageParams:
    limit: int
    offset: int


def get_page_params(
    limit: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Page size")
    ] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=MAX_DB_INT, description="How many results to skip")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


PageDep = Annotated[PageParams, Depends(get_page_params)]

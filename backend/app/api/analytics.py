"""Analytics endpoints: read-only reports for the dashboard.

Routes only validate the query and shape the answer. The figures come from the analytics service,
which applies the domain rules and never writes. "Now" is the request clock, so `X-Test-Clock` moves
every report.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AnalyticsServiceDep
from app.api.errors import ERROR_RESPONSES
from app.domain.analytics import DEFAULT_REPORT_DAYS, MAX_REPORT_DAYS, Bucket
from app.schemas.analytics import (
    DemandRead,
    MaintenanceRead,
    OverdueAgingRead,
    PaymentsRead,
    SummaryRead,
    UtilizationRead,
)

router = APIRouter(prefix="/analytics", tags=["analytics"], responses=ERROR_RESPONSES)

DaysParam = Annotated[
    int,
    Query(
        ge=1,
        le=MAX_REPORT_DAYS,
        description="Report period: the last N IST calendar days including today. The previous N "
        "days are used for comparison.",
    ),
]


@router.get(
    "/summary",
    summary="Headline figures: fleet, loans, members, receivables and period activity",
    description="Item and loan counts are as of now (a lapsed hold counts as available, a late "
    "loan as overdue). Fleet counts items by status; `loans.overdue` counts late loans, including "
    "those on items under maintenance. Activity figures cover the report period so far and the "
    "same elapsed time in the period before it, so the two are comparable.",
)
def summary(service: AnalyticsServiceDep, days: DaysParam = DEFAULT_REPORT_DAYS) -> SummaryRead:
    return SummaryRead.model_validate(service.summary(days=days))


@router.get(
    "/overdue-aging",
    summary="Overdue loans by age, who owes most, and how returns have been",
    description="Bands use the same rounded-up late days as the late fee. `open` is as of now; "
    "`returns` covers loans returned during the report period.",
)
def overdue_aging(
    service: AnalyticsServiceDep, days: DaysParam = DEFAULT_REPORT_DAYS
) -> OverdueAgingRead:
    return OverdueAgingRead.model_validate(service.overdue_aging(days=days))


@router.get(
    "/payments",
    summary="Payments collected, receivables and who owes most",
    description="`series` buckets payments by IST day or by IST week (Monday to Sunday). The last "
    "bucket holds today and the first weekly bucket may start before the period; both are flagged "
    "`partial`. Totals and balances are as of now: payments and fees dated later are not counted.",
)
def payments(
    service: AnalyticsServiceDep,
    days: DaysParam = DEFAULT_REPORT_DAYS,
    bucket: Annotated[Bucket, Query(description="Series granularity")] = Bucket.DAY,
) -> PaymentsRead:
    return PaymentsRead.model_validate(service.payments(days=days, bucket=bucket))


@router.get(
    "/utilization",
    summary="How much of the fleet's time was spent checked out",
    description="Checked-out item-days ÷ fleet item-days over the period so far (IST days up to "
    "now), against the same length of the previous period. `series` buckets the period by IST day "
    "or week; the last bucket (today) and a cut-off first week are flagged `partial`. Maintenance "
    "history is not recorded, so no maintenance time is removed from the fleet.",
)
def utilization(
    service: AnalyticsServiceDep,
    days: DaysParam = DEFAULT_REPORT_DAYS,
    bucket: Annotated[Bucket, Query(description="Series granularity")] = Bucket.DAY,
) -> UtilizationRead:
    return UtilizationRead.model_validate(service.utilization(days=days, bucket=bucket))


@router.get(
    "/demand",
    summary="Reservation funnel, demand by category and the most reserved items",
    description="Counts the reservations made in the period and what became of them as of now "
    "(checked out, cancelled, expired, still held), against the same elapsed time of the previous "
    "period. Both funnels are judged at now, so the previous one has had longer to settle and its "
    "conversion rate is not maturity-adjusted. Expired holds are recognised by the 48-hour rule "
    "even if not yet saved. Unmet demand (trying to reserve an unavailable item) is not recorded "
    "and so not counted.",
)
def demand(service: AnalyticsServiceDep, days: DaysParam = DEFAULT_REPORT_DAYS) -> DemandRead:
    return DemandRead.model_validate(service.demand(days=days))


@router.get(
    "/maintenance",
    summary="Items under maintenance right now (a snapshot, not a history)",
    description="Current fleet counts (the same as `GET /items?status=`) and the items under "
    "maintenance, with whether a member still has them on loan. The database records only each "
    "item's current status, never when maintenance started or ended, so there are no downtime "
    "durations or trends here and none are inferred.",
)
def maintenance(service: AnalyticsServiceDep) -> MaintenanceRead:
    return MaintenanceRead.model_validate(service.maintenance())

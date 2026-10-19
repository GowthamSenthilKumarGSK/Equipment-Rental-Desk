"""Response models for the analytics endpoints. Money is whole paise; dates are IST calendar dates;
instants are UTC. Percentages have one decimal and are null when there is nothing to divide by.

Every report is calculated at `as_of` (the request clock) and the current period ends at the next
IST midnight. Activity and money figures (reservations, checkouts, returns, fees, payments, ledger
and balances) leave out anything dated after `as_of`. So do the counts derived from balances:
`members.blocked*`, `receivables.*` and `members_over_limit` use the balance as of `as_of`.
Fleet and loan totals and `members.total`, `members.active` and `members.suspended` describe the
rows as they are now, judged at `as_of`: a loan or member dated after `as_of` is still counted."""

from datetime import date, datetime

from pydantic import Field

from app.domain.analytics import Bucket
from app.domain.enums import ItemStatus
from app.schemas.common import ResponseModel


class WindowRead(ResponseModel):
    days: int
    start_date: date = Field(description="First IST day of the report (today minus days − 1)")
    end_date: date = Field(description="Last IST day of the report: today")
    previous_start_date: date = Field(description="First IST day of the period compared against")
    previous_end_date: date = Field(
        description="IST day that `previous_through` falls on. The previous period is compared "
        "only up to that point, so this is not necessarily its last day."
    )
    previous_through: datetime = Field(
        description="Where the previous period is cut off: `as_of` minus `days` days. Today is not "
        "over, so the current figures cover `start_date` up to `as_of`; the previous ones cover "
        "`previous_start_date` up to the same elapsed time. Every `previous` figure is therefore "
        "like for like with its `current`. Counts include events stamped exactly at this instant "
        "(as they include events stamped exactly at `as_of`); utilization measures time as the "
        "half-open stretch from `previous_start_date` up to, but not including, this instant, so "
        "a loan that begins exactly then adds nothing."
    )
    timezone: str = "Asia/Kolkata (IST, UTC+05:30)"


class ChangeRead(ResponseModel):
    current: int = Field(description="From the start of the report period up to now")
    previous: int = Field(
        description="Same elapsed time in the previous period (`previous_through`)"
    )
    change_pct: float | None = Field(
        description="Change from previous to current in percent; null when previous is 0"
    )


class RateRead(ResponseModel):
    current_pct: float | None
    previous_pct: float | None


class FleetRead(ResponseModel):
    """Items by status right now. Each item is counted once, under its own status, so the five
    statuses add up to `total_items` and agree with `GET /items?status=`."""

    total_items: int
    available: int = Field(description="Includes items whose reservation hold has lapsed")
    reserved: int
    checked_out: int = Field(description="On loan and not yet past the due time")
    overdue: int = Field(
        description="Items shown as overdue: on loan past the due time and not under maintenance. "
        "An item pulled for maintenance while on a late loan is counted under under_maintenance, "
        "so this can be lower than loans.overdue."
    )
    under_maintenance: int = Field(
        description="Includes items under maintenance that are still on a loan"
    )


class LoansNowRead(ResponseModel):
    """Loans (not items) right now. A loan is counted whatever status its item has, so `overdue`
    agrees with `GET /loans/overdue` and can exceed fleet.overdue by the late loans whose item is
    under maintenance."""

    active: int = Field(description="Held reservations plus checked-out loans (overdue included)")
    reserved: int = Field(description="Reservations whose 48-hour hold has not run out")
    checked_out: int = Field(description="All checked-out loans, overdue included")
    overdue: int = Field(
        description="Checked-out loans past their due time, including those whose item is under "
        "maintenance (a subset of checked_out)"
    )
    overdue_share_pct: float | None = Field(description="overdue ÷ checked_out; null if none out")


class MembersRead(ResponseModel):
    total: int
    active: int
    suspended: int
    blocked: int = Field(description="Members who cannot reserve or check out right now")
    blocked_suspended: int = Field(description="Blocked because suspended")
    blocked_unpaid_fees: int = Field(description="Blocked because the balance is over ₹100")
    blocked_long_overdue: int = Field(description="Blocked by a loan overdue more than 14 days")


class ReceivablesRead(ResponseModel):
    """What members owe, as of now. A member's balance is fees charged minus payments received.
    Members who owe money are summed in `outstanding_paise`; members who have paid ahead (a
    negative balance) are summed in `unapplied_credit_paise` and never reduce what others owe."""

    outstanding_paise: int = Field(
        description="Total of the balances above zero: never negative, and equal to the sum of "
        "`top_balances` if every owing member were listed"
    )
    unapplied_credit_paise: int = Field(
        description="Total of the negative balances, as a positive amount (0 unless a member has "
        "paid more than they owed)"
    )
    members_with_balance: int = Field(description="Members with a balance above zero")
    members_over_limit: int = Field(description="Members whose balance is over ₹100")


class SummaryRead(ResponseModel):
    as_of: datetime = Field(
        description="The moment the report was calculated (honours X-Test-Clock)"
    )
    window: WindowRead
    fleet: FleetRead
    loans: LoansNowRead
    members: MembersRead
    receivables: ReceivablesRead
    reservations_created: ChangeRead = Field(
        description="Reservations made in the period, including ones later cancelled or lapsed"
    )
    checkouts: ChangeRead = Field(description="Items handed out in the period")
    returns: ChangeRead = Field(description="Items returned in the period")
    late_return_rate: RateRead = Field(description="Late returns ÷ returns in the period")
    payments_collected_paise: ChangeRead
    fees_charged_paise: ChangeRead = Field(description="Late fees charged on returns in the period")


class AgingBandRead(ResponseModel):
    label: str
    min_days: int
    max_days: int | None = Field(description="null for the open-ended last band")
    count: int
    accrued_fee_paise: int = Field(description="What returning these loans now would be charged")


class OverdueNowRead(ResponseModel):
    """Checked-out loans past their due time, as of now: the same loans as `GET /loans/overdue`."""

    count: int
    accrued_fee_paise: int = Field(
        description="Sum of the fees that returning every overdue loan now would be charged. "
        "Fees are only charged at return, so this is an estimate, not money owed yet."
    )
    blocking_count: int = Field(description="Loans overdue by more than 14 days")
    oldest_days_overdue: int | None
    bands: list[AgingBandRead]


class OverdueMemberRead(ResponseModel):
    member_id: int
    member_name: str
    loans: int
    longest_days_overdue: int
    accrued_fee_paise: int


class LateReturnsRead(ResponseModel):
    returned: int = Field(description="Loans returned in the period")
    late: int = Field(description="Of those, returned after their due time")
    late_rate_pct: float | None
    average_days_late: float | None = Field(description="Mean chargeable late days of late returns")
    fees_charged_paise: int


class OverdueAgingRead(ResponseModel):
    as_of: datetime
    window: WindowRead
    open: OverdueNowRead = Field(description="Loans that are overdue right now")
    top_members: list[OverdueMemberRead] = Field(
        description="Up to 5 members by accrued fee, then longest overdue"
    )
    returns: LateReturnsRead = Field(description="Late returns during the report period")


class PaymentBucketRead(ResponseModel):
    start: date = Field(description="First IST day of the bucket (a Monday for weekly buckets)")
    collected_paise: int = Field(description="Money received on the covered days, up to now")
    count: int
    covered_from: date = Field(
        description="First day of the bucket inside the report period; later than `start` for a "
        "weekly bucket that the period cuts off at its beginning"
    )
    covered_to: date = Field(
        description="Last day of the bucket inside the report period (today, for the last bucket)"
    )
    partial: bool = Field(
        description="True when the bucket does not cover its whole day or week: the first weekly "
        "bucket if the period starts mid-week, and the last bucket, which holds today and a week "
        "that has not ended. Do not compare partial buckets with whole ones."
    )


class LedgerRead(ResponseModel):
    """Running totals since the start, as of now (fees and payments dated later are not included).
    `fees_charged_paise − collected_paise = outstanding_paise − unapplied_credit_paise`."""

    fees_charged_paise: int = Field(description="All late fees charged by now")
    collected_paise: int = Field(description="All payments received by now")
    outstanding_paise: int = Field(
        description="Total of the member balances above zero (see receivables.outstanding_paise)"
    )
    unapplied_credit_paise: int = Field(description="Total of the member balances below zero")
    members_with_balance: int
    members_over_limit: int


class MemberBalanceRead(ResponseModel):
    member_id: int
    member_name: str
    balance_paise: int


class PaymentsRead(ResponseModel):
    as_of: datetime
    window: WindowRead
    bucket: Bucket
    collected: ChangeRead = Field(description="Money received in the period, in paise")
    payments: ChangeRead = Field(description="Number of payments in the period")
    average_payment_paise: int | None
    fees_charged_paise: ChangeRead = Field(description="Late fees charged on returns in the period")
    collected_to_charged_pct: float | None = Field(
        description="Collected ÷ fees charged in the period; can exceed 100 when old fees are paid"
    )
    series: list[PaymentBucketRead] = Field(description="One entry per bucket, empty ones included")
    ledger: LedgerRead
    top_balances: list[MemberBalanceRead] = Field(
        description="Up to 5 members with the largest balances above zero; members in credit are "
        "never listed"
    )


# --- utilization -----------------------------------------------------------------------------


CATEGORY_NOTE = (
    "Items are grouped by their category folded to lower case by the database's own lower(), as "
    "the `category` filter of GET /items folds the column; the spelling shown is the first in "
    "string order. SQLite folds only ASCII letters, so on SQLite 'École' and 'école' are two "
    "categories (PostgreSQL folds according to its locale)"
)


class UtilizationFleetRead(ResponseModel):
    items: int = Field(
        description="Items in the fleet. Every item counts for the whole measured time: the "
        "database does not record when an item was added"
    )
    under_maintenance_now: int = Field(
        description="Items under maintenance right now (informational). They stay in the fleet "
        "above: the database keeps no history of maintenance, so no maintenance time is removed"
    )


class UtilizationFigureRead(ResponseModel):
    checked_out_item_days: float = Field(
        description="Total time items spent checked out (overdue included), in days with two "
        "decimals. Reserved time is not counted"
    )
    fleet_item_days: float = Field(
        description="Time the fleet could have been out: items × measured time, in days"
    )
    utilization_pct: float | None = Field(
        description="checked_out_item_days ÷ fleet_item_days; null when there is no fleet or no "
        "time has passed yet"
    )


class UtilizationBucketRead(ResponseModel):
    start: date = Field(description="First IST day of the bucket (a Monday for weekly buckets)")
    covered_from: date = Field(description="First day of the bucket inside the report period")
    covered_to: date = Field(description="Last day of the bucket inside the report period")
    partial: bool = Field(
        description="True when the bucket is not a whole day or week of finished time: the first "
        "weekly bucket if the period starts mid-week, and the last bucket, which holds today so "
        "far. Its fleet_item_days is smaller, so compare utilization_pct, not item-days"
    )
    checked_out_item_days: float
    fleet_item_days: float
    utilization_pct: float | None


class CategoryUtilizationRead(ResponseModel):
    category: str = Field(description=CATEGORY_NOTE)
    items: int
    checked_out_item_days: float
    fleet_item_days: float
    utilization_pct: float | None


class UtilizationRead(ResponseModel):
    """How much of the fleet's time was spent checked out.

    Measured time runs from the first IST midnight of the period up to `as_of`: only time that has
    passed counts. `previous` measures the same length of time from the start of the previous
    period, so the two percentages are comparable. An item is checked out from its check-out until
    its return (or `as_of` while it is still out).

    Limitation: the database holds no maintenance history, only each item's current status. An
    item that was under maintenance, or not yet bought, still counts as available fleet time, so
    utilization is understated whenever the fleet was not fully usable. Nothing is estimated."""

    as_of: datetime
    window: WindowRead
    bucket: Bucket
    fleet: UtilizationFleetRead
    current: UtilizationFigureRead = Field(description="From the start of the period up to now")
    previous: UtilizationFigureRead = Field(
        description="The same length of time from the start of the previous period"
    )
    change_points: float | None = Field(
        description="current minus previous utilization, in percentage points; null if either is"
    )
    series: list[UtilizationBucketRead] = Field(
        description="One entry per IST day or week, empty ones included"
    )
    by_category: list[CategoryUtilizationRead] = Field(
        description="Most checked-out time first. Categories with no items never appear"
    )


# --- demand ----------------------------------------------------------------------------------


class FunnelRead(ResponseModel):
    """What became of the reservations made in a period, judged at `as_of`. Every reservation is
    in exactly one of `checked_out`, `cancelled`, `expired` or `still_held`."""

    reserved: int = Field(description="Reservations made in the period")
    checked_out: int = Field(description="Of those, handed over to the member by now")
    returned: int = Field(description="Of the checked-out ones, already returned")
    cancelled: int = Field(
        description="Cancelled by now. A reservation cancelled because its item went into "
        "maintenance looks the same: the database does not record why"
    )
    expired: int = Field(
        description="The 48-hour hold ran out by now, whether or not that has been saved yet"
    )
    still_held: int = Field(description="Waiting, with the hold not yet run out")
    conversion_rate_pct: float | None = Field(
        description="checked_out ÷ (checked_out + cancelled + expired), the reservations that "
        "have been settled; null if none has. Outcomes are judged at `as_of`, so this rate is not "
        "maturity-adjusted when compared with `previous_funnel`'s"
    )


class CategoryDemandRead(ResponseModel):
    category: str = Field(description=CATEGORY_NOTE)
    items: int = Field(description="Items in the category now")
    reservations: int = Field(description="Reservations made in the period")
    checked_out: int = Field(description="Of those, handed over by now")
    share_pct: float | None = Field(description="Share of all reservations in the period")
    reservations_per_item: float | None


class TopItemRead(ResponseModel):
    item_id: int
    item_name: str
    category: str
    reservations: int = Field(description="Reservations made in the period")
    checked_out: int = Field(description="Of those, handed over by now")
    current_status: ItemStatus = Field(description="Status now, as `GET /items` shows it")


class DemandRead(ResponseModel):
    """Demand is the reservations members made in the period. Attempts to reserve an item that was
    not available are not recorded anywhere, so unmet demand cannot be measured."""

    as_of: datetime
    window: WindowRead
    reservations: ChangeRead = Field(description="Reservations made, against the same elapsed time")
    funnel: FunnelRead = Field(description="Reservations made in the period")
    previous_funnel: FunnelRead = Field(
        description="Reservations made in the previous period up to `window.previous_through`. "
        "Their outcomes are judged at `as_of`, not at `previous_through`, so they have had longer "
        "to be settled than the current funnel's: its `still_held` is smaller and its "
        "`conversion_rate_pct` is not maturity-adjusted against the current funnel's"
    )
    categories: list[CategoryDemandRead] = Field(
        description="Most reservations first; categories with no reservations are listed too"
    )
    top_items: list[TopItemRead] = Field(
        description="Up to 5 items with the most reservations in the period (ties: most checked "
        "out, then lowest id); items nobody reserved are not listed"
    )


# --- maintenance -----------------------------------------------------------------------------


class MaintenanceLoanRead(ResponseModel):
    loan_id: int
    checked_out_at: datetime
    due_at: datetime
    overdue: bool = Field(description="Past the due time at `as_of`")
    days_overdue: int = Field(description="Late days so far, rounded up; 0 if not overdue")


class MaintenanceItemRead(ResponseModel):
    item_id: int
    item_name: str
    category: str
    condition_note: str
    open_loan: MaintenanceLoanRead | None = Field(
        description="The loan still open on this item, if any. Maintenance does not end a loan: "
        "the member can still return the item (and be charged), after which it stays here"
    )


class CategoryMaintenanceRead(ResponseModel):
    category: str = Field(description=CATEGORY_NOTE)
    items: int = Field(description="Items in the category now")
    under_maintenance: int
    share_pct: float | None = Field(description="under_maintenance ÷ items")


class MaintenanceRead(ResponseModel):
    """Which items are under maintenance right now, and how that fits the fleet.

    This is a snapshot, not a history. The database stores only each item's current status; it
    never records when maintenance started or ended, so there are no downtime durations, no
    trends and no counts of past maintenance, and none are inferred from loans or anything else.
    `history_available` is always false.

    `fleet` agrees with `GET /items?status=`, and the items listed are the ones
    `GET /items?status=under_maintenance` returns. Maintenance itself is stored status, so only
    the other fleet counts (a lapsed hold, a late loan) move with `X-Test-Clock`."""

    as_of: datetime
    history_available: bool = Field(
        description="Always false: maintenance start and end times are not recorded"
    )
    fleet: FleetRead
    share_of_fleet_pct: float | None = Field(
        description="under_maintenance ÷ total_items now; null if there are no items"
    )
    on_loan: int = Field(
        description="Items under maintenance that a member still has on loan (an open loan)"
    )
    on_loan_overdue: int = Field(description="Of those, loans past their due time")
    without_open_loan: int = Field(
        description="Items under maintenance with no open loan: staff can bring these back now. "
        "on_loan + without_open_loan = fleet.under_maintenance"
    )
    by_category: list[CategoryMaintenanceRead] = Field(
        description="Most items under maintenance first; categories with none are listed too"
    )
    items: list[MaintenanceItemRead] = Field(
        description="The items under maintenance, by name, up to 50"
    )
    items_truncated: bool = Field(
        description="True when more than 50 items are under maintenance and the list is cut"
    )

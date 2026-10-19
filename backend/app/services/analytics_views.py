"""What the analytics service returns: plain frozen dataclasses the API layer turns into JSON."""

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.analytics import Bucket
from app.domain.enums import ItemStatus


@dataclass(frozen=True)
class WindowView:
    """The report window, as IST calendar dates (both ends included), and what it is compared with.

    The previous period is counted only up to `previous_through`, the same elapsed time as the
    current one, so `previous_end_date` is the day that point falls on.
    """

    days: int
    start_date: date
    end_date: date
    previous_start_date: date
    previous_end_date: date
    previous_through: datetime


@dataclass(frozen=True)
class ChangeView:
    """A count or an amount for the window, for the window before it, and the percentage change."""

    current: int
    previous: int
    change_pct: float | None


@dataclass(frozen=True)
class RateView:
    current_pct: float | None
    previous_pct: float | None


@dataclass(frozen=True)
class FleetView:
    """Items by status right now (a lapsed hold counts as available, a late loan as overdue)."""

    total_items: int
    available: int
    reserved: int
    checked_out: int
    overdue: int
    under_maintenance: int


@dataclass(frozen=True)
class LoansNowView:
    """Loans right now. `active` is held reservations plus checked-out loans (overdue included)."""

    active: int
    reserved: int
    checked_out: int
    overdue: int
    overdue_share_pct: float | None


@dataclass(frozen=True)
class MembersView:
    total: int
    active: int
    suspended: int
    blocked: int
    blocked_suspended: int
    blocked_unpaid_fees: int
    blocked_long_overdue: int


@dataclass(frozen=True)
class ReceivablesView:
    """Money owed (balances above zero) and money paid ahead (balances below zero), apart."""

    outstanding_paise: int
    unapplied_credit_paise: int
    members_with_balance: int
    members_over_limit: int


@dataclass(frozen=True)
class SummaryView:
    as_of: datetime
    window: WindowView
    fleet: FleetView
    loans: LoansNowView
    members: MembersView
    receivables: ReceivablesView
    reservations_created: ChangeView
    checkouts: ChangeView
    returns: ChangeView
    late_return_rate: RateView
    payments_collected_paise: ChangeView
    fees_charged_paise: ChangeView


@dataclass(frozen=True)
class AgingBandView:
    label: str
    min_days: int
    max_days: int | None
    count: int
    accrued_fee_paise: int


@dataclass(frozen=True)
class OverdueNowView:
    count: int
    accrued_fee_paise: int
    blocking_count: int
    oldest_days_overdue: int | None
    bands: list[AgingBandView]


@dataclass(frozen=True)
class OverdueMemberView:
    member_id: int
    member_name: str
    loans: int
    longest_days_overdue: int
    accrued_fee_paise: int


@dataclass(frozen=True)
class LateReturnsView:
    returned: int
    late: int
    late_rate_pct: float | None
    average_days_late: float | None
    fees_charged_paise: int


@dataclass(frozen=True)
class OverdueAgingView:
    as_of: datetime
    window: WindowView
    open: OverdueNowView
    top_members: list[OverdueMemberView]
    returns: LateReturnsView


@dataclass(frozen=True)
class PaymentBucketView:
    start: date
    collected_paise: int
    count: int
    covered_from: date
    covered_to: date
    partial: bool


@dataclass(frozen=True)
class LedgerView:
    fees_charged_paise: int
    collected_paise: int
    outstanding_paise: int
    unapplied_credit_paise: int
    members_with_balance: int
    members_over_limit: int


@dataclass(frozen=True)
class MemberBalanceView:
    member_id: int
    member_name: str
    balance_paise: int


@dataclass(frozen=True)
class PaymentsView:
    as_of: datetime
    window: WindowView
    bucket: Bucket
    collected: ChangeView
    payments: ChangeView
    average_payment_paise: int | None
    fees_charged_paise: ChangeView
    collected_to_charged_pct: float | None
    series: list[PaymentBucketView]
    ledger: LedgerView
    top_balances: list[MemberBalanceView]


# --- utilization -----------------------------------------------------------------------------


@dataclass(frozen=True)
class UtilizationFleetView:
    items: int
    under_maintenance_now: int


@dataclass(frozen=True)
class UtilizationFigureView:
    checked_out_item_days: float
    fleet_item_days: float
    utilization_pct: float | None


@dataclass(frozen=True)
class UtilizationBucketView:
    start: date
    covered_from: date
    covered_to: date
    partial: bool
    checked_out_item_days: float
    fleet_item_days: float
    utilization_pct: float | None


@dataclass(frozen=True)
class CategoryUtilizationView:
    category: str
    items: int
    checked_out_item_days: float
    fleet_item_days: float
    utilization_pct: float | None


@dataclass(frozen=True)
class UtilizationView:
    as_of: datetime
    window: WindowView
    bucket: Bucket
    fleet: UtilizationFleetView
    current: UtilizationFigureView
    previous: UtilizationFigureView
    change_points: float | None
    series: list[UtilizationBucketView]
    by_category: list[CategoryUtilizationView]


# --- demand ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class FunnelView:
    reserved: int
    checked_out: int
    returned: int
    cancelled: int
    expired: int
    still_held: int
    conversion_rate_pct: float | None


@dataclass(frozen=True)
class CategoryDemandView:
    category: str
    items: int
    reservations: int
    checked_out: int
    share_pct: float | None
    reservations_per_item: float | None


@dataclass(frozen=True)
class TopItemView:
    item_id: int
    item_name: str
    category: str
    reservations: int
    checked_out: int
    current_status: ItemStatus


@dataclass(frozen=True)
class DemandView:
    as_of: datetime
    window: WindowView
    reservations: ChangeView
    funnel: FunnelView
    previous_funnel: FunnelView
    categories: list[CategoryDemandView]
    top_items: list[TopItemView]


# --- maintenance -----------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceLoanView:
    loan_id: int
    checked_out_at: datetime
    due_at: datetime
    overdue: bool
    days_overdue: int


@dataclass(frozen=True)
class MaintenanceItemView:
    item_id: int
    item_name: str
    category: str
    condition_note: str
    open_loan: MaintenanceLoanView | None


@dataclass(frozen=True)
class CategoryMaintenanceView:
    category: str
    items: int
    under_maintenance: int
    share_pct: float | None


@dataclass(frozen=True)
class MaintenanceView:
    as_of: datetime
    history_available: bool
    fleet: FleetView
    share_of_fleet_pct: float | None
    on_loan: int
    on_loan_overdue: int
    without_open_loan: int
    by_category: list[CategoryMaintenanceView]
    items: list[MaintenanceItemView]
    items_truncated: bool

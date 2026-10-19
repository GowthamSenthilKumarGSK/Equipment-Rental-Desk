"""Read-only reporting for the analytics dashboard.

Every method reads a picture of the database, applies the domain rules to it and returns plain
views. Nothing is written and no reservation is expired: a hold that has lapsed but has not been
saved yet is judged by `effective_loan_status` / `current_item_status`, exactly as the item and
statement endpoints judge it, so the dashboard agrees with them.

"Now" comes from the injected clock, so `X-Test-Clock` moves every figure. Each request issues a
fixed number of queries; the volume of data only changes how many rows come back.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.clock import Clock
from app.db import transaction
from app.domain import analytics as reporting
from app.domain import utilization as usage
from app.domain.analytics import Bucket, Period
from app.domain.enums import BlockReason, ItemStatus, LoanStatus, MemberStatus
from app.domain.policy import BLOCKING_BALANCE_PAISE
from app.domain.rules import (
    calculate_late_fee_paise,
    effective_loan_status,
    is_overdue,
    late_fee_days,
    member_block_reasons,
)
from app.models import Item, Loan
from app.repositories import analytics as repo
from app.repositories import items as items_repo
from app.services.analytics_views import (
    AgingBandView,
    CategoryDemandView,
    CategoryMaintenanceView,
    CategoryUtilizationView,
    ChangeView,
    DemandView,
    FleetView,
    FunnelView,
    LateReturnsView,
    LedgerView,
    LoansNowView,
    MaintenanceItemView,
    MaintenanceLoanView,
    MaintenanceView,
    MemberBalanceView,
    MembersView,
    OverdueAgingView,
    OverdueMemberView,
    OverdueNowView,
    PaymentBucketView,
    PaymentsView,
    RateView,
    ReceivablesView,
    SummaryView,
    TopItemView,
    UtilizationBucketView,
    UtilizationFigureView,
    UtilizationFleetView,
    UtilizationView,
    WindowView,
)
from app.services.support import current_item_status

TOP_LIST_SIZE = 5
MAINTENANCE_LIST_SIZE = 50


@dataclass(frozen=True)
class _Ledgers:
    members: list["_MemberLedger"]
    fees_total_paise: int
    paid_total_paise: int


@dataclass(frozen=True)
class _MemberLedger:
    member_id: int
    name: str
    status: MemberStatus
    balance_paise: int
    reasons: list[BlockReason]


def _window(current: Period, compared: Period, days: int) -> WindowView:
    """`compared` is the part of the previous period that matches how far `current` has got."""
    return WindowView(
        days=days,
        start_date=current.first_day,
        end_date=current.last_day,
        previous_start_date=compared.first_day,
        previous_end_date=compared.last_day,
        previous_through=(compared.end - timedelta(microseconds=1)).astimezone(UTC),
    )


def _change(current: int, previous: int) -> ChangeView:
    return ChangeView(
        current=current, previous=previous, change_pct=reporting.change_pct(current, previous)
    )


def _returned_late(due_at: datetime, returned_at: datetime) -> bool:
    """A loan came back late if it was returned after its due time (the overdue rule's own test)."""
    return is_overdue(due_at, returned_at)


def _fleet(item_rows: Sequence[tuple[Item, Loan | None]], now: datetime) -> FleetView:
    """Items by status at `now`, exactly as `GET /items?status=` judges them."""
    statuses = Counter(current_item_status(item, loan, now) for item, loan in item_rows)
    return FleetView(
        total_items=len(item_rows),
        available=statuses[ItemStatus.AVAILABLE],
        reserved=statuses[ItemStatus.RESERVED],
        checked_out=statuses[ItemStatus.CHECKED_OUT],
        overdue=statuses[ItemStatus.OVERDUE],
        under_maintenance=statuses[ItemStatus.UNDER_MAINTENANCE],
    )


def _figure(busy: timedelta, items: int, measured: Period) -> UtilizationFigureView:
    """Checked-out time against the time `items` items could have been out over `measured`."""
    fleet_time = (measured.end - measured.start) * items
    return UtilizationFigureView(
        checked_out_item_days=usage.item_days(busy),
        fleet_item_days=usage.item_days(fleet_time),
        utilization_pct=reporting.ratio_pct(
            usage.duration_microseconds(busy), usage.duration_microseconds(fleet_time)
        ),
    )


@dataclass(frozen=True)
class _Categories:
    """The items grouped into categories without regard to case.

    The group of an item is its category folded by the database's own `lower()`
    (`repo.category_keys`), the same function the `category` filter of `GET /items` applies to the
    column, so the dashboard cannot group differently from the database. `label` is the spelling
    shown for a group: the first in plain string order.
    """

    sizes: Counter[str]
    label: dict[str, str]

    def order(self, key: str) -> tuple[str, str, str]:
        """How equal groups are told apart: by name ignoring case, then exactly, then by key."""
        label = self.label[key]
        return (label.casefold(), label, key)


def _group_by_category(items: Sequence[Item], keys: dict[int, str]) -> _Categories:
    sizes: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for item in items:
        key = keys[item.id]
        sizes[key] += 1
        labels[key] = min(labels.get(key, item.category), item.category)
    return _Categories(sizes=sizes, label=labels)


def _count_in(instants: Sequence[datetime], period: Period) -> int:
    return sum(1 for moment in instants if period.contains(moment))


class AnalyticsService:
    def __init__(self, session_factory: sessionmaker[Session], clock: Clock):
        self._session_factory = session_factory
        self._clock = clock

    # --- GET /analytics/summary -----------------------------------------------------------------

    def summary(self, *, days: int) -> SummaryView:
        now = self._clock.now()
        current, previous = reporting.reporting_periods(now, days)
        compared = reporting.comparison_period(current, previous, now)
        span_start, span_end = previous.start, current.end
        with transaction(self._session_factory) as session:
            item_rows = items_repo.find_with_active_loan(session, category=None, search=None)
            active_rows = repo.active_loans(session)
            reserved = repo.loan_instants(session, Loan.reserved_at, span_start, span_end, now)
            checked_out = repo.loan_instants(
                session, Loan.checked_out_at, span_start, span_end, now
            )
            returned = repo.returned_loans(session, span_start, span_end, now)
            payments = repo.payments_between(session, span_start, span_end, now)
            ledgers = self._ledgers(session, now).members

        fleet = _fleet(item_rows, now)

        held = sum(
            1
            for row in active_rows
            if row.status is LoanStatus.RESERVED
            and effective_loan_status(row.status, reserved_at=row.reserved_at, now=now)
            is LoanStatus.RESERVED
        )
        out = [row for row in active_rows if row.status is LoanStatus.CHECKED_OUT]
        late = sum(1 for row in out if is_overdue(row.due_at, now))
        loans = LoansNowView(
            active=held + len(out),
            reserved=held,
            checked_out=len(out),
            overdue=late,
            overdue_share_pct=reporting.ratio_pct(late, len(out)),
        )

        reasons = Counter(reason for ledger in ledgers for reason in ledger.reasons)
        members = MembersView(
            total=len(ledgers),
            active=sum(1 for ledger in ledgers if ledger.status is MemberStatus.ACTIVE),
            suspended=sum(1 for ledger in ledgers if ledger.status is MemberStatus.SUSPENDED),
            blocked=sum(1 for ledger in ledgers if ledger.reasons),
            blocked_suspended=reasons[BlockReason.SUSPENDED],
            blocked_unpaid_fees=reasons[BlockReason.UNPAID_FEES],
            blocked_long_overdue=reasons[BlockReason.LONG_OVERDUE],
        )
        receivables = self._receivables(ledgers)

        def returns_in(period: Period):
            return [row for row in returned if period.contains(row.returned_at)]

        now_returns, before_returns = returns_in(current), returns_in(compared)

        def late_in(rows) -> int:
            return sum(1 for row in rows if _returned_late(row.due_at, row.returned_at))

        def collected_in(period: Period) -> int:
            return sum(amount for paid_at, amount in payments if period.contains(paid_at))

        return SummaryView(
            as_of=now,
            window=_window(current, compared, days),
            fleet=fleet,
            loans=loans,
            members=members,
            receivables=receivables,
            reservations_created=_change(
                _count_in(reserved, current), _count_in(reserved, compared)
            ),
            checkouts=_change(_count_in(checked_out, current), _count_in(checked_out, compared)),
            returns=_change(len(now_returns), len(before_returns)),
            late_return_rate=RateView(
                current_pct=reporting.ratio_pct(late_in(now_returns), len(now_returns)),
                previous_pct=reporting.ratio_pct(late_in(before_returns), len(before_returns)),
            ),
            payments_collected_paise=_change(collected_in(current), collected_in(compared)),
            fees_charged_paise=_change(
                sum(row.fee_charged_paise for row in now_returns),
                sum(row.fee_charged_paise for row in before_returns),
            ),
        )

    # --- GET /analytics/overdue-aging -----------------------------------------------------------

    def overdue_aging(self, *, days: int) -> OverdueAgingView:
        now = self._clock.now()
        current, previous = reporting.reporting_periods(now, days)
        compared = reporting.comparison_period(current, previous, now)
        with transaction(self._session_factory) as session:
            overdue = repo.overdue_loans(session, now)
            returned = repo.returned_loans(session, current.start, current.end, now)

        counts = [0] * len(reporting.AGING_BANDS)
        fees = [0] * len(reporting.AGING_BANDS)
        blocking = 0
        by_member: dict[int, list] = {}
        for row in overdue:
            late_days = late_fee_days(row.due_at, now)
            fee = calculate_late_fee_paise(row.due_at, now, row.replacement_value_paise)
            index = reporting.aging_band_index(late_days)
            counts[index] += 1
            fees[index] += fee
            blocking += reporting.blocks_member(late_days)
            entry = by_member.setdefault(row.member_id, [row.member_name, 0, 0, 0])
            entry[1] += 1
            entry[2] = max(entry[2], late_days)
            entry[3] += fee

        bands = [
            AgingBandView(
                label=band.label,
                min_days=band.min_days,
                max_days=band.max_days,
                count=counts[index],
                accrued_fee_paise=fees[index],
            )
            for index, band in enumerate(reporting.AGING_BANDS)
        ]
        top_members = [
            OverdueMemberView(
                member_id=member_id,
                member_name=name,
                loans=loans,
                longest_days_overdue=longest,
                accrued_fee_paise=fee,
            )
            for member_id, (name, loans, longest, fee) in sorted(
                by_member.items(), key=lambda item: (-item[1][3], -item[1][2], item[0])
            )[:TOP_LIST_SIZE]
        ]

        late_returns = [row for row in returned if _returned_late(row.due_at, row.returned_at)]
        late_days_total = sum(late_fee_days(row.due_at, row.returned_at) for row in late_returns)
        return OverdueAgingView(
            as_of=now,
            window=_window(current, compared, days),
            open=OverdueNowView(
                count=len(overdue),
                accrued_fee_paise=sum(fees),
                blocking_count=blocking,
                oldest_days_overdue=late_fee_days(overdue[0].due_at, now) if overdue else None,
                bands=bands,
            ),
            top_members=top_members,
            returns=LateReturnsView(
                returned=len(returned),
                late=len(late_returns),
                late_rate_pct=reporting.ratio_pct(len(late_returns), len(returned)),
                average_days_late=reporting.average_1dp(late_days_total, len(late_returns)),
                fees_charged_paise=sum(row.fee_charged_paise for row in returned),
            ),
        )

    # --- GET /analytics/payments ----------------------------------------------------------------

    def payments(self, *, days: int, bucket: Bucket) -> PaymentsView:
        now = self._clock.now()
        current, previous = reporting.reporting_periods(now, days)
        compared = reporting.comparison_period(current, previous, now)
        with transaction(self._session_factory) as session:
            payments = repo.payments_between(session, previous.start, current.end, now)
            returned = repo.returned_loans(session, previous.start, current.end, now)
            book = self._ledgers(session, now)
        ledgers = book.members

        in_current = [
            (paid_at, amount) for paid_at, amount in payments if current.contains(paid_at)
        ]
        collected_now = sum(amount for _, amount in in_current)
        collected_before = sum(amount for paid_at, amount in payments if compared.contains(paid_at))
        fees_now = sum(
            row.fee_charged_paise for row in returned if current.contains(row.returned_at)
        )
        fees_before = sum(
            row.fee_charged_paise for row in returned if compared.contains(row.returned_at)
        )
        receivables = self._receivables(ledgers)
        owing = sorted(
            (ledger for ledger in ledgers if ledger.balance_paise > 0),
            key=lambda ledger: (-ledger.balance_paise, ledger.member_id),
        )
        return PaymentsView(
            as_of=now,
            window=_window(current, compared, days),
            bucket=bucket,
            collected=_change(collected_now, collected_before),
            payments=_change(
                len(in_current), sum(1 for paid_at, _ in payments if compared.contains(paid_at))
            ),
            average_payment_paise=reporting.average_paise(collected_now, len(in_current)),
            fees_charged_paise=_change(fees_now, fees_before),
            collected_to_charged_pct=reporting.ratio_pct(collected_now, fees_now),
            series=[
                PaymentBucketView(
                    start=slot.start,
                    collected_paise=slot.total,
                    count=slot.count,
                    covered_from=slot.covered_from,
                    covered_to=slot.covered_to,
                    partial=slot.partial,
                )
                for slot in reporting.bucketize(in_current, current, bucket)
            ],
            ledger=LedgerView(
                fees_charged_paise=book.fees_total_paise,
                collected_paise=book.paid_total_paise,
                outstanding_paise=receivables.outstanding_paise,
                unapplied_credit_paise=receivables.unapplied_credit_paise,
                members_with_balance=receivables.members_with_balance,
                members_over_limit=receivables.members_over_limit,
            ),
            top_balances=[
                MemberBalanceView(
                    member_id=ledger.member_id,
                    member_name=ledger.name,
                    balance_paise=ledger.balance_paise,
                )
                for ledger in owing[:TOP_LIST_SIZE]
            ],
        )

    # --- GET /analytics/utilization -------------------------------------------------------------

    def utilization(self, *, days: int, bucket: Bucket) -> UtilizationView:
        now = self._clock.now()
        current, previous = reporting.reporting_periods(now, days)
        compared = reporting.comparison_period(current, previous, now)
        measured, measured_before = usage.observed_periods(current, previous, now)
        with transaction(self._session_factory) as session:
            item_rows = items_repo.find_with_active_loan(session, category=None, search=None)
            usage_rows = repo.loan_usage(session, previous.start, now)
            keys = repo.category_keys(session)

        groups = _group_by_category([item for item, _ in item_rows], keys)
        sizes = groups.sizes
        under_maintenance = sum(
            1
            for item, loan in item_rows
            if current_item_status(item, loan, now) is ItemStatus.UNDER_MAINTENANCE
        )

        # A loan still out is out until `now`; one returned after `now` is clipped to the period.
        intervals = [(row.checked_out_at, row.returned_at or now) for row in usage_rows]
        by_category: dict[str, list[tuple[datetime, datetime]]] = {key: [] for key in sizes}
        for row, interval in zip(usage_rows, intervals, strict=True):
            by_category[keys[row.item_id]].append(interval)

        total = len(item_rows)
        current_figure = _figure(usage.busy_time(intervals, measured), total, measured)
        previous_figure = _figure(
            usage.busy_time(intervals, measured_before), total, measured_before
        )

        windows = usage.bucket_windows(current, measured, bucket)
        busy_in_window = usage.busy_by_window(intervals, [window.period for window in windows])
        series = []
        for window, busy in zip(windows, busy_in_window, strict=True):
            figure = _figure(busy, total, window.period)
            series.append(
                UtilizationBucketView(
                    start=window.start,
                    covered_from=window.covered_from,
                    covered_to=window.covered_to,
                    partial=window.partial,
                    checked_out_item_days=figure.checked_out_item_days,
                    fleet_item_days=figure.fleet_item_days,
                    utilization_pct=figure.utilization_pct,
                )
            )

        ranked = sorted(
            ((usage.busy_time(by_category[key], measured), key) for key in sizes),
            key=lambda entry: (-entry[0], groups.order(entry[1])),
        )
        categories = []
        for busy, key in ranked:
            figure = _figure(busy, sizes[key], measured)
            categories.append(
                CategoryUtilizationView(
                    category=groups.label[key],
                    items=sizes[key],
                    checked_out_item_days=figure.checked_out_item_days,
                    fleet_item_days=figure.fleet_item_days,
                    utilization_pct=figure.utilization_pct,
                )
            )
        return UtilizationView(
            as_of=now,
            window=_window(current, compared, days),
            bucket=bucket,
            fleet=UtilizationFleetView(items=total, under_maintenance_now=under_maintenance),
            current=current_figure,
            previous=previous_figure,
            change_points=usage.change_in_points(
                current_figure.utilization_pct, previous_figure.utilization_pct
            ),
            series=series,
            by_category=categories,
        )

    # --- GET /analytics/demand ------------------------------------------------------------------

    def demand(self, *, days: int) -> DemandView:
        now = self._clock.now()
        current, previous = reporting.reporting_periods(now, days)
        compared = reporting.comparison_period(current, previous, now)
        with transaction(self._session_factory) as session:
            item_rows = items_repo.find_with_active_loan(session, category=None, search=None)
            rows = repo.reservations_between(session, previous.start, current.end, now)
            keys = repo.category_keys(session)

        def outcome(row: repo.ReservationRow) -> usage.Outcome:
            return usage.reservation_outcome(
                reserved_at=row.reserved_at,
                checked_out_at=row.checked_out_at,
                cancelled_at=row.cancelled_at,
                now=now,
            )

        def funnel(cohort: list[repo.ReservationRow]) -> FunnelView:
            results = Counter(outcome(row) for row in cohort)
            converted = results[usage.Outcome.CONVERTED]
            cancelled = results[usage.Outcome.CANCELLED]
            expired = results[usage.Outcome.EXPIRED]
            return FunnelView(
                reserved=len(cohort),
                checked_out=converted,
                returned=sum(1 for row in cohort if row.returned_at and row.returned_at <= now),
                cancelled=cancelled,
                expired=expired,
                still_held=results[usage.Outcome.HELD],
                conversion_rate_pct=reporting.ratio_pct(converted, converted + cancelled + expired),
            )

        now_cohort = [row for row in rows if current.contains(row.reserved_at)]
        before_cohort = [row for row in rows if compared.contains(row.reserved_at)]

        items = {item.id: item for item, _ in item_rows}
        statuses = {item.id: current_item_status(item, loan, now) for item, loan in item_rows}
        groups = _group_by_category(list(items.values()), keys)
        sizes = groups.sizes
        asked: Counter[str] = Counter()
        handed_over: Counter[str] = Counter()
        item_asked: Counter[int] = Counter()
        item_handed: Counter[int] = Counter()
        for row in now_cohort:
            key = keys[row.item_id]
            asked[key] += 1
            item_asked[row.item_id] += 1
            if outcome(row) is usage.Outcome.CONVERTED:
                handed_over[key] += 1
                item_handed[row.item_id] += 1

        categories = [
            CategoryDemandView(
                category=groups.label[key],
                items=sizes[key],
                reservations=asked[key],
                checked_out=handed_over[key],
                share_pct=reporting.ratio_pct(asked[key], len(now_cohort)),
                reservations_per_item=reporting.average_1dp(asked[key], sizes[key]),
            )
            for key in sorted(sizes, key=lambda key: (-asked[key], groups.order(key)))
        ]
        top = sorted(item_asked, key=lambda i: (-item_asked[i], -item_handed[i], i))
        return DemandView(
            as_of=now,
            window=_window(current, compared, days),
            reservations=_change(len(now_cohort), len(before_cohort)),
            funnel=funnel(now_cohort),
            previous_funnel=funnel(before_cohort),
            categories=categories,
            top_items=[
                TopItemView(
                    item_id=item_id,
                    item_name=items[item_id].name,
                    category=items[item_id].category,
                    reservations=item_asked[item_id],
                    checked_out=item_handed[item_id],
                    current_status=statuses[item_id],
                )
                for item_id in top[:TOP_LIST_SIZE]
            ],
        )

    # --- GET /analytics/maintenance -------------------------------------------------------------

    def maintenance(self) -> MaintenanceView:
        """A snapshot of the items under maintenance right now. There is no history to report:
        the database stores only each item's current status, never when maintenance began or
        ended, so nothing here is a duration, a trend or a count of past maintenance."""
        now = self._clock.now()
        with transaction(self._session_factory) as session:
            item_rows = items_repo.find_with_active_loan(session, category=None, search=None)
            keys = repo.category_keys(session)

        groups = _group_by_category([item for item, _ in item_rows], keys)
        fleet = _fleet(item_rows, now)
        in_maintenance = [
            (item, loan)
            for item, loan in item_rows
            if current_item_status(item, loan, now) is ItemStatus.UNDER_MAINTENANCE
        ]

        def open_loan(loan: Loan | None) -> MaintenanceLoanView | None:
            if loan is None or loan.status is not LoanStatus.CHECKED_OUT:
                return None
            late = is_overdue(loan.due_at, now)
            return MaintenanceLoanView(
                loan_id=loan.id,
                checked_out_at=loan.checked_out_at,
                due_at=loan.due_at,
                overdue=late,
                days_overdue=late_fee_days(loan.due_at, now) if late else 0,
            )

        entries = [
            MaintenanceItemView(
                item_id=item.id,
                item_name=item.name,
                category=item.category,
                condition_note=item.condition_note,
                open_loan=open_loan(loan),
            )
            for item, loan in sorted(
                in_maintenance, key=lambda row: (row[0].name.casefold(), row[0].name, row[0].id)
            )
        ]
        on_loan = [entry for entry in entries if entry.open_loan is not None]
        under: Counter[str] = Counter(keys[item.id] for item, _ in in_maintenance)
        return MaintenanceView(
            as_of=now,
            history_available=False,
            fleet=fleet,
            share_of_fleet_pct=reporting.ratio_pct(fleet.under_maintenance, fleet.total_items),
            on_loan=len(on_loan),
            on_loan_overdue=sum(1 for entry in on_loan if entry.open_loan.overdue),
            without_open_loan=len(entries) - len(on_loan),
            by_category=[
                CategoryMaintenanceView(
                    category=groups.label[key],
                    items=groups.sizes[key],
                    under_maintenance=under[key],
                    share_pct=reporting.ratio_pct(under[key], groups.sizes[key]),
                )
                for key in sorted(groups.sizes, key=lambda key: (-under[key], groups.order(key)))
            ],
            items=entries[:MAINTENANCE_LIST_SIZE],
            items_truncated=len(entries) > MAINTENANCE_LIST_SIZE,
        )

    # --- shared ---------------------------------------------------------------------------------

    @staticmethod
    def _ledgers(session: Session, now: datetime) -> _Ledgers:
        """Each member's balance and block reasons as of `now`, from grouped queries.

        Fees and payments dated after `now` (only possible under a pretend clock) are not counted,
        the same cut-off the period figures use.
        """
        fees = repo.fees_by_member(session, now)
        paid = repo.payments_by_member(session, now)
        oldest_due = repo.oldest_due_by_member(session, now)
        ledgers = []
        for row in repo.members(session):
            balance = fees.get(row.member_id, 0) - paid.get(row.member_id, 0)
            due = oldest_due.get(row.member_id)
            ledgers.append(
                _MemberLedger(
                    member_id=row.member_id,
                    name=row.name,
                    status=row.status,
                    balance_paise=balance,
                    reasons=member_block_reasons(
                        status=row.status,
                        balance_paise=balance,
                        longest_overdue=None if due is None else now - due,
                    ),
                )
            )
        return _Ledgers(
            members=ledgers,
            fees_total_paise=sum(fees.values()),
            paid_total_paise=sum(paid.values()),
        )

    @staticmethod
    def _receivables(ledgers: list[_MemberLedger]) -> ReceivablesView:
        return ReceivablesView(
            outstanding_paise=sum(
                ledger.balance_paise for ledger in ledgers if ledger.balance_paise > 0
            ),
            unapplied_credit_paise=-sum(
                ledger.balance_paise for ledger in ledgers if ledger.balance_paise < 0
            ),
            members_with_balance=sum(1 for ledger in ledgers if ledger.balance_paise > 0),
            members_over_limit=sum(
                1 for ledger in ledgers if ledger.balance_paise > BLOCKING_BALANCE_PAISE
            ),
        )

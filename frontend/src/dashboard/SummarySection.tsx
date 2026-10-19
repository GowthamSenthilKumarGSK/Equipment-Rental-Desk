import { formatCount, formatPct, formatRupees } from "../format";
import type { AnalyticsSummary } from "../types";
import { PeriodNote, Stat, Stats } from "./ReportSection";
import { versusPrevious } from "./versus";
import { membersOwe } from "./wording";

/** Headline figures. The first group is how things stand now; the second is activity in the period. */
export function SummaryView({ data }: { data: AnalyticsSummary }) {
  const { fleet, loans, members, receivables } = data;
  return (
    <>
      <PeriodNote window={data.window} asOf={data.as_of} />
      <h3>Right now</h3>
      <Stats label="Current position">
        <Stat
          label="Items in the fleet"
          icon="box"
          value={formatCount(fleet.total_items)}
          note={`${fleet.available} available · ${fleet.reserved} reserved · ${fleet.checked_out} checked out · ${fleet.overdue} overdue · ${fleet.under_maintenance} under maintenance`}
        />
        <Stat
          label="Active loans"
          icon="clock"
          tone="info"
          value={formatCount(loans.active)}
          note={`${loans.reserved} reserved · ${loans.checked_out} checked out · ${loans.overdue} overdue (${formatPct(loans.overdue_share_pct)} of checked out)`}
        />
        <Stat
          label="Members"
          icon="users"
          value={formatCount(members.total)}
          note={`${members.active} active · ${members.suspended} suspended · ${members.blocked} cannot borrow right now`}
        />
        <Stat
          label="Fees outstanding"
          icon="wallet"
          tone="warn"
          value={formatRupees(receivables.outstanding_paise)}
          note={`${membersOwe(receivables.members_with_balance)} · ${receivables.members_over_limit} over the ₹100 limit · ${formatRupees(receivables.unapplied_credit_paise)} paid ahead`}
        />
      </Stats>
      {fleet.overdue !== loans.overdue && (
        <p className="hint">
          Overdue items ({fleet.overdue}) and overdue loans ({loans.overdue}) differ: a late loan on
          an item that was put under maintenance counts as a loan, but the item shows as under
          maintenance.
        </p>
      )}

      <h3>In this period</h3>
      <Stats label="Activity in the period">
        <Stat
          label="Reservations made"
          icon="calendar"
          tone="info"
          value={formatCount(data.reservations_created.current)}
          note={versusPrevious(data.reservations_created)}
        />
        <Stat
          label="Items checked out"
          icon="box"
          tone="info"
          value={formatCount(data.checkouts.current)}
          note={versusPrevious(data.checkouts)}
        />
        <Stat
          label="Items returned"
          icon="check"
          tone="ok"
          value={formatCount(data.returns.current)}
          note={versusPrevious(data.returns)}
        />
        <Stat
          label="Late returns"
          icon="warning"
          tone="orange"
          value={formatPct(data.late_return_rate.current_pct)}
          note={`${formatPct(data.late_return_rate.previous_pct)} before`}
        />
        <Stat
          label="Payments collected"
          icon="rupee"
          tone="ok"
          value={formatRupees(data.payments_collected_paise.current)}
          note={versusPrevious(data.payments_collected_paise, formatRupees)}
        />
        <Stat
          label="Late fees charged"
          icon="rupee"
          tone="orange"
          value={formatRupees(data.fees_charged_paise.current)}
          note={versusPrevious(data.fees_charged_paise, formatRupees)}
        />
      </Stats>
    </>
  );
}

import { Link } from "react-router-dom";
import { bucketLabels, formatCount, formatRupees } from "../format";
import type { PaymentsReport } from "../types";
import { ColumnChart, type Bar } from "./charts";
import { PeriodNote, Stat, Stats } from "./ReportSection";
import { niceMaxPaise } from "./axis";
import { versusPrevious } from "./versus";
import { collectedAgainstCharged } from "./wording";

export function PaymentsView({ data }: { data: PaymentsReport }) {
  const bars: Bar[] = data.series.map((slot) => ({
    key: slot.start,
    ...bucketLabels(slot.start, data.bucket),
    value: slot.collected_paise,
    valueText: `${formatRupees(slot.collected_paise)} (${slot.count} ${slot.count === 1 ? "payment" : "payments"})`,
    partial: slot.partial,
  }));
  const biggest = data.series.reduce<(typeof data.series)[number] | undefined>(
    (best, slot) => (slot.collected_paise > (best?.collected_paise ?? 0) ? slot : best),
    undefined,
  );
  const summary = biggest
    ? `Most collected: ${formatRupees(biggest.collected_paise)} in ${bucketLabels(biggest.start, data.bucket).label}.`
    : "No payments were collected in this period.";
  const { ledger } = data;

  return (
    <>
      <PeriodNote window={data.window} asOf={data.as_of} />
      <Stats label="Payments in the period">
        <Stat
          label="Collected"
          value={formatRupees(data.collected.current)}
          note={versusPrevious(data.collected, formatRupees)}
        />
        <Stat
          label="Payments received"
          value={formatCount(data.payments.current)}
          note={versusPrevious(data.payments)}
        />
        <Stat
          label="Average payment"
          value={
            data.average_payment_paise === null ? "—" : formatRupees(data.average_payment_paise)
          }
        />
        <Stat
          label="Late fees charged"
          value={formatRupees(data.fees_charged_paise.current)}
          note={collectedAgainstCharged(data.collected_to_charged_pct)}
        />
      </Stats>
      <ColumnChart
        title={`Payments collected by ${data.bucket}`}
        summary={summary}
        valueHeading="Collected"
        bars={bars}
        max={niceMaxPaise(Math.max(0, ...data.series.map((slot) => slot.collected_paise)))}
        axisText={formatRupees}
      />

      <h3>All time, as of now</h3>
      <Stats label="Fees and payments to date">
        <Stat label="Fees charged" value={formatRupees(ledger.fees_charged_paise)} />
        <Stat label="Payments received" value={formatRupees(ledger.collected_paise)} />
        <Stat
          label="Still owed"
          value={formatRupees(ledger.outstanding_paise)}
          note={`${ledger.members_with_balance} with a balance · ${ledger.members_over_limit} over the ₹100 limit`}
        />
        <Stat
          label="Paid ahead"
          value={formatRupees(ledger.unapplied_credit_paise)}
          note="not subtracted from what others owe"
        />
      </Stats>

      <h3>Largest balances</h3>
      {data.top_balances.length === 0 ? (
        <p className="muted">No member owes anything.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption>Members who owe the most</caption>
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col" className="num">
                  Balance
                </th>
              </tr>
            </thead>
            <tbody>
              {data.top_balances.map((row) => (
                <tr key={row.member_id}>
                  <td>
                    <Link to={`/members/${row.member_id}`}>{row.member_name}</Link>
                  </td>
                  <td className="num">{formatRupees(row.balance_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

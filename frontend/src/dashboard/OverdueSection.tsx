import { Link } from "react-router-dom";
import { formatCount, formatPct, formatRupees, pluralise } from "../format";
import type { OverdueAging } from "../types";
import { BarList } from "./charts";
import { PeriodNote, Stat, Stats } from "./ReportSection";

export function OverdueView({ data }: { data: OverdueAging }) {
  const { open, returns } = data;
  return (
    <>
      <PeriodNote window={data.window} asOf={data.as_of} />
      <Stats label="Overdue now">
        <Stat
          label="Loans overdue now"
          value={formatCount(open.count)}
          note={
            open.oldest_days_overdue === null
              ? "nothing is overdue"
              : `oldest ${pluralise(open.oldest_days_overdue, "day")} overdue`
          }
        />
        <Stat
          label="Fees if all returned now"
          value={formatRupees(open.accrued_fee_paise)}
          note="an estimate: a fee is only charged when the item comes back"
        />
        <Stat
          label="Overdue by more than 14 days"
          value={formatCount(open.blocking_count)}
          note="their members cannot borrow until returned"
        />
      </Stats>

      <h3>How long they have been overdue</h3>
      {open.count === 0 ? (
        <p className="muted">Nothing is overdue.</p>
      ) : (
        <BarList
          label="Overdue loans by age"
          rows={open.bands.map((band) => ({
            key: band.label,
            label: band.label,
            value: band.count,
            valueText: pluralise(band.count, "loan"),
            note: `fees if returned now ${formatRupees(band.accrued_fee_paise)}`,
          }))}
        />
      )}

      <h3>Who owes most</h3>
      {data.top_members.length === 0 ? (
        <p className="muted">No member has an overdue loan.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption>Members with overdue loans, highest fees first</caption>
            <thead>
              <tr>
                <th scope="col">Member</th>
                <th scope="col" className="num">
                  Loans
                </th>
                <th scope="col" className="num">
                  Longest overdue
                </th>
                <th scope="col" className="num">
                  Fees if returned now
                </th>
              </tr>
            </thead>
            <tbody>
              {data.top_members.map((row) => (
                <tr key={row.member_id}>
                  <td>
                    <Link to={`/members/${row.member_id}`}>{row.member_name}</Link>
                  </td>
                  <td className="num">{formatCount(row.loans)}</td>
                  <td className="num">{pluralise(row.longest_days_overdue, "day")}</td>
                  <td className="num">{formatRupees(row.accrued_fee_paise)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="hint">
        <Link to="/overdue">See every overdue loan</Link>
      </p>

      <h3>Loans returned in this period</h3>
      {returns.returned === 0 ? (
        <p className="muted">No loan was returned in this period.</p>
      ) : (
        <Stats label="Returns in the period">
          <Stat label="Returned" value={formatCount(returns.returned)} />
          <Stat
            label="Returned late"
            value={formatCount(returns.late)}
            note={`${formatPct(returns.late_rate_pct)} of returns`}
          />
          <Stat
            label="Average days late"
            value={returns.average_days_late === null ? "—" : String(returns.average_days_late)}
            note="of the late returns"
          />
          <Stat label="Fees charged" value={formatRupees(returns.fees_charged_paise)} />
        </Stats>
      )}
    </>
  );
}

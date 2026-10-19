import { Link } from "react-router-dom";
import { formatCount, formatIst, formatPct, pluralise } from "../format";
import type { MaintenanceReport } from "../types";
import { BarList } from "./charts";
import { Limitation, Stat, Stats } from "./ReportSection";

export function MaintenanceView({ data }: { data: MaintenanceReport }) {
  const { fleet } = data;
  return (
    <>
      <Limitation title="A snapshot, not a history">
        This shows what is under maintenance as of {formatIst(data.as_of)}. The system records only
        each item&apos;s current status, never when maintenance started or ended, so downtime,
        trends and past maintenance are not available and are not estimated.
      </Limitation>
      <Stats label="Maintenance now">
        <Stat
          label="Items under maintenance"
          value={formatCount(fleet.under_maintenance)}
          note={`${formatPct(data.share_of_fleet_pct)} of ${fleet.total_items} items`}
        />
        <Stat
          label="Still on loan"
          value={formatCount(data.on_loan)}
          note={`${data.on_loan_overdue} of them overdue`}
        />
        <Stat
          label="Ready to bring back"
          value={formatCount(data.without_open_loan)}
          note="no member has them on loan"
        />
      </Stats>

      <h3>The rest of the fleet</h3>
      <BarList
        label="Items by status"
        max={fleet.total_items}
        rows={[
          { key: "available", label: "Available", value: fleet.available },
          { key: "reserved", label: "Reserved", value: fleet.reserved },
          { key: "checked_out", label: "Checked out", value: fleet.checked_out },
          { key: "overdue", label: "Overdue", value: fleet.overdue },
          { key: "under_maintenance", label: "Under maintenance", value: fleet.under_maintenance },
        ].map((row) => ({ ...row, valueText: formatCount(row.value) }))}
      />

      <h3>Under maintenance</h3>
      {data.items.length === 0 ? (
        <p className="muted">No item is under maintenance.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption>Items under maintenance</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Category</th>
                <th scope="col">Condition note</th>
                <th scope="col">Loan</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.item_id}>
                  <td>
                    <Link to={`/items/${row.item_id}`}>{row.item_name}</Link>
                  </td>
                  <td>{row.category}</td>
                  <td>{row.condition_note || "—"}</td>
                  <td>
                    {row.open_loan === null
                      ? "None: can be brought back"
                      : row.open_loan.overdue
                        ? `Overdue by ${pluralise(row.open_loan.days_overdue, "day")}`
                        : `On loan, due ${formatIst(row.open_loan.due_at)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data.items_truncated && (
        <p className="hint">
          Only the first {data.items.length} of {fleet.under_maintenance} items are listed. See{" "}
          <Link to="/items?status=under_maintenance">all items under maintenance</Link>.
        </p>
      )}

      <h3>By category</h3>
      {data.by_category.length === 0 ? (
        <p className="muted">There are no items yet.</p>
      ) : (
        <BarList
          label="Items under maintenance by category"
          max={Math.max(1, ...data.by_category.map((row) => row.items))}
          rows={data.by_category.map((row) => ({
            key: row.category,
            label: row.category,
            value: row.under_maintenance,
            valueText: `${row.under_maintenance} of ${row.items}`,
            note: formatPct(row.share_pct),
          }))}
        />
      )}
    </>
  );
}

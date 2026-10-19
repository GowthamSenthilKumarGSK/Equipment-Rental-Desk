import { Link } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { formatCount, formatPct } from "../format";
import type { DemandReport, Funnel } from "../types";
import { BarList } from "./charts";
import { Limitation, PeriodNote, Stat, Stats } from "./ReportSection";
import { versusPrevious } from "./versus";
import { previousConversionNote } from "./wording";

function funnelRows(funnel: Funnel) {
  const share = (count: number) =>
    funnel.reserved > 0
      ? `${formatPct(Math.round((count / funnel.reserved) * 1000) / 10)} of reserved`
      : "";
  return [
    {
      key: "reserved",
      label: "Reserved",
      value: funnel.reserved,
      valueText: formatCount(funnel.reserved),
      note: "",
    },
    {
      key: "checked_out",
      label: "Checked out",
      value: funnel.checked_out,
      valueText: formatCount(funnel.checked_out),
      note: share(funnel.checked_out),
    },
    {
      key: "returned",
      label: "Returned",
      value: funnel.returned,
      valueText: formatCount(funnel.returned),
      note: `of those checked out`,
    },
    {
      key: "cancelled",
      label: "Cancelled",
      value: funnel.cancelled,
      valueText: formatCount(funnel.cancelled),
      note: share(funnel.cancelled),
    },
    {
      key: "expired",
      label: "Hold ran out",
      value: funnel.expired,
      valueText: formatCount(funnel.expired),
      note: share(funnel.expired),
    },
    {
      key: "still_held",
      label: "Still waiting",
      value: funnel.still_held,
      valueText: formatCount(funnel.still_held),
      note: share(funnel.still_held),
    },
  ];
}

export function DemandView({ data }: { data: DemandReport }) {
  return (
    <>
      <PeriodNote window={data.window} asOf={data.as_of} />
      <Limitation title="What counts as demand">
        Demand is the reservations members made in the period. Attempts to reserve an item that was
        not available are not recorded, so unmet demand cannot be measured. A reservation cancelled
        because its item went into maintenance looks like any other cancellation.
      </Limitation>
      <Stats label="Demand">
        <Stat
          label="Reservations made"
          value={formatCount(data.reservations.current)}
          note={versusPrevious(data.reservations)}
        />
        <Stat
          label="Reservations that became loans"
          value={formatPct(data.funnel.conversion_rate_pct)}
          note={previousConversionNote(data.previous_funnel.conversion_rate_pct)}
        />
      </Stats>

      <h3>What became of the reservations</h3>
      {data.funnel.reserved === 0 ? (
        <p className="muted">No reservations were made in this period.</p>
      ) : (
        <>
          <BarList
            label="Reservation funnel"
            max={data.funnel.reserved}
            rows={funnelRows(data.funnel)}
          />
          <p className="hint">
            Each reservation is in exactly one of: checked out, cancelled, hold ran out (48 hours),
            still waiting. The rate above counts only reservations that have been settled.
          </p>
        </>
      )}

      <h3>By category</h3>
      {data.categories.length === 0 ? (
        <p className="muted">There are no items yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption>Reservations by category in this period</caption>
            <thead>
              <tr>
                <th scope="col">Category</th>
                <th scope="col" className="num">
                  Items
                </th>
                <th scope="col" className="num">
                  Reservations
                </th>
                <th scope="col" className="num">
                  Share
                </th>
                <th scope="col" className="num">
                  Per item
                </th>
                <th scope="col" className="num">
                  Checked out
                </th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((row) => (
                <tr key={row.category}>
                  <th scope="row">{row.category}</th>
                  <td className="num">{formatCount(row.items)}</td>
                  <td className="num">{formatCount(row.reservations)}</td>
                  <td className="num">{formatPct(row.share_pct)}</td>
                  <td className="num">{row.reservations_per_item ?? "—"}</td>
                  <td className="num">{formatCount(row.checked_out)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>Most reserved items</h3>
      {data.top_items.length === 0 ? (
        <p className="muted">No item was reserved in this period.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption>The items reserved most often in this period</caption>
            <thead>
              <tr>
                <th scope="col">Item</th>
                <th scope="col">Category</th>
                <th scope="col" className="num">
                  Reservations
                </th>
                <th scope="col" className="num">
                  Checked out
                </th>
                <th scope="col">Status now</th>
              </tr>
            </thead>
            <tbody>
              {data.top_items.map((row) => (
                <tr key={row.item_id}>
                  <td>
                    <Link to={`/items/${row.item_id}`}>{row.item_name}</Link>
                  </td>
                  <td>{row.category}</td>
                  <td className="num">{formatCount(row.reservations)}</td>
                  <td className="num">{formatCount(row.checked_out)}</td>
                  <td>
                    <StatusBadge status={row.current_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

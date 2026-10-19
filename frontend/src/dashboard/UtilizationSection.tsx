import { bucketLabels, formatDateRange, formatItemDays, formatPct, formatPoints } from "../format";
import type { UtilizationReport } from "../types";
import { BarList, ColumnChart, type Bar } from "./charts";
import { Limitation, PeriodNote, Stat, Stats } from "./ReportSection";

export function UtilizationView({ data }: { data: UtilizationReport }) {
  const bars: Bar[] = data.series.map((slot) => ({
    key: slot.start,
    ...bucketLabels(slot.start, data.bucket),
    value: slot.utilization_pct,
    valueText:
      slot.utilization_pct === null
        ? "nothing measured yet"
        : `${formatPct(slot.utilization_pct)} (${formatItemDays(slot.checked_out_item_days)} of ${formatItemDays(slot.fleet_item_days)} item-days)`,
    partial: slot.partial,
  }));
  const measured = data.series.filter((slot) => slot.utilization_pct !== null);
  const peak = measured.reduce<(typeof measured)[number] | undefined>(
    (best, slot) =>
      !best || (slot.utilization_pct ?? 0) > (best.utilization_pct ?? 0) ? slot : best,
    undefined,
  );
  const top = Math.max(
    10,
    Math.ceil(Math.max(0, ...measured.map((s) => s.utilization_pct ?? 0)) / 10) * 10,
  );
  const summary = peak
    ? `Highest ${formatPct(peak.utilization_pct)} in ${bucketLabels(peak.start, data.bucket).label}, across ${formatDateRange(data.window.start_date, data.window.end_date)}.`
    : "Nothing has been measured yet.";
  const unit = data.bucket === "week" ? "week" : "day";

  return (
    <>
      <PeriodNote window={data.window} asOf={data.as_of} />
      <Limitation title="What this number can and cannot tell you">
        Utilization is the time items spent checked out divided by the time the whole fleet could
        have been out. The system keeps no history of maintenance or of when items were added, so
        every item counts as available for the whole period, including the{" "}
        {data.fleet.under_maintenance_now} now under maintenance. Utilization is therefore
        understated whenever part of the fleet could not be lent. Reserved time is not counted, and
        overdue time is.
      </Limitation>
      <Stats label="Utilization">
        <Stat
          label="Utilization this period"
          value={formatPct(data.current.utilization_pct)}
          note={`${formatItemDays(data.current.checked_out_item_days)} of ${formatItemDays(data.current.fleet_item_days)} item-days`}
        />
        <Stat
          label="Same time in the previous period"
          value={formatPct(data.previous.utilization_pct)}
          note={`${formatItemDays(data.previous.checked_out_item_days)} of ${formatItemDays(data.previous.fleet_item_days)} item-days · ${formatPoints(data.change_points)}`}
        />
        <Stat label="Items in the fleet" value={String(data.fleet.items)} />
      </Stats>
      <ColumnChart
        title={`Utilization by ${unit}`}
        summary={summary}
        valueHeading="Utilization"
        bars={bars}
        max={top}
        axisText={(value) => `${value}%`}
      />
      <h3>By category</h3>
      {data.by_category.length === 0 ? (
        <p className="muted">There are no items yet.</p>
      ) : (
        <BarList
          label="Utilization by category"
          max={100}
          rows={data.by_category.map((row) => ({
            key: row.category,
            label: row.category,
            value: row.utilization_pct ?? 0,
            valueText: formatPct(row.utilization_pct),
            note: `${row.items} ${row.items === 1 ? "item" : "items"} · ${formatItemDays(row.checked_out_item_days)} of ${formatItemDays(row.fleet_item_days)} item-days`,
          }))}
        />
      )}
    </>
  );
}

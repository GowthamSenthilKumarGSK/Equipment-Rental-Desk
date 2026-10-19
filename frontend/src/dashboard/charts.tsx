import { useId, type ReactNode } from "react";

/**
 * Small, dependency-free charts. A chart is never the only way to read the numbers: every bar
 * carries its value as text (a tooltip title or visible text), the column chart is a labelled image
 * with a data table behind a disclosure, and "partial" is stated in words and drawn hatched, never
 * by colour alone.
 */

export interface Bar {
  key: string; // unique within the chart, e.g. the bucket's first date
  label: string; // for the table and the tooltip: "8 Oct 2026" or "Week of 5 Oct 2026"
  short: string; // for the chart axis: "8 Oct"
  value: number | null; // null: nothing was measured (draws no bar)
  valueText: string;
  partial: boolean;
}

interface ColumnChartProps {
  title: string; // what the chart shows, also its accessible name
  summary: string; // one sentence with the headline reading, for screen readers
  valueHeading: string; // the table's value column
  bars: Bar[];
  max: number; // the value at the top of the chart
  axisText: (value: number) => string;
}

const WIDTH = 640;
const HEIGHT = 230;
const LEFT = 64;
const RIGHT = 8;
const TOP = 12;
const BOTTOM = 30;

export function ColumnChart({
  title,
  summary,
  valueHeading,
  bars,
  max,
  axisText,
}: ColumnChartProps) {
  const id = useId().replace(/:/g, ""); // a plain id, safe inside url(#…)
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const slot = bars.length > 0 ? plotWidth / bars.length : plotWidth;
  const barWidth = Math.max(1, slot * 0.72);
  const top = max > 0 ? max : 1;
  const ticks = [0, top / 2, top];
  const labelled = new Set([0, Math.floor((bars.length - 1) / 2), bars.length - 1]);
  const hasPartial = bars.some((bar) => bar.partial);

  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <div
        className="chart__scroll"
        role="group"
        aria-label={`${title}: scrolls sideways on a narrow screen`}
        tabIndex={0}
      >
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${title}. ${summary}`}
          className="chart__svg"
        >
          <defs>
            <pattern
              id={`${id}-hatch`}
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="6" height="6" className="chart__hatch-bg" />
              <line x1="0" y1="0" x2="0" y2="6" className="chart__hatch-line" />
            </pattern>
          </defs>
          {ticks.map((tick) => {
            const y = TOP + plotHeight - (tick / top) * plotHeight;
            return (
              <g key={tick}>
                <line x1={LEFT} x2={WIDTH - RIGHT} y1={y} y2={y} className="chart__grid" />
                <text x={LEFT - 6} y={y + 4} textAnchor="end" className="chart__axis">
                  {axisText(tick)}
                </text>
              </g>
            );
          })}
          {bars.map((bar, index) => {
            const x = LEFT + index * slot + (slot - barWidth) / 2;
            const height = bar.value === null ? 0 : (Math.min(bar.value, top) / top) * plotHeight;
            return (
              <g key={bar.key}>
                {bar.value !== null && (
                  <rect
                    x={x}
                    y={TOP + plotHeight - height}
                    width={barWidth}
                    height={height}
                    className={bar.partial ? "chart__bar chart__bar--partial" : "chart__bar"}
                    style={bar.partial ? { fill: `url(#${id}-hatch)` } : undefined}
                  >
                    <title>{`${bar.label}: ${bar.valueText}${bar.partial ? " (partial)" : ""}`}</title>
                  </rect>
                )}
                {labelled.has(index) && (
                  <text
                    x={x + barWidth / 2}
                    y={HEIGHT - 10}
                    textAnchor={
                      index === 0 ? "start" : index === bars.length - 1 ? "end" : "middle"
                    }
                    className="chart__axis"
                  >
                    {bar.short}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      {hasPartial && (
        <p className="hint">
          Hatched bars are partial: they cover only part of a day or week, so compare them with
          care.
        </p>
      )}
      <details className="chart__data">
        <summary>Show the values as a table</summary>
        <div className="table-wrap">
          <table>
            <caption>{title}</caption>
            <thead>
              <tr>
                <th scope="col">Period</th>
                <th scope="col" className="num">
                  {valueHeading}
                </th>
                <th scope="col">Complete?</th>
              </tr>
            </thead>
            <tbody>
              {bars.map((bar) => (
                <tr key={bar.key}>
                  <th scope="row">{bar.label}</th>
                  <td className="num">{bar.valueText}</td>
                  <td>{bar.partial ? "Partial" : "Yes"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  valueText: string;
  note?: ReactNode;
}

/** Horizontal bars as a list: each row says its value in words, the bar is only a picture of it. */
export function BarList({ label, rows, max }: { label: string; rows: BarRow[]; max?: number }) {
  const top = max ?? Math.max(0, ...rows.map((row) => row.value));
  return (
    <ul className="bars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.key} className="bars__row">
          <span className="bars__label">{row.label}</span>
          <span className="bars__track" aria-hidden="true">
            <span
              className="bars__fill"
              style={{ width: `${top > 0 ? Math.min(100, (row.value / top) * 100) : 0}%` }}
            />
          </span>
          <strong className="bars__value">{row.valueText}</strong>
          {row.note && <span className="bars__note muted">{row.note}</span>}
        </li>
      ))}
    </ul>
  );
}

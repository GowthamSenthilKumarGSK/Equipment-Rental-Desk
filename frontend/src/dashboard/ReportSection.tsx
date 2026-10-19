import type { ReactNode } from "react";
import type { AsyncState } from "../useAsync";
import { ErrorNotice, Loading, Notice } from "../components/Notice";
import { formatDateRange, formatIst } from "../format";
import type { AnalyticsWindow } from "../types";

interface ReportSectionProps<T> {
  id: string;
  title: string;
  what: string; // "utilization", for "Loading utilization…"
  state: AsyncState<T>;
  children: (data: T) => ReactNode;
}

/**
 * One report on the dashboard. Each report loads on its own, so a failing report shows its own error
 * with its own retry while the others stay usable.
 */
export function ReportSection<T>({ id, title, what, state, children }: ReportSectionProps<T>) {
  return (
    <section className="report" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{title}</h2>
      {state.error && <ErrorNotice error={state.error} onRetry={state.reload} />}
      {state.loading && !state.data && <Loading what={what} />}
      {state.data && children(state.data)}
    </section>
  );
}

/** Says exactly which dates a report covers, that today is unfinished, and what it is compared with. */
export function PeriodNote({ window, asOf }: { window: AnalyticsWindow; asOf: string }) {
  return (
    <p className="hint period-note">
      <strong>{formatDateRange(window.start_date, window.end_date)}</strong> (last {window.days}{" "}
      {window.days === 1 ? "day" : "days"}, IST), so far: today is not over, and the figures run up
      to {formatIst(asOf)}. Compared with{" "}
      {formatDateRange(window.previous_start_date, window.previous_end_date)}, counted up to the
      same point ({formatIst(window.previous_through)}).
    </p>
  );
}

/** A limitation the reader must not miss. Always visible, never in a tooltip. */
export function Limitation({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Notice kind="info">
      <strong>{title}</strong>
      <p>{children}</p>
    </Notice>
  );
}

interface StatProps {
  label: string;
  value: string;
  note?: ReactNode;
}

export function Stat({ label, value, note }: StatProps) {
  return (
    <li className="stat">
      <span className="stat__label">{label}</span>
      <strong className="stat__value">{value}</strong>
      {note && <span className="stat__note muted">{note}</span>}
    </li>
  );
}

export function Stats({ label, children }: { label: string; children: ReactNode }) {
  return (
    <ul className="stats" aria-label={label}>
      {children}
    </ul>
  );
}

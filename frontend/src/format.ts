/** Display helpers. Money stays in whole paise; times arrive as UTC and are shown in IST. */

const rupeeGrouping = new Intl.NumberFormat("en-IN");
const istDateTime = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});
const calendarDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: "UTC",
  day: "numeric",
  month: "short",
  year: "numeric",
});

/** 1250 -> "₹12.50". Integer arithmetic only, so no floating-point rounding can creep in. */
export function formatRupees(paise: number): string {
  const sign = paise < 0 ? "-" : "";
  const absolute = Math.abs(paise);
  const rupees = Math.trunc(absolute / 100);
  const fraction = String(absolute % 100).padStart(2, "0");
  return `${sign}₹${rupeeGrouping.format(rupees)}.${fraction}`;
}

/**
 * Reads an amount typed in rupees ("12", "12.5", "12.50") as whole paise, or null if it is not a
 * plain amount. This is input parsing, not a business rule: the server decides what is allowed.
 */
export function parseRupees(text: string): number | null {
  const match = /^(\d{1,7})(?:\.(\d{1,2}))?$/.exec(text.trim());
  if (!match) return null;
  const rupees = Number(match[1]);
  const paise = Number((match[2] ?? "").padEnd(2, "0"));
  return rupees * 100 + paise;
}

/** "2026-10-12T10:00:00Z" -> "12 Oct 2026, 3:30 pm IST". */
export function formatIst(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return `${istDateTime.format(date)} IST`;
}

/** A plain calendar date such as a member's join date: "2026-02-09" -> "9 Feb 2026". */
export function formatDate(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? isoDate : calendarDate.format(date);
}

export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`;
}

/** 41.1 -> "41.1%". The API sends null when there is nothing to divide by: shown as a dash. */
export function formatPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value}%`;
}

/** A change against the previous period: 50 -> "+50%", -12.5 -> "−12.5%", null -> "no earlier data". */
export function formatChange(value: number | null | undefined): string {
  if (value === null || value === undefined) return "no earlier data";
  if (value === 0) return "no change";
  return `${value > 0 ? "+" : "−"}${Math.abs(value)}%`;
}

/** Percentage-point difference of two percentages: 6.4 -> "+6.4 points". */
export function formatPoints(value: number | null | undefined): string {
  if (value === null || value === undefined) return "no earlier data";
  if (value === 0) return "no change";
  return `${value > 0 ? "+" : "−"}${Math.abs(value)} points`;
}

/** Item-days with at most two decimals: 1.06 -> "1.06", 12 -> "12". */
export function formatItemDays(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, "");
}

/** "2026-10-06", "2026-10-12" -> "6 Oct – 12 Oct 2026" (one date when they are the same day). */
export function formatDateRange(start: string, end: string): string {
  if (start === end) return formatDate(start);
  const first = formatDate(start);
  const last = formatDate(end);
  const sameYear = first.slice(-4) === last.slice(-4);
  return `${sameYear ? first.slice(0, -5) : first} – ${last}`;
}

/** A whole count with Indian digit grouping: 1234567 -> "12,34,567". */
export function formatCount(value: number): string {
  return rupeeGrouping.format(value);
}

/**
 * Labels for one bucket of a series: the full one ("Week of 5 Oct 2026") for tables and tooltips,
 * and a short one ("5 Oct") for the chart axis. The year is in the full label because a long period
 * can show the same day twice.
 */
export function bucketLabels(
  start: string,
  bucket: "day" | "week",
): { label: string; short: string } {
  const full = formatDate(start);
  return {
    label: bucket === "week" ? `Week of ${full}` : full,
    short: full.slice(0, -5),
  };
}

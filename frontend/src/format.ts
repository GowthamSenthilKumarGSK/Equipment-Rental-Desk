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

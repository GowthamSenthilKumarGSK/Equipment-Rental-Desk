/**
 * How urgent an overdue loan looks on the Overdue page. These four groups are only a way of showing
 * the list (the page is already sorted longest-overdue first); they are not the shop's rules. What
 * actually blocks a member is decided by the server and reported as block reasons.
 */
export interface Severity {
  /** 0 (just late) to 3 (very late). Drives the colour; the label always says it in words. */
  level: 0 | 1 | 2 | 3;
  label: string;
  rowClass: "" | "is-watch" | "is-serious" | "is-urgent";
}

export function severityOf(daysOverdue: number): Severity {
  if (daysOverdue >= 14) return { level: 3, label: "Over 2 weeks late", rowClass: "is-urgent" };
  if (daysOverdue >= 7) return { level: 2, label: "1–2 weeks late", rowClass: "is-serious" };
  if (daysOverdue >= 3) return { level: 1, label: "3–6 days late", rowClass: "is-watch" };
  return { level: 0, label: "Just late", rowClass: "" };
}

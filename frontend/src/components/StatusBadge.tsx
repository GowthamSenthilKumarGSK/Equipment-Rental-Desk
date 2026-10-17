import type { ItemStatus, LoanStatus, MemberStatus } from "../types";
import { ITEM_STATUS_LABELS, LOAN_STATUS_LABELS } from "../messages";

type Kind = ItemStatus | LoanStatus | MemberStatus | "late";

const LABELS: Record<string, string> = {
  ...LOAN_STATUS_LABELS,
  ...ITEM_STATUS_LABELS,
  active: "Active",
  suspended: "Suspended",
  late: "Overdue",
};

/** The status is always spelled out; colour is only a second cue. */
export function StatusBadge({ status }: { status: Kind }) {
  return <span className={`badge badge--${status}`}>{LABELS[status] ?? status}</span>;
}

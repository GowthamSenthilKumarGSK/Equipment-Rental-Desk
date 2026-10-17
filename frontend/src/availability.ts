import { formatIst } from "./format";
import type { Item } from "./types";

/** One line saying what is going on with an item, built from what the API reports. */
export function availabilityText(item: Item): string {
  const loan = item.current_loan;
  switch (item.status) {
    case "available":
      return "Available now";
    case "reserved":
      return loan?.expires_at ? `Held until ${formatIst(loan.expires_at)}` : "Reserved";
    case "checked_out":
      return loan?.due_at ? `Out on loan, due ${formatIst(loan.due_at)}` : "Out on loan";
    case "overdue":
      return loan?.due_at ? `Overdue: was due ${formatIst(loan.due_at)}` : "Overdue";
    case "under_maintenance":
      return loan?.due_at
        ? `Under maintenance, still on loan (due ${formatIst(loan.due_at)})`
        : "Under maintenance, not available";
  }
}

/** Plain id from a URL segment, or null if it is not a positive 32-bit integer. */
export function parseId(segment: string | undefined): number | null {
  if (!segment || !/^[1-9]\d{0,9}$/.test(segment)) return null;
  const id = Number(segment);
  return id <= 2_147_483_647 ? id : null;
}

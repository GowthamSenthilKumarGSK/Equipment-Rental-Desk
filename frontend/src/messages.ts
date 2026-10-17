/** Plain-language wording for statuses, actions and errors. Wording only: no rules live here. */
import type { ApiError } from "./api";
import type { BlockReason, ItemAction, ItemStatus, LoanStatus } from "./types";

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  available: "Available",
  reserved: "Reserved",
  checked_out: "Checked out",
  overdue: "Overdue",
  under_maintenance: "Under maintenance",
};

export const LOAN_STATUS_LABELS: Record<LoanStatus, string> = {
  reserved: "Reserved",
  checked_out: "Checked out",
  returned: "Returned",
  cancelled: "Cancelled",
  expired: "Expired",
};

export const ACTION_LABELS: Record<ItemAction, string> = {
  reserve: "Reserve",
  check_out: "Check out",
  return: "Return",
  cancel_reservation: "Cancel reservation",
  start_maintenance: "Put under maintenance",
  finish_maintenance: "End maintenance",
};

export const BLOCK_REASON_TEXT: Record<BlockReason, string> = {
  suspended: "The member is suspended.",
  unpaid_fees: "Their unpaid fees are over the limit. Record a payment to clear it.",
  long_overdue: "A loan is overdue by too long. It has to be returned first.",
};

export function blockReasonText(reason: string): string {
  return BLOCK_REASON_TEXT[reason as BlockReason] ?? reason;
}

/** Shown when the API says the member cannot reserve more. The limit itself is the server's rule. */
export function loanLimitText(activeLoanCount: number): string {
  const loans = activeLoanCount === 1 ? "1 active loan" : `${activeLoanCount} active loans`;
  return `They hold ${loans}, the most a member can have, so they can't reserve another item until one is returned, cancelled or runs out.`;
}

export interface ErrorView {
  title: string;
  message: string;
  lines: string[];
  reference: string | null;
}

/** "body.replacement_value_paise" -> "Replacement value paise". */
function friendlyField(field: string): string {
  const last = field.split(".").pop() ?? field;
  const words = last.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Turns any API failure into something a person at the desk can act on. */
export function describeError(error: ApiError): ErrorView {
  const base = { message: error.message, lines: [] as string[], reference: null as string | null };
  switch (true) {
    case error.status === 0:
      return { ...base, title: "Can't reach the server" };
    case error.status === 403:
      return error.blockReasons.length > 0
        ? {
            ...base,
            title: "This member can't borrow right now",
            message: "Reserving and checking out are blocked for the following reasons:",
            lines: error.blockReasons.map(blockReasonText),
          }
        : { ...base, title: "Not allowed" };
    case error.status === 404:
      return { ...base, title: "Not found" };
    case error.status === 409:
      return { ...base, title: "That can't be done right now" };
    case error.status === 422 && error.fieldErrors.length > 0:
      return {
        ...base,
        title: "Please check the form",
        message: "The server did not accept the details:",
        lines: error.fieldErrors.map(
          (detail) =>
            `${friendlyField(detail.field)}: ${detail.message.replace(/^Value error, /, "")}`,
        ),
      };
    case error.status === 422:
      return { ...base, title: "Please check the amount" };
    case error.status >= 500:
      return {
        ...base,
        title: "Server error",
        message: "Something went wrong on the server. Please try again.",
        reference: error.requestId,
      };
    default:
      return { ...base, title: "Request refused" };
  }
}

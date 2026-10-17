/** Shapes returned by the backend API (see the backend's /openapi.json). Money is whole paise. */

export type ItemStatus = "available" | "reserved" | "checked_out" | "overdue" | "under_maintenance";
export type ItemAction =
  | "reserve"
  | "check_out"
  | "return"
  | "cancel_reservation"
  | "start_maintenance"
  | "finish_maintenance";
export type LoanStatus = "reserved" | "checked_out" | "returned" | "cancelled" | "expired";
export type MemberStatus = "active" | "suspended";
export type BlockReason = "suspended" | "unpaid_fees" | "long_overdue";

export interface Loan {
  id: number;
  member_id: number;
  item_id: number;
  status: LoanStatus;
  reserved_at: string;
  expires_at: string | null;
  checked_out_at: string | null;
  due_at: string | null;
  returned_at: string | null;
  cancelled_at: string | null;
  fee_charged_paise: number;
}

export interface Item {
  id: number;
  name: string;
  category: string;
  replacement_value_paise: number;
  condition_note: string;
  status: ItemStatus;
  current_loan: Loan | null;
  allowed_actions: ItemAction[];
}

export interface Member {
  id: number;
  name: string;
  phone: string;
  join_date: string;
  status: MemberStatus;
}

export interface Payment {
  id: number;
  member_id: number;
  amount_paise: number;
  paid_at: string;
  note: string | null;
}

export interface StatementLoan {
  loan: Loan;
  item_name: string;
  status: LoanStatus;
  is_overdue: boolean;
  days_overdue: number;
}

export interface Statement {
  member: Member;
  balance_paise: number;
  total_fees_paise: number;
  total_payments_paise: number;
  active_loan_count: number;
  block_reasons: BlockReason[];
  at_loan_limit: boolean;
  loans: StatementLoan[];
  payments: Payment[];
}

export interface OverdueLoan {
  loan_id: number;
  member_id: number;
  member_name: string;
  member_phone: string;
  item_id: number;
  item_name: string;
  checked_out_at: string;
  due_at: string;
  days_overdue: number;
  fee_if_returned_now_paise: number;
}

export interface Page<T> {
  results: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ErrorDetail {
  field: string;
  message: string;
  type: string;
}

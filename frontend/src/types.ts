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

// --- analytics dashboard (GET /analytics/*). Money is whole paise; dates are IST calendar dates;
// instants are UTC. Percentages have one decimal and are null when there is nothing to divide by.

export type Bucket = "day" | "week";

export interface AnalyticsWindow {
  days: number;
  start_date: string;
  end_date: string; // today (IST): the period is "so far"
  previous_start_date: string;
  previous_end_date: string;
  previous_through: string; // the previous period is compared only up to this instant
  timezone: string;
}

export interface Change {
  current: number;
  previous: number;
  change_pct: number | null;
}

export interface Rate {
  current_pct: number | null;
  previous_pct: number | null;
}

export interface FleetCounts {
  total_items: number;
  available: number;
  reserved: number;
  checked_out: number;
  overdue: number;
  under_maintenance: number;
}

export interface LoansNow {
  active: number;
  reserved: number;
  checked_out: number;
  overdue: number;
  overdue_share_pct: number | null;
}

export interface MemberCounts {
  total: number;
  active: number;
  suspended: number;
  blocked: number;
  blocked_suspended: number;
  blocked_unpaid_fees: number;
  blocked_long_overdue: number;
}

export interface Receivables {
  outstanding_paise: number;
  unapplied_credit_paise: number;
  members_with_balance: number;
  members_over_limit: number;
}

export interface AnalyticsSummary {
  as_of: string;
  window: AnalyticsWindow;
  fleet: FleetCounts;
  loans: LoansNow;
  members: MemberCounts;
  receivables: Receivables;
  reservations_created: Change;
  checkouts: Change;
  returns: Change;
  late_return_rate: Rate;
  payments_collected_paise: Change;
  fees_charged_paise: Change;
}

export interface AgingBand {
  label: string;
  min_days: number;
  max_days: number | null;
  count: number;
  accrued_fee_paise: number;
}

export interface OverdueNow {
  count: number;
  accrued_fee_paise: number;
  blocking_count: number;
  oldest_days_overdue: number | null;
  bands: AgingBand[];
}

export interface OverdueMember {
  member_id: number;
  member_name: string;
  loans: number;
  longest_days_overdue: number;
  accrued_fee_paise: number;
}

export interface LateReturns {
  returned: number;
  late: number;
  late_rate_pct: number | null;
  average_days_late: number | null;
  fees_charged_paise: number;
}

export interface OverdueAging {
  as_of: string;
  window: AnalyticsWindow;
  open: OverdueNow;
  top_members: OverdueMember[];
  returns: LateReturns;
}

export interface PaymentBucket {
  start: string;
  collected_paise: number;
  count: number;
  covered_from: string;
  covered_to: string;
  partial: boolean;
}

export interface Ledger {
  fees_charged_paise: number;
  collected_paise: number;
  outstanding_paise: number;
  unapplied_credit_paise: number;
  members_with_balance: number;
  members_over_limit: number;
}

export interface MemberBalance {
  member_id: number;
  member_name: string;
  balance_paise: number;
}

export interface PaymentsReport {
  as_of: string;
  window: AnalyticsWindow;
  bucket: Bucket;
  collected: Change;
  payments: Change;
  average_payment_paise: number | null;
  fees_charged_paise: Change;
  collected_to_charged_pct: number | null;
  series: PaymentBucket[];
  ledger: Ledger;
  top_balances: MemberBalance[];
}

export interface UtilizationFigure {
  checked_out_item_days: number;
  fleet_item_days: number;
  utilization_pct: number | null;
}

export interface UtilizationBucket extends UtilizationFigure {
  start: string;
  covered_from: string;
  covered_to: string;
  partial: boolean;
}

export interface CategoryUtilization extends UtilizationFigure {
  category: string;
  items: number;
}

export interface UtilizationReport {
  as_of: string;
  window: AnalyticsWindow;
  bucket: Bucket;
  fleet: { items: number; under_maintenance_now: number };
  current: UtilizationFigure;
  previous: UtilizationFigure;
  change_points: number | null;
  series: UtilizationBucket[];
  by_category: CategoryUtilization[];
}

export interface Funnel {
  reserved: number;
  checked_out: number;
  returned: number;
  cancelled: number;
  expired: number;
  still_held: number;
  conversion_rate_pct: number | null;
}

export interface CategoryDemand {
  category: string;
  items: number;
  reservations: number;
  checked_out: number;
  share_pct: number | null;
  reservations_per_item: number | null;
}

export interface TopItem {
  item_id: number;
  item_name: string;
  category: string;
  reservations: number;
  checked_out: number;
  current_status: ItemStatus;
}

export interface DemandReport {
  as_of: string;
  window: AnalyticsWindow;
  reservations: Change;
  funnel: Funnel;
  previous_funnel: Funnel;
  categories: CategoryDemand[];
  top_items: TopItem[];
}

export interface MaintenanceLoan {
  loan_id: number;
  checked_out_at: string;
  due_at: string;
  overdue: boolean;
  days_overdue: number;
}

export interface MaintenanceItem {
  item_id: number;
  item_name: string;
  category: string;
  condition_note: string;
  open_loan: MaintenanceLoan | null;
}

export interface CategoryMaintenance {
  category: string;
  items: number;
  under_maintenance: number;
  share_pct: number | null;
}

export interface MaintenanceReport {
  as_of: string;
  history_available: boolean; // always false: start and end times of maintenance are not recorded
  fleet: FleetCounts;
  share_of_fleet_pct: number | null;
  on_loan: number;
  on_loan_overdue: number;
  without_open_loan: number;
  by_category: CategoryMaintenance[];
  items: MaintenanceItem[];
  items_truncated: boolean;
}

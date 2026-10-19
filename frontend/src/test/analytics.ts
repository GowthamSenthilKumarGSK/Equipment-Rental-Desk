/** Builders for the analytics API replies, shaped like the backend's /analytics/* responses. */
import type {
  AnalyticsSummary,
  AnalyticsWindow,
  DemandReport,
  Funnel,
  MaintenanceReport,
  OverdueAging,
  PaymentsReport,
  UtilizationReport,
} from "../types";

export const AS_OF = "2026-10-12T10:00:00Z"; // 15:30 IST on Monday 12 Oct 2026

export function makeWindow(overrides: Partial<AnalyticsWindow> = {}): AnalyticsWindow {
  return {
    days: 7,
    start_date: "2026-10-06",
    end_date: "2026-10-12",
    previous_start_date: "2026-09-29",
    previous_end_date: "2026-10-05",
    previous_through: "2026-10-05T10:00:00Z",
    timezone: "Asia/Kolkata (IST, UTC+05:30)",
    ...overrides,
  };
}

const NO_CHANGE = { current: 0, previous: 0, change_pct: null };

export function makeSummary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    as_of: AS_OF,
    window: makeWindow(),
    fleet: {
      total_items: 8,
      available: 1,
      reserved: 1,
      checked_out: 1,
      overdue: 1,
      under_maintenance: 4,
    },
    loans: { active: 5, reserved: 1, checked_out: 4, overdue: 3, overdue_share_pct: 75 },
    members: {
      total: 7,
      active: 5,
      suspended: 2,
      blocked: 4,
      blocked_suspended: 2,
      blocked_unpaid_fees: 2,
      blocked_long_overdue: 1,
    },
    receivables: {
      outstanding_paise: 1_234_567,
      unapplied_credit_paise: 2_000,
      members_with_balance: 3,
      members_over_limit: 2,
    },
    reservations_created: { current: 6, previous: 2, change_pct: 200 },
    checkouts: { current: 3, previous: 2, change_pct: 50 },
    returns: { current: 3, previous: 4, change_pct: -25 },
    late_return_rate: { current_pct: 66.7, previous_pct: 50 },
    payments_collected_paise: { current: 150_050, previous: 500_000, change_pct: -70 },
    fees_charged_paise: { current: 400_000, previous: 200_000, change_pct: 100 },
    ...overrides,
  };
}

export function emptySummary(): AnalyticsSummary {
  return makeSummary({
    fleet: {
      total_items: 0,
      available: 0,
      reserved: 0,
      checked_out: 0,
      overdue: 0,
      under_maintenance: 0,
    },
    loans: { active: 0, reserved: 0, checked_out: 0, overdue: 0, overdue_share_pct: null },
    members: {
      total: 0,
      active: 0,
      suspended: 0,
      blocked: 0,
      blocked_suspended: 0,
      blocked_unpaid_fees: 0,
      blocked_long_overdue: 0,
    },
    receivables: {
      outstanding_paise: 0,
      unapplied_credit_paise: 0,
      members_with_balance: 0,
      members_over_limit: 0,
    },
    reservations_created: NO_CHANGE,
    checkouts: NO_CHANGE,
    returns: NO_CHANGE,
    late_return_rate: { current_pct: null, previous_pct: null },
    payments_collected_paise: NO_CHANGE,
    fees_charged_paise: NO_CHANGE,
  });
}

export function makeUtilization(overrides: Partial<UtilizationReport> = {}): UtilizationReport {
  return {
    as_of: AS_OF,
    window: makeWindow({ days: 3, start_date: "2026-10-10", previous_start_date: "2026-10-07" }),
    bucket: "day",
    fleet: { items: 4, under_maintenance_now: 1 },
    current: { checked_out_item_days: 1.06, fleet_item_days: 2.58, utilization_pct: 41.1 },
    previous: { checked_out_item_days: 0.9, fleet_item_days: 2.58, utilization_pct: 34.7 },
    change_points: 6.4,
    series: [
      {
        start: "2026-10-10",
        covered_from: "2026-10-10",
        covered_to: "2026-10-10",
        partial: false,
        checked_out_item_days: 1,
        fleet_item_days: 4,
        utilization_pct: 25,
      },
      {
        start: "2026-10-11",
        covered_from: "2026-10-11",
        covered_to: "2026-10-11",
        partial: false,
        checked_out_item_days: 2,
        fleet_item_days: 4,
        utilization_pct: 50,
      },
      {
        start: "2026-10-12",
        covered_from: "2026-10-12",
        covered_to: "2026-10-12",
        partial: true,
        checked_out_item_days: 1.06,
        fleet_item_days: 2.58,
        utilization_pct: 41.1,
      },
    ],
    by_category: [
      {
        category: "Power Tools",
        items: 3,
        checked_out_item_days: 0.38,
        fleet_item_days: 1.94,
        utilization_pct: 19.4,
      },
      {
        category: "Garden",
        items: 1,
        checked_out_item_days: 0.04,
        fleet_item_days: 0.65,
        utilization_pct: 6.5,
      },
    ],
    ...overrides,
  };
}

export function emptyUtilization(): UtilizationReport {
  return makeUtilization({
    fleet: { items: 0, under_maintenance_now: 0 },
    current: { checked_out_item_days: 0, fleet_item_days: 0, utilization_pct: null },
    previous: { checked_out_item_days: 0, fleet_item_days: 0, utilization_pct: null },
    change_points: null,
    series: [
      {
        start: "2026-10-12",
        covered_from: "2026-10-12",
        covered_to: "2026-10-12",
        partial: true,
        checked_out_item_days: 0,
        fleet_item_days: 0,
        utilization_pct: null,
      },
    ],
    by_category: [],
  });
}

const FUNNEL: Funnel = {
  reserved: 6,
  checked_out: 2,
  returned: 1,
  cancelled: 1,
  expired: 2,
  still_held: 1,
  conversion_rate_pct: 40,
};
const EMPTY_FUNNEL: Funnel = {
  reserved: 0,
  checked_out: 0,
  returned: 0,
  cancelled: 0,
  expired: 0,
  still_held: 0,
  conversion_rate_pct: null,
};

export function makeDemand(overrides: Partial<DemandReport> = {}): DemandReport {
  return {
    as_of: AS_OF,
    window: makeWindow(),
    reservations: { current: 6, previous: 2, change_pct: 200 },
    funnel: FUNNEL,
    previous_funnel: { ...FUNNEL, reserved: 2, checked_out: 1, conversion_rate_pct: 50 },
    categories: [
      {
        category: "Power Tools",
        items: 2,
        reservations: 4,
        checked_out: 2,
        share_pct: 66.7,
        reservations_per_item: 2,
      },
      {
        category: "Garden",
        items: 2,
        reservations: 2,
        checked_out: 0,
        share_pct: 33.3,
        reservations_per_item: 1,
      },
    ],
    top_items: [
      {
        item_id: 11,
        item_name: "Cordless Drill",
        category: "Power Tools",
        reservations: 2,
        checked_out: 2,
        current_status: "checked_out",
      },
      {
        item_id: 12,
        item_name: "Lawn Mower",
        category: "Garden",
        reservations: 1,
        checked_out: 0,
        current_status: "available",
      },
    ],
    ...overrides,
  };
}

export function emptyDemand(): DemandReport {
  return makeDemand({
    reservations: NO_CHANGE,
    funnel: EMPTY_FUNNEL,
    previous_funnel: EMPTY_FUNNEL,
    categories: [],
    top_items: [],
  });
}

export function makeOverdueAging(overrides: Partial<OverdueAging> = {}): OverdueAging {
  return {
    as_of: AS_OF,
    window: makeWindow(),
    open: {
      count: 9,
      accrued_fee_paise: 87_000,
      blocking_count: 3,
      oldest_days_overdue: 30,
      bands: [
        { label: "1–3 days", min_days: 1, max_days: 3, count: 2, accrued_fee_paise: 4_000 },
        { label: "4–7 days", min_days: 4, max_days: 7, count: 2, accrued_fee_paise: 11_000 },
        { label: "8–14 days", min_days: 8, max_days: 14, count: 2, accrued_fee_paise: 22_000 },
        { label: "15+ days", min_days: 15, max_days: null, count: 3, accrued_fee_paise: 50_000 },
      ],
    },
    top_members: [
      {
        member_id: 4,
        member_name: "Meera Kulkarni",
        loans: 2,
        longest_days_overdue: 30,
        accrued_fee_paise: 35_000,
      },
    ],
    returns: {
      returned: 3,
      late: 2,
      late_rate_pct: 66.7,
      average_days_late: 2,
      fees_charged_paise: 4_000,
    },
    ...overrides,
  };
}

export function emptyOverdueAging(): OverdueAging {
  return makeOverdueAging({
    open: {
      count: 0,
      accrued_fee_paise: 0,
      blocking_count: 0,
      oldest_days_overdue: null,
      bands: [
        { label: "1–3 days", min_days: 1, max_days: 3, count: 0, accrued_fee_paise: 0 },
        { label: "4–7 days", min_days: 4, max_days: 7, count: 0, accrued_fee_paise: 0 },
        { label: "8–14 days", min_days: 8, max_days: 14, count: 0, accrued_fee_paise: 0 },
        { label: "15+ days", min_days: 15, max_days: null, count: 0, accrued_fee_paise: 0 },
      ],
    },
    top_members: [],
    returns: {
      returned: 0,
      late: 0,
      late_rate_pct: null,
      average_days_late: null,
      fees_charged_paise: 0,
    },
  });
}

export function makePayments(overrides: Partial<PaymentsReport> = {}): PaymentsReport {
  return {
    as_of: AS_OF,
    window: makeWindow({ days: 3, start_date: "2026-10-10", previous_start_date: "2026-10-07" }),
    bucket: "day",
    collected: { current: 150_050, previous: 500_000, change_pct: -70 },
    payments: { current: 4, previous: 2, change_pct: 100 },
    average_payment_paise: 37_513,
    fees_charged_paise: { current: 300_000, previous: 0, change_pct: null },
    collected_to_charged_pct: 50,
    series: [
      {
        start: "2026-10-10",
        collected_paise: 100_000,
        count: 1,
        covered_from: "2026-10-10",
        covered_to: "2026-10-10",
        partial: false,
      },
      {
        start: "2026-10-11",
        collected_paise: 0,
        count: 0,
        covered_from: "2026-10-11",
        covered_to: "2026-10-11",
        partial: false,
      },
      {
        start: "2026-10-12",
        collected_paise: 50_050,
        count: 3,
        covered_from: "2026-10-12",
        covered_to: "2026-10-12",
        partial: true,
      },
    ],
    ledger: {
      fees_charged_paise: 4_850_000,
      collected_paise: 3_615_433,
      outstanding_paise: 1_234_567,
      unapplied_credit_paise: 0,
      members_with_balance: 3,
      members_over_limit: 2,
    },
    top_balances: [{ member_id: 4, member_name: "Meera Kulkarni", balance_paise: 1_000_000 }],
    ...overrides,
  };
}

export function emptyPayments(): PaymentsReport {
  return makePayments({
    collected: NO_CHANGE,
    payments: NO_CHANGE,
    average_payment_paise: null,
    fees_charged_paise: NO_CHANGE,
    collected_to_charged_pct: null,
    series: [
      {
        start: "2026-10-12",
        collected_paise: 0,
        count: 0,
        covered_from: "2026-10-12",
        covered_to: "2026-10-12",
        partial: true,
      },
    ],
    ledger: {
      fees_charged_paise: 0,
      collected_paise: 0,
      outstanding_paise: 0,
      unapplied_credit_paise: 0,
      members_with_balance: 0,
      members_over_limit: 0,
    },
    top_balances: [],
  });
}

export function makeMaintenance(overrides: Partial<MaintenanceReport> = {}): MaintenanceReport {
  return {
    as_of: AS_OF,
    history_available: false,
    fleet: {
      total_items: 8,
      available: 1,
      reserved: 1,
      checked_out: 1,
      overdue: 1,
      under_maintenance: 4,
    },
    share_of_fleet_pct: 50,
    on_loan: 2,
    on_loan_overdue: 1,
    without_open_loan: 2,
    by_category: [
      { category: "Garden", items: 2, under_maintenance: 2, share_pct: 100 },
      { category: "Tools", items: 4, under_maintenance: 0, share_pct: 0 },
    ],
    items: [
      {
        item_id: 21,
        item_name: "Hedge Trimmer",
        category: "Garden",
        condition_note: "Chuck jammed",
        open_loan: null,
      },
      {
        item_id: 22,
        item_name: "Lawn Mower",
        category: "Garden",
        condition_note: "",
        open_loan: {
          loan_id: 7,
          checked_out_at: "2026-10-02T10:00:00Z",
          due_at: "2026-10-09T10:00:00Z",
          overdue: true,
          days_overdue: 3,
        },
      },
    ],
    items_truncated: false,
    ...overrides,
  };
}

export function emptyMaintenance(): MaintenanceReport {
  return makeMaintenance({
    fleet: {
      total_items: 0,
      available: 0,
      reserved: 0,
      checked_out: 0,
      overdue: 0,
      under_maintenance: 0,
    },
    share_of_fleet_pct: null,
    on_loan: 0,
    on_loan_overdue: 0,
    without_open_loan: 0,
    by_category: [],
    items: [],
  });
}

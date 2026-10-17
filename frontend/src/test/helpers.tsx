/**
 * Test helpers. The app code never mocks anything; tests replace only `fetch`, the network edge, and
 * any request a test did not expect fails the test instead of quietly succeeding.
 */
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";
import type { Item, Loan, Member, OverdueLoan, Page, Statement, StatementLoan } from "../types";

export interface Call {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
  headers: Record<string, string>;
}

export interface Reply {
  status?: number;
  body?: unknown;
}

type Handler = Reply | ((call: Call) => Reply);

/** Routes are keyed "METHOD /path", for example "GET /items" or "POST /items/3/check-out". */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    const call: Call = {
      method,
      path: url.pathname,
      query: url.searchParams,
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      headers: { ...(init?.headers as Record<string, string>) },
    };
    calls.push(call);
    const handler = routes[`${method} ${url.pathname}`];
    if (!handler) throw new Error(`Unexpected request: ${method} ${url.pathname}${url.search}`);
    const reply = typeof handler === "function" ? handler(call) : handler;
    const status = reply.status ?? 200;
    if (status === 204) return new Response(null, { status });
    return new Response(JSON.stringify(reply.body), {
      status,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req-test-1" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    calls,
    fetchMock,
    callsTo: (key: string) => calls.filter((call) => `${call.method} ${call.path}` === key),
  };
}

/** What the API sends for a failure. */
export function apiError(status: number, code: string, message: string, details: unknown = null) {
  return { status, body: { error: { code, message, request_id: "req-test-1", details } } };
}

export function page<T>(results: T[], total = results.length, limit = 12, offset = 0): Page<T> {
  return { results, total, limit, offset };
}

export function makeLoan(overrides: Partial<Loan> = {}): Loan {
  return {
    id: 1,
    member_id: 5,
    item_id: 1,
    status: "reserved",
    reserved_at: "2026-10-12T10:00:00Z",
    expires_at: "2026-10-14T10:00:00Z",
    checked_out_at: null,
    due_at: null,
    returned_at: null,
    cancelled_at: null,
    fee_charged_paise: 0,
    ...overrides,
  };
}

export function makeItem(overrides: Partial<Item> = {}): Item {
  return {
    id: 1,
    name: "Cordless Drill",
    category: "Power Tools",
    replacement_value_paise: 650_000,
    condition_note: "Two batteries and charger",
    status: "available",
    current_loan: null,
    allowed_actions: ["reserve", "start_maintenance"],
    ...overrides,
  };
}

export function makeMember(overrides: Partial<Member> = {}): Member {
  return {
    id: 5,
    name: "Kavita Iyer",
    phone: "+91 00000 10005",
    join_date: "2026-02-09",
    status: "active",
    ...overrides,
  };
}

export function makeStatement(overrides: Partial<Statement> = {}): Statement {
  return {
    member: makeMember(),
    balance_paise: 0,
    total_fees_paise: 0,
    total_payments_paise: 0,
    active_loan_count: 0,
    block_reasons: [],
    at_loan_limit: false,
    loans: [],
    payments: [],
    ...overrides,
  };
}

export function makeStatementLoan(overrides: Partial<StatementLoan> = {}): StatementLoan {
  return {
    loan: makeLoan(),
    item_name: "Cordless Drill",
    status: "reserved",
    is_overdue: false,
    days_overdue: 0,
    ...overrides,
  };
}

export function makeOverdue(overrides: Partial<OverdueLoan> = {}): OverdueLoan {
  return {
    loan_id: 1,
    member_id: 5,
    member_name: "Meera Kulkarni",
    member_phone: "+91 00000 10004",
    item_id: 3,
    item_name: "Pressure Washer",
    checked_out_at: "2026-09-24T10:00:00Z",
    due_at: "2026-10-01T10:00:00Z",
    days_overdue: 17,
    fee_if_returned_now_paise: 17_000,
    ...overrides,
  };
}

export function renderApp(path: string) {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return { user };
}

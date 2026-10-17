import { API_URL } from "./config";
import { getTestClock } from "./testClock";
import type {
  ErrorDetail,
  Item,
  ItemStatus,
  Loan,
  Member,
  MemberStatus,
  OverdueLoan,
  Page,
  Payment,
  Statement,
} from "./types";

/** Any failure talking to the API: a rule or validation error answered by the server, or no answer. */
export class ApiError extends Error {
  readonly status: number; // HTTP status, or 0 when there was no response at all
  readonly code: string; // stable machine-readable code, e.g. "member_blocked"
  readonly requestId: string | null;
  readonly details: unknown;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null = null,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }

  /** Per-field problems from a 422 response, if any. */
  get fieldErrors(): ErrorDetail[] {
    return this.status === 422 && Array.isArray(this.details)
      ? (this.details as ErrorDetail[])
      : [];
  }

  /** Block reasons from a 403 member_blocked response, if any. */
  get blockReasons(): string[] {
    const details = this.details as { reasons?: unknown } | null;
    return this.code === "member_blocked" && Array.isArray(details?.reasons)
      ? (details.reasons as string[])
      : [];
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  return new ApiError(0, "unexpected", error instanceof Error ? error.message : "Unknown error");
}

type QueryValue = string | number | null | undefined;

interface RequestOptions {
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
}

function buildUrl(path: string, query: Record<string, QueryValue> = {}): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const queryString = params.toString();
  return `${API_URL}${path}${queryString ? `?${queryString}` : ""}`;
}

async function readErrorBody(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; request_id?: string | null; details?: unknown };
    };
    const error = body.error;
    if (error?.code && error.message) {
      return new ApiError(
        response.status,
        error.code,
        error.message,
        error.request_id ?? requestId,
        error.details ?? null,
      );
    }
  } catch {
    // not JSON: fall through to the generic message
  }
  return new ApiError(
    response.status,
    "http_error",
    `The server answered with HTTP ${response.status}.`,
    requestId,
  );
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      0,
      "not_configured",
      "VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env and restart.",
    );
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const testClock = getTestClock(); // null unless the reviewer panel is enabled and a time is set
  if (testClock) headers["X-Test-Clock"] = testClock;

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(
      0,
      "network_error",
      "Cannot reach the server. Check your connection and that the API is running.",
    );
  }
  if (!response.ok) throw await readErrorBody(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface ListItemsParams {
  q?: string;
  category?: string;
  status?: ItemStatus | "";
  limit?: number;
  offset?: number;
}

export interface ListMembersParams {
  q?: string;
  status?: MemberStatus | "";
  limit?: number;
  offset?: number;
}

export interface NewItem {
  name: string;
  category: string;
  replacement_value_paise: number;
  condition_note: string;
}

export interface NewMember {
  name: string;
  phone: string;
}

/** One function per backend endpoint. No business rules live here: the server decides everything. */
export const api = {
  listItems: (params: ListItemsParams, signal?: AbortSignal) =>
    request<Page<Item>>("GET", "/items", { query: { ...params }, signal }),
  getItem: (id: number, signal?: AbortSignal) => request<Item>("GET", `/items/${id}`, { signal }),
  createItem: (body: NewItem) => request<Item>("POST", "/items", { body }),
  reserveItem: (itemId: number, memberId: number) =>
    request<Loan>("POST", `/items/${itemId}/reservation`, { body: { member_id: memberId } }),
  cancelReservation: (itemId: number) => request<Loan>("DELETE", `/items/${itemId}/reservation`),
  checkOut: (itemId: number) => request<Loan>("POST", `/items/${itemId}/check-out`),
  returnItem: (itemId: number) => request<Loan>("POST", `/items/${itemId}/return`),
  startMaintenance: (itemId: number) => request<Item>("POST", `/items/${itemId}/maintenance`),
  finishMaintenance: (itemId: number) => request<Item>("DELETE", `/items/${itemId}/maintenance`),

  listMembers: (params: ListMembersParams, signal?: AbortSignal) =>
    request<Page<Member>>("GET", "/members", { query: { ...params }, signal }),
  createMember: (body: NewMember) => request<Member>("POST", "/members", { body }),
  getStatement: (id: number, signal?: AbortSignal) =>
    request<Statement>("GET", `/members/${id}/statement`, { signal }),
  suspendMember: (id: number, reason: string) =>
    request<Member>("POST", `/members/${id}/suspension`, {
      body: reason ? { reason } : undefined,
    }),
  reinstateMember: (id: number) => request<Member>("DELETE", `/members/${id}/suspension`),
  recordPayment: (id: number, amountPaise: number, note: string) =>
    request<Payment>("POST", `/members/${id}/payments`, {
      body: { amount_paise: amountPaise, ...(note ? { note } : {}) },
    }),

  listOverdue: (params: { limit?: number; offset?: number }, signal?: AbortSignal) =>
    request<Page<OverdueLoan>>("GET", "/loans/overdue", { query: { ...params }, signal }),
};

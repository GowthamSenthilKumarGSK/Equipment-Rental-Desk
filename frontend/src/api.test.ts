import { describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { setTestClock } from "./testClock";
import { apiError, mockApi } from "./test/helpers";

describe("the API client", () => {
  it("sends requests to the configured base URL with a JSON body", async () => {
    const { calls } = mockApi({ "POST /items/7/reservation": { status: 201, body: { id: 1 } } });

    await api.reserveItem(7, 5);

    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({
      method: "POST",
      path: "/items/7/reservation",
      body: { member_id: 5 },
    });
    expect(calls[0].headers["Content-Type"]).toBe("application/json");
  });

  it("builds the query string and leaves out empty filters", async () => {
    const { calls } = mockApi({ "GET /items": { body: { results: [], total: 0 } } });

    await api.listItems({ q: "drill", category: "", status: "overdue", limit: 12, offset: 24 });

    expect(Object.fromEntries(calls[0].query)).toEqual({
      q: "drill",
      status: "overdue",
      limit: "12",
      offset: "24",
    });
  });

  it("encodes characters that would otherwise change the query", async () => {
    const { calls } = mockApi({ "GET /members": { body: { results: [], total: 0 } } });

    await api.listMembers({ q: "a&b=c #1" });

    expect(calls[0].query.get("q")).toBe("a&b=c #1");
  });

  it("turns the server's error body into an ApiError with code, message and request id", async () => {
    mockApi({
      "POST /items/1/check-out": apiError(
        409,
        "reservation_expired",
        "The reservation has expired",
      ),
    });

    const failure = await api.checkOut(1).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({
      status: 409,
      code: "reservation_expired",
      message: "The reservation has expired",
      requestId: "req-test-1",
    });
  });

  it("exposes block reasons and field errors from the details", async () => {
    mockApi({
      "POST /items/1/reservation": apiError(403, "member_blocked", "blocked", {
        reasons: ["suspended", "unpaid_fees"],
      }),
      "POST /items": apiError(422, "validation_error", "invalid", [
        { field: "body.name", message: "Field required", type: "missing" },
      ]),
    });

    const blocked = (await api.reserveItem(1, 5).catch((e: unknown) => e)) as ApiError;
    const invalid = (await api
      .createItem({ name: "", category: "x", replacement_value_paise: 1, condition_note: "" })
      .catch((e: unknown) => e)) as ApiError;

    expect(blocked.blockReasons).toEqual(["suspended", "unpaid_fees"]);
    expect(invalid.fieldErrors).toEqual([
      { field: "body.name", message: "Field required", type: "missing" },
    ]);
  });

  it("copes with an error that is not our JSON shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>Bad gateway</html>", { status: 502 })),
    );

    await expect(api.getItem(1)).rejects.toMatchObject({ status: 502, code: "http_error" });
  });

  it("reports an unreachable server as a status-0 network error, not a crash", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    await expect(api.getItem(1)).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("understands a 204 with no body", async () => {
    mockApi({ "DELETE /items/1/maintenance": { status: 204 } });

    await expect(api.finishMaintenance(1)).resolves.toBeUndefined();
  });
});

describe("the test clock header", () => {
  it("is never sent by default", async () => {
    const { calls } = mockApi({ "GET /items": { body: { results: [], total: 0 } } });

    await api.listItems({});

    expect(calls[0].headers["X-Test-Clock"]).toBeUndefined();
  });

  it("is not sent even if a time was stored, unless the build enables the feature", async () => {
    setTestClock("2026-10-20T10:00:00+05:30");
    const { calls } = mockApi({ "GET /items": { body: { results: [], total: 0 } } });

    await api.listItems({});

    expect(calls[0].headers["X-Test-Clock"]).toBeUndefined();
  });

  it("is sent when the build enables it and a time is set", async () => {
    vi.stubEnv("VITE_ENABLE_TEST_CLOCK", "true");
    setTestClock("2026-10-20T10:00:00+05:30");
    const { calls } = mockApi({ "GET /items": { body: { results: [], total: 0 } } });

    await api.listItems({});

    expect(calls[0].headers["X-Test-Clock"]).toBe("2026-10-20T10:00:00+05:30");
    vi.unstubAllEnvs();
  });
});

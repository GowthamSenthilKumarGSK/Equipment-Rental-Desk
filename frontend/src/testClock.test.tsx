import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getTestClock, istInputToIso } from "./testClock";
import { makeItem, mockApi, page, renderApp } from "./test/helpers";

describe("the reviewer test clock in the UI", () => {
  it("is not offered in a normal build", async () => {
    mockApi({ "GET /items": { body: page([makeItem()]) } });

    renderApp("/items");

    await screen.findByRole("link", { name: "Cordless Drill" });
    expect(screen.queryByText(/test clock/i)).not.toBeInTheDocument();
    expect(getTestClock()).toBeNull();
  });

  it("never sends the header from a normal build, even if a stale value is in storage", async () => {
    window.sessionStorage.setItem("rental-desk-test-clock", "2026-10-20T10:00:00+05:30");
    const api = mockApi({ "GET /items": { body: page([makeItem()]) } });

    renderApp("/items");

    await screen.findByRole("link", { name: "Cordless Drill" });
    expect(api.calls.every((call) => call.headers["X-Test-Clock"] === undefined)).toBe(true);
    expect(screen.queryByText(/Test clock is on/)).not.toBeInTheDocument();
  });

  it("is off until someone sets a time, in a build that offers it", async () => {
    vi.stubEnv("VITE_ENABLE_TEST_CLOCK", "true");
    const api = mockApi({ "GET /items": { body: page([makeItem()]) } });

    renderApp("/items");

    await screen.findByRole("link", { name: "Cordless Drill" });
    expect(screen.getByText("Reviewer test clock (testing only)")).toBeInTheDocument();
    expect(screen.queryByText(/Test clock is on/)).not.toBeInTheDocument();
    expect(api.calls.every((call) => call.headers["X-Test-Clock"] === undefined)).toBe(true);
  });

  it("shows a banner while on, sends the header, and goes back to real time", async () => {
    vi.stubEnv("VITE_ENABLE_TEST_CLOCK", "true");
    const api = mockApi({ "GET /items": { body: page([makeItem()]) } });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.click(screen.getByText("Reviewer test clock (testing only)"));
    await user.type(screen.getByLabelText("Pretend it is (IST)"), "2026-10-20T10:30");
    await user.click(screen.getByRole("button", { name: "Use this time" }));

    const banner = await screen.findByText(/Test clock is on/);
    expect(banner.closest(".banner")).toHaveTextContent("20 Oct 2026, 10:30 am IST");
    await waitFor(() =>
      expect(api.calls.at(-1)?.headers["X-Test-Clock"]).toBe("2026-10-20T10:30:00+05:30"),
    );

    await user.click(screen.getByRole("button", { name: "Go back to real time" }));

    await waitFor(() => expect(screen.queryByText(/Test clock is on/)).not.toBeInTheDocument());
    await waitFor(() => expect(api.calls.at(-1)?.headers["X-Test-Clock"]).toBeUndefined());
  });

  it("asks for a time rather than sending an empty one", async () => {
    vi.stubEnv("VITE_ENABLE_TEST_CLOCK", "true");
    const api = mockApi({ "GET /items": { body: page([makeItem()]) } });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.click(screen.getByText("Reviewer test clock (testing only)"));
    await user.click(screen.getByRole("button", { name: "Use this time" }));

    const panel = screen.getByText("Reviewer test clock (testing only)").closest("details")!;
    expect(within(panel).getByText("Choose a date and time.")).toBeInTheDocument();
    expect(getTestClock()).toBeNull();
    expect(api.calls.every((call) => call.headers["X-Test-Clock"] === undefined)).toBe(true);
  });
});

describe("istInputToIso", () => {
  it("reads a datetime-local value as India time", () => {
    expect(istInputToIso("2026-10-20T10:30")).toBe("2026-10-20T10:30:00+05:30");
  });

  it.each(["", "2026-10-20", "yesterday", "2026-10-20T10:30:00Z"])("refuses %j", (value) => {
    expect(istInputToIso(value)).toBeNull();
  });
});

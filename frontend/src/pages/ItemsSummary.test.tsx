import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Item, ItemStatus } from "../types";
import { apiError, makeItem, mockApi, page, renderApp } from "../test/helpers";

const STATUS_TOTALS: Record<string, number> = {
  "": 13,
  available: 4,
  reserved: 2,
  checked_out: 3,
  overdue: 3,
  under_maintenance: 1,
};

const FIGURES = [
  "All items13",
  "Available4",
  "Reserved2",
  "Checked out3",
  "Overdue3",
  "Under maintenance1",
];

/** Thirteen items spread over the statuses exactly as STATUS_TOTALS says. */
function thirteenItems(): Item[] {
  const spread: [ItemStatus, number][] = [
    ["available", 4],
    ["reserved", 2],
    ["checked_out", 3],
    ["overdue", 3],
    ["under_maintenance", 1],
  ];
  let id = 0;
  return spread.flatMap(([status, count]) =>
    Array.from({ length: count }, () => makeItem({ id: ++id, name: `Item ${id}`, status })),
  );
}

/** Every item fits in the one 200-item request, so nothing else needs to be asked. */
function completeInventory() {
  const all = thirteenItems();
  return (call: { query: URLSearchParams }) => {
    const limit = Number(call.query.get("limit"));
    return { body: page(limit === 200 ? all : all.slice(0, limit), all.length, limit) };
  };
}

/** More items than one request can hold: the page has to ask for each status's total. */
function largeInventory(failTotals = false) {
  const all = thirteenItems();
  return (call: { query: URLSearchParams }) => {
    const limit = Number(call.query.get("limit"));
    if (limit === 200) return { body: page(all.slice(0, 5), STATUS_TOTALS[""], 200) };
    if (limit === 1) {
      if (failTotals) return apiError(500, "internal_error", "An unexpected error occurred.");
      return { body: page(all.slice(0, 1), STATUS_TOTALS[call.query.get("status") ?? ""], 1) };
    }
    return { body: page(all.slice(0, limit), all.length, limit) };
  };
}

function figures(list: HTMLElement) {
  return within(list)
    .getAllByRole("listitem")
    .map((li) => li.textContent);
}

describe("items: inventory summary", () => {
  it("tallies the counts from the one request that also supplies the categories", async () => {
    const api = mockApi({ "GET /items": completeInventory() });

    renderApp("/items");

    const summary = await screen.findByRole("list", { name: "Inventory summary" });
    expect(figures(summary)).toEqual(FIGURES);
    // No extra requests: just the page of items and the 200-item request.
    const limits = api.callsTo("GET /items").map((call) => call.query.get("limit"));
    expect(limits.sort()).toEqual(["12", "200"]);
  });

  it("asks the API for each status's total only when the inventory is too big for one request", async () => {
    const api = mockApi({ "GET /items": largeInventory() });

    renderApp("/items");

    const summary = await screen.findByRole("list", { name: "Inventory summary" });
    expect(figures(summary)).toEqual(FIGURES);
    const asked = api
      .callsTo("GET /items")
      .filter((call) => call.query.get("limit") === "1")
      .map((call) => call.query.get("status") ?? "");
    expect(asked.sort()).toEqual(
      ["", "available", "checked_out", "overdue", "reserved", "under_maintenance"].sort(),
    );
  });

  it("links each figure to the item list filtered by that status", async () => {
    mockApi({ "GET /items": completeInventory() });

    renderApp("/items");

    const summary = await screen.findByRole("list", { name: "Inventory summary" });
    expect(within(summary).getByRole("link", { name: "Overdue" })).toHaveAttribute(
      "href",
      "/items?status=overdue",
    );
    expect(within(summary).getByRole("link", { name: "Under maintenance" })).toHaveAttribute(
      "href",
      "/items?status=under_maintenance",
    );
    expect(within(summary).getByRole("link", { name: "All items" })).toHaveAttribute(
      "href",
      "/items",
    );
  });

  it("shows placeholders while the counts load, hidden from assistive technology", async () => {
    mockApi({ "GET /items": completeInventory() });

    renderApp("/items");

    const placeholders = document.querySelectorAll(
      ".skeleton-cards .skeleton, .skeleton-block .skeleton",
    );
    expect(placeholders.length).toBeGreaterThan(0);
    placeholders.forEach((shape) => expect(shape).toHaveAttribute("aria-hidden", "true"));
    await screen.findByRole("list", { name: "Inventory summary" });
    expect(document.querySelector(".skeleton-cards")).toBeNull();
  });

  it("does not raise an alarm when only the summary fails: the list still works and the summary can be retried", async () => {
    let failing = true;
    mockApi({
      "GET /items": (call) =>
        call.query.get("limit") === "200" && failing
          ? apiError(500, "internal_error", "An unexpected error occurred.")
          : completeInventory()(call),
    });
    const { user } = renderApp("/items");

    expect(await screen.findByText(/inventory summary is not available/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Item 1" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    failing = false;
    await user.click(screen.getByRole("button", { name: "Retry the summary" }));

    await waitFor(() =>
      expect(screen.getByRole("list", { name: "Inventory summary" })).toBeInTheDocument(),
    );
  });

  it("keeps the category choices when only the per-status totals fail", async () => {
    mockApi({ "GET /items": largeInventory(true) });

    renderApp("/items");

    expect(await screen.findByText(/inventory summary is not available/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Power Tools" })).toBeInTheDocument();
  });

  it("keeps the filter in the address when a summary figure is followed", async () => {
    mockApi({ "GET /items": completeInventory() });
    const { user } = renderApp("/items");
    const summary = await screen.findByRole("list", { name: "Inventory summary" });

    await user.click(within(summary).getByRole("link", { name: "Available" }));

    expect(await screen.findByLabelText("Status")).toHaveValue("available");
  });
});

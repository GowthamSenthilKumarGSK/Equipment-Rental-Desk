import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { apiError, makeItem, makeLoan, mockApi, page, renderApp } from "../test/helpers";

const DRILL = makeItem({ id: 1, name: "Cordless Drill" });
const LADDER = makeItem({
  id: 2,
  name: "Extension Ladder",
  category: "Ladders",
  status: "checked_out",
  current_loan: makeLoan({ status: "checked_out", due_at: "2026-10-19T10:00:00Z" }),
  allowed_actions: ["return", "start_maintenance"],
});

function itemsRoute(all = [DRILL, LADDER]) {
  return (call: { query: URLSearchParams }) => {
    if (call.query.get("limit") === "200") return { body: page(all, all.length, 200) };
    return { body: page(all, all.length) };
  };
}

describe("item catalogue", () => {
  const filters = () => within(screen.getByRole("group", { name: "Filter items" }));

  it("lists items with their status and availability", async () => {
    mockApi({ "GET /items": itemsRoute() });

    renderApp("/items");

    const list = await screen.findByRole("list", { name: "Items" });
    expect(within(list).getByRole("link", { name: "Cordless Drill" })).toHaveAttribute(
      "href",
      "/items/1",
    );
    expect(within(list).getByText("Available now")).toBeInTheDocument();
    expect(within(list).getByText(/Out on loan, due 19 Oct 2026/)).toBeInTheDocument();
    expect(within(list).getByText("Checked out")).toBeInTheDocument();
    expect(within(list).getAllByText(/replacement value ₹6,500\.00/)).toHaveLength(2);
  });

  it("shows a loading message first, then the items", async () => {
    mockApi({ "GET /items": itemsRoute() });

    renderApp("/items");

    expect(screen.getByRole("status")).toHaveTextContent("Loading items");
    expect(await screen.findByRole("link", { name: "Cordless Drill" })).toBeInTheDocument();
  });

  it("searches by name through the API and keeps the search in the address", async () => {
    const api = mockApi({
      "GET /items": (call) =>
        call.query.get("limit") === "200"
          ? { body: page([DRILL, LADDER], 2, 200) }
          : { body: page(call.query.get("q") === "lad" ? [LADDER] : [DRILL, LADDER]) },
    });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.type(screen.getByLabelText("Search by name"), "lad");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(screen.queryByRole("link", { name: "Cordless Drill" })).not.toBeInTheDocument(),
    );
    expect(screen.getByRole("link", { name: "Extension Ladder" })).toBeInTheDocument();
    const lastList = api
      .callsTo("GET /items")
      .filter((c) => c.query.get("limit") === "12")
      .at(-1);
    expect(lastList?.query.get("q")).toBe("lad");
  });

  it("filters by status and by category using the options the API reported", async () => {
    const api = mockApi({ "GET /items": itemsRoute() });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.selectOptions(filters().getByLabelText("Status"), "overdue");
    await waitFor(() =>
      expect(api.callsTo("GET /items").some((c) => c.query.get("status") === "overdue")).toBe(true),
    );

    await user.selectOptions(filters().getByLabelText("Category"), "Ladders");
    await waitFor(() =>
      expect(
        api
          .callsTo("GET /items")
          .some(
            (c) => c.query.get("category") === "Ladders" && c.query.get("status") === "overdue",
          ),
      ).toBe(true),
    );
    expect(
      within(filters().getByLabelText("Category"))
        .getAllByRole("option")
        .map((o) => o.textContent),
    ).toEqual(["All categories", "Ladders", "Power Tools"]);
  });

  it("starts from the filters in the address", async () => {
    const api = mockApi({ "GET /items": itemsRoute([]) });

    renderApp("/items?q=saw&status=available&category=Garden&page=3");

    await screen.findByText("No items match these filters.");
    const call = api.callsTo("GET /items").find((c) => c.query.get("limit") === "12");
    expect(Object.fromEntries(call!.query)).toMatchObject({
      q: "saw",
      status: "available",
      category: "Garden",
      offset: "24",
    });
  });

  it("shows an empty state with a way to clear the filters", async () => {
    mockApi({ "GET /items": itemsRoute([]) });

    renderApp("/items?q=zzz");

    expect(await screen.findByText("No items match these filters.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clear filters" })).toHaveAttribute("href", "/items");
  });

  it("says so when there are no items at all", async () => {
    mockApi({ "GET /items": itemsRoute([]) });

    renderApp("/items");

    expect(await screen.findByText("There are no items yet.")).toBeInTheDocument();
  });

  it("pages through results", async () => {
    const many = Array.from({ length: 12 }, (_, n) =>
      makeItem({ id: n + 1, name: `Item ${n + 1}` }),
    );
    const api = mockApi({
      "GET /items": (call) =>
        call.query.get("limit") === "200"
          ? { body: page(many, 30, 200) }
          : { body: page(many, 30, 12, Number(call.query.get("offset"))) },
    });
    const { user } = renderApp("/items");
    expect(await screen.findByText("Showing 1–12 of 30")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() =>
      expect(api.callsTo("GET /items").some((c) => c.query.get("offset") === "12")).toBe(true),
    );
    expect(await screen.findByText("Showing 13–24 of 30")).toBeInTheDocument();
  });

  it("shows a readable error with a retry when the server fails", async () => {
    let fail = true;
    mockApi({
      "GET /items": (call) =>
        fail && call.query.get("limit") === "12"
          ? apiError(500, "internal_error", "An unexpected error occurred.")
          : { body: page([DRILL]) },
    });
    const { user } = renderApp("/items");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Server error");
    expect(alert).toHaveTextContent("Reference: req-test-1");
    fail = false;
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("link", { name: "Cordless Drill" })).toBeInTheDocument();
  });

  it("explains when the server cannot be reached", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );

    renderApp("/items");

    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach the server");
  });
});

describe("adding an item", () => {
  const form = () => within(screen.getByRole("form", { name: "Add an item" }));

  it("checks the form before sending anything", async () => {
    const api = mockApi({ "GET /items": itemsRoute() });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.click(screen.getByText("Add an item"));
    await user.click(form().getByRole("button", { name: "Add item" }));

    expect(screen.getByText("Enter the item's name.")).toBeInTheDocument();
    expect(screen.getByText(/Enter a category/)).toBeInTheDocument();
    expect(screen.getByText(/Enter the value in rupees/)).toBeInTheDocument();
    expect(api.callsTo("POST /items")).toHaveLength(0);

    await user.type(form().getByLabelText("Name"), "Saw");
    await user.type(form().getByLabelText("Category"), "Power Tools");
    await user.type(form().getByLabelText("Replacement value (₹)"), "0");
    await user.click(form().getByRole("button", { name: "Add item" }));
    expect(screen.getByText("The value must be more than zero.")).toBeInTheDocument();
    expect(api.callsTo("POST /items")).toHaveLength(0);
  });

  it("sends the value as whole paise and confirms", async () => {
    const created = makeItem({ id: 9, name: "Saw" });
    const api = mockApi({
      "GET /items": itemsRoute(),
      "POST /items": { status: 201, body: created },
    });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.click(screen.getByText("Add an item"));
    await user.type(form().getByLabelText("Name"), "  Saw ");
    await user.type(form().getByLabelText("Category"), "Power Tools");
    await user.type(form().getByLabelText("Replacement value (₹)"), "1500.50");
    await user.click(form().getByRole("button", { name: "Add item" }));

    expect(await screen.findByText(/Added/)).toHaveTextContent("Added Saw.");
    expect(api.callsTo("POST /items")[0].body).toEqual({
      name: "Saw",
      category: "Power Tools",
      replacement_value_paise: 150_050,
      condition_note: "",
    });
  });

  it("shows what the server refused", async () => {
    mockApi({
      "GET /items": itemsRoute(),
      "POST /items": apiError(422, "validation_error", "The request is invalid", [
        {
          field: "body.name",
          message: "Text must not contain NUL (0x00) characters",
          type: "value_error",
        },
      ]),
    });
    const { user } = renderApp("/items");
    await screen.findByRole("link", { name: "Cordless Drill" });

    await user.click(screen.getByText("Add an item"));
    await user.type(form().getByLabelText("Name"), "Saw");
    await user.type(form().getByLabelText("Category"), "Tools");
    await user.type(form().getByLabelText("Replacement value (₹)"), "10");
    await user.click(form().getByRole("button", { name: "Add item" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Please check the form");
    expect(alert).toHaveTextContent("Name: Text must not contain NUL (0x00) characters");
  });
});

describe("a page past the end of the list", () => {
  const forty = Array.from({ length: 12 }, (_, n) =>
    makeItem({ id: n + 1, name: `Item ${n + 1}` }),
  );

  function route() {
    return (call: { query: URLSearchParams }) => {
      if (call.query.get("limit") === "200") return { body: page(forty, 40, 200) };
      const offset = Number(call.query.get("offset"));
      return { body: page(offset < 40 ? forty : [], 40, 12, offset) };
    };
  }

  it("says so instead of claiming there are no items, with no impossible range", async () => {
    mockApi({ "GET /items": route() });

    renderApp("/items?page=99");

    expect(await screen.findByText(/There is nothing on this page/)).toHaveTextContent(
      "The list has 40 items.",
    );
    expect(screen.queryByText("There are no items yet.")).not.toBeInTheDocument();
    expect(screen.queryByText("No items match these filters.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next" })).not.toBeInTheDocument();
  });

  it("takes you to the last page that has items", async () => {
    const api = mockApi({ "GET /items": route() });
    const { user } = renderApp("/items?page=99");

    await user.click(await screen.findByRole("button", { name: "Go to the last page" }));

    expect(await screen.findByText("Showing 37–40 of 40")).toBeInTheDocument();
    expect(api.callsTo("GET /items").some((c) => c.query.get("offset") === "36")).toBe(true);
    expect(screen.queryByText(/There is nothing on this page/)).not.toBeInTheDocument();
  });

  it("treats a page just past an exact multiple the same way", async () => {
    mockApi({
      "GET /items": (call) =>
        call.query.get("limit") === "200"
          ? { body: page(forty, 24, 200) }
          : { body: page([], 24, 12, Number(call.query.get("offset"))) },
    });

    renderApp("/items?page=3"); // 24 items fill pages 1 and 2 exactly

    expect(await screen.findByText(/The list has 24 items\./)).toBeInTheDocument();
  });

  it("shows no pager and the empty message for a list with nothing in it", async () => {
    mockApi({ "GET /items": itemsRoute([]) });

    renderApp("/items");

    expect(await screen.findByText("There are no items yet.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Item pages" })).not.toBeInTheDocument();
    expect(screen.queryByText(/There is nothing on this page/)).not.toBeInTheDocument();
  });
});

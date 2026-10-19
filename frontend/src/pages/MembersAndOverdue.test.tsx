import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { apiError, makeMember, makeOverdue, mockApi, page, renderApp } from "../test/helpers";

const KAVITA = makeMember({ id: 5, name: "Kavita Iyer" });
const DINESH = makeMember({ id: 9, name: "Dinesh Patel", status: "suspended" });

describe("members list", () => {
  it("lists members with their status", async () => {
    mockApi({ "GET /members": { body: page([KAVITA, DINESH]) } });

    renderApp("/members");

    const list = await screen.findByRole("list", { name: "Members" });
    expect(within(list).getByRole("link", { name: "Kavita Iyer" })).toHaveAttribute(
      "href",
      "/members/5",
    );
    expect(within(list).getByText("Active")).toBeInTheDocument();
    expect(within(list).getByText("Suspended")).toBeInTheDocument();
    expect(within(list).getAllByText(/joined 9 Feb 2026/, { selector: "p" })).toHaveLength(2);
  });

  it("searches and filters through the API", async () => {
    const api = mockApi({
      "GET /members": (call) => ({
        body: page(call.query.get("q") === "dine" ? [DINESH] : [KAVITA, DINESH]),
      }),
    });
    const { user } = renderApp("/members");
    await screen.findByRole("link", { name: "Kavita Iyer" });

    await user.type(screen.getByLabelText("Search by name or phone"), "dine");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(screen.queryByRole("link", { name: "Kavita Iyer" })).toBeNull());
    expect(screen.getByRole("link", { name: "Dinesh Patel" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Status"), "suspended");
    await waitFor(() =>
      expect(api.callsTo("GET /members").some((c) => c.query.get("status") === "suspended")).toBe(
        true,
      ),
    );
  });

  it("shows empty and error states", async () => {
    mockApi({ "GET /members": { body: page([]) } });
    renderApp("/members?q=nobody");
    expect(await screen.findByText("No members match these filters.")).toBeInTheDocument();
  });

  it("shows a readable error when the list cannot be loaded", async () => {
    mockApi({ "GET /members": apiError(500, "internal_error", "An unexpected error occurred.") });

    renderApp("/members");

    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
  });
});

describe("registering a member", () => {
  function form() {
    return within(screen.getByRole("form", { name: "Register a member" }));
  }

  it("checks the name and phone before sending anything", async () => {
    const api = mockApi({ "GET /members": { body: page([KAVITA]) } });
    const { user } = renderApp("/members");
    await screen.findByRole("link", { name: "Kavita Iyer" });

    await user.click(screen.getByText("Register a member"));
    await user.click(form().getByRole("button", { name: "Register member" }));
    expect(form().getByText("Enter the member's name.")).toBeInTheDocument();
    expect(form().getByText(/Enter a phone number/)).toBeInTheDocument();

    await user.type(form().getByLabelText("Name"), "Asha Rao");
    await user.type(form().getByLabelText("Phone"), "call me");
    await user.click(form().getByRole("button", { name: "Register member" }));
    expect(form().getByText(/Enter a phone number/)).toBeInTheDocument();
    expect(api.callsTo("POST /members")).toHaveLength(0);
  });

  it("registers a member and links to them", async () => {
    const api = mockApi({
      "GET /members": { body: page([KAVITA]) },
      "POST /members": { status: 201, body: makeMember({ id: 12, name: "Asha Rao" }) },
    });
    const { user } = renderApp("/members");
    await screen.findByRole("link", { name: "Kavita Iyer" });

    await user.click(screen.getByText("Register a member"));
    await user.type(form().getByLabelText("Name"), " Asha Rao ");
    await user.type(form().getByLabelText("Phone"), "+91 00000 20001");
    await user.click(form().getByRole("button", { name: "Register member" }));

    const done = await screen.findByText(/Registered/);
    expect(within(done).getByRole("link", { name: "Asha Rao" })).toHaveAttribute(
      "href",
      "/members/12",
    );
    expect(api.callsTo("POST /members")[0].body).toEqual({
      name: "Asha Rao",
      phone: "+91 00000 20001",
    });
  });
});

describe("overdue dashboard", () => {
  it("lists overdue loans with member, item, due date, days and the fee so far", async () => {
    mockApi({ "GET /loans/overdue": { body: page([makeOverdue()], 1, 20) } });

    renderApp("/overdue");

    const table = await screen.findByRole("table", { name: "Loans past their due time" });
    expect(within(table).getByRole("link", { name: "Pressure Washer" })).toHaveAttribute(
      "href",
      "/items/3",
    );
    expect(within(table).getByRole("link", { name: "Meera Kulkarni" })).toHaveAttribute(
      "href",
      "/members/5",
    );
    expect(within(table).getByText("+91 00000 10004")).toBeInTheDocument();
    expect(within(table).getByText("1 Oct 2026, 3:30 pm IST")).toBeInTheDocument();
    expect(within(table).getByText("17 days")).toBeInTheDocument();
    expect(within(table).getByText("₹170.00")).toBeInTheDocument();
  });

  it("says when nothing is overdue", async () => {
    mockApi({ "GET /loans/overdue": { body: page([], 0, 20) } });

    renderApp("/overdue");

    expect(await screen.findByText("Nothing is overdue.")).toBeInTheDocument();
  });

  it("pages through a long list", async () => {
    const rows = Array.from({ length: 20 }, (_, n) =>
      makeOverdue({ loan_id: n + 1, item_name: `Item ${n + 1}` }),
    );
    const api = mockApi({
      "GET /loans/overdue": (call) => ({
        body: page(rows, 45, 20, Number(call.query.get("offset"))),
      }),
    });
    const { user } = renderApp("/overdue");
    expect(await screen.findByText("Showing 1–20 of 45")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Showing 21–40 of 45")).toBeInTheDocument();
    expect(api.callsTo("GET /loans/overdue").some((c) => c.query.get("offset") === "20")).toBe(
      true,
    );
  });

  it("shows an error with a retry", async () => {
    mockApi({
      "GET /loans/overdue": apiError(500, "internal_error", "An unexpected error occurred."),
    });

    renderApp("/overdue");

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});

describe("navigation", () => {
  it("opens the item list from the front page and has a working menu", async () => {
    mockApi({ "GET /items": { body: page([]) } });

    renderApp("/");

    expect(await screen.findByRole("heading", { level: 1, name: "Items" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((a) => a.textContent),
    ).toEqual(["Items", "Members", "Overdue", "Dashboard"]);
    expect(within(nav).getByRole("link", { name: "Items" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("shows a helpful page for an unknown address", async () => {
    mockApi({});

    renderApp("/nowhere");

    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });

  it("offers a skip link and a labelled main area", async () => {
    mockApi({ "GET /items": { body: page([]) } });

    renderApp("/items");

    expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  });
});

describe("members: a page past the end of the list", () => {
  function route() {
    return (call: { query: URLSearchParams }) => {
      const offset = Number(call.query.get("offset"));
      return { body: page(offset < 14 ? [KAVITA, DINESH] : [], 14, 12, offset) };
    };
  }

  it("does not claim there are no members or show an impossible range", async () => {
    mockApi({ "GET /members": route() });

    renderApp("/members?page=50");

    expect(await screen.findByText(/There is nothing on this page/)).toHaveTextContent(
      "The list has 14 members.",
    );
    expect(screen.queryByText("There are no members yet.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
  });

  it("goes to the last page that has members", async () => {
    const api = mockApi({ "GET /members": route() });
    const { user } = renderApp("/members?page=50");

    await user.click(await screen.findByRole("button", { name: "Go to the last page" }));

    expect(await screen.findByText("Showing 13–14 of 14")).toBeInTheDocument();
    expect(api.callsTo("GET /members").some((c) => c.query.get("offset") === "12")).toBe(true);
  });

  it("shows the empty message and no pager for no members at all", async () => {
    mockApi({ "GET /members": { body: page([]) } });

    renderApp("/members");

    expect(await screen.findByText("There are no members yet.")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Member pages" })).not.toBeInTheDocument();
  });
});

describe("overdue: a page past the end of the list", () => {
  it("recovers when the list shrinks while you are on a later page", async () => {
    const rows = Array.from({ length: 20 }, (_, n) =>
      makeOverdue({ loan_id: n + 1, item_name: `Item ${n + 1}` }),
    );
    let shrunk = false;
    const api = mockApi({
      "GET /loans/overdue": (call) => {
        const offset = Number(call.query.get("offset"));
        if (!shrunk) return { body: page(rows, 45, 20, offset) };
        return { body: page(offset === 0 ? rows.slice(0, 5) : [], 5, 20, offset) };
      },
    });
    const { user } = renderApp("/overdue");
    expect(await screen.findByText("Showing 1–20 of 45")).toBeInTheDocument();

    shrunk = true; // returns elsewhere removed most of them
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText(/There is nothing on this page/)).toHaveTextContent(
      "The list has 5 overdue loans.",
    );
    expect(screen.queryByText("Nothing is overdue.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Go to the last page" }));

    expect(await screen.findByText("Showing 1–5 of 5")).toBeInTheDocument();
    expect(api.callsTo("GET /loans/overdue").at(-1)?.query.get("offset")).toBe("0");
  });
});

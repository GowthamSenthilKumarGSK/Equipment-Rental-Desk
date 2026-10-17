import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Item, ItemAction } from "../types";
import {
  apiError,
  makeItem,
  makeLoan,
  makeMember,
  mockApi,
  page,
  renderApp,
} from "../test/helpers";

const KAVITA = makeMember({ id: 5, name: "Kavita Iyer" });
const DINESH = makeMember({ id: 9, name: "Dinesh Patel", status: "suspended" });

const BUTTONS = [
  /^(Choose a member to reserve for|Reserve for)/,
  "Check out",
  "Return",
  "Cancel reservation",
  "Put under maintenance",
  "End maintenance",
] as const;

function visibleButtons(): string[] {
  return screen
    .queryAllByRole("button")
    .map((button) => button.textContent ?? "")
    .filter((text) => BUTTONS.some((b) => (typeof b === "string" ? text === b : b.test(text))));
}

const reservedLoan = makeLoan({ status: "reserved" });
const checkedOutLoan = makeLoan({
  status: "checked_out",
  expires_at: null,
  checked_out_at: "2026-10-12T10:00:00Z",
  due_at: "2026-10-19T10:00:00Z",
});

describe("item detail: only the actions the API allows", () => {
  const cases: [string, Item, string[]][] = [
    ["available", makeItem(), ["Choose a member to reserve for", "Put under maintenance"]],
    [
      "reserved",
      makeItem({
        status: "reserved",
        current_loan: reservedLoan,
        allowed_actions: ["check_out", "cancel_reservation", "start_maintenance"],
      }),
      ["Check out", "Cancel reservation", "Put under maintenance"],
    ],
    [
      "checked out",
      makeItem({
        status: "checked_out",
        current_loan: checkedOutLoan,
        allowed_actions: ["return", "start_maintenance"],
      }),
      ["Return", "Put under maintenance"],
    ],
    [
      "overdue",
      makeItem({
        status: "overdue",
        current_loan: checkedOutLoan,
        allowed_actions: ["return", "start_maintenance"],
      }),
      ["Return", "Put under maintenance"],
    ],
    [
      "under maintenance",
      makeItem({ status: "under_maintenance", allowed_actions: ["finish_maintenance"] }),
      ["End maintenance"],
    ],
    [
      "under maintenance but still on loan",
      makeItem({
        status: "under_maintenance",
        current_loan: checkedOutLoan,
        allowed_actions: ["return"],
      }),
      ["Return"],
    ],
  ];

  it.each(cases)("%s", async (_name, item, expected) => {
    mockApi({ "GET /items/1": { body: item }, "GET /members": { body: page([KAVITA]) } });

    renderApp("/items/1");

    await screen.findByRole("heading", { level: 1, name: item.name });
    expect(visibleButtons()).toEqual(expected);
  });

  it("says so when nothing can be done", async () => {
    mockApi({ "GET /items/1": { body: makeItem({ allowed_actions: [] }) } });

    renderApp("/items/1");

    expect(await screen.findByText("Nothing can be done with this item right now.")).toBeVisible();
    expect(visibleButtons()).toEqual([]);
  });

  it("follows whatever the API says, even for a combination the UI has never seen", async () => {
    const odd: ItemAction[] = ["return", "check_out"];
    mockApi({ "GET /items/1": { body: makeItem({ allowed_actions: odd }) } });

    renderApp("/items/1");

    await screen.findByRole("heading", { level: 1, name: "Cordless Drill" });
    expect(visibleButtons()).toEqual(["Check out", "Return"]);
  });

  it("shows the item's details and its current loan", async () => {
    mockApi({
      "GET /items/1": {
        body: makeItem({
          status: "checked_out",
          current_loan: checkedOutLoan,
          allowed_actions: ["return"],
        }),
      },
    });

    renderApp("/items/1");

    expect(await screen.findByText("Power Tools")).toBeInTheDocument();
    expect(screen.getByText("₹6,500.00")).toBeInTheDocument();
    expect(screen.getByText("Two batteries and charger")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Member #5" })).toHaveAttribute("href", "/members/5");
    expect(screen.getByText("19 Oct 2026, 3:30 pm IST", { selector: "dd" })).toBeInTheDocument();
  });
});

describe("item detail: actions", () => {
  it("reserves for the chosen member, then shows the reserved item", async () => {
    let current = makeItem();
    const api = mockApi({
      "GET /items/1": () => ({ body: current }),
      "GET /members": { body: page([KAVITA, DINESH]) },
      "POST /items/1/reservation": () => {
        current = makeItem({
          status: "reserved",
          current_loan: reservedLoan,
          allowed_actions: ["check_out", "cancel_reservation", "start_maintenance"],
        });
        return { status: 201, body: reservedLoan };
      },
    });
    const { user } = renderApp("/items/1");

    const reserve = await screen.findByRole("button", { name: "Choose a member to reserve for" });
    expect(reserve).toBeDisabled();
    expect(await screen.findByText(/Dinesh Patel/)).toBeInTheDocument();
    expect(screen.getByText("Suspended")).toBeInTheDocument(); // shown, but the server decides
    await user.click(await screen.findByRole("radio", { name: /Kavita Iyer/ }));
    await user.click(screen.getByRole("button", { name: "Reserve for Kavita Iyer" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Reserved for Kavita Iyer. The hold lasts until 14 Oct 2026, 3:30 pm IST.",
    );
    expect(api.callsTo("POST /items/1/reservation")[0].body).toEqual({ member_id: 5 });
    expect(await screen.findByRole("button", { name: "Check out" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reserve for/ })).not.toBeInTheDocument();
  });

  it("searches members by what is typed", async () => {
    const api = mockApi({
      "GET /items/1": { body: makeItem() },
      "GET /members": (call) => ({
        body: page(call.query.get("q") === "dine" ? [DINESH] : [KAVITA, DINESH]),
      }),
    });
    const { user } = renderApp("/items/1");
    await screen.findByRole("radio", { name: /Kavita Iyer/ });

    await user.type(screen.getByLabelText("Find a member (name or phone)"), "dine");

    await waitFor(() => expect(screen.queryByRole("radio", { name: /Kavita Iyer/ })).toBeNull());
    expect(await screen.findByRole("radio", { name: /Dinesh Patel/ })).toBeInTheDocument();
    expect(api.callsTo("GET /members").some((call) => call.query.get("q") === "dine")).toBe(true);
  });

  it("explains why a blocked member could not reserve, listing each reason", async () => {
    mockApi({
      "GET /items/1": { body: makeItem() },
      "GET /members": { body: page([DINESH]) },
      "POST /items/1/reservation": apiError(403, "member_blocked", "Member is blocked", {
        reasons: ["suspended", "unpaid_fees"],
      }),
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("radio", { name: /Dinesh Patel/ }));
    await user.click(screen.getByRole("button", { name: "Reserve for Dinesh Patel" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This member can't borrow right now");
    expect(within(alert).getByText("The member is suspended.")).toBeInTheDocument();
    expect(within(alert).getByText(/unpaid fees are over the limit/)).toBeInTheDocument();
    expect(screen.getByText("Available now")).toBeInTheDocument(); // nothing changed
  });

  it("checks out and reports the due date", async () => {
    let current = makeItem({
      status: "reserved",
      current_loan: reservedLoan,
      allowed_actions: ["check_out", "cancel_reservation", "start_maintenance"],
    });
    const api = mockApi({
      "GET /items/1": () => ({ body: current }),
      "POST /items/1/check-out": () => {
        current = makeItem({
          status: "checked_out",
          current_loan: checkedOutLoan,
          allowed_actions: ["return", "start_maintenance"],
        });
        return { body: checkedOutLoan };
      },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "Check out" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Checked out. It is due back 19 Oct 2026, 3:30 pm IST.",
    );
    expect(api.callsTo("POST /items/1/check-out")).toHaveLength(1);
    expect(await screen.findByRole("button", { name: "Return" })).toBeInTheDocument();
  });

  it("reports a late fee when an item comes back late", async () => {
    const out = makeItem({
      status: "overdue",
      current_loan: checkedOutLoan,
      allowed_actions: ["return", "start_maintenance"],
    });
    mockApi({
      "GET /items/1": { body: out },
      "POST /items/1/return": {
        body: makeLoan({ status: "returned", expires_at: null, fee_charged_paise: 3000 }),
      },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "Return" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Returned. A late fee of ₹30.00 was added to the member's balance.",
    );
  });

  it("says when an item comes back on time", async () => {
    mockApi({
      "GET /items/1": {
        body: makeItem({
          status: "checked_out",
          current_loan: checkedOutLoan,
          allowed_actions: ["return"],
        }),
      },
      "POST /items/1/return": { body: makeLoan({ status: "returned", fee_charged_paise: 0 }) },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "Return" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Returned on time. No late fee.");
  });

  it.each([
    ["Cancel reservation", "DELETE /items/1/reservation", "Reservation cancelled."],
    ["Put under maintenance", "POST /items/1/maintenance", "The item is now under maintenance."],
  ])("%s", async (label, route, message) => {
    const api = mockApi({
      "GET /items/1": {
        body: makeItem({
          status: "reserved",
          current_loan: reservedLoan,
          allowed_actions: ["check_out", "cancel_reservation", "start_maintenance"],
        }),
      },
      [route]: { body: makeLoan({ status: "cancelled" }) },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: label }));

    expect(await screen.findByRole("status")).toHaveTextContent(message);
    expect(api.callsTo(route)).toHaveLength(1);
  });

  it("ends maintenance", async () => {
    const api = mockApi({
      "GET /items/1": {
        body: makeItem({ status: "under_maintenance", allowed_actions: ["finish_maintenance"] }),
      },
      "DELETE /items/1/maintenance": { body: makeItem() },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "End maintenance" }));

    expect(await screen.findByRole("status")).toHaveTextContent("The item is available again.");
    expect(api.callsTo("DELETE /items/1/maintenance")).toHaveLength(1);
  });
});

describe("item detail: when something goes wrong", () => {
  it("shows a 409, and fetches the item again because it has changed", async () => {
    let expired = false;
    const reserved = makeItem({
      status: "reserved",
      current_loan: reservedLoan,
      allowed_actions: ["check_out", "cancel_reservation", "start_maintenance"],
    });
    const api = mockApi({
      "GET /items/1": () => ({ body: expired ? makeItem() : reserved }),
      "POST /items/1/check-out": () => {
        expired = true; // the hold ran out while the page was open
        return apiError(409, "reservation_expired", "The reservation on item 1 has expired");
      },
    });
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "Check out" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("That can't be done right now");
    expect(alert).toHaveTextContent("The reservation on item 1 has expired");
    expect(await screen.findByText("Available now")).toBeInTheDocument();
    expect(api.callsTo("GET /items/1")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Check out" })).not.toBeInTheDocument();
  });

  it("shows a 404 for an item that does not exist, with a way back", async () => {
    mockApi({ "GET /items/99": apiError(404, "not_found", "Item 99 not found") });

    renderApp("/items/99");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Not found");
    expect(alert).toHaveTextContent("Item 99 not found");
    expect(screen.getByRole("link", { name: "Back to all items" })).toHaveAttribute(
      "href",
      "/items",
    );
  });

  it("does not ask the server about an id that cannot be valid", async () => {
    const api = mockApi({});

    renderApp("/items/abc");

    expect(await screen.findByRole("heading", { name: "Item not found" })).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
  });

  it("shows a network failure during an action without crashing", async () => {
    let first = true;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if ((init?.method ?? "GET") === "GET" && first) {
          first = false;
          return new Response(
            JSON.stringify(
              makeItem({
                status: "checked_out",
                current_loan: checkedOutLoan,
                allowed_actions: ["return"],
              }),
            ),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if ((init?.method ?? "GET") === "GET") {
          return new Response(JSON.stringify(makeItem({ allowed_actions: ["return"] })), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new TypeError(`Failed to fetch ${String(input)}`);
      }),
    );
    const { user } = renderApp("/items/1");

    await user.click(await screen.findByRole("button", { name: "Return" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach the server");
  });
});

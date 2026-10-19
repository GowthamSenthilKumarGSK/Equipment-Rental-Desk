import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  apiError,
  makeLoan,
  makeMember,
  makeStatement,
  makeStatementLoan,
  mockApi,
  renderApp,
} from "../test/helpers";
import type { Statement } from "../types";

const overdueRow = makeStatementLoan({
  loan: makeLoan({
    id: 11,
    item_id: 3,
    status: "checked_out",
    expires_at: null,
    checked_out_at: "2026-09-24T10:00:00Z",
    due_at: "2026-10-01T10:00:00Z",
  }),
  item_name: "Pressure Washer",
  status: "checked_out",
  is_overdue: true,
  days_overdue: 17,
});
const reservedRow = makeStatementLoan({
  loan: makeLoan({ id: 12, item_id: 4, expires_at: "2026-10-14T10:00:00Z" }),
  item_name: "Step Ladder",
  status: "reserved",
});
const returnedRow = makeStatementLoan({
  loan: makeLoan({
    id: 13,
    item_id: 5,
    status: "returned",
    expires_at: null,
    returned_at: "2026-09-10T10:00:00Z",
    fee_charged_paise: 8000,
  }),
  item_name: "Wet/Dry Vacuum",
  status: "returned",
});
const expiredRow = makeStatementLoan({
  loan: makeLoan({ id: 14, item_id: 6 }),
  item_name: "Tile Cutter",
  status: "expired",
});

const blocked: Statement = makeStatement({
  balance_paise: 12_000,
  total_fees_paise: 13_000,
  total_payments_paise: 1000,
  active_loan_count: 2,
  block_reasons: ["unpaid_fees", "long_overdue"],
  loans: [overdueRow, reservedRow, returnedRow, expiredRow],
  payments: [
    { id: 1, member_id: 5, amount_paise: 1000, paid_at: "2026-10-05T10:00:00Z", note: "Cash" },
  ],
});

describe("member page", () => {
  it("explains clearly why a blocked member cannot borrow", async () => {
    mockApi({ "GET /members/5/statement": { body: blocked } });

    renderApp("/members/5");

    const why = await screen.findByRole("region", { name: "Why this member can't borrow" });
    expect(
      within(why)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual([
      "Their unpaid fees are over the limit. Record a payment to clear it.",
      "A loan is overdue by too long. It has to be returned first.",
    ]);
  });

  it("points each blocking reason to the place on the page where it is dealt with", async () => {
    mockApi({ "GET /members/5/statement": { body: blocked } });

    renderApp("/members/5");

    const why = await screen.findByRole("region", { name: "Why this member can't borrow" });
    expect(within(why).getByRole("link", { name: "Go to payments" })).toHaveAttribute(
      "href",
      "#payments-heading",
    );
    expect(within(why).getByRole("link", { name: "See the overdue loan" })).toHaveAttribute(
      "href",
      "#active-heading",
    );
    expect(screen.getByRole("heading", { name: "Payments" })).toHaveAttribute(
      "id",
      "payments-heading",
    );
  });

  it("shows the account figures as a labelled summary, with the overdue row marked", async () => {
    mockApi({ "GET /members/5/statement": { body: blocked } });

    renderApp("/members/5");

    const summary = await screen.findByRole("list", { name: "Account summary" });
    expect(within(summary).getAllByRole("listitem")).toHaveLength(4);
    expect(within(summary).getByText("Owed by the member")).toBeInTheDocument();
    const active = screen.getByRole("table", { name: "Reserved and checked-out items" });
    const overdueRow = within(active).getByRole("link", { name: "Pressure Washer" }).closest("tr");
    expect(overdueRow).toHaveClass("is-urgent");
  });

  it("says a member in good standing can borrow", async () => {
    mockApi({ "GET /members/5/statement": { body: makeStatement() } });

    renderApp("/members/5");

    expect(await screen.findByText("Can borrow.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /can't borrow/ })).not.toBeInTheDocument();
  });

  it("does not say 'Can borrow' for a member who is at the loan limit", async () => {
    mockApi({
      "GET /members/5/statement": {
        body: makeStatement({ active_loan_count: 3, at_loan_limit: true }),
      },
    });

    renderApp("/members/5");

    const status = await screen.findByText("At the loan limit.");
    expect(status.closest("[role=status]")).toHaveTextContent("They hold 3 active loans");
    expect(status.closest("[role=status]")).toHaveTextContent("still check out items");
    expect(screen.queryByText("Can borrow.")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /can't borrow/ })).not.toBeInTheDocument();
  });

  it("says a member one place below the limit can borrow", async () => {
    mockApi({
      "GET /members/5/statement": {
        body: makeStatement({ active_loan_count: 2, at_loan_limit: false }),
      },
    });

    renderApp("/members/5");

    expect(await screen.findByText("Can borrow.")).toBeInTheDocument();
    expect(screen.queryByText("At the loan limit.")).not.toBeInTheDocument();
  });

  it("lists the loan limit alongside other reasons when both apply", async () => {
    mockApi({
      "GET /members/5/statement": {
        body: makeStatement({
          active_loan_count: 3,
          at_loan_limit: true,
          block_reasons: ["suspended"],
        }),
      },
    });

    renderApp("/members/5");

    const why = await screen.findByRole("region", { name: "Why this member can't borrow" });
    expect(within(why).getByText("The member is suspended.")).toBeInTheDocument();
    expect(within(why).getByText(/They hold 3 active loans/)).toBeInTheDocument();
  });

  it("shows the balance, active loans, history and payments", async () => {
    mockApi({ "GET /members/5/statement": { body: blocked } });

    renderApp("/members/5");

    await screen.findByRole("heading", { level: 1, name: "Kavita Iyer" });
    expect(screen.getByText("₹120.00")).toBeInTheDocument(); // balance
    expect(screen.getByText("₹130.00")).toBeInTheDocument(); // fees so far

    const active = screen.getByRole("table", { name: "Reserved and checked-out items" });
    expect(within(active).getByRole("link", { name: "Pressure Washer" })).toHaveAttribute(
      "href",
      "/items/3",
    );
    expect(within(active).getByText("Overdue")).toBeInTheDocument();
    expect(within(active).getByText("17 days")).toBeInTheDocument();
    expect(within(active).getByText(/Hold ends 14 Oct 2026/)).toBeInTheDocument();
    expect(within(active).queryByText("Wet/Dry Vacuum")).not.toBeInTheDocument();

    const history = screen.getByRole("table", { name: "Returned, cancelled and expired loans" });
    expect(within(history).getByText("Wet/Dry Vacuum")).toBeInTheDocument();
    expect(within(history).getByText("₹80.00")).toBeInTheDocument(); // late fee charged
    expect(within(history).getByText("Expired")).toBeInTheDocument(); // a lapsed reservation
    expect(within(history).getByText(/hold ran out/)).toBeInTheDocument();

    const payments = screen.getByRole("table", { name: "Payments received" });
    expect(within(payments).getByText("Cash")).toBeInTheDocument();
    expect(within(payments).getByText("₹10.00")).toBeInTheDocument();
  });

  it("shows friendly empty states for a new member", async () => {
    mockApi({ "GET /members/5/statement": { body: makeStatement() } });

    renderApp("/members/5");

    expect(await screen.findByText("No active loans.")).toBeInTheDocument();
    expect(screen.getByText("No past loans.")).toBeInTheDocument();
    expect(screen.getByText("No payments yet.")).toBeInTheDocument();
  });

  it("shows a suspended member as suspended and offers to lift it", async () => {
    mockApi({
      "GET /members/5/statement": {
        body: makeStatement({
          member: makeMember({ status: "suspended" }),
          block_reasons: ["suspended"],
        }),
      },
    });

    renderApp("/members/5");

    expect(await screen.findByRole("button", { name: "Lift suspension" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suspend member" })).not.toBeInTheDocument();
    expect(screen.getByText("The member is suspended.")).toBeInTheDocument();
  });

  it("shows a 404 and a way back for a member that does not exist", async () => {
    mockApi({ "GET /members/99/statement": apiError(404, "not_found", "Member 99 not found") });

    renderApp("/members/99");

    expect(await screen.findByRole("alert")).toHaveTextContent("Member 99 not found");
    expect(screen.getByRole("link", { name: "Back to all members" })).toBeInTheDocument();
  });

  it("does not ask the server about an id that cannot be valid", async () => {
    const api = mockApi({});

    renderApp("/members/0");

    expect(await screen.findByRole("heading", { name: "Member not found" })).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
  });
});

describe("recording a payment", () => {
  const owing = makeStatement({ balance_paise: 12_000, total_fees_paise: 12_000 });

  function paymentForm() {
    return within(screen.getByRole("form", { name: "Record a payment" }));
  }

  it.each([
    ["", "Enter the amount in rupees"],
    ["abc", "Enter the amount in rupees"],
    ["12.345", "Enter the amount in rupees"],
    ["-5", "Enter the amount in rupees"],
    ["0", "The amount must be more than zero."],
    ["0.00", "The amount must be more than zero."],
  ])("refuses %j on the page without calling the server", async (typed, message) => {
    const api = mockApi({ "GET /members/5/statement": { body: owing } });
    const { user } = renderApp("/members/5");
    await screen.findByRole("form", { name: "Record a payment" });

    if (typed) await user.type(paymentForm().getByLabelText("Amount (₹)"), typed);
    await user.click(paymentForm().getByRole("button", { name: "Record payment" }));

    expect(paymentForm().getByText(new RegExp(message))).toBeInTheDocument();
    expect(api.callsTo("POST /members/5/payments")).toHaveLength(0);
  });

  it("sends whole paise and shows the new balance", async () => {
    let statement = owing;
    const api = mockApi({
      "GET /members/5/statement": () => ({ body: statement }),
      "POST /members/5/payments": () => {
        statement = makeStatement({
          balance_paise: 8766,
          total_fees_paise: 12_000,
          total_payments_paise: 3234,
        });
        return {
          status: 201,
          body: {
            id: 2,
            member_id: 5,
            amount_paise: 3234,
            paid_at: "2026-10-12T10:00:00Z",
            note: "UPI",
          },
        };
      },
    });
    const { user } = renderApp("/members/5");
    await screen.findByRole("form", { name: "Record a payment" });
    expect(paymentForm().getByText("Outstanding balance: ₹120.00")).toBeInTheDocument();

    await user.type(paymentForm().getByLabelText("Amount (₹)"), "32.34");
    await user.type(paymentForm().getByLabelText("Note (optional)"), "UPI");
    await user.click(paymentForm().getByRole("button", { name: "Record payment" }));

    expect(await screen.findByText("Recorded a payment of ₹32.34.")).toBeInTheDocument();
    expect(api.callsTo("POST /members/5/payments")[0].body).toEqual({
      amount_paise: 3234,
      note: "UPI",
    });
    expect(await screen.findByText("Outstanding balance: ₹87.66")).toBeInTheDocument();
  });

  it("leaves the note out when it is empty", async () => {
    const api = mockApi({
      "GET /members/5/statement": { body: owing },
      "POST /members/5/payments": {
        status: 201,
        body: {
          id: 2,
          member_id: 5,
          amount_paise: 100,
          paid_at: "2026-10-12T10:00:00Z",
          note: null,
        },
      },
    });
    const { user } = renderApp("/members/5");
    await screen.findByRole("form", { name: "Record a payment" });

    await user.type(paymentForm().getByLabelText("Amount (₹)"), "1");
    await user.click(paymentForm().getByRole("button", { name: "Record payment" }));

    await screen.findByText("Recorded a payment of ₹1.00.");
    expect(api.callsTo("POST /members/5/payments")[0].body).toEqual({ amount_paise: 100 });
  });

  it("shows the server's refusal of an overpayment and keeps what was typed", async () => {
    mockApi({
      "GET /members/5/statement": { body: owing },
      "POST /members/5/payments": apiError(
        422,
        "payment_exceeds_balance",
        "Payment of ₹120.01 is more than the outstanding balance of ₹120.00",
      ),
    });
    const { user } = renderApp("/members/5");
    await screen.findByRole("form", { name: "Record a payment" });

    await user.type(paymentForm().getByLabelText("Amount (₹)"), "120.01");
    await user.click(paymentForm().getByRole("button", { name: "Record payment" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Please check the amount");
    expect(alert).toHaveTextContent("more than the outstanding balance of ₹120.00");
    expect(paymentForm().getByLabelText("Amount (₹)")).toHaveValue("120.01");
  });

  it("disables recording when nothing is owed, and says why", async () => {
    mockApi({ "GET /members/5/statement": { body: makeStatement() } });

    renderApp("/members/5");

    await screen.findByRole("form", { name: "Record a payment" });
    expect(paymentForm().getByRole("button", { name: "Record payment" })).toBeDisabled();
    expect(
      paymentForm().getByText("Nothing is owed, so there is nothing to pay."),
    ).toBeInTheDocument();
  });
});

describe("suspension", () => {
  it("suspends with a reason and shows the result", async () => {
    let status: "active" | "suspended" = "active";
    const api = mockApi({
      "GET /members/5/statement": () => ({
        body: makeStatement({
          member: makeMember({ status }),
          block_reasons: status === "suspended" ? ["suspended"] : [],
        }),
      }),
      "POST /members/5/suspension": () => {
        status = "suspended";
        return { body: makeMember({ status: "suspended" }) };
      },
    });
    const { user } = renderApp("/members/5");

    await user.type(await screen.findByLabelText("Reason (optional)"), "Damaged a tool");
    await user.click(screen.getByRole("button", { name: "Suspend member" }));
    const dialog = await screen.findByRole("dialog", { name: "Suspend Kavita Iyer?" });
    expect(within(dialog).getByText("Reason: Damaged a tool")).toBeInTheDocument();
    expect(api.callsTo("POST /members/5/suspension")).toHaveLength(0); // nothing sent yet
    await user.click(within(dialog).getByRole("button", { name: "Yes, suspend member" }));

    expect(await screen.findByText("Kavita Iyer is now suspended.")).toBeInTheDocument();
    expect(api.callsTo("POST /members/5/suspension")[0].body).toEqual({ reason: "Damaged a tool" });
    expect(await screen.findByRole("button", { name: "Lift suspension" })).toBeInTheDocument();
  });

  it("moves focus to the result when the Suspend button is replaced by Lift suspension", async () => {
    let status: "active" | "suspended" = "active";
    mockApi({
      "GET /members/5/statement": () => ({
        body: makeStatement({
          member: makeMember({ status }),
          block_reasons: status === "suspended" ? ["suspended"] : [],
        }),
      }),
      "POST /members/5/suspension": () => {
        status = "suspended";
        return { body: makeMember({ status: "suspended" }) };
      },
    });
    const { user } = renderApp("/members/5");

    await user.click(await screen.findByRole("button", { name: "Suspend member" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Yes, suspend member",
      }),
    );

    expect(await screen.findByRole("button", { name: "Lift suspension" })).toBeInTheDocument();
    const notice = screen.getByText("Kavita Iyer is now suspended.").closest("[role=status]");
    await waitFor(() => expect(notice).toHaveFocus());
  });

  it("suspends without a reason", async () => {
    const api = mockApi({
      "GET /members/5/statement": { body: makeStatement() },
      "POST /members/5/suspension": { body: makeMember({ status: "suspended" }) },
    });
    const { user } = renderApp("/members/5");

    await user.click(await screen.findByRole("button", { name: "Suspend member" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Yes, suspend member",
      }),
    );

    await screen.findByText("Kavita Iyer is now suspended.");
    expect(api.callsTo("POST /members/5/suspension")[0].body).toBeUndefined();
  });

  it("lifts a suspension", async () => {
    const api = mockApi({
      "GET /members/5/statement": {
        body: makeStatement({
          member: makeMember({ status: "suspended" }),
          block_reasons: ["suspended"],
        }),
      },
      "DELETE /members/5/suspension": { body: makeMember() },
    });
    const { user } = renderApp("/members/5");

    await user.click(await screen.findByRole("button", { name: "Lift suspension" }));

    expect(await screen.findByText("Kavita Iyer is active again.")).toBeInTheDocument();
    expect(api.callsTo("DELETE /members/5/suspension")).toHaveLength(1);
  });

  it("shows a 409 when the member was already suspended by someone else", async () => {
    mockApi({
      "GET /members/5/statement": { body: makeStatement() },
      "POST /members/5/suspension": apiError(
        409,
        "invalid_transition",
        "Member 5 is already suspended",
      ),
    });
    const { user } = renderApp("/members/5");

    await user.click(await screen.findByRole("button", { name: "Suspend member" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Yes, suspend member",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Member 5 is already suspended");
  });

  it("does not suspend when the confirmation is declined", async () => {
    const api = mockApi({ "GET /members/5/statement": { body: makeStatement() } });
    const { user } = renderApp("/members/5");

    await user.click(await screen.findByRole("button", { name: "Suspend member" }));
    await user.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Keep active" }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.callsTo("POST /members/5/suspension")).toHaveLength(0);
  });
});

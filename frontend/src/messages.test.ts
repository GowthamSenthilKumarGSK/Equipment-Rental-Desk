import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { availabilityText, parseId } from "./availability";
import { describeError } from "./messages";
import { makeItem, makeLoan } from "./test/helpers";

describe("describeError", () => {
  it("explains a blocked member reason by reason", () => {
    const error = new ApiError(403, "member_blocked", "Member is blocked: suspended", "r1", {
      reasons: ["suspended", "unpaid_fees", "long_overdue"],
    });

    const view = describeError(error);

    expect(view.title).toBe("This member can't borrow right now");
    expect(view.lines).toEqual([
      "The member is suspended.",
      "Their unpaid fees are over the limit. Record a payment to clear it.",
      "A loan is overdue by too long. It has to be returned first.",
    ]);
  });

  it("uses the server's own words for other 403s, 404s and 409s", () => {
    const limit = describeError(
      new ApiError(403, "loan_limit_exceeded", "Member already has 3 active loans (maximum 3)"),
    );
    const missing = describeError(new ApiError(404, "not_found", "Item 9 not found"));
    const conflict = describeError(
      new ApiError(409, "reservation_expired", "The reservation on item 2 has expired"),
    );

    expect([limit.title, limit.message]).toEqual([
      "Not allowed",
      "Member already has 3 active loans (maximum 3)",
    ]);
    expect([missing.title, missing.message]).toEqual(["Not found", "Item 9 not found"]);
    expect([conflict.title, conflict.message]).toEqual([
      "That can't be done right now",
      "The reservation on item 2 has expired",
    ]);
  });

  it("lists field problems for a 422, without the technical prefix", () => {
    const error = new ApiError(422, "validation_error", "The request is invalid", "r2", [
      { field: "body.phone", message: "String should match pattern", type: "string_pattern" },
      { field: "body.replacement_value_paise", message: "Value error, bad", type: "value_error" },
    ]);

    expect(describeError(error).lines).toEqual([
      "Phone: String should match pattern",
      "Replacement value paise: bad",
    ]);
  });

  it("shows a payment that is too large as a plain message", () => {
    const view = describeError(
      new ApiError(422, "payment_exceeds_balance", "Payment of ₹120.01 is more than the balance"),
    );

    expect(view).toMatchObject({
      title: "Please check the amount",
      message: "Payment of ₹120.01 is more than the balance",
      lines: [],
    });
  });

  it("gives a server error a reference and no internals", () => {
    const view = describeError(
      new ApiError(500, "internal_error", "An unexpected error", "abc123"),
    );

    expect(view.title).toBe("Server error");
    expect(view.reference).toBe("abc123");
  });

  it("says when the server cannot be reached", () => {
    expect(describeError(new ApiError(0, "network_error", "Cannot reach the server")).title).toBe(
      "Can't reach the server",
    );
  });
});

describe("availabilityText", () => {
  it.each([
    [makeItem(), "Available now"],
    [
      makeItem({
        status: "reserved",
        current_loan: makeLoan({ expires_at: "2026-10-14T10:00:00Z" }),
      }),
      "Held until 14 Oct 2026, 3:30 pm IST",
    ],
    [
      makeItem({
        status: "checked_out",
        current_loan: makeLoan({ status: "checked_out", due_at: "2026-10-19T10:00:00Z" }),
      }),
      "Out on loan, due 19 Oct 2026, 3:30 pm IST",
    ],
    [
      makeItem({
        status: "overdue",
        current_loan: makeLoan({ status: "checked_out", due_at: "2026-10-01T10:00:00Z" }),
      }),
      "Overdue: was due 1 Oct 2026, 3:30 pm IST",
    ],
    [makeItem({ status: "under_maintenance" }), "Under maintenance, not available"],
    [
      makeItem({
        status: "under_maintenance",
        current_loan: makeLoan({ status: "checked_out", due_at: "2026-10-19T10:00:00Z" }),
      }),
      "Under maintenance, still on loan (due 19 Oct 2026, 3:30 pm IST)",
    ],
  ])("describes %#", (item, expected) => {
    expect(availabilityText(item)).toBe(expected);
  });
});

describe("parseId", () => {
  it.each([
    ["7", 7],
    ["2147483647", 2_147_483_647],
  ])("accepts %s", (segment, expected) => {
    expect(parseId(segment)).toBe(expected);
  });

  it.each([undefined, "", "0", "-1", "01", "abc", "1.5", "2147483648", "99999999999999999999"])(
    "refuses %s",
    (segment) => {
      expect(parseId(segment)).toBeNull();
    },
  );
});

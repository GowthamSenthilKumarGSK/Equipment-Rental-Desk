import { describe, expect, it } from "vitest";
import { formatDate, formatIst, formatRupees, parseRupees, pluralise } from "./format";

describe("formatRupees", () => {
  it.each([
    [0, "₹0.00"],
    [1, "₹0.01"],
    [1000, "₹10.00"],
    [12_345, "₹123.45"],
    [10_001, "₹100.01"],
    [123_456_789, "₹12,34,567.89"], // Indian digit grouping
  ])("shows %i paise as %s", (paise, expected) => {
    expect(formatRupees(paise)).toBe(expected);
  });
});

describe("parseRupees", () => {
  it.each([
    ["0", 0],
    ["12", 1200],
    ["12.5", 1250],
    ["12.50", 1250],
    ["0.05", 5],
    ["100.01", 10_001],
    ["  250  ", 25_000],
    ["1234567.99", 123_456_799],
  ])("reads %j as %i paise", (text, expected) => {
    expect(parseRupees(text)).toBe(expected);
  });

  it.each(["", "abc", "-5", "1,000", "12.345", "1e3", ".5", "12.", "₹5", "99999999", "1 2"])(
    "refuses %j",
    (text) => {
      expect(parseRupees(text)).toBeNull();
    },
  );

  it("never goes through floating point, so 0.1 + 0.2 style errors cannot appear", () => {
    expect(parseRupees("1.15")).toBe(115);
    expect(parseRupees("4.35")).toBe(435);
    expect(parseRupees("8.20")).toBe(820);
  });
});

describe("formatIst", () => {
  it("converts a UTC instant to India time whatever the browser's own zone is", () => {
    expect(formatIst("2026-10-12T10:00:00Z")).toBe("12 Oct 2026, 3:30 pm IST");
  });

  it("rolls the date over when UTC evening is already the next day in India", () => {
    expect(formatIst("2026-10-12T20:00:00Z")).toBe("13 Oct 2026, 1:30 am IST");
  });

  it("shows a dash when there is no time", () => {
    expect(formatIst(null)).toBe("—");
    expect(formatIst(undefined)).toBe("—");
    expect(formatIst("not a date")).toBe("—");
  });
});

describe("formatDate", () => {
  it("shows a calendar date without shifting it by a time zone", () => {
    expect(formatDate("2026-02-09")).toBe("9 Feb 2026");
    expect(formatDate("2026-12-31")).toBe("31 Dec 2026");
  });
});

describe("pluralise", () => {
  it("handles one and many", () => {
    expect(pluralise(1, "day")).toBe("1 day");
    expect(pluralise(0, "day")).toBe("0 days");
    expect(pluralise(17, "day")).toBe("17 days");
  });
});

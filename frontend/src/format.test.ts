import { describe, expect, it } from "vitest";
import {
  bucketLabels,
  formatChange,
  formatCount,
  formatDate,
  formatDateRange,
  formatIst,
  formatItemDays,
  formatPct,
  formatPoints,
  formatRupees,
  parseRupees,
  pluralise,
} from "./format";

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

describe("dashboard formatting", () => {
  it("shows a percentage with its sign-free value and a dash when there is none", () => {
    expect(formatPct(41.1)).toBe("41.1%");
    expect(formatPct(0)).toBe("0%");
    expect(formatPct(100)).toBe("100%");
    expect(formatPct(null)).toBe("—");
    expect(formatPct(undefined)).toBe("—");
  });

  it.each([
    [50, "+50%"],
    [200, "+200%"],
    [-12.5, "−12.5%"], // a real minus sign, not a hyphen
    [0, "no change"],
    [null, "no earlier data"],
  ])("describes a change of %s as %s", (value, expected) => {
    expect(formatChange(value)).toBe(expected);
  });

  it.each([
    [6.4, "+6.4 points"],
    [-0.5, "−0.5 points"],
    [0, "no change"],
    [null, "no earlier data"],
  ])("describes %s percentage points as %s", (value, expected) => {
    expect(formatPoints(value)).toBe(expected);
  });

  it.each([
    [0, "0"],
    [12, "12"],
    [1.5, "1.5"],
    [1.06, "1.06"],
    [0.04, "0.04"],
    [13.29, "13.29"],
  ])("shows %s item-days as %s", (value, expected) => {
    expect(formatItemDays(value)).toBe(expected);
  });

  it("groups counts the Indian way", () => {
    expect(formatCount(950)).toBe("950");
    expect(formatCount(1_234_567)).toBe("12,34,567");
  });

  it("shows a date range, leaving out what both ends share", () => {
    expect(formatDateRange("2026-10-12", "2026-10-12")).toBe("12 Oct 2026");
    expect(formatDateRange("2026-10-06", "2026-10-12")).toBe("6 Oct – 12 Oct 2026");
    expect(formatDateRange("2025-12-30", "2026-01-05")).toBe("30 Dec 2025 – 5 Jan 2026");
  });

  it("labels buckets in full for tables and short for the axis", () => {
    expect(bucketLabels("2026-10-05", "day")).toEqual({ label: "5 Oct 2026", short: "5 Oct" });
    expect(bucketLabels("2026-10-05", "week")).toEqual({
      label: "Week of 5 Oct 2026",
      short: "5 Oct",
    });
  });

  it("keeps money in rupees with two decimals and no floating point", () => {
    expect(formatRupees(1_234_567)).toBe("₹12,345.67");
    expect(formatRupees(37_513)).toBe("₹375.13");
    expect(formatRupees(-2_000)).toBe("-₹20.00");
  });
});

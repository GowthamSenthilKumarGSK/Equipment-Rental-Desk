import { describe, expect, it } from "vitest";
import { formatRupees } from "../format";
import { niceMaxPaise } from "./axis";

// Rupees as the chart prints them: Indian grouping, always exactly two decimals, one point.
const WELL_FORMED = /^₹\d{1,3}(,\d{2,3})*\.\d{2}$/;

function ticks(top: number): string[] {
  return [0, top / 2, top].map(formatRupees);
}

describe("niceMaxPaise", () => {
  it.each([
    [0, 100], // an empty chart is ₹1 high
    [-5, 100],
    [10, 10],
    [11, 20],
    [20, 20],
    [21, 50],
    [50, 50],
    [51, 100],
    [150, 200],
    [999, 1000],
    [50_050, 100_000],
    [123_456, 200_000],
  ])("rounds %i paise up to %i", (paise, expected) => {
    expect(niceMaxPaise(paise)).toBe(expected);
  });

  it.each([1, 3, 4, 5])("never lets a maximum of %i paise put a tick at half a paise", (paise) => {
    const top = niceMaxPaise(paise);

    expect(top).toBe(10);
    expect(Number.isInteger(top / 2)).toBe(true);
    expect(ticks(top)).toEqual(["₹0.00", "₹0.05", "₹0.10"]);
  });

  it("gives every maximum a top that is whole paise, at least the maximum, with a whole-paise middle", () => {
    const problems: string[] = [];
    for (let paise = 1; paise <= 5_000; paise += 1) {
      const top = niceMaxPaise(paise);
      const wellFormed = ticks(top).every((label) => WELL_FORMED.test(label));
      if (!Number.isInteger(top) || top < paise || !Number.isInteger(top / 2) || !wellFormed) {
        problems.push(`${paise} -> ${top}`);
      }
    }

    expect(problems).toEqual([]);
  });

  it("stays tight: the top is never more than 2.5 times the maximum once it is above 10 paise", () => {
    const tooLoose = [];
    for (let paise = 11; paise <= 5_000; paise += 1) {
      if (niceMaxPaise(paise) > paise * 2.5) tooLoose.push(paise);
    }
    expect(tooLoose).toEqual([]);
  });
});

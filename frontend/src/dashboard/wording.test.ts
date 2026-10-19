import { describe, expect, it } from "vitest";
import { collectedAgainstCharged, membersOwe, previousConversionNote } from "./wording";

describe("membersOwe", () => {
  it.each([
    [0, "0 members owe money"],
    [1, "1 member owes money"],
    [2, "2 members owe money"],
    [12, "12 members owe money"],
  ])("says it for %i members", (count, expected) => {
    expect(membersOwe(count)).toBe(expected);
  });
});

describe("collectedAgainstCharged", () => {
  it("explains a missing percentage instead of printing a dash", () => {
    const text = collectedAgainstCharged(null);

    expect(text).toBe(
      "No late fees were charged in this period, so there is nothing to compare collections with",
    );
    expect(text).not.toContain("—");
  });

  it("states the percentage and that it can pass 100%", () => {
    expect(collectedAgainstCharged(50)).toBe(
      "Collections are 50% of the late fees charged in this period (more than 100% when older fees are paid)",
    );
    expect(collectedAgainstCharged(0)).toContain("Collections are 0% of the late fees");
    expect(collectedAgainstCharged(150)).toContain("150%");
  });
});

describe("previousConversionNote", () => {
  it("compares with the previous rate and says the two are not directly comparable", () => {
    expect(previousConversionNote(50)).toBe(
      "50% in the previous period, which has had longer to settle, so the two rates are not directly comparable",
    );
    expect(previousConversionNote(0)).toContain("0% in the previous period");
  });

  it("explains that there is nothing to compare with when the previous rate is missing", () => {
    const text = previousConversionNote(null);

    expect(text).toContain("No rate comparison is available");
    expect(text).toContain("none of the previous period's reservations has been settled");
    expect(text).not.toContain("—");
    expect(text).not.toContain("in the previous period, which");
  });
});

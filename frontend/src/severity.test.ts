import { describe, expect, it } from "vitest";
import { initials } from "./components/Avatar";
import { severityOf } from "./severity";

describe("severityOf", () => {
  it.each([
    [1, 0, "Just late", ""],
    [2, 0, "Just late", ""],
    [3, 1, "3–6 days late", "is-watch"],
    [6, 1, "3–6 days late", "is-watch"],
    [7, 2, "1–2 weeks late", "is-serious"],
    [13, 2, "1–2 weeks late", "is-serious"],
    [14, 3, "Over 2 weeks late", "is-urgent"],
    [90, 3, "Over 2 weeks late", "is-urgent"],
  ])("%i days late is level %i (%s)", (days, level, label, rowClass) => {
    expect(severityOf(days)).toEqual({ level, label, rowClass });
  });

  it("never gets less urgent as a loan gets later", () => {
    const levels = Array.from({ length: 60 }, (_, day) => severityOf(day + 1).level);
    expect([...levels].sort((a, b) => a - b)).toEqual(levels);
  });
});

describe("initials", () => {
  it.each([
    ["Kavita Iyer", "KI"],
    ["Meera", "ME"],
    ["  asha   devi  rao ", "AR"],
    ["", "?"],
  ])("%j gives %s", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});

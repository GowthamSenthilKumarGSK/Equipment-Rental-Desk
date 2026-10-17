import { describe, expect, it } from "vitest";
import { isPastEnd, lastOffset } from "./paging";

describe("isPastEnd", () => {
  it.each([
    [0, 0, false], // an empty list is not "past the end": it is empty
    [0, 24, false],
    [40, 0, false],
    [40, 36, false],
    [40, 39, false],
    [40, 40, true], // the first offset with nothing in it
    [40, 1188, true],
  ])("total %i, offset %i -> %s", (total, offset, expected) => {
    expect(isPastEnd(total, offset)).toBe(expected);
  });
});

describe("lastOffset", () => {
  it.each([
    [0, 12, 0],
    [1, 12, 0],
    [12, 12, 0],
    [13, 12, 12],
    [24, 12, 12], // an exact multiple: the last page is the second, not a third
    [25, 12, 24],
    [40, 12, 36],
  ])("total %i with pages of %i starts the last page at %i", (total, limit, expected) => {
    expect(lastOffset(total, limit)).toBe(expected);
  });
});

import { describe, expect, it } from "vitest";
import css from "./styles.css?raw"; // the stylesheet as plain text (see css.include in vite.config.ts)

/** The body of the first rule whose selector is exactly `selector`. */
function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`(?:^|[}/])\\s*${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match) throw new Error(`no rule for ${selector}`);
  return match[1];
}

// jsdom does not lay anything out, so these guard the rules themselves. The real check is to open
// every page at 320, 360 and 375 pixels wide: the page must not scroll sideways.
describe("layout on a narrow screen", () => {
  it("keeps the navigation off the page until the menu is opened", () => {
    const closed = ruleBody(".sidebar");
    expect(closed).toMatch(/position:\s*fixed/);
    expect(closed).toMatch(/visibility:\s*hidden/);
    expect(ruleBody(".sidebar--open")).toMatch(/visibility:\s*visible/);
  });

  it("lets the content column shrink so a wide table or chart cannot widen the page", () => {
    expect(ruleBody(".shell__main")).toMatch(/min-width:\s*0/);
    expect(ruleBody(".page")).toMatch(/width:\s*100%/);
  });

  it("scrolls wide tables and charts inside their own box", () => {
    expect(ruleBody(".table-wrap")).toMatch(/overflow-x:\s*auto/);
    expect(ruleBody(".chart__scroll")).toMatch(/overflow-x:\s*auto/);
  });

  it("lets the page header and the pager wrap instead of overflowing", () => {
    expect(ruleBody(".page-header")).toMatch(/flex-wrap:\s*wrap/);
    expect(ruleBody(".pager")).toMatch(/flex-wrap:\s*wrap/);
  });
});

describe("focus and motion", () => {
  it("shows a visible focus ring on every focusable element", () => {
    expect(ruleBody(":focus-visible")).toMatch(/outline:\s*3px solid/);
  });

  it("stops the skeleton shimmer for people who ask for reduced motion", () => {
    expect(css).toMatch(
      /prefers-reduced-motion: reduce\)\s*\{\s*\.skeleton\s*\{\s*animation:\s*none/,
    );
  });
});

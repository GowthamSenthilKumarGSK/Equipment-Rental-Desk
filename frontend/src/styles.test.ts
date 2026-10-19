import { describe, expect, it } from "vitest";
import css from "./styles.css?raw"; // the stylesheet as plain text (see css.include in vite.config.ts)

/** The body of the first rule whose selector is exactly `selector`. */
function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`(?:^|\\})\\s*${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match) throw new Error(`no rule for ${selector}`);
  return match[1];
}

describe("header layout on a narrow screen", () => {
  // jsdom does not lay anything out, so this guards the rule itself. The real check is to open any
  // page at 320, 360 and 375 pixels wide: the page must not scroll sideways.
  it("lets the main navigation wrap onto a second line instead of widening the page", () => {
    const nav = ruleBody(".site-header nav");

    expect(nav).toMatch(/display:\s*flex/);
    expect(nav).toMatch(/flex-wrap:\s*wrap/);
  });

  it("lets the header row itself wrap too", () => {
    expect(ruleBody(".site-header__inner")).toMatch(/flex-wrap:\s*wrap/);
  });
});

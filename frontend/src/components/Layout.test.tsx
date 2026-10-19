import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { mockApi, page, renderApp } from "../test/helpers";

describe("application shell", () => {
  it("has one main navigation with the current page marked, and a menu button for small screens", async () => {
    mockApi({ "GET /members": { body: page([]) } });

    renderApp("/members");

    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Members" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Items" })).not.toHaveAttribute("aria-current");
    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveAttribute("aria-controls", "sidebar");
  });

  it("opens the menu, closes it with Escape and puts focus back on the menu button", async () => {
    mockApi({ "GET /members": { body: page([]) } });
    const { user } = renderApp("/members");
    const menu = await screen.findByRole("button", { name: "Menu" });

    await user.click(menu);

    expect(menu).toHaveAttribute("aria-expanded", "true");
    expect(document.getElementById("sidebar")).toHaveClass("sidebar--open");
    expect(
      within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Items" }),
    ).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("sidebar")).not.toHaveClass("sidebar--open");
    expect(menu).toHaveFocus();
  });

  it("blocks the page behind the open menu, so Tab cannot wander off into it", async () => {
    mockApi({ "GET /members": { body: page([]) } });
    const { user } = renderApp("/members");
    const menu = await screen.findByRole("button", { name: "Menu" });
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");

    await user.click(menu);

    expect(screen.getByRole("main", { hidden: true })).toHaveAttribute("inert");
    await user.keyboard("{Escape}");
    expect(screen.getByRole("main")).not.toHaveAttribute("inert");
  });

  it("closes the menu when a page is chosen, and with the close button", async () => {
    mockApi({
      "GET /members": { body: page([]) },
      "GET /loans/overdue": { body: page([], 0, 20) },
    });
    const { user } = renderApp("/members");
    const menu = await screen.findByRole("button", { name: "Menu" });

    await user.click(menu);
    await user.click(
      within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", {
        name: "Overdue",
      }),
    );

    expect(
      await screen.findByRole("heading", { level: 1, name: "Overdue loans" }),
    ).toBeInTheDocument();
    expect(document.getElementById("sidebar")).not.toHaveClass("sidebar--open");

    await user.click(menu);
    await user.click(screen.getByRole("button", { name: "Close menu" }));
    expect(document.getElementById("sidebar")).not.toHaveClass("sidebar--open");
  });

  it("gives every page one level-one heading, so the page header is consistent", async () => {
    mockApi({ "GET /members": { body: page([]) } });

    renderApp("/members");

    expect(await screen.findAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});

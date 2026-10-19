import { cleanup, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  emptyDemand,
  emptyMaintenance,
  emptyOverdueAging,
  emptyPayments,
  emptySummary,
  emptyUtilization,
  makeDemand,
  makeMaintenance,
  makeOverdueAging,
  makePayments,
  makeSummary,
  makeUtilization,
} from "../test/analytics";
import { apiError, mockApi, renderApp } from "../test/helpers";

const FILLED = {
  "GET /analytics/summary": { body: makeSummary() },
  "GET /analytics/utilization": { body: makeUtilization() },
  "GET /analytics/demand": { body: makeDemand() },
  "GET /analytics/overdue-aging": { body: makeOverdueAging() },
  "GET /analytics/payments": { body: makePayments() },
  "GET /analytics/maintenance": { body: makeMaintenance() },
};

const EMPTY = {
  "GET /analytics/summary": { body: emptySummary() },
  "GET /analytics/utilization": { body: emptyUtilization() },
  "GET /analytics/demand": { body: emptyDemand() },
  "GET /analytics/overdue-aging": { body: emptyOverdueAging() },
  "GET /analytics/payments": { body: emptyPayments() },
  "GET /analytics/maintenance": { body: emptyMaintenance() },
};

async function region(name: string) {
  return await screen.findByRole("region", { name });
}

describe("dashboard: what it shows", () => {
  it("has a section for each of the six reports", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    for (const name of [
      "Summary",
      "Utilization",
      "Demand",
      "Overdue loans",
      "Payments",
      "Maintenance snapshot",
    ]) {
      expect(await region(name)).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
  });

  it("offers the sections in a jump list", async () => {
    mockApi(FILLED);
    renderApp("/dashboard?days=7");
    await region("Summary");

    const jump = screen.getByRole("navigation", { name: "Dashboard sections" });
    expect(
      within(jump)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Summary", "Utilization", "Demand", "Overdue", "Payments", "Maintenance"]);
  });

  it("shows the headline numbers in rupees and percentages", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const summary = await region("Summary");
    expect(within(summary).getByText("₹12,345.67")).toBeInTheDocument(); // fees outstanding
    expect(within(summary).getByText("₹1,500.50")).toBeInTheDocument(); // payments collected
    expect(within(summary).getByText("₹4,000.00")).toBeInTheDocument(); // late fees charged
    expect(within(summary).getByText("66.7%")).toBeInTheDocument(); // late returns
    expect(within(summary).getByText(/₹20\.00 paid ahead/)).toBeInTheDocument();
    expect(within(summary).getByText("200 before · +200%".replace("200", "2"))).toBeInTheDocument();
    expect(within(summary).getByText("4 before · −25%")).toBeInTheDocument();
    expect(within(summary).getByText("₹5,000.00 before · −70%")).toBeInTheDocument();
    expect(within(summary).getByText(/8 items|^8$/)).toBeTruthy();
  });

  it("explains why overdue items and overdue loans can differ", async () => {
    mockApi(FILLED);
    renderApp("/dashboard?days=7");

    const summary = await region("Summary");

    expect(
      within(summary).getByText(/Overdue items \(1\) and overdue loans \(3\) differ/),
    ).toBeInTheDocument();
  });

  it("says nothing about overdue items versus loans when the two counts agree", async () => {
    const summary = makeSummary();
    mockApi({
      ...FILLED,
      "GET /analytics/summary": {
        body: { ...summary, loans: { ...summary.loans, overdue: summary.fleet.overdue } },
      },
    });
    renderApp("/dashboard?days=7");

    const region = await screen.findByRole("region", { name: "Summary" });

    expect(await within(region).findByText("Active loans")).toBeInTheDocument();
    expect(within(region).queryByText(/overdue loans \(\d+\) differ/)).toBeNull();
  });

  it("shows utilization with its comparison and category breakdown", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const utilization = await region("Utilization");
    expect(within(utilization).getByText("41.1%")).toBeInTheDocument();
    expect(within(utilization).getByText("34.7%")).toBeInTheDocument();
    expect(within(utilization).getByText(/\+6\.4 points/)).toBeInTheDocument();
    const categories = within(utilization).getByRole("list", { name: "Utilization by category" });
    expect(within(categories).getByText("Power Tools")).toBeInTheDocument();
    expect(within(categories).getByText("19.4%")).toBeInTheDocument();
    expect(within(categories).getByText(/3 items · 0\.38 of 1\.94 item-days/)).toBeInTheDocument();
  });

  it("shows the demand funnel, categories and the most reserved items", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const demand = await region("Demand");
    const funnel = within(demand).getByRole("list", { name: "Reservation funnel" });
    expect(within(funnel).getAllByRole("listitem")).toHaveLength(6);
    expect(within(funnel).getByText("Hold ran out")).toBeInTheDocument();
    expect(within(demand).getByText("40%")).toBeInTheDocument(); // conversion
    expect(within(demand).getByText(/50% in the previous period/)).toBeInTheDocument();
    const categories = within(demand).getByRole("table", {
      name: "Reservations by category in this period",
    });
    expect(
      within(categories).getByRole("row", { name: /Power Tools 2 4 66\.7% 2 2/ }),
    ).toBeTruthy();
    expect(within(demand).getByRole("link", { name: "Cordless Drill" })).toHaveAttribute(
      "href",
      "/items/11",
    );
    expect(within(demand).getByText("Checked out", { selector: ".badge" })).toBeInTheDocument();
    expect(within(demand).getByText("Available", { selector: ".badge" })).toBeInTheDocument();
  });

  it("says '1 member owes money' for one member and '2 members owe money' for two", async () => {
    const summary = makeSummary();
    const withBalance = (count: number) => ({
      "GET /analytics/summary": {
        body: { ...summary, receivables: { ...summary.receivables, members_with_balance: count } },
      },
    });
    mockApi({ ...FILLED, ...withBalance(1) });
    renderApp("/dashboard?days=7");
    expect(await within(await region("Summary")).findByText(/1 member owes money/)).toBeTruthy();
    cleanup();

    mockApi({ ...FILLED, ...withBalance(2) });
    renderApp("/dashboard?days=7");
    expect(await within(await region("Summary")).findByText(/2 members owe money/)).toBeTruthy();
  });

  it("shows overdue aging in rupees with links to the members", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const overdue = await region("Overdue loans");
    expect(within(overdue).getByText("₹870.00")).toBeInTheDocument();
    expect(within(overdue).getByText(/oldest 30 days overdue/)).toBeInTheDocument();
    const bands = within(overdue).getByRole("list", { name: "Overdue loans by age" });
    expect(within(bands).getByText("15+ days")).toBeInTheDocument();
    expect(within(bands).getByText("3 loans")).toBeInTheDocument();
    expect(within(bands).getByText("fees if returned now ₹500.00")).toBeInTheDocument();
    expect(within(overdue).getByRole("link", { name: "Meera Kulkarni" })).toHaveAttribute(
      "href",
      "/members/4",
    );
    expect(within(overdue).getByText("₹350.00")).toBeInTheDocument();
    expect(within(overdue).getByText(/an estimate: a fee is only charged/)).toBeInTheDocument();
  });

  it("shows payments, the ledger and the largest balances", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const payments = await region("Payments");
    expect(within(payments).getByText("₹1,500.50")).toBeInTheDocument();
    expect(within(payments).getByText("₹375.13")).toBeInTheDocument(); // average payment
    expect(within(payments).getByText("₹48,500.00")).toBeInTheDocument(); // fees to date
    expect(within(payments).getByText("₹36,154.33")).toBeInTheDocument(); // payments to date
    expect(within(payments).getAllByText("₹12,345.67").length).toBeGreaterThan(0);
    expect(within(payments).getByText("₹10,000.00")).toBeInTheDocument(); // largest balance
    expect(within(payments).getByRole("link", { name: "Meera Kulkarni" })).toHaveAttribute(
      "href",
      "/members/4",
    );
  });

  it("compares collections with the period's late fees in words, with or without fees", async () => {
    mockApi(FILLED);
    renderApp("/dashboard?days=7");
    expect(
      await within(await region("Payments")).findByText(
        /Collections are 50% of the late fees charged in this period/,
      ),
    ).toBeInTheDocument();
    cleanup();

    mockApi({ ...FILLED, "GET /analytics/payments": { body: emptyPayments() } });
    renderApp("/dashboard?days=7");
    const payments = await region("Payments");
    expect(
      await within(payments).findByText(/No late fees were charged in this period/),
    ).toBeInTheDocument();
    expect(payments).not.toHaveTextContent("— collected");
  });

  it.each([1, 3, 4, 5])(
    "labels the payments chart in well-formed rupees when the biggest payment is %i paise",
    async (paise) => {
      const base = makePayments();
      const series = base.series.map((slot, index) => ({
        ...slot,
        collected_paise: index === 0 ? paise : 0,
        count: index === 0 ? 1 : 0,
      }));
      mockApi({ ...FILLED, "GET /analytics/payments": { body: { ...base, series } } });

      renderApp("/dashboard?days=7");

      const payments = await region("Payments");
      await within(payments).findByRole("img", { name: /Payments collected by day/ });
      const figure = payments.querySelector("figure.chart") as HTMLElement;
      const labels = [...figure.querySelectorAll("svg text.chart__axis")]
        .map((text) => text.textContent ?? "")
        .filter((text) => text.startsWith("₹"));
      expect(labels).toEqual(["₹0.00", "₹0.05", "₹0.10"]); // 0, half, top
      for (const label of labels) expect(label).toMatch(/^₹\d{1,3}(,\d{2,3})*\.\d{2}$/);
    },
  );

  it("lists what is under maintenance and whether it is still on loan", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const maintenance = await region("Maintenance snapshot");
    expect(within(maintenance).getByRole("link", { name: "Hedge Trimmer" })).toHaveAttribute(
      "href",
      "/items/21",
    );
    expect(within(maintenance).getByText("None: can be brought back")).toBeInTheDocument();
    expect(within(maintenance).getByText("Overdue by 3 days")).toBeInTheDocument();
    expect(within(maintenance).getByText("Chuck jammed")).toBeInTheDocument();
    expect(within(maintenance).getByText("50% of 8 items")).toBeInTheDocument();
    expect(within(maintenance).getByText("1 of them overdue")).toBeInTheDocument();
    expect(within(maintenance).queryByText(/Only the first/)).toBeNull();
  });

  it("says when the maintenance list is cut short", async () => {
    mockApi({
      ...FILLED,
      "GET /analytics/maintenance": { body: makeMaintenance({ items_truncated: true }) },
    });

    renderApp("/dashboard?days=7");

    const maintenance = await region("Maintenance snapshot");
    expect(
      await within(maintenance).findByText(/Only the first 2 of 4 items are listed/),
    ).toBeTruthy();
    expect(
      within(maintenance).getByRole("link", { name: "all items under maintenance" }),
    ).toHaveAttribute("href", "/items?status=under_maintenance");
  });
});

describe("dashboard: periods, partial data and limits", () => {
  it("labels the dates each report covers, that today is unfinished and the comparison point", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const summary = await region("Summary");
    expect(within(summary).getByText("6 Oct – 12 Oct 2026")).toBeInTheDocument();
    const note = within(summary).getByText(/Compared with/);
    expect(note).toHaveTextContent("last 7 days, IST");
    expect(note).toHaveTextContent("today is not over");
    expect(note).toHaveTextContent("12 Oct 2026, 3:30 pm IST");
    // Some Node/ICU versions spell September "Sept", so the month is matched loosely.
    expect(note).toHaveTextContent(/29 Sep\w* – 5 Oct 2026/);
    expect(note).toHaveTextContent("same point (5 Oct 2026, 3:30 pm IST)");
  });

  it("labels the period on every report", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    await region("Summary");
    for (const name of ["Utilization", "Demand", "Overdue loans", "Payments"]) {
      expect(within(await region(name)).getAllByText(/Compared with/).length).toBeGreaterThan(0);
    }
  });

  it("marks the bar for the part-day as partial, in words and in the table", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const utilization = await region("Utilization");
    expect(within(utilization).getByText(/Hatched bars are partial/)).toBeInTheDocument();
    const table = within(utilization).getByRole("table", { name: "Utilization by day" });
    const rows = within(table).getAllByRole("row");
    expect(within(rows[3]).getByText("12 Oct 2026")).toBeInTheDocument();
    expect(within(rows[3]).getByText("Partial")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Yes")).toBeInTheDocument();
  });

  it("gives each chart an accessible name that states its headline", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const utilization = await region("Utilization");
    expect(
      within(utilization).getByRole("img", {
        name: "Utilization by day. Highest 50% in 11 Oct 2026, across 10 Oct – 12 Oct 2026.",
      }),
    ).toBeInTheDocument();
    const payments = await region("Payments");
    expect(
      within(payments).getByRole("img", {
        name: "Payments collected by day. Most collected: ₹1,000.00 in 10 Oct 2026.",
      }),
    ).toBeInTheDocument();
    expect(within(payments).getByText("₹1,000.00 (1 payment)")).toBeInTheDocument();
  });

  it("states that maintenance history is unavailable", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const maintenance = await region("Maintenance snapshot");
    expect(within(maintenance).getByText("A snapshot, not a history")).toBeInTheDocument();
    expect(
      within(maintenance).getByText(/never when maintenance started or ended/),
    ).toBeInTheDocument();
    expect(
      within(maintenance).getByText(/not available and are not estimated/),
    ).toBeInTheDocument();
  });

  it("states the limits of the utilization figure", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const utilization = await region("Utilization");
    expect(
      within(utilization).getByText("What this number can and cannot tell you"),
    ).toBeInTheDocument();
    expect(within(utilization).getByText(/keeps no history of maintenance/)).toBeInTheDocument();
    expect(
      within(utilization).getByText(/including the 1 now under maintenance/),
    ).toBeInTheDocument();
    expect(within(utilization).getByText(/understated/)).toBeInTheDocument();
  });

  it("states what demand cannot know and that the previous rate is not comparable", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    const demand = await region("Demand");
    expect(within(demand).getByText(/unmet demand cannot be measured/)).toBeInTheDocument();
    expect(within(demand).getByText(/not directly comparable/)).toBeInTheDocument();
  });

  it("explains that no rate comparison exists when the previous period has no settled reservations", async () => {
    const demand = makeDemand();
    mockApi({
      ...FILLED,
      "GET /analytics/demand": {
        body: {
          ...demand,
          previous_funnel: { ...demand.previous_funnel, conversion_rate_pct: null },
        },
      },
    });

    renderApp("/dashboard?days=7");

    const section = await region("Demand");
    expect(await within(section).findByText(/No rate comparison is available/)).toBeInTheDocument();
    expect(section).not.toHaveTextContent("— in the previous period");
    expect(within(section).queryByText(/not directly comparable/)).toBeNull();
    expect(within(section).getByText("40%")).toBeInTheDocument(); // the current rate still shows
  });

  it("asks the server for 30 days by day unless told otherwise", async () => {
    const api = mockApi(FILLED);

    renderApp("/dashboard");
    await region("Summary");

    await waitFor(() => expect(api.calls).toHaveLength(6));
    for (const path of ["summary", "demand", "overdue-aging"]) {
      expect(api.callsTo(`GET /analytics/${path}`)[0].query.get("days")).toBe("30");
    }
    for (const path of ["utilization", "payments"]) {
      const query = api.callsTo(`GET /analytics/${path}`)[0].query;
      expect([query.get("days"), query.get("bucket")]).toEqual(["30", "day"]);
    }
    expect(api.callsTo("GET /analytics/maintenance")[0].query.toString()).toBe("");
  });

  it("falls back to 30 days for a period it does not offer", async () => {
    const api = mockApi(FILLED);

    renderApp("/dashboard?days=9999&bucket=month");
    await region("Summary");

    await waitFor(() => expect(api.calls).toHaveLength(6));
    expect(api.callsTo("GET /analytics/summary")[0].query.get("days")).toBe("30");
    expect(api.callsTo("GET /analytics/payments")[0].query.get("bucket")).toBe("day");
  });

  it("loads the reports again when the period or the grouping changes", async () => {
    const api = mockApi(FILLED);
    const { user } = renderApp("/dashboard?days=7");
    await region("Summary");
    await waitFor(() => expect(api.calls).toHaveLength(6));

    await user.selectOptions(screen.getByLabelText("Period"), "90");
    await waitFor(() =>
      expect(api.callsTo("GET /analytics/summary").map((c) => c.query.get("days"))).toEqual([
        "7",
        "90",
      ]),
    );
    await user.selectOptions(screen.getByLabelText("Group charts by"), "week");

    await waitFor(() =>
      expect(
        api
          .callsTo("GET /analytics/utilization")
          .map((c) => [c.query.get("days"), c.query.get("bucket")]),
      ).toEqual([
        ["7", "day"],
        ["90", "day"],
        ["90", "week"],
      ]),
    );
    expect(api.callsTo("GET /analytics/maintenance")).toHaveLength(1); // it has no period
    expect(screen.getByLabelText("Period")).toHaveValue("90");
  });
});

describe("dashboard: loading, errors and empty data", () => {
  it("shows a loading message for each report until it arrives", async () => {
    mockApi(FILLED);

    renderApp("/dashboard?days=7");

    for (const what of [
      "the summary",
      "utilization",
      "demand",
      "overdue loans",
      "payments",
      "maintenance",
    ]) {
      expect(screen.getByText(`Loading ${what}…`)).toBeInTheDocument();
    }
    await region("Summary");
    await waitFor(() => expect(screen.queryByText(/^Loading /)).toBeNull());
  });

  it("shows one report's error and retry without hiding the others", async () => {
    let attempts = 0;
    mockApi({
      ...FILLED,
      "GET /analytics/payments": () => {
        attempts += 1;
        return attempts === 1
          ? apiError(500, "internal_error", "Something broke.")
          : { body: makePayments() };
      },
    });
    const { user } = renderApp("/dashboard?days=7");

    const payments = await region("Payments");
    const alert = await within(payments).findByRole("alert");
    expect(alert).toHaveTextContent("Server error");
    expect(alert).toHaveTextContent("Reference: req-test-1");
    // The other reports are unaffected.
    expect(within(await region("Summary")).getByText("₹12,345.67")).toBeInTheDocument();
    expect(within(await region("Maintenance snapshot")).getByText("Hedge Trimmer")).toBeTruthy();

    await user.click(within(payments).getByRole("button", { name: "Try again" }));

    expect(await within(payments).findByText("₹375.13")).toBeInTheDocument();
    expect(within(payments).queryByRole("alert")).toBeNull();
    expect(attempts).toBe(2);
  });

  it("explains when the server cannot be reached", async () => {
    // No route for the summary: that request fails like a dropped connection.
    mockApi(
      Object.fromEntries(Object.entries(FILLED).filter(([key]) => !key.endsWith("/summary"))),
    );

    renderApp("/dashboard?days=7");

    expect(await within(await region("Summary")).findByRole("alert")).toHaveTextContent(
      "Can't reach the server",
    );
    expect(within(await region("Demand")).getByText("40%")).toBeInTheDocument();
  });

  it("shows empty states and dashes, never NaN or undefined, when there is no data", async () => {
    mockApi(EMPTY);

    renderApp("/dashboard?days=7");

    const summary = await region("Summary");
    expect(await within(summary).findAllByText("0")).not.toHaveLength(0);
    expect(within(summary).getAllByText("—").length).toBeGreaterThan(0);
    expect(within(summary).getAllByText("₹0.00").length).toBeGreaterThan(0);
    expect(within(await region("Utilization")).getByText("There are no items yet.")).toBeTruthy();
    const demand = await region("Demand");
    expect(within(demand).getByText("No reservations were made in this period.")).toBeTruthy();
    expect(within(demand).getByText("No item was reserved in this period.")).toBeTruthy();
    const overdue = await region("Overdue loans");
    expect(within(overdue).getByText("Nothing is overdue.")).toBeInTheDocument();
    expect(within(overdue).getByText("No member has an overdue loan.")).toBeInTheDocument();
    expect(within(overdue).getByText("No loan was returned in this period.")).toBeInTheDocument();
    const payments = await region("Payments");
    expect(within(payments).getByText("No member owes anything.")).toBeInTheDocument();
    expect(
      within(payments).getByRole("img", {
        name: /No payments were collected in this period\./,
      }),
    ).toBeInTheDocument();
    expect(
      within(await region("Maintenance snapshot")).getByText("No item is under maintenance."),
    ).toBeTruthy();
    expect(document.body).not.toHaveTextContent(/NaN|undefined|null|Infinity/);
  });

  it("keeps the disclosures visible even when there is no data", async () => {
    mockApi(EMPTY);

    renderApp("/dashboard?days=7");

    expect(await screen.findByText("A snapshot, not a history")).toBeInTheDocument();
    expect(screen.getByText("What this number can and cannot tell you")).toBeInTheDocument();
    expect(screen.getByText("What counts as demand")).toBeInTheDocument();
  });
});

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarList, ColumnChart, type Bar } from "./charts";

function bar(key: string, value: number | null, partial = false): Bar {
  return {
    key,
    label: `${key} 2026`,
    short: key,
    value,
    valueText: value === null ? "nothing measured yet" : `${value}%`,
    partial,
  };
}

function renderChart(bars: Bar[], max = 100) {
  return render(
    <ColumnChart
      title="Utilization by day"
      summary="Highest 50% on 11 Oct."
      valueHeading="Utilization"
      bars={bars}
      max={max}
      axisText={(value) => `${value}%`}
    />,
  );
}

describe("ColumnChart", () => {
  it("is one labelled image that states its headline", () => {
    renderChart([bar("10 Oct", 25), bar("11 Oct", 50)]);

    expect(
      screen.getByRole("img", { name: "Utilization by day. Highest 50% on 11 Oct." }),
    ).toBeInTheDocument();
  });

  it("draws a bar per measured value and none where nothing was measured", () => {
    const { container } = renderChart([bar("10 Oct", 25), bar("11 Oct", null), bar("12 Oct", 50)]);

    const rects = container.querySelectorAll("rect.chart__bar");
    expect(rects).toHaveLength(2);
    expect(rects[0].querySelector("title")?.textContent).toBe("10 Oct 2026: 25%");
  });

  it("scales bar heights to the top of the chart and never past it", () => {
    const { container } = renderChart([bar("a", 25), bar("b", 50), bar("c", 250)], 50);

    const heights = [...container.querySelectorAll("rect.chart__bar")].map((rect) =>
      Number(rect.getAttribute("height")),
    );
    expect(heights[1]).toBeCloseTo(heights[0] * 2);
    expect(heights[2]).toBeCloseTo(heights[1]); // clipped to the top
  });

  it("hatches a partial bar and says so in words, in the tooltip and in the table", () => {
    const { container } = renderChart([bar("11 Oct", 50), bar("12 Oct", 40, true)]);

    const partial = container.querySelector("rect.chart__bar--partial") as SVGRectElement;
    const reference = /^url\("?#([^":)]+-hatch)"?\)$/.exec(partial.style.fill);
    expect(reference).not.toBeNull();
    expect(container.querySelector(`pattern[id="${reference?.[1]}"]`)).not.toBeNull();
    expect(partial.querySelector("title")?.textContent).toBe("12 Oct 2026: 40% (partial)");
    expect(screen.getByText(/Hatched bars are partial/)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Utilization by day" });
    const rows = within(table).getAllByRole("row");
    expect(within(rows[1]).getByText("Yes")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Partial")).toBeInTheDocument();
  });

  it("says nothing about hatching when no bar is partial", () => {
    renderChart([bar("10 Oct", 25)]);

    expect(screen.queryByText(/Hatched bars/)).toBeNull();
  });

  it("offers every value as a table, with the full labels", () => {
    renderChart([bar("10 Oct", 25), bar("11 Oct", null)]);

    const table = screen.getByRole("table", { name: "Utilization by day" });
    expect(within(table).getByRole("row", { name: "10 Oct 2026 25% Yes" })).toBeTruthy();
    expect(
      within(table).getByRole("row", { name: "11 Oct 2026 nothing measured yet Yes" }),
    ).toBeTruthy();
    expect(screen.getByText("Show the values as a table")).toBeInTheDocument();
  });

  it("labels the axis with the first, middle and last bar and the scale", () => {
    const { container } = renderChart(
      [bar("1 Oct", 1), bar("2 Oct", 2), bar("3 Oct", 3), bar("4 Oct", 4), bar("5 Oct", 5)],
      10,
    );

    const texts = [...container.querySelectorAll("text")].map((text) => text.textContent);
    expect(texts).toEqual(expect.arrayContaining(["0%", "5%", "10%", "1 Oct", "3 Oct", "5 Oct"]));
    expect(texts).not.toContain("2 Oct");
  });

  it("copes with no bars and with a zero maximum", () => {
    const { container } = renderChart([], 0);

    expect(container.querySelectorAll("rect.chart__bar")).toHaveLength(0);
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
});

describe("BarList", () => {
  it("writes every value as text next to its bar", () => {
    render(
      <BarList
        label="Funnel"
        rows={[
          { key: "a", label: "Reserved", value: 6, valueText: "6" },
          { key: "b", label: "Checked out", value: 3, valueText: "3", note: "50% of reserved" },
        ]}
      />,
    );

    const list = screen.getByRole("list", { name: "Funnel" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
    expect(within(list).getByText("Checked out")).toBeInTheDocument();
    expect(within(list).getByText("3")).toBeInTheDocument();
    expect(within(list).getByText("50% of reserved")).toBeInTheDocument();
  });

  it("sizes each bar against the largest value, or a given maximum", () => {
    const { container, rerender } = render(
      <BarList
        label="Funnel"
        rows={[
          { key: "a", label: "A", value: 6, valueText: "6" },
          { key: "b", label: "B", value: 3, valueText: "3" },
        ]}
      />,
    );
    const widths = () =>
      [...container.querySelectorAll<HTMLElement>(".bars__fill")].map((el) => el.style.width);
    expect(widths()).toEqual(["100%", "50%"]);

    rerender(
      <BarList
        label="Funnel"
        max={12}
        rows={[
          { key: "a", label: "A", value: 6, valueText: "6" },
          { key: "b", label: "B", value: 30, valueText: "30" },
        ]}
      />,
    );
    expect(widths()).toEqual(["50%", "100%"]); // never wider than the track
  });

  it("draws empty bars, not broken ones, when every value is zero", () => {
    const { container } = render(
      <BarList label="Funnel" rows={[{ key: "a", label: "A", value: 0, valueText: "0" }]} />,
    );

    expect(container.querySelector<HTMLElement>(".bars__fill")?.style.width).toBe("0%");
  });

  it("keeps the bars out of the accessibility tree", () => {
    const { container } = render(
      <BarList label="Funnel" rows={[{ key: "a", label: "A", value: 1, valueText: "1" }]} />,
    );

    expect(container.querySelector(".bars__track")).toHaveAttribute("aria-hidden", "true");
  });
});

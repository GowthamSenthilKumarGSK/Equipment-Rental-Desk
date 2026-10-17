import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TextField } from "./Field";

describe("TextField errors", () => {
  it("announces an error and ties it to its input", () => {
    render(
      <TextField label="Amount (₹)" error="Enter the amount in rupees." hint="Owed: ₹10.00" />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Enter the amount in rupees.");
    const input = screen.getByLabelText("Amount (₹)");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")?.split(" ")).toEqual([
      alert.id,
      expect.stringContaining("-hint"),
    ]);
  });

  it("has no alert and is not marked invalid when there is no error", () => {
    render(<TextField label="Name" />);

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Name")).not.toHaveAttribute("aria-invalid");
  });
});

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

function setup(props: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(
    <>
      <button type="button">Opener</button>
      <ConfirmDialog
        title="Delete the thing?"
        confirmLabel="Yes, delete"
        onConfirm={onConfirm}
        onCancel={onCancel}
        {...props}
      >
        <p>This cannot be undone.</p>
      </ConfirmDialog>
    </>,
  );
  return { user, onConfirm, onCancel };
}

describe("ConfirmDialog", () => {
  it("is a named, described modal dialog", () => {
    setup();

    const dialog = screen.getByRole("dialog", { name: "Delete the thing?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("This cannot be undone.");
  });

  it("starts on Cancel, so pressing Enter by reflex does not confirm", async () => {
    const { user, onConfirm, onCancel } = setup();

    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("keeps Tab and Shift+Tab inside the dialog", async () => {
    const { user } = setup();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Yes, delete" });

    await user.tab();
    expect(confirm).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus(); // wrapped round, not out to the page behind
    await user.tab({ shift: true });
    expect(confirm).toHaveFocus();
  });

  it("cancels on Escape and on a click outside the box, and confirms only on the button", async () => {
    const { user, onConfirm, onCancel } = setup();

    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);

    await user.pointer({ target: document.querySelector(".dialog-scrim")!, keys: "[MouseLeft]" });
    expect(onCancel).toHaveBeenCalledTimes(2);
    expect(onConfirm).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Yes, delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("uses the danger style for hard-to-undo actions and disables both buttons while busy", () => {
    setup({ danger: true, busy: true });

    expect(screen.getByRole("button", { name: "Yes, delete" })).toHaveClass("button--danger");
    expect(screen.getByRole("button", { name: "Yes, delete" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("locks page scrolling while open and gives focus back when it closes", () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    const { unmount } = render(
      <ConfirmDialog title="Sure?" confirmLabel="Yes" onConfirm={vi.fn()} onCancel={vi.fn()}>
        <p>Body</p>
      </ConfirmDialog>,
    );
    expect(document.body).toHaveClass("modal-open");

    unmount();

    expect(document.body).not.toHaveClass("modal-open");
    expect(opener).toHaveFocus();
    opener.remove();
  });
});

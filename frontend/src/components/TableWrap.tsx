import type { ReactNode } from "react";

/**
 * A table that scrolls sideways inside its own box on a narrow screen instead of widening the page.
 * It is focusable so a keyboard user can scroll it with the arrow keys, and named so a screen
 * reader says what it holds.
 */
export function TableWrap({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

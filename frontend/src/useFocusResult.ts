import { useEffect, useRef } from "react";

/**
 * Keeps keyboard and screen-reader users from being dropped at the top of the page when the button
 * they used disappears (for example "Cancel reservation" once the reservation is gone).
 *
 * Call `expectResult()` when an action starts. Once the page has the result and has finished
 * fetching again (`ready`), focus moves to the result message (`target`) only if focus was lost;
 * a control that still exists keeps it.
 */
export function useFocusResult(ready: boolean) {
  const target = useRef<HTMLDivElement>(null);
  const wanted = useRef(false);

  useEffect(() => {
    if (!wanted.current || !ready) return;
    wanted.current = false;
    const active = document.activeElement;
    const lost = !active || active === document.body || !document.body.contains(active);
    if (lost) target.current?.focus();
  }, [ready]);

  return {
    target,
    expectResult: () => {
      wanted.current = true;
    },
  };
}

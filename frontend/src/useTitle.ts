import { useEffect } from "react";

/** Sets the browser tab title, so each page is distinguishable in history and to screen readers. */
export function useTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Equipment Rental Desk`;
  }, [title]);
}

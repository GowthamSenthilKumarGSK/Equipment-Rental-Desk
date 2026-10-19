import { formatChange, formatCount } from "../format";
import type { Change } from "../types";

/** "3 before · +50%": the previous period's figure (same elapsed time) and the change from it. */
export function versusPrevious(
  change: Change,
  format: (value: number) => string = formatCount,
): string {
  return `${format(change.previous)} before · ${formatChange(change.change_pct)}`;
}

/** True when records exist but the page asked for starts after the last one (a stale link or bookmark). */
export function isPastEnd(total: number, offset: number): boolean {
  return total > 0 && offset >= total;
}

/** Offset of the page that holds the last record. */
export function lastOffset(total: number, limit: number): number {
  return total <= 0 ? 0 : Math.floor((total - 1) / limit) * limit;
}

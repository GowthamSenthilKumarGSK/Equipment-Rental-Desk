import { formatPct } from "../format";

/** "1 member owes money", "2 members owe money": the verb agrees with the count. */
export function membersOwe(count: number): string {
  return count === 1 ? "1 member owes money" : `${count} members owe money`;
}

/**
 * How the period's collections compare with the late fees charged in it. With no fees charged there
 * is nothing to divide by (the API sends null), and that is said instead of showing a bare dash.
 */
export function collectedAgainstCharged(pct: number | null): string {
  return pct === null
    ? "No late fees were charged in this period, so there is nothing to compare collections with"
    : `Collections are ${formatPct(pct)} of the late fees charged in this period (more than 100% when older fees are paid)`;
}

/**
 * The note under the demand conversion rate. The previous period's rate is judged at the same
 * moment as the current one, so it has had longer to settle and the two are not directly
 * comparable. It is null when none of that period's reservations has been settled (checked out,
 * cancelled or expired): there is then no rate to compare with, which is said in words.
 */
export function previousConversionNote(previousPct: number | null): string {
  return previousPct === null
    ? "No rate comparison is available: none of the previous period's reservations has been settled (checked out, cancelled or hold run out), so it has no rate"
    : `${formatPct(previousPct)} in the previous period, which has had longer to settle, so the two rates are not directly comparable`;
}

/**
 * The top of the payments chart, in whole paise: 1, 2 or 5 times a power of ten, never below 10.
 *
 * The chart labels 0, half and the top. Staying at 10 paise or more keeps every one of them a whole
 * number of paise, because each candidate is then a multiple of 10. (A top of 1, 3 or 5 paise would
 * put a tick at half a paise, which cannot be written as rupees.) An empty chart gets ₹1.00.
 */
export function niceMaxPaise(paise: number): number {
  if (paise <= 0) return 100;
  let magnitude = 10; // never smaller: this is what keeps the half-way tick a whole number of paise
  while (magnitude * 10 <= paise) magnitude *= 10; // integer steps, no logarithms
  for (const step of [1, 2, 5]) {
    if (paise <= step * magnitude) return step * magnitude;
  }
  return 10 * magnitude;
}

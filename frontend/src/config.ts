/** Backend base URL, injected at build time. Undefined means the env var was not set. */
export const API_URL: string | undefined = import.meta.env.VITE_API_URL?.replace(/\/$/, "");

/**
 * Whether the reviewer test-clock panel may be shown. Off unless a build explicitly sets
 * VITE_ENABLE_TEST_CLOCK=true, so a normal deployment has no clock control and never sends the
 * X-Test-Clock header. Read on each call (not at import) so tests can switch it.
 */
export function isTestClockEnabled(): boolean {
  return import.meta.env.VITE_ENABLE_TEST_CLOCK === "true";
}

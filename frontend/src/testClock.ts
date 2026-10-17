/**
 * Reviewer test clock. Off by default: it exists only when the build sets VITE_ENABLE_TEST_CLOCK=true
 * (see config.ts), and even then nothing is sent until someone sets a time in the panel. When a time
 * is set, a banner on every page says so, so it can never be active unnoticed. The value lives in
 * sessionStorage, so it ends with the browser tab.
 */
import { useSyncExternalStore } from "react";
import { isTestClockEnabled } from "./config";

const STORAGE_KEY = "rental-desk-test-clock";
const listeners = new Set<() => void>();

function readStored(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null; // storage can be blocked; the clock simply stays off
  }
}

/** The ISO timestamp to send as X-Test-Clock, or null (always null when the feature is off). */
export function getTestClock(): string | null {
  return isTestClockEnabled() ? readStored() : null;
}

export function setTestClock(value: string | null): void {
  try {
    if (value) window.sessionStorage.setItem(STORAGE_KEY, value);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignored: see readStored
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTestClock(): string | null {
  return useSyncExternalStore(subscribe, getTestClock, () => null);
}

/** "2026-10-20T10:30" typed as IST in a datetime-local input -> "2026-10-20T10:30:00+05:30". */
export function istInputToIso(local: string): string | null {
  return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local) ? `${local}:00+05:30` : null;
}

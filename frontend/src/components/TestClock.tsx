import { useState } from "react";
import { isTestClockEnabled } from "../config";
import { formatIst } from "../format";
import { istInputToIso, setTestClock, useTestClock } from "../testClock";
import { TextField } from "./Field";

/** Shown on every page while a test time is set, so the clock can never be active unnoticed. */
export function TestClockBanner() {
  const clock = useTestClock();
  if (!clock) return null;
  return (
    <div className="banner" role="status">
      <p>
        <strong>Test clock is on.</strong> The app is pretending it is {formatIst(clock)}. Anything
        you change is saved with that time.
      </p>
      <button type="button" className="button button--secondary" onClick={() => setTestClock(null)}>
        Go back to real time
      </button>
    </div>
  );
}

/**
 * Reviewer-only control, present only in builds with VITE_ENABLE_TEST_CLOCK=true. It lets someone
 * try expiry and overdue without waiting; it is not part of the normal workflow.
 */
export function TestClockPanel() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  if (!isTestClockEnabled()) return null;

  function apply(event: React.FormEvent) {
    event.preventDefault();
    const iso = istInputToIso(value);
    if (!iso) {
      setError("Choose a date and time.");
      return;
    }
    setError("");
    setTestClock(iso);
  }

  return (
    <details className="test-clock">
      <summary>Reviewer test clock (testing only)</summary>
      <form onSubmit={apply} noValidate>
        <p className="hint">
          Makes every request pretend it is this moment (India time, between the years 2000 and
          2200). Changes you make are saved with that time, so use a scratch database.
        </p>
        <TextField
          label="Pretend it is (IST)"
          type="datetime-local"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          error={error}
        />
        <button type="submit" className="button button--secondary">
          Use this time
        </button>
      </form>
    </details>
  );
}

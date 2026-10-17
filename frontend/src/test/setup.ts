import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// A fake backend URL for tests; the real one comes from .env at build time.
const FAKE_API = "http://api.test";
vi.stubEnv("VITE_API_URL", FAKE_API);

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.stubEnv("VITE_API_URL", FAKE_API);
});

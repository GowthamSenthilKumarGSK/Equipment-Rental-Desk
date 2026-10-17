import { useEffect, useState } from "react";
import { fetchHealth } from "./api";
import { API_URL } from "./config";

type ApiStatus = { state: "loading" } | { state: "ok" } | { state: "error"; message: string };

export default function App() {
  const [status, setStatus] = useState<ApiStatus>({ state: "loading" });

  useEffect(() => {
    fetchHealth()
      .then(() => setStatus({ state: "ok" }))
      .catch((error: unknown) =>
        setStatus({
          state: "error",
          message: error instanceof Error ? error.message : "Unknown error",
        }),
      );
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "1rem", maxWidth: 640 }}>
      <h1>Equipment Rental Desk</h1>
      <p>API: {API_URL ?? "not configured"}</p>
      {status.state === "loading" && <p>Checking API…</p>}
      {status.state === "ok" && <p>API is reachable.</p>}
      {status.state === "error" && <p role="alert">Cannot reach the API: {status.message}</p>}
    </main>
  );
}

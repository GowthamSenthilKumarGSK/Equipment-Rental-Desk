import { API_URL } from "./config";

export interface HealthResponse {
  status: string;
}

export async function fetchHealth(): Promise<HealthResponse> {
  if (!API_URL) {
    throw new Error("VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env.");
  }
  const response = await fetch(`${API_URL}/health`);
  if (!response.ok) {
    throw new Error(`API responded with HTTP ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}

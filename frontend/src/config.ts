/** Backend base URL, injected at build time. Undefined means the env var was not set. */
export const API_URL: string | undefined = import.meta.env.VITE_API_URL?.replace(/\/$/, "");

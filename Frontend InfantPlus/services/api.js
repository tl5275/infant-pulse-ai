const DEFAULT_API_URL = "http://localhost:8000";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");

export function getApiBaseUrl() {
  return API_URL;
}

export function buildApiUrl(path = "") {
  const normalizedPath = path.replace(/^\/+/, "");
  return new URL(normalizedPath, `${API_URL}/`).toString();
}

export function getLiveWebSocketUrl() {
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/live";
  return url.toString();
}

export async function fetchOverview() {
  const response = await fetch(buildApiUrl("overview"));
  if (!response.ok) {
    throw new Error(`Overview request failed with status ${response.status}`);
  }

  return response.json();
}

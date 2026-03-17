const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export function getLiveWebSocketUrl() {
  const url = new URL(API_BASE_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/live";
  return url.toString();
}

export async function fetchOverview() {
  const response = await fetch(`${API_BASE_URL}/overview`);
  if (!response.ok) {
    throw new Error(`Overview request failed with status ${response.status}`);
  }

  return response.json();
}

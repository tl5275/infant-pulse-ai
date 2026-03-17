import { getLiveWebSocketUrl } from "./api";

export function createNICUSocket() {
  return new WebSocket(getLiveWebSocketUrl());
}

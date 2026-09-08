import type { WebSocketEvent } from "../types/domain";

const DEFAULT_WS_BASE =
  window.location.protocol === "https:"
    ? `wss://${window.location.host}`
    : `ws://${window.location.hostname}${window.location.port === "9010" ? ":9000" : `:${window.location.port}`}`;

export const WS_BASE_URL = window.__WS_BASE_URL__ ?? DEFAULT_WS_BASE;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseWebSocketEvent(raw: string): WebSocketEvent | null {
  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed) || typeof parsed.type !== "string" || !("payload" in parsed)) {
    return null;
  }

  switch (parsed.type) {
    case "sensor_reading":
    case "anomaly":
    case "alert":
    case "incident":
    case "timeline":
    case "stats":
      return parsed as WebSocketEvent;
    default:
      return null;
  }
}

export interface DashboardSocket {
  close(): void;
}

export function connectDashboardSocket(
  onEvent: (event: WebSocketEvent) => void,
  onError: (event: Event) => void,
  path = "/ws",
): DashboardSocket {
  const socket = new WebSocket(`${WS_BASE_URL}${path}`);

  socket.addEventListener("message", (event: MessageEvent<string>) => {
    const parsed = parseWebSocketEvent(event.data);
    if (parsed) {
      onEvent(parsed);
    }
  });

  socket.addEventListener("error", onError);

  return {
    close: () => {
      socket.close();
    },
  };
}

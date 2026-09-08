import { parseWebSocketEvent } from "./websocket";

describe("parseWebSocketEvent", () => {
  it("returns typed dashboard events for known event names", () => {
    const event = parseWebSocketEvent(
      JSON.stringify({
        type: "stats",
        payload: {
          system_status: "healthy",
          open_incidents: 0,
          mitigated_incidents: 1,
          active_anomalies: 0,
          mean_confidence: 0.2,
          mttr_minutes_estimate: 65,
        },
      }),
    );

    expect(event?.type).toBe("stats");
  });

  it("drops unknown event names", () => {
    const event = parseWebSocketEvent(JSON.stringify({ type: "unknown", payload: {} }));

    expect(event).toBeNull();
  });
});

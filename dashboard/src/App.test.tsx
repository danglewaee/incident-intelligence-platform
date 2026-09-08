import { render, screen, waitFor } from "@testing-library/react";
import App from "./App";
import type { IncidentApiClient } from "./api/client";
import type { Incident, IncidentDetail, TimelineEvent, TriageStats } from "./types/domain";

const stats: TriageStats = {
  system_status: "degraded",
  open_incidents: 2,
  mitigated_incidents: 1,
  active_anomalies: 4,
  mean_confidence: 0.7,
  mttr_minutes_estimate: 32.4,
};

const incident: Incident = {
  id: 42,
  status: "triaged",
  title: "Payment latency spike",
  service: "payment-service",
  environment: "prod",
  severity: "high",
  severity_score: 8.4,
  probable_root_cause: "db-primary",
  root_cause_hint: null,
  confidence: 0.83,
  started_at: "2026-03-17T10:00:00Z",
  updated_at: "2026-03-17T10:05:00Z",
  linked_events: 9,
};

const detail: IncidentDetail = {
  ...incident,
  recent_event_messages: ["payment-service timeout"],
  root_cause_ranking: [{ service: "db-primary", score: 0.91, confidence: 0.86, evidence: ["timeout"] }],
};

const timeline: TimelineEvent[] = [
  {
    kind: "incident",
    service: "payment-service",
    title: "Incident #42 high",
    score: 0.83,
    timestamp: "2026-03-17T10:05:00Z",
  },
];

function createClient(): IncidentApiClient {
  return {
    getTriageStats: () => Promise.resolve(stats),
    listIncidents: () => Promise.resolve([incident]),
    getIncidentDetail: () => Promise.resolve(detail),
    listTimeline: () => Promise.resolve(timeline),
    listAnomalies: () => Promise.resolve([]),
    listRegressions: () => Promise.resolve([]),
  };
}

describe("App", () => {
  it("renders typed API data into the incident dashboard", async () => {
    render(<App client={createClient()} />);

    await waitFor(() => expect(screen.getByTestId("system-status-text")).toHaveTextContent("DEGRADED"));

    expect(screen.getByText("Payment latency spike")).toBeInTheDocument();
    expect(screen.getAllByText("payment-service")[0]).toBeInTheDocument();
    expect(screen.getByText("32.4")).toBeInTheDocument();
  });
});

import type { Anomaly, Incident, IncidentDetail, Regression, TimelineEvent, TriageStats } from "../types/domain";

const DEFAULT_API_BASE =
  window.location.port === "9000"
    ? window.location.origin
    : window.location.port === "9010"
      ? "/api"
      : "http://127.0.0.1:9000";

export const API_BASE_URL = window.__API_BASE_URL__ ?? DEFAULT_API_BASE;

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    throw new Error(`API request failed: GET ${path} ${String(response.status)}`);
  }

  return (await response.json()) as T;
}

export interface IncidentApiClient {
  getTriageStats: (signal?: AbortSignal) => Promise<TriageStats>;
  listIncidents: (signal?: AbortSignal) => Promise<Incident[]>;
  getIncidentDetail: (incidentId: number, signal?: AbortSignal) => Promise<IncidentDetail>;
  listTimeline: (signal?: AbortSignal) => Promise<TimelineEvent[]>;
  listAnomalies: (signal?: AbortSignal) => Promise<Anomaly[]>;
  listRegressions: (signal?: AbortSignal) => Promise<Regression[]>;
}

export const apiClient: IncidentApiClient = {
  getTriageStats: (signal) => getJson<TriageStats>("/triage/stats", signal),
  listIncidents: (signal) => getJson<Incident[]>("/incidents", signal),
  getIncidentDetail: (incidentId, signal) => getJson<IncidentDetail>(`/incidents/${String(incidentId)}`, signal),
  listTimeline: (signal) => getJson<TimelineEvent[]>("/timeline", signal),
  listAnomalies: (signal) => getJson<Anomaly[]>("/anomalies", signal),
  listRegressions: (signal) => getJson<Regression[]>("/regressions", signal),
};

type UnknownString = string & Record<never, never>;

export type ServiceEnvironment = "prod" | "staging" | "dev" | UnknownString;

export type EventType = "log" | "metric" | "alert" | "deploy";

export type EventLevel = "info" | "warn" | "error" | "critical";

export type IncidentStatus = "new" | "triaged" | "mitigated" | UnknownString;

export type IncidentSeverity = "low" | "medium" | "high" | "critical" | UnknownString;

export type SystemStatus = "healthy" | "degraded" | "critical";

export type TimelineKind = "deploy" | "anomaly" | "incident";

export interface SensorReading {
  timestamp: string;
  service: string;
  environment: ServiceEnvironment;
  metric_name: string;
  metric_value: number;
  latency_ms: number | null;
  level: EventLevel;
  trace_id: string | null;
}

export interface Alert {
  id: number;
  service: string;
  environment: ServiceEnvironment;
  severity: EventLevel;
  message: string;
  timestamp: string;
  incident_id: number | null;
}

export interface RootCauseCandidate {
  service: string;
  score: number;
  confidence: number;
  evidence: string[];
}

export interface Incident {
  id: number;
  status: IncidentStatus;
  title: string;
  service: string;
  environment: ServiceEnvironment;
  severity: IncidentSeverity;
  severity_score: number;
  probable_root_cause: string | null;
  root_cause_hint: string | null;
  confidence: number;
  started_at: string;
  updated_at: string;
  linked_events: number;
}

export interface IncidentDetail extends Incident {
  recent_event_messages: string[];
  root_cause_ranking: RootCauseCandidate[];
}

export interface Regression {
  service: string;
  deploy_tag: string;
  baseline_error_rate: number;
  current_error_rate: number;
  baseline_latency_ms: number;
  current_latency_ms: number;
  score: number;
}

export interface Anomaly {
  service: string;
  metric: string;
  method: string;
  score: number;
  details: string | null;
  created_at: string;
}

export interface TimelineEvent {
  kind: TimelineKind;
  service: string;
  title: string;
  score: number | null;
  timestamp: string;
}

export interface TriageStats {
  system_status: SystemStatus;
  open_incidents: number;
  mitigated_incidents: number;
  active_anomalies: number;
  mean_confidence: number;
  mttr_minutes_estimate: number;
}

export type WebSocketEvent =
  | { type: "sensor_reading"; payload: SensorReading }
  | { type: "anomaly"; payload: Anomaly }
  | { type: "alert"; payload: Alert }
  | { type: "incident"; payload: Incident }
  | { type: "timeline"; payload: TimelineEvent }
  | { type: "stats"; payload: TriageStats };

declare global {
  interface Window {
    __API_BASE_URL__?: string;
    __WS_BASE_URL__?: string;
  }
}

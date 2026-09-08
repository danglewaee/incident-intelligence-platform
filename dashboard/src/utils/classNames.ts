import type { IncidentSeverity, SystemStatus, TimelineKind } from "../types/domain";

export function severityClass(severity: IncidentSeverity): string {
  if (severity === "critical") {
    return "sev-critical";
  }
  if (severity === "high") {
    return "sev-high";
  }
  if (severity === "medium") {
    return "sev-medium";
  }
  return "sev-low";
}

export function statusClass(status: SystemStatus): string {
  if (status === "critical") {
    return "critical";
  }
  if (status === "degraded") {
    return "degraded";
  }
  return "healthy";
}

export function toneClass(kind: TimelineKind): string {
  if (kind === "incident") {
    return "tone-incident";
  }
  if (kind === "deploy") {
    return "tone-deploy";
  }
  return "tone-anomaly";
}

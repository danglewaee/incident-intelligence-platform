from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    timestamp: datetime | None = None
    service: str
    environment: str = "prod"
    event_type: Literal["log", "metric", "alert", "deploy"] = "log"
    level: Literal["info", "warn", "error", "critical"] = "error"
    severity: Literal["info", "warn", "error", "critical"] | None = None
    message: str
    error_code: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    trace_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    deploy_tag: str | None = None
    deployment_id: str | None = None


class EventOut(EventIn):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class IngestAck(BaseModel):
    accepted: bool
    raw_event_id: int
    stream_id: str


class RootCauseCandidate(BaseModel):
    service: str
    score: float
    confidence: float
    evidence: list[str]


class IncidentOut(BaseModel):
    id: int
    status: str
    title: str
    service: str
    environment: str
    severity: str
    severity_score: float
    probable_root_cause: str | None = None
    root_cause_hint: str | None = None
    confidence: float
    started_at: datetime
    updated_at: datetime
    linked_events: int


class IncidentDetail(IncidentOut):
    recent_event_messages: list[str]
    root_cause_ranking: list[RootCauseCandidate]


class RegressionOut(BaseModel):
    service: str
    deploy_tag: str
    baseline_error_rate: float
    current_error_rate: float
    baseline_latency_ms: float
    current_latency_ms: float
    score: float


class AnomalyOut(BaseModel):
    service: str
    metric: str
    method: str
    score: float
    details: str | None = None
    created_at: datetime


class TimelineEvent(BaseModel):
    kind: Literal["deploy", "anomaly", "incident"]
    service: str
    title: str
    score: float | None = None
    timestamp: datetime


class TriageStats(BaseModel):
    system_status: Literal["healthy", "degraded", "critical"]
    open_incidents: int
    mitigated_incidents: int
    active_anomalies: int
    mean_confidence: float
    mttr_minutes_estimate: float

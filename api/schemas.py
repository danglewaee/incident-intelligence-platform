from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class EventIn(BaseModel):
    service: str
    environment: str = "prod"
    level: Literal["info", "warn", "error", "critical"] = "error"
    message: str
    error_code: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    deploy_tag: str | None = None


class EventOut(EventIn):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True


class IncidentOut(BaseModel):
    id: int
    status: str
    title: str
    service: str
    environment: str
    severity: str
    root_cause_hint: str | None = None
    confidence: float
    started_at: datetime
    updated_at: datetime
    linked_events: int


class IncidentDetail(IncidentOut):
    recent_event_messages: list[str]


class RegressionOut(BaseModel):
    service: str
    deploy_tag: str
    baseline_error_rate: float
    current_error_rate: float
    baseline_latency_ms: float
    current_latency_ms: float
    score: float


class TriageStats(BaseModel):
    open_incidents: int
    mitigated_incidents: int
    mean_confidence: float
    mttr_minutes_estimate: float
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from api.database import Base


class RawTelemetryEvent(Base):
    __tablename__ = "raw_telemetry_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    service = Column(String(80), nullable=False, index=True)
    event_type = Column(String(24), nullable=False, default="log", index=True)
    severity = Column(String(20), nullable=False, default="error")
    message = Column(Text, nullable=False)
    metric_name = Column(String(80), nullable=True)
    metric_value = Column(Float, nullable=True)
    trace_id = Column(String(120), nullable=True, index=True)
    deployment_id = Column(String(120), nullable=True, index=True)
    payload_json = Column(Text, nullable=False)


class ServiceEvent(Base):
    __tablename__ = "service_events"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(80), nullable=False, index=True)
    environment = Column(String(40), nullable=False, default="prod")
    event_type = Column(String(24), nullable=False, default="log", index=True)
    level = Column(String(20), nullable=False, default="error")
    message = Column(Text, nullable=False)
    error_code = Column(String(64), nullable=True, index=True)
    metric_name = Column(String(80), nullable=True)
    metric_value = Column(Float, nullable=True)
    trace_id = Column(String(120), nullable=True, index=True)
    latency_ms = Column(Float, nullable=True)
    deploy_tag = Column(String(120), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(24), nullable=False, default="new", index=True)
    title = Column(String(200), nullable=False)
    service = Column(String(80), nullable=False, index=True)
    environment = Column(String(40), nullable=False)
    severity = Column(String(16), nullable=False, default="medium")
    root_cause_hint = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    event_links = relationship("IncidentEvent", back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("service_events.id"), nullable=False, index=True)

    incident = relationship("Incident", back_populates="event_links")


class RegressionSignal(Base):
    __tablename__ = "regression_signals"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String(80), nullable=False, index=True)
    deploy_tag = Column(String(120), nullable=False, index=True)
    baseline_error_rate = Column(Float, nullable=False)
    current_error_rate = Column(Float, nullable=False)
    baseline_latency_ms = Column(Float, nullable=False)
    current_latency_ms = Column(Float, nullable=False)
    score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class AnomalySignal(Base):
    __tablename__ = "anomaly_signals"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("service_events.id"), nullable=False, index=True)
    service = Column(String(80), nullable=False, index=True)
    metric = Column(String(48), nullable=False, index=True)
    method = Column(String(48), nullable=False)
    score = Column(Float, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

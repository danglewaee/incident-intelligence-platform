from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Incident, IncidentEvent, RegressionSignal, ServiceEvent


def _severity_from_level(level: str) -> str:
    if level == "critical":
        return "critical"
    if level == "error":
        return "high"
    if level == "warn":
        return "medium"
    return "low"


def _confidence_from_event(message: str, level: str) -> float:
    conf = 0.55
    if "timeout" in message.lower() or "exception" in message.lower():
        conf += 0.2
    if level in ("error", "critical"):
        conf += 0.15
    return min(0.98, conf)


def assign_event_to_incident(db: Session, event: ServiceEvent) -> Incident:
    now = datetime.utcnow()
    recent_cutoff = now - timedelta(minutes=25)

    candidate = (
        db.query(Incident)
        .filter(Incident.service == event.service)
        .filter(Incident.environment == event.environment)
        .filter(Incident.status.in_(["new", "triaged", "mitigated"]))
        .filter(Incident.updated_at >= recent_cutoff)
        .order_by(Incident.updated_at.desc())
        .first()
    )

    message_key = (event.error_code or event.message[:60]).strip()

    if candidate and message_key.lower() in (candidate.title.lower() + " " + (candidate.root_cause_hint or "").lower()):
        candidate.updated_at = now
        if event.level == "critical":
            candidate.severity = "critical"
        db.add(candidate)
        db.flush()
        link = IncidentEvent(incident_id=candidate.id, event_id=event.id)
        db.add(link)
        return candidate

    incident = Incident(
        status="new",
        title=f"{event.service}: {message_key[:90]}",
        service=event.service,
        environment=event.environment,
        severity=_severity_from_level(event.level),
        root_cause_hint=event.error_code or "Pattern match required",
        confidence=_confidence_from_event(event.message, event.level),
        started_at=now,
        updated_at=now,
    )
    db.add(incident)
    db.flush()
    db.add(IncidentEvent(incident_id=incident.id, event_id=event.id))
    return incident


def detect_regression(db: Session, event: ServiceEvent) -> RegressionSignal | None:
    if not event.deploy_tag:
        return None

    now = datetime.utcnow()
    baseline_start = now - timedelta(hours=3)
    baseline_end = now - timedelta(hours=1)
    current_start = now - timedelta(hours=1)

    baseline_query = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.service == event.service)
        .filter(ServiceEvent.timestamp >= baseline_start)
        .filter(ServiceEvent.timestamp < baseline_end)
    )

    current_query = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.service == event.service)
        .filter(ServiceEvent.timestamp >= current_start)
    )

    baseline_count = baseline_query.count() or 1
    current_count = current_query.count() or 1

    baseline_errors = baseline_query.filter(ServiceEvent.level.in_(["error", "critical"])).count()
    current_errors = current_query.filter(ServiceEvent.level.in_(["error", "critical"])).count()

    baseline_rate = baseline_errors / baseline_count
    current_rate = current_errors / current_count

    baseline_latency = float(
        baseline_query.with_entities(func.avg(ServiceEvent.latency_ms)).scalar() or 0.0
    )
    current_latency = float(
        current_query.with_entities(func.avg(ServiceEvent.latency_ms)).scalar() or 0.0
    )

    if baseline_rate == 0 and current_rate == 0:
        return None

    rate_ratio = (current_rate + 1e-6) / (baseline_rate + 1e-6)
    latency_ratio = (current_latency + 1e-6) / (baseline_latency + 1e-6) if baseline_latency > 0 else 1.0
    score = max(0.0, (rate_ratio - 1.0) * 0.7 + (latency_ratio - 1.0) * 0.3)

    if score < 0.25:
        return None

    signal = RegressionSignal(
        service=event.service,
        deploy_tag=event.deploy_tag,
        baseline_error_rate=round(baseline_rate, 4),
        current_error_rate=round(current_rate, 4),
        baseline_latency_ms=round(baseline_latency, 2),
        current_latency_ms=round(current_latency, 2),
        score=round(score, 3),
    )
    db.add(signal)
    return signal
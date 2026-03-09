from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models import AnomalySignal, Incident, IncidentEvent, RegressionSignal, ServiceEvent


SERVICE_DEPENDENCY_GRAPH = {
    "api-gateway": ["auth-service", "payment-service", "notification-service"],
    "auth-service": ["db-primary", "cache-layer"],
    "payment-service": ["db-primary", "payment-provider"],
    "notification-service": ["queue-broker"],
    "billing-service": ["db-primary", "payment-provider"],
    "search-service": ["cache-layer", "index-store"],
    "feed-service": ["db-primary", "queue-broker"],
}


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return {x for x in cleaned.split() if len(x) > 2}


def _message_similarity(left: str, right: str) -> float:
    lset = _tokenize(left)
    rset = _tokenize(right)
    if not lset or not rset:
        return 0.0
    common = len(lset.intersection(rset))
    denom = len(lset.union(rset))
    return common / max(1, denom)


def _severity_from_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _event_weight(level: str) -> float:
    return {
        "critical": 2.8,
        "error": 2.0,
        "warn": 1.1,
        "info": 0.4,
    }.get(level, 0.6)


def _confidence_from_event(message: str, level: str) -> float:
    conf = 0.53
    lowered = message.lower()
    if "timeout" in lowered or "exception" in lowered or "refused" in lowered:
        conf += 0.2
    if level in ("error", "critical"):
        conf += 0.16
    return min(0.98, conf)


def detect_anomaly(db: Session, event: ServiceEvent) -> list[AnomalySignal]:
    anomalies: list[AnomalySignal] = []
    history_cutoff = event.timestamp - timedelta(minutes=40)

    recent_latency = (
        db.query(ServiceEvent.latency_ms)
        .filter(ServiceEvent.service == event.service)
        .filter(ServiceEvent.timestamp >= history_cutoff)
        .filter(ServiceEvent.id != event.id)
        .filter(ServiceEvent.latency_ms.isnot(None))
        .all()
    )

    if len(recent_latency) >= 10 and event.latency_ms is not None:
        vals = [float(x[0]) for x in recent_latency]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
        std = var ** 0.5
        z = 0.0 if std < 1e-6 else (event.latency_ms - mean) / std
        if z >= 2.6:
            anomalies.append(
                AnomalySignal(
                    event_id=event.id,
                    service=event.service,
                    metric="latency_ms",
                    method="z_score",
                    score=round(float(z), 3),
                    details=f"Latency spike: {event.latency_ms:.1f}ms vs baseline {mean:.1f}ms",
                )
            )

    window_start = event.timestamp - timedelta(minutes=12)
    prev_start = event.timestamp - timedelta(minutes=24)
    prev_end = window_start

    current = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.service == event.service)
        .filter(ServiceEvent.timestamp >= window_start)
    )
    prev = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.service == event.service)
        .filter(ServiceEvent.timestamp >= prev_start)
        .filter(ServiceEvent.timestamp < prev_end)
    )

    cur_total = current.count() or 1
    prev_total = prev.count() or 1
    cur_err = current.filter(ServiceEvent.level.in_(["error", "critical"])) .count()
    prev_err = prev.filter(ServiceEvent.level.in_(["error", "critical"])) .count()

    cur_rate = cur_err / cur_total
    prev_rate = prev_err / prev_total
    if cur_rate > 0.18 and cur_rate > (prev_rate + 0.12):
        spike_score = ((cur_rate + 1e-6) / (prev_rate + 1e-6))
        anomalies.append(
            AnomalySignal(
                event_id=event.id,
                service=event.service,
                metric="error_rate",
                method="rolling_delta",
                score=round(float(spike_score), 3),
                details=f"Error rate jump: {cur_rate:.2f} vs baseline {prev_rate:.2f}",
            )
        )

    for a in anomalies:
        db.add(a)

    return anomalies


def _incident_baseline_match(event: ServiceEvent, candidate: Incident) -> bool:
    if candidate.service != event.service:
        return False
    if candidate.environment != event.environment:
        return False
    if (event.timestamp - candidate.updated_at) > timedelta(minutes=12):
        return False
    if event.error_code and candidate.root_cause_hint and event.error_code in candidate.root_cause_hint:
        return True
    return _message_similarity(event.message, candidate.title) >= 0.22


def assign_event_to_incident(db: Session, event: ServiceEvent) -> Incident:
    recent_cutoff = event.timestamp - timedelta(minutes=25)
    candidates = (
        db.query(Incident)
        .filter(Incident.environment == event.environment)
        .filter(Incident.status.in_(["new", "triaged", "mitigated"]))
        .filter(Incident.updated_at >= recent_cutoff)
        .order_by(Incident.updated_at.desc())
        .limit(20)
        .all()
    )

    baseline_candidate = None
    for item in candidates:
        if _incident_baseline_match(event, item):
            baseline_candidate = item
            break

    if baseline_candidate:
        baseline_candidate.updated_at = event.timestamp
        baseline_candidate.confidence = max(
            baseline_candidate.confidence,
            _confidence_from_event(event.message, event.level),
        )
        db.add(baseline_candidate)
        db.flush()
        db.add(IncidentEvent(incident_id=baseline_candidate.id, event_id=event.id))
        return baseline_candidate

    semantic_candidate = None
    best_score = 0.0
    for item in candidates:
        score = _message_similarity(event.message, item.title)
        if score > best_score:
            best_score = score
            semantic_candidate = item

    if semantic_candidate and best_score >= 0.42:
        semantic_candidate.updated_at = event.timestamp
        semantic_candidate.confidence = min(0.97, semantic_candidate.confidence + 0.04)
        db.add(semantic_candidate)
        db.flush()
        db.add(IncidentEvent(incident_id=semantic_candidate.id, event_id=event.id))
        return semantic_candidate

    message_key = (event.error_code or event.message[:60]).strip()
    incident = Incident(
        status="new",
        title=f"{event.service}: {message_key[:90]}",
        service=event.service,
        environment=event.environment,
        severity="medium",
        root_cause_hint=event.error_code or "Correlation pending",
        confidence=_confidence_from_event(event.message, event.level),
        started_at=event.timestamp,
        updated_at=event.timestamp,
    )
    db.add(incident)
    db.flush()
    db.add(IncidentEvent(incident_id=incident.id, event_id=event.id))
    return incident


def detect_regression(db: Session, event: ServiceEvent) -> RegressionSignal | None:
    if not event.deploy_tag:
        return None

    baseline_start = event.timestamp - timedelta(hours=3)
    baseline_end = event.timestamp - timedelta(hours=1)
    current_start = event.timestamp - timedelta(hours=1)

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

    baseline_errors = baseline_query.filter(ServiceEvent.level.in_(["error", "critical"])) .count()
    current_errors = current_query.filter(ServiceEvent.level.in_(["error", "critical"])) .count()

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


def rank_root_causes(db: Session, incident: Incident, max_candidates: int = 4) -> list[dict]:
    event_ids = [
        x.event_id
        for x in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident.id).all()
    ]
    if not event_ids:
        return []

    events = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.id.in_(event_ids))
        .order_by(ServiceEvent.timestamp.asc())
        .all()
    )
    if not events:
        return []

    services = {x.service for x in events}
    first_seen = {s: min(e.timestamp for e in events if e.service == s) for s in services}
    service_event_counts = Counter([x.service for x in events])

    latest_anomaly = (
        db.query(AnomalySignal)
        .filter(AnomalySignal.service.in_(list(services)))
        .order_by(AnomalySignal.created_at.desc())
        .limit(50)
        .all()
    )
    anomaly_boost: dict[str, float] = {}
    for a in latest_anomaly:
        anomaly_boost[a.service] = max(anomaly_boost.get(a.service, 0.0), float(a.score))

    recent_reg = (
        db.query(RegressionSignal)
        .filter(RegressionSignal.created_at >= incident.started_at - timedelta(minutes=30))
        .filter(RegressionSignal.service.in_(list(services)))
        .all()
    )
    deploy_hit = {x.service for x in recent_reg}

    ranked = []
    ordered_services = sorted(first_seen.items(), key=lambda x: x[1])
    for idx, (service, ts) in enumerate(ordered_services):
        upstream_weight = 0.0
        for child, deps in SERVICE_DEPENDENCY_GRAPH.items():
            if child in services and service in deps:
                upstream_weight += 0.35

        temporal_priority = 1.0 / (idx + 1)
        anomaly_weight = min(2.2, anomaly_boost.get(service, 0.0) / 2.3)
        deploy_weight = 0.7 if service in deploy_hit else 0.0
        volume_weight = min(1.0, service_event_counts.get(service, 0) / 6.0)

        root_score = anomaly_weight + upstream_weight + deploy_weight + temporal_priority + volume_weight
        confidence = min(0.98, 0.38 + (root_score / 5.0))
        evidence = [
            f"first_seen={ts.isoformat()}",
            f"event_count={service_event_counts.get(service, 0)}",
            f"anomaly_boost={anomaly_boost.get(service, 0.0):.2f}",
            f"deploy_proximity={'yes' if service in deploy_hit else 'no'}",
        ]
        ranked.append(
            {
                "service": service,
                "score": round(root_score, 3),
                "confidence": round(confidence, 3),
                "evidence": evidence,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:max_candidates]


def compute_incident_severity_score(
    db: Session,
    incident: Incident,
    root_ranking: list[dict],
) -> float:
    linked_event_ids = [
        x.event_id
        for x in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident.id).all()
    ]
    if not linked_event_ids:
        return 15.0

    events = db.query(ServiceEvent).filter(ServiceEvent.id.in_(linked_event_ids)).all()
    impacted_services = len({x.service for x in events})
    event_volume = len(events)
    level_weight = sum(_event_weight(x.level) for x in events)
    avg_latency = sum((x.latency_ms or 0.0) for x in events) / max(1, len(events))

    recent_reg = (
        db.query(RegressionSignal)
        .filter(RegressionSignal.service == incident.service)
        .filter(RegressionSignal.created_at >= incident.started_at - timedelta(minutes=30))
        .order_by(RegressionSignal.created_at.desc())
        .first()
    )

    regression_boost = (recent_reg.score * 20.0) if recent_reg else 0.0
    root_conf = root_ranking[0]["confidence"] * 12.0 if root_ranking else 0.0

    raw = (
        impacted_services * 11.0
        + min(20.0, event_volume * 1.4)
        + min(18.0, level_weight * 2.2)
        + min(18.0, avg_latency / 90.0)
        + regression_boost
        + root_conf
    )
    return max(0.0, min(100.0, raw))


def refresh_incident_intelligence(db: Session, incident: Incident) -> dict:
    ranking = rank_root_causes(db, incident)
    score = compute_incident_severity_score(db, incident, ranking)
    incident.severity = _severity_from_score(score)
    if ranking:
        incident.root_cause_hint = ranking[0]["service"]
        incident.confidence = max(incident.confidence, ranking[0]["confidence"])
    db.add(incident)
    return {
        "severity_score": round(score, 2),
        "probable_root_cause": ranking[0]["service"] if ranking else incident.root_cause_hint,
        "root_cause_ranking": ranking,
    }

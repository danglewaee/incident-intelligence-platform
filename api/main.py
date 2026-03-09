from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.analyzer_core import refresh_incident_intelligence
from api.database import Base, engine, get_db
from api.models import AnomalySignal, Incident, IncidentEvent, RegressionSignal, ServiceEvent
from api.schemas import (
    AnomalyOut,
    IncidentDetail,
    IncidentOut,
    RegressionOut,
    TimelineEvent,
    TriageStats,
)

app = FastAPI(title="AI Reliability Intelligence Platform API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "service": "api"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _incident_out(db: Session, inc: Incident) -> IncidentOut:
    linked = db.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()
    intelligence = refresh_incident_intelligence(db, inc)
    return IncidentOut(
        id=inc.id,
        status=inc.status,
        title=inc.title,
        service=inc.service,
        environment=inc.environment,
        severity=inc.severity,
        severity_score=intelligence["severity_score"],
        probable_root_cause=intelligence["probable_root_cause"],
        root_cause_hint=inc.root_cause_hint,
        confidence=inc.confidence,
        started_at=inc.started_at,
        updated_at=inc.updated_at,
        linked_events=linked,
    )


@app.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    rows = db.query(Incident).order_by(Incident.updated_at.desc()).limit(80).all()
    out = [_incident_out(db, inc) for inc in rows]
    db.commit()
    return out


@app.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: int, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")

    event_ids = [
        x.event_id
        for x in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).limit(40).all()
    ]
    messages = []
    if event_ids:
        messages = [x.message for x in db.query(ServiceEvent).filter(ServiceEvent.id.in_(event_ids)).all()]

    base = _incident_out(db, inc)
    ranking = refresh_incident_intelligence(db, inc)["root_cause_ranking"]
    db.commit()

    return IncidentDetail(
        **base.model_dump(),
        recent_event_messages=messages[:12],
        root_cause_ranking=ranking,
    )


@app.get("/regressions", response_model=list[RegressionOut])
def regressions(db: Session = Depends(get_db)):
    rows = db.query(RegressionSignal).order_by(RegressionSignal.created_at.desc()).limit(50).all()
    return [
        RegressionOut(
            service=x.service,
            deploy_tag=x.deploy_tag,
            baseline_error_rate=x.baseline_error_rate,
            current_error_rate=x.current_error_rate,
            baseline_latency_ms=x.baseline_latency_ms,
            current_latency_ms=x.current_latency_ms,
            score=x.score,
        )
        for x in rows
    ]


@app.get("/anomalies", response_model=list[AnomalyOut])
def anomalies(db: Session = Depends(get_db)):
    rows = db.query(AnomalySignal).order_by(AnomalySignal.created_at.desc()).limit(80).all()
    return [
        AnomalyOut(
            service=x.service,
            metric=x.metric,
            method=x.method,
            score=x.score,
            details=x.details,
            created_at=x.created_at,
        )
        for x in rows
    ]


@app.get("/timeline", response_model=list[TimelineEvent])
def timeline(db: Session = Depends(get_db)):
    out: list[TimelineEvent] = []

    deploy_events = (
        db.query(ServiceEvent)
        .filter(ServiceEvent.deploy_tag.isnot(None))
        .order_by(ServiceEvent.timestamp.desc())
        .limit(16)
        .all()
    )
    for x in deploy_events:
        out.append(
            TimelineEvent(
                kind="deploy",
                service=x.service,
                title=f"Deploy {x.deploy_tag}",
                score=None,
                timestamp=x.timestamp,
            )
        )

    anomaly_rows = db.query(AnomalySignal).order_by(AnomalySignal.created_at.desc()).limit(16).all()
    for x in anomaly_rows:
        out.append(
            TimelineEvent(
                kind="anomaly",
                service=x.service,
                title=f"{x.metric} anomaly ({x.method})",
                score=x.score,
                timestamp=x.created_at,
            )
        )

    incident_rows = db.query(Incident).order_by(Incident.updated_at.desc()).limit(16).all()
    for x in incident_rows:
        out.append(
            TimelineEvent(
                kind="incident",
                service=x.service,
                title=f"Incident #{x.id} {x.severity}",
                score=x.confidence,
                timestamp=x.updated_at,
            )
        )

    out.sort(key=lambda x: x.timestamp, reverse=True)
    return out[:30]


@app.get("/triage/stats", response_model=TriageStats)
def triage_stats(db: Session = Depends(get_db)):
    open_incidents = db.query(Incident).filter(Incident.status.in_(["new", "triaged"])) .count()
    mitigated = db.query(Incident).filter(Incident.status == "mitigated").count()
    mean_conf = float(db.query(func.avg(Incident.confidence)).scalar() or 0.0)

    recent_cutoff = datetime.utcnow() - timedelta(minutes=20)
    active_anomalies = db.query(AnomalySignal).filter(AnomalySignal.created_at >= recent_cutoff).count()

    if open_incidents >= 6 or active_anomalies >= 10:
        status = "critical"
    elif open_incidents >= 2 or active_anomalies >= 4:
        status = "degraded"
    else:
        status = "healthy"

    mttr_est = max(8.0, 72.0 - (mean_conf * 31.0) - min(10.0, active_anomalies * 0.8))
    return TriageStats(
        system_status=status,
        open_incidents=open_incidents,
        mitigated_incidents=mitigated,
        active_anomalies=active_anomalies,
        mean_confidence=round(mean_conf, 3),
        mttr_minutes_estimate=round(mttr_est, 1),
    )

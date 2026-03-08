from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import Base, engine, get_db
from models import Incident, IncidentEvent, RegressionSignal, ServiceEvent
from schemas import EventIn, EventOut, IncidentOut, IncidentDetail, RegressionOut, TriageStats
from analyzer_core import assign_event_to_incident, detect_regression

app = FastAPI(title="Incident Intelligence Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        closed = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                closed.append(ws)
        for ws in closed:
            self.disconnect(ws)


ws_manager = ConnectionManager()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/events", response_model=EventOut)
async def ingest_event(payload: EventIn, db: Session = Depends(get_db)):
    event = ServiceEvent(**payload.model_dump())
    db.add(event)
    db.flush()

    incident = assign_event_to_incident(db, event)
    signal = detect_regression(db, event)

    db.commit()
    db.refresh(event)

    await ws_manager.broadcast(
        {
            "type": "event_ingested",
            "service": event.service,
            "level": event.level,
            "incident_id": incident.id,
            "regression_score": signal.score if signal else None,
        }
    )

    return event


@app.get("/incidents", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    rows = db.query(Incident).order_by(Incident.updated_at.desc()).limit(80).all()
    out = []
    for inc in rows:
        linked = db.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()
        out.append(
            IncidentOut(
                id=inc.id,
                status=inc.status,
                title=inc.title,
                service=inc.service,
                environment=inc.environment,
                severity=inc.severity,
                root_cause_hint=inc.root_cause_hint,
                confidence=inc.confidence,
                started_at=inc.started_at,
                updated_at=inc.updated_at,
                linked_events=linked,
            )
        )
    return out


@app.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: int, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")

    event_ids = [
        x.event_id
        for x in db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).limit(12).all()
    ]
    messages = []
    if event_ids:
        messages = [x.message for x in db.query(ServiceEvent).filter(ServiceEvent.id.in_(event_ids)).all()]

    linked = db.query(IncidentEvent).filter(IncidentEvent.incident_id == inc.id).count()
    return IncidentDetail(
        id=inc.id,
        status=inc.status,
        title=inc.title,
        service=inc.service,
        environment=inc.environment,
        severity=inc.severity,
        root_cause_hint=inc.root_cause_hint,
        confidence=inc.confidence,
        started_at=inc.started_at,
        updated_at=inc.updated_at,
        linked_events=linked,
        recent_event_messages=messages,
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


@app.get("/triage/stats", response_model=TriageStats)
def triage_stats(db: Session = Depends(get_db)):
    open_incidents = db.query(Incident).filter(Incident.status.in_(["new", "triaged"])).count()
    mitigated = db.query(Incident).filter(Incident.status == "mitigated").count()
    mean_conf = float(db.query(func.avg(Incident.confidence)).scalar() or 0.0)
    mttr_est = max(8.0, 70.0 - (mean_conf * 32.0))
    return TriageStats(
        open_incidents=open_incidents,
        mitigated_incidents=mitigated,
        mean_confidence=round(mean_conf, 3),
        mttr_minutes_estimate=round(mttr_est, 1),
    )


@app.websocket("/ws")
async def ws_feed(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)
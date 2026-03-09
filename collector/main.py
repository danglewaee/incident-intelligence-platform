import json
import os
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from api.database import Base, SessionLocal, engine
from api.models import RawTelemetryEvent
from api.schemas import EventIn, IngestAck

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "telemetry_events")

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="Telemetry Collector", version="0.1.0")

Base.metadata.create_all(bind=engine)


def _ts(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return value


@app.get("/health")
def health():
    return {"status": "ok", "service": "collector"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/events", response_model=IngestAck)
def ingest_event(payload: EventIn):
    db: Session = SessionLocal()
    try:
        timestamp = _ts(payload.timestamp)
        severity = payload.severity or payload.level
        deploy_id = payload.deployment_id or payload.deploy_tag
        event_data = payload.model_dump()
        event_data["timestamp"] = timestamp.isoformat()
        event_data["severity"] = severity
        event_data["deployment_id"] = deploy_id

        raw_event = RawTelemetryEvent(
            timestamp=timestamp,
            service=payload.service,
            event_type=payload.event_type,
            severity=severity,
            message=payload.message,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            trace_id=payload.trace_id,
            deployment_id=deploy_id,
            payload_json=json.dumps(event_data),
        )
        db.add(raw_event)
        db.flush()

        stream_id = redis_client.xadd(
            REDIS_STREAM_KEY,
            {"payload": json.dumps(event_data), "raw_event_id": str(raw_event.id)},
        )

        db.commit()
        return IngestAck(accepted=True, raw_event_id=raw_event.id, stream_id=stream_id)
    finally:
        db.close()

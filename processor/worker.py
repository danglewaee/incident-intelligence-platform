import json
import os
import time
from datetime import datetime, timezone

import redis
from sqlalchemy.orm import Session

from api.analyzer_core import (
    assign_event_to_incident,
    detect_anomaly,
    detect_regression,
    refresh_incident_intelligence,
)
from api.database import SessionLocal, ensure_schema
from api.models import ServiceEvent

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_STREAM_KEY = os.getenv("REDIS_STREAM_KEY", "telemetry_events")
REDIS_UPDATE_CHANNEL = os.getenv("REDIS_UPDATE_CHANNEL", "incident_updates")
POLL_BLOCK_MS = int(os.getenv("POLL_BLOCK_MS", "4000"))

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
ensure_schema()


def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _to_service_event(payload: dict) -> ServiceEvent:
    level = payload.get("severity") or payload.get("level") or "error"
    return ServiceEvent(
        service=payload.get("service", "unknown-service"),
        environment=payload.get("environment", "prod"),
        event_type=payload.get("event_type", "log"),
        level=level,
        message=payload.get("message", ""),
        error_code=payload.get("error_code"),
        metric_name=payload.get("metric_name"),
        metric_value=payload.get("metric_value"),
        trace_id=payload.get("trace_id"),
        latency_ms=payload.get("latency_ms"),
        deploy_tag=payload.get("deploy_tag") or payload.get("deployment_id"),
        timestamp=_parse_ts(payload.get("timestamp")),
    )


def process_message(db: Session, payload: dict):
    event = _to_service_event(payload)
    db.add(event)
    db.flush()

    anomalies = detect_anomaly(db, event)
    incident = assign_event_to_incident(db, event)
    signal = detect_regression(db, event)
    intelligence = refresh_incident_intelligence(db, incident)

    db.commit()

    redis_client.publish(
        REDIS_UPDATE_CHANNEL,
        json.dumps(
            {
                "type": "event_processed",
                "service": event.service,
                "level": event.level,
                "incident_id": incident.id,
                "severity": incident.severity,
                "severity_score": intelligence["severity_score"],
                "probable_root_cause": intelligence["probable_root_cause"],
                "anomaly_count": len(anomalies),
                "regression_score": signal.score if signal else None,
            }
        ),
    )


def run():
    last_id = "0-0"
    while True:
        try:
            messages = redis_client.xread({REDIS_STREAM_KEY: last_id}, count=20, block=POLL_BLOCK_MS)
            if not messages:
                continue

            for _, entries in messages:
                for message_id, fields in entries:
                    last_id = message_id
                    payload_str = fields.get("payload")
                    if not payload_str:
                        continue

                    db: Session = SessionLocal()
                    try:
                        payload = json.loads(payload_str)
                        process_message(db, payload)
                    except Exception:
                        db.rollback()
                    finally:
                        db.close()
        except Exception:
            time.sleep(1.5)


if __name__ == "__main__":
    run()

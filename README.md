# Incident Intelligence Platform (MVP)

Realtime platform to ingest service events, cluster related failures into incidents, detect deploy regressions, and track triage health.

## Services
- `api`: FastAPI + SQLite incident API
- `ingestor`: mock event producer (simulates multi-service failures)
- `dashboard`: realtime incident console (WS + REST)

## Quick start
```bash
cd incident-intelligence-platform
docker compose up --build
```

## URLs
- API docs: http://localhost:9000/docs
- Dashboard: http://localhost:9010

## Core endpoints
- `POST /events`
- `GET /incidents`
- `GET /incidents/{id}`
- `GET /regressions`
- `GET /triage/stats`
- `GET /health`
- `WS /ws`

## Demo flow (45s)
1. Open dashboard and watch incidents appear in realtime.
2. Open `/regressions` to show deploy impact scores.
3. Explain how clustering + regression signals reduce triage time.
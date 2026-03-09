# AI Reliability Intelligence Platform

Build an AI-driven platform that ingests telemetry from distributed services, detects anomalies, clusters related failures into incidents, infers likely root causes, and surfaces actionable signals for faster production debugging.

## Full Pipeline

```text
ingestor -> collector -> Redis Stream -> processor -> PostgreSQL -> api -> dashboard
                                    |
                                    -> anomaly / clustering / root-cause / deploy-regression engine
```

## Why this project is strong
- Distributed event-driven backend (`collector`, `Redis Streams`, `worker`)
- Incident intelligence logic with both statistical and ML anomaly layers
- Graph-based root-cause reasoning using dependency structure
- End-to-end observability UX + monitoring stack (`Prometheus`, `Grafana`)

## Services
- `collector/`: FastAPI telemetry collector (`POST /events`) + stream publisher
- `processor/`: stream consumer worker (anomaly, clustering, root cause, regression, severity)
- `api/`: read/query API for incidents, anomalies, regressions, timeline
- `ingestor/`: simulated multi-service telemetry generator with injected failure scenarios
- `dashboard/`: UI for live reliability intelligence
- infra: `postgres`, `redis`, `prometheus`, `grafana`

## Diversified tech stack
- Backend/API: `Python`, `FastAPI`, `SQLAlchemy`
- Data/stream: `PostgreSQL`, `Redis Streams`
- ML/analytics: `scikit-learn` (Isolation Forest), `NumPy`, `Pandas`
- Graph reasoning: `NetworkX`
- Observability: `Prometheus`, `Grafana`
- Infra: `Docker Compose`, `Nginx`

## Simulated playground and failures
Simulated services:
- `api-gateway`
- `auth-service`
- `payment-service`
- `notification-service`
- `db-primary`
- `cache-layer`

Injected scenarios:
- latency spike
- DB timeout
- failed deployment
- cascading upstream failure

## Quick start
```bash
docker compose up --build
```

## URLs
- Collector health: http://localhost:9001/health
- API docs: http://localhost:9000/docs
- Dashboard: http://localhost:9010
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## Key endpoints
Collector:
- `POST /events`

API:
- `GET /incidents`
- `GET /incidents/{id}`
- `GET /anomalies`
- `GET /regressions`
- `GET /timeline`
- `GET /triage/stats`

## Intelligence logic
- Anomaly detection:
  - statistical: latency z-score + rolling error-rate jump
  - ML: Isolation Forest on service health vectors
- Incident clustering:
  - rule baseline (service + window + pattern)
  - similarity layer for correlated message grouping
- Root cause ranking via weighted heuristic:
  - temporal precedence
  - upstream dependency weight
  - graph centrality boost (NetworkX)
  - anomaly strength
  - deployment proximity
  - event concentration
- Deploy regression detector: pre/post deploy error-rate and latency deltas
- Severity score: service impact + event volume + level weights + latency + regression + confidence

## Project docs
- Architecture: [docs/architecture.md](docs/architecture.md)
- 4-week roadmap: [docs/roadmap.md](docs/roadmap.md)
- Resume bullets template: [docs/resume-bullets.md](docs/resume-bullets.md)

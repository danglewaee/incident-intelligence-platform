# System Architecture

## One-line project statement
Build an AI-driven platform that ingests telemetry from distributed services, detects anomalies, clusters related failures into incidents, infers likely root causes, and surfaces actionable signals for faster production debugging.

## Architecture flow

```text
Microservices -> Telemetry Collector -> Event Stream -> Processing Engine -> Incident Store -> Dashboard
                                         |                  |
                                         |                  -> Anomaly Detection
                                         |                  -> Incident Clustering
                                         |                  -> Root Cause Inference
                                         |
                                         -> Deployment Event Tracker
```

## Components

### 1) Microservice playground
- `api-gateway`
- `auth-service`
- `payment-service`
- `notification-service`
- backing infra: `postgres`, `redis`, `prometheus`

Failure scenarios:
- auth timeout
- payment DB latency spike
- notification queue backlog
- bad deployment error jump
- gateway memory pressure
- cascading upstream failure

### 2) Telemetry collector
Ingest event categories:
- logs
- metrics
- alerts
- deployment events

Canonical event schema:

```json
{
  "timestamp": "...",
  "service": "payment-service",
  "event_type": "log|metric|alert|deploy",
  "severity": "info|warn|error|critical",
  "message": "...",
  "metric_name": "p95_latency",
  "metric_value": 820,
  "trace_id": "...",
  "deployment_id": "deploy_017"
}
```

### 3) Processing engine
- Anomaly detection: rolling baseline + z-score + error-rate jump
- Incident clustering:
  - V1: rule-based time/service/error family grouping
  - V2: embedding-based clustering (TF-IDF/sentence-transformers + DBSCAN/HDBSCAN)
- Root cause inference:
  - dependency graph reasoning
  - temporal precedence
  - deployment proximity
  - anomaly severity weighting
- Deployment regression detector:
  - compare pre/post deployment windows
  - track error-rate and latency regressions
- Severity ranking:
  - impacted services
  - error and latency shifts
  - service criticality
  - confidence

### 4) Dashboard surfaces
- Overview: active incidents, anomalies, system health, latest deploys
- Incident list: severity, impacted services, probable root cause, status
- Incident detail: correlated events, anomaly timeline, root-cause candidates, related deploy
- Service map: dependency graph + per-node health
- Timeline: deploys + anomaly spikes + incident markers

## Current implementation status
- Implemented now: ingestion API, anomaly baseline, incident clustering, root-cause ranking, regression signals, realtime dashboard
- Next step: add true event stream (`Redis Streams`), postgres persistence, and embedding clustering

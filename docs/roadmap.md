# 4-Week Execution Roadmap

## Week 1: Playground + Ingestion
Goals:
- Set up microservice playground in Docker Compose
- Stabilize telemetry schema for logs/metrics/deploy events
- Persist events in PostgreSQL + queue via Redis Streams
- Ship a basic dashboard shell

Deliverables:
- 4 core services running
- canonical event schema locked
- ingestion pipeline producing stored events

## Week 2: Incident Grouping + Anomaly Detection
Goals:
- Implement rule-based incident grouping
- Implement latency and error-rate anomaly detection
- Add severity score V1

Deliverables:
- incidents auto-generated from raw events
- anomaly panel live in dashboard
- severity surfaced in incident list

## Week 3: Root Cause Inference + Deploy Regression
Goals:
- Add dependency graph
- Add root-cause candidate ranking
- Add deploy regression detector with confidence

Deliverables:
- incident detail view with top root-cause candidates
- deploy-induced incident flags
- supporting evidence shown in UI

## Week 4: AI Upgrade + Polish
Goals:
- Add embedding-based clustering baseline
- Benchmark on injected failure scenarios
- Polish README, architecture docs, screenshots, and demo video
- Finalize resume bullets with measurable outcomes

Deliverables:
- polished GitHub repository
- metrics section with clear evaluation methodology
- 2-3 minute demo video

## Execution guardrails
- Keep MVP explainable first, then add ML upgrades
- Track precision/recall and false-positive cost each week
- Avoid scope creep before Week 3 core logic is stable

# Observability

## Metrics (Prometheus)
- `backgrid_jobs_submitted_total`
- `backgrid_jobs_latency_seconds` (histogram: p50/p95/p99)
- `backgrid_queue_depth`
- `backgrid_worker_throughput`
- `backgrid_api_requests_total`, `backgrid_api_request_duration_seconds`

## Logs
- Structured JSON to stdout
- Correlation IDs propagated from API ↔ worker ↔ metrics
- Error contexts shipped to Sentry

## Tracing
- OpenTelemetry instrumentation for FastAPI + Celery
- gRPC client/server spans (Go metrics)

## Dashboards
- Grafana boards for job throughput, latency, error rates, queue saturation

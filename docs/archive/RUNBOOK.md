# Runbook (Operations)

## On‑Call Checklist
1. Check Grafana: queue depth, job latency, error rate
2. Inspect Sentry: new exceptions?
3. Verify Redis + TimescaleDB health

## Common Incidents
- **Queue backlog ↑** → scale workers, inspect slow strategies
- **DB connections maxed** → enable pgbouncer, raise pool
- **API 5xx** → dependency health, rollback last deploy

## Emergency Controls
- Maintenance mode: set `MAINTENANCE_MODE=1` on API
- Drain workers: send SIGTERM, wait for graceful shutdown
- Kill‑switch: disable job submission endpoint

## Playbooks
- Data API throttling → increase cache TTL, slow retries (exponential backoff)
- gRPC timeouts → bump deadline, check metrics service CPU/mem

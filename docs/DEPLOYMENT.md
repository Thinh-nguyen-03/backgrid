# Deployment Guide

**Current Phase**: 1 (Local only)

**Target**: Fly.io (Phase 2)

---

## Phase 1: Local Development

No deployment yet. Run directly on local machine.

```bash
python src/api.py
```

---

## Phase 2: Fly.io (Single App)

### Steps

```bash
# 1. Create app
flyctl launch --name backgrid-demo --dockerfile Dockerfile

# 2. Set secrets
flyctl secrets set \
  DATABASE_URL="postgres://..." \
  REDIS_URL="redis://..." \
  --app backgrid-demo

# 3. Deploy
flyctl deploy

# 4. Scale workers
flyctl scale count 2 --app backgrid-demo
```

### Docker Compose (Phase 2)

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    command: uvicorn src.api:app --host 0.0.0.0
    ports: ["8000:8000"]
    depends_on: [redis, postgres]

  worker:
    build: .
    command: celery -A src.worker worker --concurrency=4
    depends_on: [redis, postgres]

  redis:
    image: redis:7-alpine

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: backgrid
```

---

## Phase 3: Multi-Service (Future)

**Trigger**: You need to deploy Go service and TimescaleDB.

### Fly.io Apps
- `backgrid-api` (FastAPI)
- `backgrid-worker` (Celery)
- `backgrid-metrics` (Go gRPC)
- `backgrid-db` (TimescaleDB)

**Not implemented yet** - will add when Phase 2 is stable.

---

## Zero-Downtime (Not Needed Yet)

Rolling deploys are sufficient for a demo with <10 users. Skip blue-green for now.

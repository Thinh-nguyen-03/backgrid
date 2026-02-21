# Deployment Guide

**Current Phase**: 2 Complete (Week 8 - UI Modernization)

**Status**: Production Ready (650 tests passing)

**Target**: Fly.io or Docker Compose

---

## Local Development (Current)

SQLite-based development mode (no infrastructure needed).

```bash
# Install dependencies
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npm run build && cd ..

# Run tests
pytest tests/  # 650 tests, ~10s

# Start API (serves UI at http://localhost:8000)
uvicorn src.api:app --reload --port 8000

# Start Celery worker (optional)
celery -A src.worker worker --loglevel=info --pool=threads
```

---

## Production Deployment Options

**Note:** Before deploying, ensure the frontend is built: `cd frontend && npm install && npm run build && cd ..`. The Dockerfile should include a multi-stage build with Node.js to build the frontend assets.

### Option 1: Docker Compose (Recommended for Phase 2)

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    command: uvicorn src.api:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://backgrid:backgrid@postgres:5432/backgrid
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
      - postgres

  worker:
    build: .
    command: celery -A src.worker worker --loglevel=info --concurrency=4
    environment:
      DATABASE_URL: postgresql://backgrid:backgrid@postgres:5432/backgrid
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: backgrid
      POSTGRES_USER: backgrid
      POSTGRES_PASSWORD: backgrid
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**Usage**:
```bash
docker compose up --build -d
docker compose logs -f api worker
```

### Option 2: Fly.io

```bash
# 1. Create app
flyctl launch --name backgrid-demo

# 2. Set secrets
flyctl secrets set \
  DATABASE_URL="postgresql://..." \
  REDIS_URL="redis://..." \
  --app backgrid-demo

# 3. Deploy
flyctl deploy

# 4. Scale workers
flyctl scale count 2 --app backgrid-demo
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

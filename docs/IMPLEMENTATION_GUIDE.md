# Backgrid Implementation Guide

**Version**: 2.0 (Phased Approach)
**Last Updated**: 2025-01-15
**Status**: Phase 1 - MVP (In Progress)

---

## Core Principles

### 1. **Start Simple, Add Complexity When Needed**
- **Phase 1**: Single file, no workers, no Docker
- **Phase 2**: Add Celery + Redis **only when jobs block**
- **Phase 3**: Add Go/TimescaleDB **only when profiling proves need**

### 2. **Document Every Decision with a Receipt**
Every major addition to the stack must include:
- What problem you measured
- Profiler output or benchmark
- Alternatives tried
- Impact after adding

### 3. **Be Honest in Public**
README must reflect **current phase**, not aspirational state. It's okay to say "Phase 1 - MVP" for 2 weeks.

---

## Phase 1: MVP (Week 1-2) - "It Works"

### Goal
Get a single backtest working end-to-end in the simplest possible way.

### Stack
- **FastAPI**: Simple, type-safe API (not using async features yet)
- **SQLite**: Zero-setup database
- **pandas**: Data manipulation
- **yfinance**: Free data source
- **pytest**: Basic unit tests

### Directory Structure
```
backgrid/
├── src/
│   ├── __init__.py
│   ├── api.py              # FastAPI app (~100 lines)
│   ├── backtest.py         # Core backtest logic (~150 lines)
│   ├── data.py             # yfinance fetcher (~50 lines)
│   └── models.py           # Pydantic models (~50 lines)
├── tests/
│   └── test_backtest.py    # 3-5 core tests
├── .env.example
├── requirements.txt
└── README.md
```

### Code Example
```python
# src/api.py
from fastapi import FastAPI
from src.backtest import run_backtest
from src.models import BacktestRequest

app = FastAPI()

@app.post("/api/v1/jobs")
def submit_job(request: BacktestRequest):
    """Synchronous endpoint - runs job immediately"""
    result = run_backtest(
        symbol=request.symbol,
        start=request.start,
        end=request.end,
        strategy=request.strategy,
        params=request.params
    )
    return result
```

### Success Criteria
```bash
# Submit a backtest
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","strategy":"ma_crossover","start":"2020-01-01"}'

# Should return:
{
  "job_id": "manual-2025-01-15-123456",
  "status": "completed",
  "sharpe": 1.23,
  "equity_curve": [...],
  "runtime_seconds": 2.3
}
```

### What to Document
Create DECISION_LOG.md entry:
```markdown
## Phase 1 - MVP (2025-01-15)

### What Works
- ✅ Single endpoint backtest
- ✅ MA crossover strategy
- ✅ Sharpe ratio calculation
- ✅ Results stored in SQLite

### Known Limitations
- ❌ Synchronous only (blocks for 2-8s)
- ❌ No data caching (re-fetches every time)
- ❌ No error handling for API failures
- ❌ Single user only

### Metrics
- Lines of code: 350
- Tests: 3 passing
- Time to build: 3 days
```

---

## Phase 2: Async Workers (Week 3-5) - "It Scales a Little"

### Trigger
You measured that jobs consistently take >5 seconds, causing HTTP timeouts.

### Stack Additions
- **Celery**: Distributed task queue
- **Redis**: Job broker and result backend
- **PostgreSQL**: Concurrent writes

### Changes from Phase 1
```python
# src/api.py
@app.post("/api/v1/jobs")
def submit_job(request: BacktestRequest):
    """Non-blocking: enqueue and return job_id"""
    job = run_backtest.delay(request.dict())  # Celery task
    return {"job_id": job.id, "status": "queued"}

# src/worker.py
from celery import Celery

app = Celery("backgrid", broker="redis://localhost:6379")

@app.task
def run_backtest(params: dict):
    # Same logic as Phase 1, but runs in worker
    result = execute_strategy(params)
    store_in_postgres(result)
    return result
```

### Complexity Receipt Template
Before starting Phase 2, fill this out:
```markdown
## Decision: Add Celery + Redis (Date: YYYY-MM-DD)

### Problem
- Backtests taking 8-12 seconds
- API timeouts at 30s
- Could not run multiple backtests in parallel

### Evidence
```bash
# Benchmark: 10 sequential backtests
Total time: 85 seconds
Average latency: 8.5s/job
```

### Alternatives Tried
1. **ThreadPoolExecutor**:
   - Result: Helped but GIL limited to ~2x speedup
   - Why not enough: True parallelism needed

2. **Multiprocessing**:
   - Why skipped: Complex debugging, memory overhead

### Decision
Added Celery + Redis with 4 workers:
- **Pros**: Battle-tested, retries, monitoring
- **Cons**: Adds Redis dependency
- **Tradeoff accepted**: Worth it for reliability

### Impact
```bash
# After Celery: 10 parallel backtests
Total time: 22 seconds
Average latency: 2.2s/job
Throughput: 4x improvement
```

### Migration Notes
- Added docker-compose.yml with Redis
- Created alembic migrations for PostgreSQL
- Workers scale horizontally (tested with 2→4 workers)
```

---

## Phase 3: Performance & Scale (Week 6-8) - "It Impresses"

### Prerequisites
You must have **profiler output** proving a bottleneck.

### Option 3A: Go gRPC Metrics Service

**Trigger**: Profiler shows metrics calculation >50% of runtime in parameter sweeps

**Stack Addition**:
- **Go 1.22+**: Metrics service
- **gRPC**: Inter-service communication
- **protobuf**: Schema definition

**Implementation Steps**:
1. Profile Python metrics calculation
2. Write protobuf definition
3. Implement Go service (parallel Sharpe/MaxDD)
4. Benchmark Python vs Go

**Complexity Receipt Required**:
```markdown
## Decision: Add Go Metrics Service (Date: YYYY-MM-DD)

### Problem
Parameter sweep of 1000 MA combos:
- Total time: 145 minutes
- Metrics calculation: 98 minutes (68%)

### Profiler Output
```python
# cProfile results
ncalls  tottime  percall  cumtime  percall filename:lineno(function)
1000    45.2s    0.045s   98.1s    0.098s  metrics.py:23(calculate_sharpe)
```

### Alternatives Considered
1. **Numba JIT**: 2.3x speedup, but still GIL-bound
2. **Vectorize more**: Already optimized, diminishing returns
3. **Cython**: Complex, less learning value

### Decision
Go gRPC service - Expected 5-10x speedup
- **Pros**: True parallelism, learning opportunity
- **Cons**: Network hop, deployment complexity

### Impact
```bash
# After Go service:
Metrics time: 98 min → 12 min (8x speedup)
Total runtime: 145 min → 59 min (2.5x overall)
```

### Tradeoffs
- Added ~100ms network overhead per job
- Acceptable: 100ms << 5.8s saved in computation
```

---

### Option 3B: TimescaleDB

**Trigger**: PostgreSQL queries on equity curves slow on 25M+ rows

**Stack Addition**:
- **TimescaleDB**: Time-series extension

**Complexity Receipt Required**:
```markdown
## Decision: Add TimescaleDB (Date: YYYY-MM-DD)

### Problem
Database: 125M equity curve rows
Query: "SELECT * FROM equity_points WHERE job_id=? AND ts > ?"
- AVG query time: 3.2 seconds

### Evidence
```sql
EXPLAIN ANALYZE SELECT * FROM equity_points WHERE job_id='abc123';
# Seq scan on 125M rows: 3200ms
```

### Alternatives
- **Better indexes**: Helped but inserts slowed
- **Partition manually**: Complex maintenance
- **TimescaleDB**: Automated partitioning, optimized queries

### Decision
Migrate equity_points to TimescaleDB hypertable
- Query time: 3.2s → 0.1s (32x improvement)
- Insert throughput: 2x faster

### Migration
- Alembic migration took 4 hours
- Zero downtime: dual-wrote to both tables during migration
```

---

### Option 3C: JWT Auth + User Isolation

**Trigger**: You want 5+ real users to try the demo

**Stack Addition**:
- **PyJWT**: Token generation/validation
- **Row-level security**: PostgreSQL policies

**Complexity Receipt Required**:
```markdown
## Decision: Add JWT Auth (Date: YYYY-MM-DD)

### Problem
- Deployed demo to Fly.io
- Users concerned about job data privacy
- Need to prevent job ID enumeration attacks

### Decision
- Access tokens (15min), refresh tokens (7 days)
- Row-level security: `WHERE user_id = current_user_id()`
- Tradeoff: Added 2 days to implement auth flows

### Impact
- 5 users registered, no security incidents
- Auth overhead: <5ms per request
```

---

## Testing Strategy (Per Phase)

### Phase 1
- **Manual testing**: curl requests
- **Unit tests**: 3-5 tests covering critical paths
- **Coverage target**: 50% (core logic only)

### Phase 2
- **Integration tests**: API ↔ Celery ↔ DB
- **Load tests**: Submit 10 jobs concurrently
- **Coverage target**: 70%

### Phase 3
- **Contract tests**: gRPC protobuf compatibility
- **Performance tests**: Profile metrics service
- **Coverage target**: 80% (critical paths ≥90%)

---

## Documentation Standards

### README.md (Update each phase)
```markdown
# Backgrid - Phased Learning Project

**Status**: Phase 2 - Async Workers (In Progress)
**Live Demo**: https://backgrid-demo.fly.dev

## What Works Now
- ✅ Submit backtests via API
- ✅ Async workers (Celery) - added 2025-01-20 [receipt](docs/decisions/celery.md)
- ✅ PostgreSQL storage
- ❌ Go metrics service (Phase 3)

## Quick Start
```bash
# Phase 2 setup
docker compose up -d  # api, redis, worker, postgres
curl -X POST http://localhost:8000/api/v1/jobs -d @examples/job.json
```

### Architecture
[Link to ARCHITECTURE.md with phased diagrams]

### Decision Log
[Link to DECISION_LOG.md]
```

### DECISION_LOG.md (New File)
Every major addition gets an entry with the template above.

---

## Git Commit Hygiene

**Good commits show evolution**:
```
✅ feat: Add Parquet cache for Yahoo Finance data

Problem: Hitting rate limits after 50 requests/hour
Solution: Cache OHLCV to data/cache/{symbol}_{start}_{end}.parquet
Impact: API calls dropped 90%, cache hit rate 95%
Files: src/data/cache.py, tests/test_cache.py
```

**Bad commits**:
```
❌ "Add Redis"
❌ "WIP on workers"
❌ "Various improvements"
```

---

## Success Metrics (Per Phase)

### Phase 1 Success
- [ ] Single backtest runs end-to-end
- [ ] Sharpe ratio calculated correctly
- [ ] Results stored and retrievable
- [ ] 3 unit tests pass
- [ ] README shows Phase 1 status

### Phase 2 Success
- [ ] 10 jobs run concurrently without blocking
- [ ] Latency <2s per job with workers
- [ ] No data loss on worker crash
- [ ] Decision log entry for Celery
- [ ] README updated to Phase 2

### Phase 3 Success
- [ ] Go service reduces metrics time by >5x (proven by profile)
- [ ] TimescaleDB queries <500ms on 25M rows
- [ ] Auth implemented with JWT
- [ ] 3 decision log entries
- [ ] README updated to Phase 3

---

## Common Pitfalls to Avoid

1. **Adding tech before Phase 2 trigger**: Don't add Celery until you measure 8s+ job latency
2. **No profiler, no Phase 3**: If you can't show the bottleneck, you can't add Go/TimescaleDB
3. **Skipping documentation**: A decision without a receipt is theater
4. **Perfect over shipped**: "Good enough" > "perfect but not deployed"
5. **Tutorial hell**: After learning a new tech, rebuild the feature from scratch without looking

---

**Final Rule**: If you can't explain a technology addition in 2 minutes with profiler data, you haven't earned it yet.

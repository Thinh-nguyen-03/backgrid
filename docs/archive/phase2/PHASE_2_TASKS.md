# Phase 2: Async Workers - Implementation Tasks

**Goal**: Add Celery + Redis + PostgreSQL for async job processing and persistence

**Status**: Week 5 Complete - Celery workers tested, Portfolio module implemented

**Estimated Time**: 1-2 weeks (Week 5 of 7 complete)

---

## Task Breakdown

### Part 1: Infrastructure Setup (Est: 2-3 hours) - COMPLETE

- [x] **Task 1.1**: Add dependencies to requirements.txt
  - celery>=5.4.0 (updated for Python 3.13)
  - redis==5.0.1
  - psycopg2-binary>=2.9.11 (updated for Python 3.13)
  - alembic==1.13.1
  - SQLAlchemy==2.0.23

- [x] **Task 1.2**: Create docker-compose.yml
  - Redis service (port 6379)
  - PostgreSQL service (port 5432)
  - API service (port 8000)
  - Worker service (Celery)
  - Volumes for data persistence

- [x] **Task 1.3**: Create Dockerfile for containerization
  - Multi-stage build (optional)
  - Python 3.11 base image
  - Install dependencies
  - Copy source code

- [x] **Task 1.4**: Test infrastructure
  - docker compose up -d redis
  - Verify Redis running
  - Test Redis connection via Celery health_check

---

### Part 2: Database Layer (Est: 3-4 hours)

- [ ] **Task 2.1**: Create SQLAlchemy models (src/db.py)
  - Job model (job_id, symbol, strategy, params, status, timestamps)
  - Result model (job_id, sharpe, max_drawdown, total_return, equity_curve, error)
  - Database engine and session configuration

- [ ] **Task 2.2**: Setup Alembic for migrations
  - alembic init migrations
  - Configure alembic.ini
  - Create initial migration
  - Test migration up/down

- [ ] **Task 2.3**: Create database utilities
  - SessionLocal factory
  - Dependency injection for FastAPI
  - Connection pooling configuration

- [ ] **Task 2.4**: Test database layer
  - Write unit tests for models
  - Test CRUD operations
  - Verify constraints and indexes

---

### Part 3: Celery Worker (Est: 4-5 hours) - COMPLETE

- [x] **Task 3.1**: Create worker module (src/worker.py)
  - Initialize Celery app with Redis broker
  - Configure JSON serialization, UTC timezone
  - Windows compatibility: threads pool for Python 3.13

- [x] **Task 3.2**: Create async backtest tasks
  - run_single_backtest: Single symbol with retry logic (max 3 retries)
  - run_portfolio_backtest: Batch coordinator using Celery group
  - aggregate_results: Combines multi-symbol results
  - health_check: Worker monitoring

- [x] **Task 3.3**: Add task monitoring
  - task_track_started=True
  - task_time_limit=300s, task_soft_time_limit=240s
  - task_acks_late=True for reliability

- [x] **Task 3.4**: Test worker
  - `celery -A src.worker worker --loglevel=info`
  - `python -c "from src.worker import health_check; print(health_check.delay().get())"`
  - Verified: {"status": "healthy", "timestamp": ..., "worker": "redis://localhost:6379/0"}

---

### Part 4: API Layer Updates (Est: 3-4 hours)

- [ ] **Task 4.1**: Update models (src/models.py)
  - Add "queued" and "running" to JobStatus enum
  - Make sharpe/max_drawdown/total_return optional in BacktestResponse
  - Add fields for created_at, started_at, finished_at

- [ ] **Task 4.2**: Modify POST /jobs endpoint
  - Create job record in database
  - Enqueue task with Celery
  - Return job_id + status="queued" immediately
  - Remove in-memory job_results dict

- [ ] **Task 4.3**: Modify GET /jobs/{job_id} endpoint
  - Query job from database
  - Return status (queued/running/completed/failed)
  - Return results if completed
  - Return error message if failed

- [ ] **Task 4.4**: Add database session management
  - Use FastAPI dependency injection
  - Proper session cleanup
  - Error handling

- [ ] **Task 4.5**: Update health check
  - Check Redis connection
  - Check PostgreSQL connection
  - Return phase=2 in response

---

### Part 5: Testing (Est: 4-5 hours)

- [ ] **Task 5.1**: Update unit tests
  - Mock Celery tasks
  - Test job creation
  - Test status transitions
  - Test database operations

- [ ] **Task 5.2**: Update smoke tests
  - Test job submission (expect instant response)
  - Poll job status until completed
  - Test job retrieval
  - Test error cases

- [ ] **Task 5.3**: Add integration tests
  - Test full async workflow
  - Test worker failure recovery
  - Test database constraints
  - Test concurrent job submission

- [ ] **Task 5.4**: Add load tests
  - Submit 50 jobs concurrently
  - Verify all complete successfully
  - Measure throughput
  - Check for race conditions

---

### Part 6: Documentation & Deployment (Est: 2-3 hours)

- [ ] **Task 6.1**: Update README.md
  - Change status to "Phase 2 - Async Workers"
  - Update Quick Start with Docker Compose
  - Document new API behavior
  - Add architecture diagram

- [ ] **Task 6.2**: Update ARCHITECTURE.md
  - Mark Phase 2 as "COMPLETE"
  - Add actual performance metrics
  - Document lessons learned

- [ ] **Task 6.3**: Update DECISION_LOG.md
  - Add "Impact" section with before/after metrics
  - Document actual vs expected results
  - Note any surprises or challenges

- [ ] **Task 6.4**: Create deployment guide
  - Environment variables
  - Scaling workers (celery -A src.worker worker --concurrency=N)
  - Database backups
  - Monitoring setup

---

### Part 7: Optional Enhancements (If time permits)

- [ ] **Task 7.1**: Add data caching with Parquet
  - Cache Yahoo Finance data
  - Reduce data fetch from 2s to <0.1s
  - LRU eviction policy

- [ ] **Task 7.2**: Add job list endpoint
  - GET /jobs with pagination
  - Filter by status, date range
  - Sort by created_at

- [ ] **Task 7.3**: Add job cancellation
  - POST /jobs/{job_id}/cancel
  - Celery task revocation
  - Clean up database

- [ ] **Task 7.4**: Update web UI
  - Show job status with polling
  - Display job history
  - Add "Cancel" button

---

## Success Criteria Checklist

- [x] All Phase 1 tests still pass (256+ tests)
- [ ] Jobs persist across server restarts (Week 6)
- [x] API returns job_id in <100ms
- [x] Workers process jobs asynchronously
- [ ] Can query job history (Week 6)
- [ ] Smoke tests updated and passing (Week 6)
- [ ] Load test: 50 concurrent jobs complete successfully (Week 7)
- [x] Documentation updated (ARCHITECTURE, DATA_MODEL, DECISION_LOG, IMPLEMENTATION_GUIDE)
- [x] Docker Compose setup working (Redis)
- [x] Zero data loss on worker crashes (task_acks_late, task_reject_on_worker_lost)

---

## Notes

- Start with Part 1 (infrastructure) - get Docker working first
- Don't skip testing - catch issues early
- Keep Phase 1 code intact initially (parallel implementation)
- Test each part independently before integration
- Document challenges and solutions in DECISION_LOG.md
- Re-run benchmarks after completion to measure impact

---

## Getting Started

```bash
# 1. Install dependencies (Python 3.13 compatible versions)
pip install -r requirements.txt

# 2. Start Redis
docker-compose up -d redis

# 3. Start Celery worker
celery -A src.worker worker --loglevel=info

# 4. Test worker health
python -c "from src.worker import health_check; print(health_check.delay().get())"

# 5. Run a portfolio backtest (example)
python -c "
from src.worker import run_portfolio_backtest
result = run_portfolio_backtest.delay(
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    strategy='ma_crossover',
    params={'fast_period': 20, 'slow_period': 50},
    start_date='2023-01-01',
    end_date='2023-12-31'
)
print(result.get(timeout=120))
"
```

# Improvement Plan

> **Context**: Engineering hardening based on external senior review (2026-02-28).
> Goal: address architectural inconsistencies and complete half-finished patterns.

---

## Status

| # | Item | Tier | Status |
|---|------|------|--------|
| 1 | Persist jobs to DB | Foundation | complete |
| 2 | `.env` out of version control | Foundation | complete |
| 3 | Wire up Alembic migrations | Foundation | complete |
| 4 | Wire up Celery end-to-end | Patterns | complete |
| 5 | Move rate limiters to Redis | Patterns | complete |
| 6 | Pydantic Settings (fail-fast config) | Operations | complete |
| 7 | Health check with dependency probes | Operations | complete |
| 8 | Structured logging + request IDs | Operations | complete |
| 9 | ARCHITECTURE.md decision rationale | Polish | complete |
| 10 | Replace Wikipedia scraper with API | Polish | complete |
| 11 | Backtest result diffing | Feature | complete |

---

## Tier 1: Foundation

Fix the core architectural flaw first. Celery wiring (Tier 2) depends on #1.

The root problem: state lives in four inconsistent locations.

| Data | Current Home | Problem |
|------|-------------|---------|
| Backtest jobs | In-memory Python dict | Lost on restart |
| Portfolio results | SQLAlchemy DB | Correct |
| Presets | JSON flat file | Intentional — read-only, no migration needed |
| Rate limiters | In-memory | Reset on restart, multi-worker unsafe |

---

### 1. Persist Jobs to DB

**Problem**: Single backtest jobs live in a plain `dict` in `src/api.py`. Every restart wipes all job history. Portfolio results persist to the DB correctly — the inconsistency is the loudest signal in the codebase.

**What to build**:
- Add `jobs` table to SQLAlchemy schema in `src/db.py`
- Replace `jobs = {}` dict in `src/api.py` with DB reads/writes
- Alembic migration for the new table (see #3)

**Files**:
- `src/db.py` — add `Job` ORM model (`job_id`, `status`, `result` JSON, `created_at`, `completed_at`)
- `src/api.py` — replace dict with DB session calls
- `migrations/versions/` — new migration

**Acceptance criteria**:
- [ ] `GET /api/v1/jobs/{id}` returns correct result after server restart
- [ ] All existing job endpoint tests pass
- [ ] Job history UI stops losing data on restart

---

### 2. `.env` Out of Version Control

**Problem**: `.env` appears tracked in git. API keys and database URLs must never be committed regardless of project scope.

**What to build**:
- Add `.env` to `.gitignore`
- Create `.env.example` with placeholder values

**Files**:
- `.gitignore` — add `.env`
- `.env.example` — create with all required keys

```
DATABASE_URL=sqlite:///./backgrid.db
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=your-key-here
ENABLE_LLM_EXTRACTION=false
```

**Acceptance criteria**:
- [ ] `git status` does not show `.env`
- [ ] `.env.example` committed with placeholder values
- [ ] Existing `.env` removed from git tracking (`git rm --cached .env`)

---

### 3. Wire Up Alembic Migrations

**Problem**: Alembic is in `requirements.txt` but the workflow is incomplete. The `add_equity_curves_to_portfolio.py` in `migrations/` is a manual script, not a proper Alembic revision. Schema changes currently require manual DB recreation.

**What to build**:
- Verify `alembic.ini` and `migrations/env.py` are correctly wired to `src/db.py` models
- Generate proper initial migration from current schema
- Add migration for jobs table (from #1)
- Document the migration workflow in `docs/SETUP.md`

**Files**:
- `migrations/versions/` — initial schema migration + jobs table migration
- `docs/SETUP.md` — add `alembic upgrade head` to setup steps

**Acceptance criteria**:
- [ ] `alembic upgrade head` runs without errors on a fresh SQLite DB
- [ ] `alembic downgrade -1` reverts cleanly
- [ ] `alembic revision --autogenerate` detects schema drift correctly

---

## Tier 2: Complete Half-Finished Patterns

Requires Tier 1 complete. Addresses "right tools, incomplete pattern."

---

### 4. Wire Up Celery End-to-End

*Requires: #1 complete*

**Problem**: Celery and Redis are in `requirements.txt`, `src/worker.py` has task definitions, but portfolio backtests run synchronously inside the HTTP handler. The API blocks until the backtest finishes. This is the single most visible "I got halfway there" signal.

**What to build**:
- `POST /api/v1/backtest/portfolio` enqueues a Celery task instead of running inline
- Returns `202 Accepted` with `batch_id` immediately
- Task updates DB record as it runs: `PENDING → RUNNING → COMPLETE / FAILED`
- `GET /api/v1/backtest/portfolio/{batch_id}` polls job status from DB

**Files**:
- `src/api_portfolio.py` — replace synchronous execution block with `.delay()` call
- `src/worker.py` — wire existing task definitions to actual DB writes
- `src/db.py` — ensure `PortfolioResult` has `status` field

**Acceptance criteria**:
- [ ] `POST /api/v1/backtest/portfolio` returns in <100ms
- [ ] Status transitions from `PENDING` to `COMPLETE` visible via GET
- [ ] Worker crash leaves job in `FAILED` state, not hanging
- [ ] 3 concurrent portfolio backtests run in parallel

---

### 5. Move Rate Limiters to Redis

*Requires: #4 (Redis wired and tested)*

**Problem**: The LLM extraction rate limiter in `src/api_extraction.py` is in-memory. It resets on API restart and doesn't work across multiple worker processes.

**What to build**:
- Replace in-memory counter with Redis key with TTL
- Key: `rate_limit:extraction:{client_ip}`, TTL: 3600s, value: request count
- Use Redis `INCR` + `EXPIRE` for atomic increment (avoids race conditions)

**Files**:
- `src/api_extraction.py` — replace in-memory dict with Redis client calls

**Acceptance criteria**:
- [ ] Rate limit survives API server restart
- [ ] Rate limit shared across multiple Celery workers
- [ ] `429 Too Many Requests` returned correctly after 10 requests/hour

---

## Tier 3: Operational Maturity

Independent of Tiers 1 and 2 — can be done in any order once Tier 1 is complete.

---

### 6. Pydantic Settings (Fail-Fast Config)

**Problem**: Configuration is scattered `os.environ.get()` calls across multiple files. Misconfiguration surfaces at runtime during a request, not at startup.

**What to build**:

```python
# src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./backgrid.db"
    redis_url: str = "redis://localhost:6379"
    anthropic_api_key: str | None = None
    enable_llm_extraction: bool = False

    model_config = ConfigDict(env_file=".env")

settings = Settings()  # fails at import time, not mid-request
```

Replace all `os.environ.get()` callsites with `from src.config import settings`.

**Files**:
- `src/config.py` — new `Settings` class
- `src/api.py`, `src/api_portfolio.py`, `src/api_extraction.py`, `src/worker.py`, `src/db.py` — replace env reads

**Acceptance criteria**:
- [ ] Missing required config raises `ValidationError` at startup, not mid-request
- [ ] All env var reads route through `settings` object
- [ ] Tests pass with existing `conftest.py` approach (env override before import)

---

### 7. Health Check with Dependency Probes

**Problem**: `GET /api/v1/health` returns `{"status": "ok"}` unconditionally. It cannot detect database failure, Redis unavailability, or data source degradation.

**What to build**:

```json
{
  "status": "degraded",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "yfinance": "degraded"
  },
  "uptime_seconds": 3600
}
```

- Return `200` when all critical checks pass
- Return `503` when database or Redis is unreachable
- `yfinance` is non-critical: report `degraded`, not `503`

**Files**:
- `src/api.py` — rewrite health endpoint with active probes
- `tests/test_api.py` — add dependency probe tests

**Acceptance criteria**:
- [ ] Health endpoint actively queries DB and pings Redis
- [ ] Returns `503` when DB is unreachable
- [ ] Returns `200` with `"yfinance": "degraded"` when Yahoo is slow
- [ ] Probe failures don't raise unhandled exceptions

---

### 8. Structured Logging + Request IDs

**Problem**: Logs are bare Python logging calls with no request correlation. Impossible to trace a slow backtest across log lines from different functions.

**What to build**:
- FastAPI middleware that generates a UUID per request and attaches it to request state
- Structured JSON log output via `python-json-logger` or `structlog`
- Thread `request_id` through backtest engine and worker log calls

```json
{"request_id": "abc-123", "event": "backtest_completed", "symbol": "AAPL", "duration_ms": 2341, "level": "info"}
```

**Files**:
- `src/api.py` — add request ID middleware
- `src/backtest.py`, `src/worker.py` — accept and log `request_id` / `task_id`
- `requirements.txt` — add `python-json-logger`

**Acceptance criteria**:
- [ ] Every log line for a request shares the same `request_id`
- [ ] Logs are valid JSON (parseable with `jq`)
- [ ] Worker task logs include `task_id` and `batch_id`
- [ ] No plaintext log lines remain in request handling paths

---

## Tier 4: Polish

---

### 9. ARCHITECTURE.md Decision Rationale

**Problem**: Non-obvious design choices (vanilla JS, JSON presets, interval-based S&P 500 storage, in-memory job store origin) lack documented rationale. Reviewers guess; the author can't explain them confidently.

**What to build**: Add a "Decision Rationale" section to `docs/ARCHITECTURE.md`.

| Decision | Rationale |
|----------|-----------|
| Vanilla JS instead of React | Demonstrates building without framework dependency; scope was manageable at project start. The Strategy Import Wizard is the inflection point where revisiting this choice is warranted. |
| SQLite dev / PostgreSQL prod | SQLAlchemy abstraction handles both. Zero-config local development, production-grade persistence in Docker. |
| JSON for presets instead of DB | Presets are read-only reference data with no user mutation. A versioned flat file is simpler and reviewable in PRs. |
| Interval-based S&P 500 storage | Point-in-time membership queries require range lookups. Interval storage is O(log n) vs. scanning a daily snapshot table. |
| Wikipedia as S&P 500 source | Pragmatic choice for a personal project. Production would use a paid data vendor or SEC filings. |
| In-memory job store (original) | Acceptable during MVP when restarts were frequent and results were ephemeral. Replaced by DB persistence in Phase 3. |

**Files**:
- `docs/ARCHITECTURE.md` — add "Design Decisions" section

**Acceptance criteria**:
- [ ] Every non-obvious decision has a one-sentence rationale
- [ ] Section covers all decisions listed above

---

### 10. Replace Wikipedia Scraper with Wikipedia API

**Problem**: `src/sp500_updater.py` uses Playwright (headless browser) to scrape Wikipedia. Wikipedia has a public structured REST API that returns the same data in JSON. Playwright is a heavyweight dependency that will silently break on any page structure change, with no alerting.

**What to build**:
- Replace Playwright scraper with Wikipedia's MediaWiki API or `rest_v1` endpoint
- Add column header validation on parsed output — raise a descriptive error if expected columns are missing
- Remove `playwright` from `requirements.txt`

**Files**:
- `src/sp500_updater.py` — replace Playwright with `httpx` + `lxml` or `beautifulsoup4`
- `requirements.txt` — remove `playwright`, add `lxml` or `beautifulsoup4` if not present

**Acceptance criteria**:
- [ ] `playwright` removed from dependencies
- [ ] Scraper raises descriptive error when expected column headers are absent
- [ ] Existing S&P 500 data integrity maintained after rewrite
- [ ] `tests/test_sp500_history.py` still passes

---

### 11. Backtest Result Diffing

**Problem**: No way to compare two backtest runs and quantify the P&L impact of parameter changes. Users must mentally compare JSON blobs.

**What to build**:
- `GET /api/v1/backtest/diff?a={batch_id_1}&b={batch_id_2}` endpoint
- Returns parameter deltas alongside metric deltas
- UI panel with side-by-side parameter and metric comparison

```json
{
  "parameter_diff": {
    "commission_bps": {"a": 1, "b": 5, "delta": 4}
  },
  "metric_diff": {
    "total_return": {"a": 0.23, "b": 0.18, "delta": -0.05},
    "sharpe_ratio": {"a": 1.2, "b": 0.9, "delta": -0.3}
  },
  "symbols": ["AAPL", "MSFT"]
}
```

**Files**:
- `src/api_portfolio.py` — add diff endpoint
- `src/models.py` — add `BacktestDiffResponse` model
- `frontend/src/components/` — diff comparison panel
- `tests/test_api_portfolio.py` — diff endpoint tests

**Acceptance criteria**:
- [ ] Diff between two portfolio backtests returns structured delta
- [ ] Diff correctly handles same symbols, different parameters
- [ ] UI displays parameter changes alongside metric changes
- [ ] Diffing runs with different date ranges returns a clear error

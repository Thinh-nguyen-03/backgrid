# Decision Log

Every major technology addition is documented here with measurements and rationale.

---

## Phase 1 - MVP (Completed: 2025-11-09)

### Decision: Start with Synchronous In-Memory MVP

**Date**: 2025-11-09

**Problem**: Need to prove the core backtesting logic works before adding distributed systems complexity.

**Approach**:
- Synchronous FastAPI endpoints
- In-memory job storage (no database)
- Single MA crossover strategy
- Direct yfinance data fetching (no caching)

**What Works**:
- ✅ 99 passing unit tests
- ✅ 5/5 smoke tests passing
- ✅ Backtest latency: 2-3 seconds
- ✅ Full equity curves and metrics (Sharpe, drawdown, returns)
- ✅ Comprehensive error handling

**Measured Performance**:
```
Test: AAPL 2023 (250 trading days)
- Data fetch + backtest: 2.66s
- Sharpe: 0.7739
- Max Drawdown: -16.84%
- Total Return: +11.11%
- Tests: 99/99 passing
```

**Tech Stack Chosen**:
- **FastAPI**: Modern, async-capable, excellent docs
- **pandas**: Industry standard for financial data
- **yfinance**: Free data, good enough for MVP
- **pytest**: Comprehensive testing

**Explicitly NOT Implemented**:
- ❌ Database (SQLite/PostgreSQL) - not needed yet
- ❌ Async workers (Celery) - synchronous is fast enough
- ❌ Data caching - re-fetching is acceptable for MVP
- ❌ Multiple strategies - prove one works first
- ❌ Authentication - single-user mode is fine

**Why These Decisions**:
1. **In-memory storage**: Results are ephemeral during development. Persistence adds no value when iterating.
2. **Synchronous execution**: 2-3s latency is acceptable. No evidence of HTTP timeouts yet.
3. **Single strategy**: Better to prove MA crossover works perfectly than half-implement multiple strategies.
4. **No caching**: Data fetching is fast enough (<3s). Premature optimization.

**Success Criteria Met**:
- [x] End-to-end backtest working
- [x] Accurate metrics calculation
- [x] >95% test coverage of critical paths
- [x] Error handling for invalid inputs
- [x] Documented API (Swagger/ReDoc)

**Git Tag**: `phase-1-mvp`

---

### Decision: Add Simple HTML UI

**Date**: 2025-11-09

**Problem**: Testing via curl/Postman requires command-line knowledge. Need faster iteration for manual testing.

**Approach**:
- Single HTML file served by FastAPI
- Zero dependencies (no npm, no build step)
- Pure vanilla JavaScript
- <30 lines of code + markup

**Implementation**:
- Created [src/ui.py](../src/ui.py) (20 lines total)
- Mounted in FastAPI with `app.include_router(ui_router)`
- Form submits to existing `/api/v1/jobs` endpoint
- Displays raw JSON response

**Benefits**:
- ✅ No build process or npm dependencies
- ✅ Works instantly on `http://localhost:8000`
- ✅ Easier for manual testing than curl
- ✅ Shows real API responses (not hiding complexity)

**Tradeoffs**:
- ❌ No charts/visualization (just JSON)
- ❌ No job history or saved results
- ❌ Basic form validation only

**Why This Approach**:
1. **Zero dependencies**: Adding React/Vue would require build process and bloat
2. **Inline HTML**: Keeping UI in single endpoint avoids static file serving
3. **Raw JSON output**: Shows real API contract, no abstraction
4. **Form over framework**: 20 lines vs thousands for minimal UI

---

## Template for Future Decisions

Every major technology addition must use this template:

```markdown
## Decision: [Technology] (Date: YYYY-MM-DD)

### Problem
[What you measured - be specific with numbers]

### Evidence
```bash
# Include profiler output, benchmark, or error log
```

### Alternatives Considered
- **Alternative 1**: Pros/cons
- **Alternative 2**: Pros/cons

### Decision
Why you chose this technology

### Impact
Before/after metrics showing improvement

### Tradeoffs
What you gave up to get this benefit
```

---

## Pending Decisions (Future Phases)

### Phase 2 Candidates

#### Async Workers (Celery + Redis)
- **Trigger**: Synchronous execution becomes bottleneck (HTTP timeouts >30s or throughput <5 jobs/min)
- **Current status**: Not triggered (2-3s latency is fine)
- **Will measure**: Job queue depth, timeout frequency
- **Estimated**: Only if load increases

#### Database Persistence
- **Trigger**: Need to analyze historical backtest results or share results across sessions
- **Current status**: In-memory is sufficient
- **Options**: PostgreSQL (production) or SQLite (simplicity)
- **Estimated**: When multiple users need access

#### Data Caching
- **Trigger**: Hitting Yahoo Finance rate limits or data fetch >50% of total latency
- **Current status**: Data fetch is fast (<3s)
- **Options**: Parquet files or Redis cache
- **Estimated**: If running hundreds of backtests daily

### Phase 3 Candidates

#### Go gRPC Metrics Service
- **Trigger**: Profiler shows metrics calculation >50% of runtime
- **Current status**: Metrics are fast (part of 2-3s total)
- **Will measure**: cProfile on 1000+ backtests
- **Estimated**: Only if parameter sweeps show bottleneck

#### TimescaleDB
- **Trigger**: PostgreSQL queries on equity curves slow on 10M+ rows
- **Current status**: No database yet
- **Will measure**: Query performance on large datasets
- **Estimated**: Only after Phase 2 database is in use

#### JWT Authentication
- **Trigger**: Multiple users need data isolation
- **Current status**: Single-user development mode
- **Will measure**: Security requirements, user count
- **Estimated**: If deploying to production with >1 user

---

## Principles

1. **No technology without a trigger**: Add complexity only when measurements show the need
2. **Document the "why"**: Every decision must explain the problem being solved
3. **Show your work**: Include benchmarks, profiler output, or error logs
4. **Admit tradeoffs**: Every technology adds complexity - what's the cost?
5. **Be honest**: If something didn't work, document it so you don't repeat it

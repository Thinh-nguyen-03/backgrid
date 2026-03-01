# Architecture

## Phase 1: MVP (COMPLETE)

**Status**: Fully implemented and tested

**Stack**: FastAPI + In-Memory Storage + pandas + yfinance

**Runtime**: Single Python process, synchronous execution

**Goal**: Prove core backtesting logic works end-to-end

```mermaid
graph TD
    UI[Web UI - Vite + Vanilla JS] -->|fetch /api/v1| B[FastAPI API]
    A[Client / curl] -->|POST /jobs| B
    B -->|Synchronous| C[Backtest Engine]
    C -->|fetch_ohlcv| D[yfinance]
    D -->|OHLCV data| C
    C -->|run_backtest| E[Strategy Layer]
    E -->|signals| F[Metrics Calculator]
    F -->|results| G[Database / In-Memory]
    G -->|response| B
    B -->|JSON| UI
    B -->|JSON| A
```

### Components

#### Frontend Layer ([frontend/](../frontend/))
- **Build tool**: Vite with ES module support, HMR, API proxy to FastAPI
- **Architecture**: Vanilla JS class-based components (no framework)
- **Components** (10 modules in `frontend/src/components/`):
  - `Header.js` - App header with version badge
  - `StrategySelector.js` - MA/RSI/Combined strategy selection with dynamic param forms
  - `ExecutionConfig.js` - Position sizing (fixed/ATR), transaction cost controls
  - `PortfolioMode.js` - Single/Portfolio toggle, symbol input, date pickers
  - `ResultsDisplay.js` - KPI cards for single-symbol results
  - `EquityCurveChart.js` - Chart.js wrapper with linear/log scale toggle
  - `PortfolioResults.js` - Summary card, per-symbol results table
  - `TradeLedgerModal.js` - Paginated trade table with filters and CSV export
  - `SymbolSelector.js` - Modal for browsing symbols by sector
  - `JobHistory.js` - localStorage-backed recent backtests panel
- **Services**: API client (`api.js`), localStorage abstraction (`storage.js`), formatters (`utils.js`)
- **State**: Lightweight `AppState` with key-based subscriptions
- **CSS**: Modular BEM methodology, brutalist industrial pop aesthetic (yellow/cyan accents, hard shadows, monospace fonts)
- **Serving**: Production build in `frontend/dist/` served by FastAPI via `app.mount()` for static assets and `FileResponse` for SPA

#### API Layer ([src/api.py](../src/api.py))
- **FastAPI application** with 10+ endpoints
- **Health check**: `GET /api/v1/health` — active DB + Redis probes, returns 503 when DB unreachable
- **Submit job**: `POST /api/v1/jobs` (synchronous, supports optional `config` for execution parameters)
- **Get job**: `GET /api/v1/jobs/{job_id}`
- **Portfolio backtest**: `POST /api/v1/backtest/portfolio` (202 Accepted, async via Celery)
- **Get portfolio**: `GET /api/v1/backtest/portfolio/{batch_id}`
- **Get trades**: `GET /api/v1/backtest/portfolio/{batch_id}/trades`
- **Diff backtests**: `GET /api/v1/backtest/diff?a={id}&b={id}`
- **Multi-strategy**: `POST /api/v1/backtest/multi-strategy`
- **List symbols**: `GET /api/v1/symbols`
- **List sectors**: `GET /api/v1/sectors`
- **Static files**: `app.mount("/assets", StaticFiles(...))` for frontend assets
- **Storage**: PostgreSQL/SQLite for all jobs and portfolio results
- **Error handling**: HTTP 400/404/422/500 with clear messages
- **Logging**: Structured JSON with per-request UUID via `X-Request-ID` header

#### Data Layer ([src/data/](../src/data/))
- **S&P 500 Module** ([src/sp500.py](../src/sp500.py)): Fetches 503 S&P 500 symbols from us500.com (primary) or Wikipedia (fallback), organizes by 11 GICS sectors, 7-day in-memory cache
- **BaseDataLoader**: Abstract interface for all data sources
- **YahooDataLoader**: Yahoo Finance implementation with caching
- **PostgresDataLoader**: RapidTrader database integration
- **Legacy functions**: `fetch_ohlcv()`, `validate_data()` for backward compatibility
- **Caching**: In-memory with configurable TTL (default 1 hour)
- **Connection pooling**: SQLAlchemy QueuePool for PostgreSQL

#### Backtest Engine ([src/backtest.py](../src/backtest.py))
- **calculate_ma_crossover_signals()**: Generate buy/sell signals
- **calculate_returns()**: Build equity curve from signals
- **calculate_sharpe_ratio()**: Annualized Sharpe ratio
- **calculate_max_drawdown()**: Maximum drawdown percentage
- **calculate_total_return()**: Total return percentage
- **run_backtest()**: Orchestrates full backtest execution (legacy)
- **run_backtest_enhanced()**: Advanced backtest with position sizing and transaction costs

#### Strategy Layer ([src/strategies/](../src/strategies/))
- **BaseStrategy**: Abstract interface for all strategies
- **MAStrategy**: Moving average crossover (refactored from backtest.py)
- **RSIStrategy**: RSI mean reversion with 2-of-3 confirmation
- **StrategyManager**: Multi-strategy orchestration with combination methods

#### Position Sizing ([src/position_sizing/](../src/position_sizing/))
- **BasePositionSizer**: Abstract interface for position sizing
- **ATRSizer**: ATR-based volatility sizing (RapidTrader compatible)
- **FixedFractionalSizer**: Fixed percentage of equity

#### Execution ([src/execution/](../src/execution/))
- **TransactionCostModel**: Commission, spread, slippage modeling
- **OrderSimulator**: Fill simulation with configurable logic (next_open, close, vwap)

#### Risk Management ([src/risk/](../src/risk/))
- **MarketRegimeFilter**: SPY 200-SMA bull/bear detection; blocks new long entries in bear markets
- **StopLossManager**: ATR-based stop prices with configurable cooldown after trigger
- **SectorLimitManager**: Enforces max exposure per sector (default 30%); supports per-sector overrides
- **PortfolioHeatTracker**: Tracks aggregate capital at risk; status levels COOL/WARM/HOT/CRITICAL

#### Portfolio Module ([src/portfolio/](../src/portfolio/))
- **PortfolioStateTracker**: Manages positions, cash, sector exposures, realized/unrealized P&L across multiple symbols
- **TradeLedger**: Records all trades with filtering by symbol, strategy, date range; generates summaries
- **Metrics**: Extended metrics including Sortino ratio, Calmar ratio, annualized returns, profit factor

#### Celery Workers ([src/worker.py](../src/worker.py))
- **run_single_backtest**: Task for single-symbol backtest with retry logic
- **run_portfolio_backtest**: Batch coordinator using Celery group for parallel execution
- **aggregate_results**: Combines results from multiple symbol backtests

#### Database Layer ([src/db.py](../src/db.py))
- **Job**: Single backtest job metadata
- **Result**: Single backtest results
- **PortfolioResult**: Portfolio batch metadata and aggregated metrics
- **SymbolResult**: Per-symbol results within a portfolio
- **TradeLedgerEntry**: Individual trade records with P&L tracking
- **Dual database support**: PostgreSQL (production) and SQLite (local dev/testing)
- **Timezone-aware timestamps**: Uses `datetime.now(timezone.utc)` throughout

#### Models ([src/models.py](../src/models.py))
- **Pydantic models** for request/response validation
- **BacktestRequest**: Validates symbol, strategy, params, dates, optional `config` for execution parameters
- **BacktestResponse**: Structures results with metrics
- **PortfolioBacktestRequest**: Multi-symbol batch request
- **PortfolioBacktestResponse**: Aggregated portfolio metrics
- **MultiStrategyRequest**: Combined strategy configuration
- **Enums**: StrategyType, JobStatus, CombinationMethodType

### Performance (Measured)

**Test Case**: AAPL 2023 (250 trading days)
- **Latency**: 2.66s (data fetch + backtest + metrics)
- **Throughput**: ~20 jobs/minute (synchronous)
- **Memory**: <100MB per job
- **Tests**: 380+ passing

**Breakdown**:
- Data fetch from yfinance: ~2s
- MA crossover signals: <0.1s
- Metrics calculation: <0.1s
- JSON serialization: <0.1s

### Testing Strategy

**Total: 650 tests passing (Week 7 complete)**

**Week 7 Test Files** (220 new tests):
- 32 tests: `test_rsi_strategy.py` - RSI calculation (Wilder's smoothing), 2-of-3 confirmation, parameter validation
- 26 tests: `test_strategy_manager.py` - OR/AND/PRIORITY/WEIGHTED combination, attribution tracking
- 18 tests: `test_postgres_loader.py` - Config validation, load/batch_load, symbol metadata
- 23 tests: `test_atr_sizer.py` - ATR calculation accuracy, position sizing constraints, volatility scaling
- 31 tests: `test_transaction_costs.py` - Commission/spread/slippage calculation, effective price, round-trip costs
- 49 tests: `test_risk_management.py` - Market regime filter, stop loss, sector limits, portfolio heat tracker
- 14 tests: `test_integration.py` - API -> Database end-to-end flow, portfolio submit/retrieve, trade ledger
- 27 tests: `test_validation.py` - RapidTrader parameter compatibility, performance targets

**Existing Tests** (430 tests):
- 22 tests: Model validation
- 26 tests: Data fetching (legacy)
- 25 tests: Data loaders (new)
- 32 tests: Backtest logic
- 45 tests: Strategy framework
- 40 tests: Position sizing
- 37 tests: Execution module
- 58 tests: Risk management
- 65+ tests: Portfolio module
- 19 tests: API endpoints (legacy)
- 29 tests: Portfolio API endpoints (Week 6)

**Test Infrastructure**:
- `tests/conftest.py`: Sets `DATABASE_URL=sqlite:///test_backgrid.db` before imports
- SQLite used for all test runs (no PostgreSQL required)
- Mock patching targets `src.data.YahooDataLoader` (where import resolves)
- Performance validated: Single symbol <500ms, signal calculation <10ms

**Smoke Tests (5 total)**:
- Health check
- Job submission
- Job retrieval
- Invalid symbol handling
- Parameter validation

**Coverage**: Critical path coverage >95%

### Limitations (By Design)

1. **No authentication**: Open API
   - Impact: Anyone with access can submit jobs
   - Why acceptable: Single-user development mode

### Deployment

**Development** (defaults to SQLite):
```bash
python src/api.py
```

**Development** (with PostgreSQL):
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/backgrid python src/api.py
```

**Testing** (uses SQLite via conftest.py):
```bash
pytest tests/
python scripts/smoke_test.py
```

**Git Tag**: `phase-1-mvp`

---

## Phase 2: Async Workers (COMPLETE)

**Status**: Week 6 Complete - Portfolio API and database persistence implemented

**Stack**: FastAPI + Celery + Redis + PostgreSQL/SQLite + pandas + yfinance

**Runtime**: Multi-worker parallel execution via Celery

```mermaid
graph TD
    A[Client] -->|POST /backtest/portfolio| B[FastAPI API]
    B -->|create job| C[PostgreSQL]
    B -->|enqueue| D[Redis Queue]
    D --> E1[Celery Worker 1]
    D --> E2[Celery Worker 2]
    D --> E3[Celery Worker N]
    E1 & E2 & E3 -->|fetch| F[yfinance / PostgreSQL]
    E1 & E2 & E3 -->|results| C
    B -->|query| C
    B -->|response| A
```

### Week 6 Implementation (COMPLETE)

#### Portfolio API ([src/api_portfolio.py](../src/api_portfolio.py))
- **POST /api/v1/backtest/portfolio**: Submit portfolio backtest with multiple symbols
- **GET /api/v1/backtest/portfolio/{batch_id}**: Retrieve portfolio results
- **GET /api/v1/backtest/portfolio/{batch_id}/trades**: Query trade ledger with filtering
- **POST /api/v1/backtest/multi-strategy**: Run multiple strategies on single symbol
- **GET /api/v1/symbols**: List available symbols from Yahoo or PostgreSQL

#### Database Tables
- **portfolio_results**: Batch metadata, aggregated metrics, status tracking
- **symbol_results**: Per-symbol results linked to batch
- **trade_ledger**: Individual trades with P&L, filtering support

#### Features
- Synchronous execution with database persistence
- Per-symbol results tracking with error handling
- Trade ledger with symbol/strategy filtering
- Pagination support for large result sets
- Multi-strategy signal combination (OR, AND, PRIORITY, WEIGHTED)
- Dual database support: PostgreSQL (production) or SQLite (local dev/testing)
- Timezone-aware timestamps using `datetime.now(timezone.utc)`
- SQLAlchemy 2.0.25+ with modern `sqlalchemy.orm.declarative_base`

### Week 5 Implementation (COMPLETE)

#### Celery Workers ([src/worker.py](../src/worker.py))
- **run_single_backtest**: Task with max 3 retries, 5s retry delay
- **run_portfolio_backtest**: Batch coordinator using Celery group for parallel dispatch
- **aggregate_results**: Combines multi-symbol results into portfolio metrics
- **health_check**: Worker monitoring task
- **Configuration**: Redis broker at localhost:6379/0, JSON serialization, UTC timezone
- **Windows Compatibility**: Uses threads pool on Windows (prefork has Python 3.13 issues)

#### Portfolio Module ([src/portfolio/](../src/portfolio/))
- **PortfolioStateTracker**: Manages positions, cash, sector exposures, realized/unrealized P&L
- **TradeLedger**: Records all trades with filtering by symbol, strategy, date range
- **Extended Metrics**: Sortino ratio, Calmar ratio, profit factor, expectancy, payoff ratio

### Performance (Measured)

**Test Case**: 3-symbol portfolio backtest
- **Total runtime**: ~8s (including data fetch)
- **Database write**: <100ms per symbol
- **Trade ledger query**: <50ms with filtering

**Test Case**: Health check task
- **Task dispatch**: <50ms
- **Worker startup**: ~2s (threads pool on Windows)
- **Result retrieval**: <100ms

---

## Phase 3: Engineering Hardening (COMPLETE)

**Status**: Complete (2026-02-28)

**Goal**: Address architectural inconsistencies and complete half-finished patterns from external senior review.

### Changes Implemented

| # | Change | Files |
|---|--------|-------|
| 1 | Persist single backtest jobs to DB | `src/db.py`, `src/api.py` |
| 2 | `.env` out of version control | `.gitignore`, `.env.example` |
| 3 | Alembic migrations wired end-to-end | `migrations/`, `docs/SETUP.md` |
| 4 | Celery portfolio backtest async (202 + poll) | `src/api_portfolio.py`, `src/worker.py`, `src/portfolio/runner.py` |
| 5 | Redis-backed rate limiter for LLM extraction | `src/api_extraction.py` |
| 6 | Pydantic Settings — centralized config | `src/config.py` |
| 7 | Health check with dependency probes | `src/api.py` |
| 8 | Structured JSON logging + per-request IDs | `src/logging_config.py`, `src/api.py` |
| 9 | Design Decisions documented | `docs/ARCHITECTURE.md` |
| 10 | Wikipedia scraper hardened, `playwright` removed | `src/sp500_updater.py`, `requirements.txt` |
| 11 | Backtest diff endpoint | `src/api_portfolio.py`, `src/models.py` |
| 12 | S&P 500 auto-update background scheduler; API key gate removed from update endpoint | `src/api_sp500_history.py`, `src/api.py` |

### New Modules

- **`src/config.py`**: Pydantic Settings class; single source of truth for all env vars. Reads `.env` at import time so misconfiguration raises at startup.
- **`src/logging_config.py`**: JSON formatter + `configure_logging()`. Each log line is a JSON object with `timestamp`, `level`, `logger`, `message`, `request_id`.
- **`src/portfolio/runner.py`**: Extracted portfolio backtest execution logic, shared between the API (sync path) and Celery worker (async path) to avoid circular imports.

---

## Phase 4: Performance & Scale (FUTURE)

**Triggers** (any of these):
- Profiler shows metrics calculation >50% of runtime
- Database queries >500ms on 10M+ rows
- Multiple users need data isolation

**Triggers** (any of these):
- Multiple concurrent users need data isolation
- Profiler shows bottlenecks in metrics calculation or DB queries

**Stack Additions**: Go gRPC + TimescaleDB + JWT Auth

```mermaid
graph TD
    A[Client] -->|JWT token| B[FastAPI API]
    B -->|enqueue| C[Redis Queue]
    C --> D[Celery Workers]
    D -->|gRPC| E[Go Metrics Service]
    E -->|fast metrics| D
    D -->|TimescaleDB| F[(Hypertables)]
    B -->|query| F
```

### Potential Additions (Only If Needed)

**Go gRPC Metrics Service**:
- Parallel calculation of Sharpe/Sortino/MaxDD
- Expected 5-10x speedup over Python
- Only if profiler proves metrics are bottleneck

**TimescaleDB**:
- Hypertables for equity curves and prices
- Automatic partitioning by time
- Only if PostgreSQL queries slow on large datasets

**JWT Authentication**:
- User isolation in database
- API rate limiting per user
- Only if multiple users need the platform

### Complexity Receipts Required

Each addition requires:
- Profiler output or benchmark showing bottleneck
- Comparison of alternatives
- Before/after metrics

---

## Design Decisions

Non-obvious choices and the reasoning behind them.

| Decision | Rationale |
|----------|-----------|
| Vanilla JS instead of React | Demonstrates building without framework dependency; the scope was manageable at project start. The Strategy Import Wizard is the inflection point where revisiting this choice is warranted. |
| SQLite dev / PostgreSQL prod | SQLAlchemy's abstraction handles both. Zero-config local development; production-grade persistence in Docker with no application-layer changes required. |
| JSON for presets instead of DB | Presets are read-only reference data with no user mutation. A versioned flat file is simpler, reviewable in PRs, and requires no migration when changed. |
| Interval-based S&P 500 storage | Point-in-time membership queries require range lookups. Storing `[start, end]` intervals enables O(log n) lookups per symbol vs. scanning a daily snapshot table. |
| Wikipedia as S&P 500 source | Pragmatic choice for a personal project. Production would use a paid data vendor (CRSP, Refinitiv) or parse SEC filings. The scraper raises a descriptive error on unexpected page structure. Updates run automatically via an asyncio background task (checks daily, scrapes when data is ≥7 days old); the manual update button in the UI remains available. |
| In-memory job store (original) | Acceptable during MVP when restarts were frequent and results were ephemeral. Replaced by full DB persistence in Phase 3 — both single jobs and portfolio batches now survive restarts. |
| Celery with threads pool on Windows | Python 3.13 broke the `prefork` pool on Windows. `--pool=threads` restores worker functionality with a small throughput tradeoff acceptable for this use case. |
| Pydantic Settings at module level | `settings = Settings()` raises `ValidationError` at import time if required env vars are missing, surfacing misconfiguration at startup rather than mid-request. |
| Fail-open rate limiter | The Redis rate limiter on LLM extraction allows the request when Redis is unavailable (`_get_redis()` returns `None`). Refusing requests due to a monitoring failure would be worse than no rate limiting. |

---

## Core Principles

1. **No technology without a trigger**: Complexity must be justified by measurements
2. **Start simple**: Phase 1 proves the logic works
3. **Evolve based on need**: Add features only when current system shows limits
4. **Document decisions**: Every change recorded in DECISION_LOG.md
5. **Git history shows evolution**: Tags for each phase
6. **Be honest in README**: Status reflects current implementation, not aspirations

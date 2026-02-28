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
- 99 passing unit tests
- 5/5 smoke tests passing
- Backtest latency: 2-3 seconds
- Full equity curves and metrics (Sharpe, drawdown, returns)
- Comprehensive error handling

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
- Database (SQLite/PostgreSQL) - not needed yet
- Async workers (Celery) - synchronous is fast enough
- Data caching - re-fetching is acceptable for MVP
- Multiple strategies - prove one works first
- Authentication - single-user mode is fine

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
- No build process or npm dependencies
- Works instantly on `http://localhost:8000`
- Easier for manual testing than curl
- Shows real API responses (not hiding complexity)

**Tradeoffs**:
- No charts/visualization (just JSON)
- No job history or saved results
- Basic form validation only

**Why This Approach**:
1. **Zero dependencies**: Adding React/Vue would require build process and bloat
2. **Inline HTML**: Keeping UI in single endpoint avoids static file serving
3. **Raw JSON output**: Shows real API contract, no abstraction
4. **Form over framework**: 20 lines vs thousands for minimal UI

---

---

## Phase 2 - Week 1: Strategy Framework (2026-02-01)

### Decision: Implement Pluggable Strategy Architecture

**Date**: 2026-02-01

**Problem**: Phase 1 MVP only supports MA crossover strategy hardcoded in backtest.py. RapidTrader integration requires:
- RSI mean reversion strategy
- Multi-strategy combinations
- Extensible architecture for future strategies

**Approach**:
- Created abstract BaseStrategy class defining signal interface
- Implemented RSI strategy with 2-of-3 confirmation logic
- Refactored MA strategy to use new interface
- Built StrategyManager for multi-strategy orchestration

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/strategies/base.py | Abstract strategy interface, Signal enum | ~90 |
| src/strategies/rsi_strategy.py | RSI with Wilder's smoothing, confirmation | ~130 |
| src/strategies/ma_strategy.py | Refactored MA crossover | ~95 |
| src/strategies/strategy_manager.py | Multi-strategy combination | ~220 |
| tests/test_strategies.py | Comprehensive unit tests | ~450 |

**Key Design Decisions**:

1. **Signal Enum over Numeric**: Using Signal.BUY/SELL/HOLD instead of 1/0/-1 improves readability and type safety

2. **Wilder's Smoothing for RSI**: Matches TA-Lib reference using exponential weighted mean with alpha=1/period

3. **Confirmation Logic**: RSI requires min_confirmation_count signals within confirmation_window bars before triggering

4. **Combination Methods**: Strategy manager supports OR, AND, PRIORITY, WEIGHTED signal combination

5. **Backward Compatibility**: MA strategy accepts both old params (fast/slow) and new (fast_period/slow_period)

**RapidTrader Parameters Supported**:
```python
RSI_DEFAULTS = {
    "rsi_period": 14,           # RT_RSI_PERIOD
    "oversold_threshold": 30,   # Buy signal
    "overbought_threshold": 55, # Sell signal (RT uses 55, not 70)
    "confirmation_window": 3,   # RT_CONFIRM_WINDOW
    "min_confirmation_count": 2 # RT_CONFIRM_MIN_COUNT
}
```

**Test Coverage**:
- 45+ new tests for strategy framework
- Tests for each combination method
- Edge cases: insufficient data, invalid params, empty managers

**Performance Targets Met**:
- Signal calculation: < 10ms for 252 trading days
- Memory: Negligible overhead from strategy objects

**What Was NOT Implemented (Intentionally Deferred)**:
- Position sizing (Week 3)
- Transaction costs (Week 3)
- Market regime filter (Week 4)
- Stop loss management (Week 4)

**Success Criteria**:
- [x] RSI calculation matches Wilder's smoothing method
- [x] 2-of-3 confirmation logic working
- [x] Multi-strategy combination methods working
- [x] All unit tests passing
- [x] Backward compatible with Phase 1 API

---

## Phase 2 - Week 2: Data Loader Abstraction (2026-02-01)

### Decision: Implement Pluggable Data Loader Architecture

**Date**: 2026-02-01

**Problem**: Phase 1 MVP uses yfinance directly with no abstraction. RapidTrader integration requires:
- Connection to PostgreSQL `bars_daily` table
- Batch loading for 500+ symbols
- In-memory caching with TTL
- Consistent interface across data sources

**Approach**:
- Created abstract BaseDataLoader class defining load interface
- Implemented YahooDataLoader (refactored from data.py)
- Implemented PostgresDataLoader for RapidTrader database
- Built-in caching with configurable TTL

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/data/base_loader.py | Abstract loader interface, caching, validation | ~150 |
| src/data/yahoo_loader.py | Yahoo Finance implementation | ~120 |
| src/data/postgres_loader.py | PostgreSQL with connection pooling | ~180 |
| tests/test_data_loaders.py | Comprehensive unit tests | ~200 |

**Key Design Decisions**:

1. **Abstract Base Class**: Enables swapping data sources without changing backtest code

2. **Connection Pooling**: PostgresDataLoader uses SQLAlchemy QueuePool with 5 connections

3. **Built-in Caching**: Each loader caches data with configurable TTL (default 1 hour)

4. **Batch Loading**: `load_batch()` method for efficient multi-symbol fetching

5. **RapidTrader Schema Compatibility**: PostgresDataLoader matches `bars_daily` table structure

**RapidTrader Database Tables Supported**:
```sql
bars_daily: symbol, d (date), open, high, low, close, volume
symbols: symbol, name, sector, sub_sector, is_active
```

**Success Criteria**:
- [x] Abstraction allows swapping Yahoo for PostgreSQL
- [x] Connection pooling prevents database connection exhaustion
- [x] Batch loading more efficient than individual queries
- [x] Caching reduces repeated data fetches
- [x] All unit tests passing

---

## Phase 2 - Week 3: Position Sizing & Transaction Costs (2026-02-01)

### Decision: Implement ATR Position Sizing and Transaction Cost Modeling

**Date**: 2026-02-01

**Problem**: Phase 1 uses fixed position sizes with no transaction costs. RapidTrader requires:
- ATR-based position sizing for volatility adjustment
- Transaction cost modeling (commission, spread, slippage)
- Realistic order execution simulation

**Approach**:
- Created position sizing module with ATR and fixed fractional sizers
- Implemented transaction cost model matching RapidTrader parameters
- Built order simulator with configurable fill logic

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/position_sizing/base_sizer.py | Abstract sizer interface | ~80 |
| src/position_sizing/atr_sizer.py | ATR-based volatility sizing | ~130 |
| src/position_sizing/fixed_sizer.py | Fixed fractional sizing | ~90 |
| src/execution/transaction_costs.py | Cost modeling | ~170 |
| src/execution/order_simulator.py | Fill simulation | ~220 |
| tests/test_position_sizing.py | Position sizing tests | ~280 |
| tests/test_execution.py | Execution tests | ~300 |

**Key Design Decisions**:

1. **ATR Calculation**: Uses Wilder's smoothing (alpha=1/period) matching TA-Lib

2. **Risk-Based Sizing**: Position size = (equity * risk_per_trade) / (ATR * multiplier)

3. **Transaction Cost Components**:
   - Commission: $0.005/share (min $1.00)
   - Spread: 5 bps
   - Slippage: 2 bps + volume impact

4. **Fill Logic Options**:
   - `next_open`: Fill at next bar's open (default, most realistic)
   - `close`: Fill at signal bar's close
   - `vwap`: Approximate VWAP

5. **Enhanced Backtest Engine**: `run_backtest_enhanced()` integrates all components

**RapidTrader Parameters Supported**:
```python
POSITION_SIZING = {
    "atr_period": 14,        # RT_ATR_LOOKBACK
    "risk_per_trade": 0.05,  # RT_PCT_PER_TRADE
    "atr_multiplier": 3.0,   # RT_ATR_STOP_K
}

TRANSACTION_COSTS = {
    "commission_per_share": 0.005,
    "spread_bps": 5.0,
    "slippage_bps": 2.0,
}
```

**Test Coverage**:
- 40+ tests for position sizing
- 30+ tests for execution module
- Edge cases: zero equity, invalid params, insufficient data

**Performance Targets Met**:
- ATR calculation: < 5ms for 252 trading days
- Position sizing: < 1ms per calculation
- Cost calculation: < 0.1ms per trade

**Success Criteria**:
- [x] ATR calculation matches Wilder's method
- [x] Position sizes respect risk limits
- [x] Transaction costs < 0.5% for liquid stocks
- [x] Fill simulation realistic
- [x] All unit tests passing

---

## Phase 2 - Week 4: Risk Management (2026-02-01)

### Decision: Implement Comprehensive Risk Management Module

**Date**: 2026-02-01

**Problem**: Phase 2 Week 1-3 implemented strategy framework, data loaders, position sizing, and transaction costs. RapidTrader integration still requires:
- Market regime filtering to avoid bear market entries
- ATR-based stop losses with cooldown periods
- Sector concentration limits to ensure diversification
- Portfolio heat tracking to limit aggregate risk exposure

**Approach**:
- Created `src/risk/` module with four components
- Each component follows established patterns (abstract base classes, dataclasses for results)
- Comprehensive parameter validation and logging
- Full test coverage

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/risk/__init__.py | Module exports | ~45 |
| src/risk/market_regime.py | SPY 200-SMA bull/bear filter | ~250 |
| src/risk/stop_loss.py | ATR-based stops with cooldown | ~350 |
| src/risk/sector_limits.py | Sector concentration limits | ~280 |
| src/risk/portfolio_heat.py | Aggregate risk exposure tracking | ~300 |
| tests/test_risk.py | Comprehensive unit tests | ~500 |

**Key Design Decisions**:

1. **Market Regime Filter**:
   - Uses SPY 200-SMA as default reference (matches RapidTrader)
   - Supports configurable buffer zone around SMA for neutral classification
   - Tracks regime duration for trend strength assessment
   - `get_bull_gate_series()` matches RapidTrader's bull_gate concept

2. **Stop Loss Manager**:
   - ATR-based stop calculation using Wilder's smoothing
   - Configurable cooldown period after stops trigger (default 1 day)
   - Position state tracking for trailing stop support
   - Stop trigger history for post-trade analysis

3. **Sector Limit Manager**:
   - Default 30% max exposure per sector (RT_MAX_EXPOSURE_PER_SECTOR)
   - Support for custom per-sector overrides
   - Warning threshold before limit reached
   - Compliance checking across all sectors

4. **Portfolio Heat Tracker**:
   - Heat = sum of position risks (entry - stop) * shares
   - Status levels: COOL, WARM, HOT, CRITICAL
   - Maximum positions limit (default 20)
   - Detailed heat reports with position breakdown

**RapidTrader Parameters Supported**:
```python
MARKET_REGIME = {
    "sma_period": 200,            # RT_MARKET_FILTER_SMA
    "reference_symbol": "SPY",    # RT_MARKET_FILTER_SYMBOL
}

STOP_LOSS = {
    "atr_multiplier": 3.0,        # RT_ATR_STOP_K
    "cooldown_days": 1,           # RT_COOLDOWN_DAYS_ON_STOP
}

SECTOR_LIMITS = {
    "max_sector_exposure": 0.30,  # RT_MAX_EXPOSURE_PER_SECTOR
}

PORTFOLIO_HEAT = {
    "max_heat_pct": 0.06,         # 6% max capital at risk
    "max_positions": 20,
}
```

**Test Coverage**:
- 60+ tests across all risk components
- Edge cases: insufficient data, invalid parameters, boundary conditions
- Integration tests for combined risk check workflow

**What Was NOT Implemented (Intentionally Deferred)**:
- Correlation checks between positions (Week 5 candidate)
- Dynamic position sizing based on current heat (can be added)
- VIX-based regime filtering (enhancement)

**Success Criteria**:
- [x] Market filter blocks trades in bear markets
- [x] Stop losses trigger correctly with ATR-based calculation
- [x] Cooldown periods enforced after stop triggers
- [x] Sector limits enforced (30% max per sector)
- [x] Portfolio heat tracking limits aggregate risk
- [x] All unit tests passing

---

## Phase 2 - Week 5: Portfolio Aggregation (2026-02-03)

### Decision: Implement Portfolio State Tracking and Celery Workers

**Date**: 2026-02-03

**Problem**: Phase 2 Week 1-4 implemented individual components (strategies, data loaders, position sizing, risk management) but lacked:
- Multi-symbol portfolio state tracking
- Centralized trade ledger for analysis
- Extended performance metrics (Sortino, Calmar)
- Parallel backtest execution for 500+ symbols

**Approach**:
- Created `src/portfolio/` module with three components
- Implemented Celery worker tasks for parallel execution
- Extended metrics beyond Sharpe/MaxDD/TotalReturn

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/portfolio/__init__.py | Module exports | ~35 |
| src/portfolio/portfolio.py | PortfolioStateTracker, PositionState, PortfolioSnapshot | ~250 |
| src/portfolio/trade_ledger.py | TradeLedger, TradeSummary, filtering/aggregation | ~200 |
| src/portfolio/metrics.py | Sortino, Calmar, annualized return, trade metrics | ~280 |
| src/worker.py | Celery tasks for parallel backtesting | ~150 |
| tests/test_portfolio.py | Comprehensive unit tests | ~500 |

**Key Design Decisions**:

1. **PortfolioStateTracker**:
   - Tracks positions, cash, sector exposures across multiple symbols
   - Enforces max_positions limit (default 20)
   - Enforces max_sector_exposure (default 30%)
   - Maintains realized/unrealized P&L separately
   - Generates point-in-time snapshots for equity curve

2. **TradeLedger**:
   - Wraps existing TradeRecord from backtest.py (no duplication)
   - Supports filtering by symbol, strategy, date range, P&L
   - Generates summaries by symbol or strategy
   - Computes profit factor, win rate, average hold days

3. **Extended Metrics**:
   - Sortino ratio: Penalizes only downside deviation
   - Calmar ratio: Annualized return / max drawdown
   - Profit factor: Gross profits / gross losses
   - Expectancy: (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

4. **Celery Workers**:
   - `run_single_backtest`: Task with retry logic (max 3 retries)
   - `run_portfolio_backtest`: Uses Celery group for parallel dispatch
   - `aggregate_results`: Combines multi-symbol results
   - Redis broker/backend at localhost:6379/0

**RapidTrader Integration**:
- Portfolio constraints match RT parameters:
  - max_sector_exposure: 0.30 (RT_MAX_EXPOSURE_PER_SECTOR)
  - max_positions: 20 (practical limit for diversified portfolio)
- Metrics support validation against RapidTrader historical results

**Test Coverage**:
- 65+ new tests for portfolio module
- Tests for all dataclasses, tracker operations, ledger filtering
- Tests for each metric function with edge cases
- Tests for result aggregation

**What Was NOT Implemented (Intentionally Deferred)**:
- Database persistence of portfolio results (Week 6)
- API endpoints for portfolio backtests (Week 6)
- Correlation-based position limits (future enhancement)
- Real-time position monitoring (out of scope)

**Success Criteria**:
- [x] PortfolioStateTracker manages multi-symbol positions
- [x] TradeLedger records and filters all trades
- [x] Extended metrics (Sortino, Calmar) implemented
- [x] Celery workers ready for parallel execution
- [x] All unit tests passing

---

## Phase 2 - Week 5: Celery Worker Fixes (2026-02-03)

### Decision: Use Threads Pool on Windows for Python 3.13 Compatibility

**Date**: 2026-02-03

**Problem**: Celery workers with the default `prefork` pool failed on Windows with Python 3.13. The error:
```
ValueError: not enough values to unpack (expected 3, got 0)
  File "celery/app/trace.py", line 664, in fast_trace_task
    tasks, accept, hostname = _loc
```

The `_loc` thread-local variable was not being initialized properly in child processes when using the spawn method (required on Windows).

**Evidence**:
- Celery 5.3.4 failed with prefork pool on Python 3.13
- Upgraded to Celery 5.6.2 - same error persisted
- Issue is in billiard's process spawning not initializing `_loc`

**Alternatives Considered**:
1. **Downgrade to Python 3.11/3.12**: Would require user to change their environment
2. **Use solo pool**: Works but provides no concurrency
3. **Use threads pool**: Full concurrency using threads instead of processes

**Decision**: Configure Celery to use `threads` pool on Windows via `app.conf.worker_pool = "threads"`. This is applied conditionally based on `sys.platform == "win32"`.

**What Was Changed**:

| File | Change |
|------|--------|
| src/worker.py | Added conditional threads pool for Windows |
| requirements.txt | Updated celery>=5.4.0, psycopg2-binary>=2.9.11, pydantic>=2.5.3 |

**Configuration Added**:
```python
if sys.platform == "win32":
    app.conf.worker_pool = "threads"

app.conf.update(
    broker_connection_retry_on_startup=True,  # Silence deprecation warning
)
```

**Impact**:
- Health check task executes successfully
- Workers start with 12 threads (matching CPU cores)
- Task dispatch and result retrieval work correctly

**Tradeoffs**:
- Threads pool doesn't provide true process isolation (GIL limits CPU parallelism)
- For backtesting workloads (I/O bound with yfinance), threads are sufficient
- On Linux/macOS, prefork pool still used for better CPU parallelism

**Dependency Updates**:
- `celery>=5.4.0`: Required for Python 3.13 compatibility improvements
- `psycopg2-binary>=2.9.11`: First version with pre-built wheels for Python 3.13
- `pydantic>=2.5.3`: Avoids Rust compilation requirement on Python 3.13

---

## Phase 2 - Week 6: API & Database Extensions (2026-02-03)

### Decision: Implement Portfolio API with Synchronous Database Persistence

**Date**: 2026-02-03

**Problem**: Phase 2 Week 5 implemented Celery workers and portfolio module, but lacked:
- API endpoints for submitting and retrieving portfolio backtests
- Database persistence for portfolio results
- Trade ledger query capabilities
- Multi-strategy backtest API

**Approach**:
- Created new API router (`src/api_portfolio.py`) for portfolio endpoints
- Extended SQLAlchemy models for portfolio data persistence
- Added Alembic migration for new tables
- Implemented synchronous execution with database writes

**What Was Built**:

| File | Purpose | Lines |
|------|---------|-------|
| src/api_portfolio.py | Portfolio API endpoints | ~450 |
| src/models.py | Extended Pydantic models | ~350 |
| src/db.py | Extended SQLAlchemy models + helpers | ~420 |
| migrations/versions/add_portfolio_tables_week6.py | Alembic migration | ~100 |
| migrations/env.py | Alembic config with SQLite default | ~90 |
| tests/test_api_portfolio.py | Comprehensive unit tests | ~575 |
| tests/conftest.py | Test environment setup (SQLite) | ~6 |

**Key Design Decisions**:

1. **Synchronous Execution with Database Persistence**:
   - Portfolio backtests run synchronously for simplicity
   - Results written to PostgreSQL/SQLite as they complete
   - Future: Can switch to async Celery execution for large portfolios

2. **Dual Database Support (PostgreSQL + SQLite)**:
   - PostgreSQL for production, SQLite for local development and testing
   - `DATABASE_URL` environment variable selects database
   - SQLite engine uses `check_same_thread=False` for FastAPI compatibility
   - PostgreSQL engine uses connection pooling (pool_size=5, max_overflow=10)
   - Alembic migrations default to SQLite when `DATABASE_URL` is not set

3. **Batch ID Generation**:
   - Format: `portfolio-{timestamp}-{short_uuid}`
   - Enables unique identification and retrieval
   - Includes timestamp for chronological ordering

4. **Trade Ledger Design**:
   - Linked to portfolio via `batch_id` foreign key
   - CASCADE delete when portfolio deleted
   - Indexed on symbol, strategy, entry_date for efficient queries

5. **Multi-Strategy API**:
   - Reuses existing StrategyManager from Week 1
   - Supports all combination methods (OR, AND, PRIORITY, WEIGHTED)
   - Returns combined metrics for strategy ensemble

6. **Symbols API**:
   - Yahoo source: Returns curated list of popular symbols
   - PostgreSQL source: Queries RapidTrader symbols table
   - Graceful fallback if PostgreSQL unavailable

7. **Timezone-Aware Timestamps**:
   - All `datetime.utcnow()` replaced with `datetime.now(timezone.utc)`
   - Eliminates Python 3.12+ deprecation warnings
   - Helper function `_utcnow()` in db.py for model defaults

8. **Modern SQLAlchemy Imports**:
   - `declarative_base` imported from `sqlalchemy.orm` (not deprecated `sqlalchemy.ext.declarative`)
   - SQLAlchemy >= 2.0.25 required for Python 3.13 compatibility

**RapidTrader Integration Points**:
- PostgreSQL loader can query RapidTrader `bars_daily` table
- Symbols API connects to `symbols` table for universe
- Transaction costs match RapidTrader parameters

**Test Coverage**:
- 29 tests for portfolio API (all passing)
- Tests for all endpoints, error cases, pagination
- Database integration tests verify persistence with SQLite
- `tests/conftest.py` sets `DATABASE_URL=sqlite:///test_backgrid.db` before imports
- Mock patching targets `src.data.YahooDataLoader` (where the import resolves from)

**What Was NOT Implemented (Intentionally Deferred)**:
- Async execution via Celery (can be added if needed)
- Real-time progress updates (WebSocket)
- Result caching (Redis)
- Authentication/authorization

**Success Criteria**:
- [x] POST /api/v1/backtest/portfolio accepts multi-symbol requests
- [x] Results persisted to database with foreign key relationships
- [x] GET endpoints return results with per-symbol breakdown
- [x] Trade ledger supports filtering by symbol/strategy
- [x] Multi-strategy backtest combines signals correctly
- [x] Symbols API returns data from Yahoo or PostgreSQL
- [x] All unit tests passing (29 tests)
- [x] SQLite support for local dev and testing (no PostgreSQL required)
- [x] No deprecation warnings in test output

---

## Phase 2 - Week 6: Compatibility Fixes (2026-02-07)

### Decision: SQLAlchemy Version Update for Python 3.13

**Date**: 2026-02-07

**Problem**: Running `alembic upgrade head` on Python 3.13 failed with:
```
AssertionError: Class SQLCoreOperations directly inherits TypingOnly but has additional attributes
```

**Evidence**: SQLAlchemy 2.0.23 is incompatible with Python 3.13's type system changes.

**Decision**: Updated `requirements.txt` from `SQLAlchemy==2.0.23` to `SQLAlchemy>=2.0.25`. Version 2.0.25+ includes fixes for Python 3.13 compatibility.

**Impact**: Alembic migrations and all database operations now work on Python 3.13.

---

### Decision: Default to SQLite for Local Development

**Date**: 2026-02-07

**Problem**: Tests and local development required a running PostgreSQL instance, creating unnecessary friction. Running `alembic upgrade head` without `DATABASE_URL` set caused `KeyError: 'url'`.

**Evidence**:
- Test suite failed with `psycopg2.OperationalError: password authentication failed`
- Alembic crashed when `DATABASE_URL` wasn't configured

**Alternatives Considered**:
1. **Require PostgreSQL locally**: Increases setup friction, Docker dependency
2. **Default to SQLite**: Zero-config, works everywhere

**Decision**: Default to SQLite when `DATABASE_URL` is not set:
- `migrations/env.py`: `database_url = os.getenv("DATABASE_URL", "sqlite:///backgrid.db")`
- `src/db.py`: Conditional engine creation (SQLite uses `check_same_thread=False`, PostgreSQL uses connection pooling)
- `tests/conftest.py`: Forces `DATABASE_URL=sqlite:///test_backgrid.db`

**Impact**: Local development and testing work without PostgreSQL. Production deployments set `DATABASE_URL` to PostgreSQL.

---

### Decision: Fix datetime.utcnow() Deprecation Warnings

**Date**: 2026-02-07

**Problem**: 45 deprecation warnings in test output:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated, use datetime.datetime.now(datetime.timezone.utc) instead
```

**Decision**: Replaced all `datetime.utcnow()` with `datetime.now(timezone.utc)`:
- `src/db.py`: Added `_utcnow()` helper function for model column defaults
- `src/api_portfolio.py`: Updated all timestamp generation

Also fixed `declarative_base` import to use `sqlalchemy.orm.declarative_base` instead of deprecated `sqlalchemy.ext.declarative.declarative_base`.

**Impact**: Zero deprecation warnings in test output. Future-proof for Python 3.14+.

---

## Week 7: Testing & Validation (Completed: 2026-02-07)

### Decision: Comprehensive Test Suite for Production Readiness

**Date**: 2026-02-07

**Problem**: Phase 2 implementation lacked thorough unit, integration, and validation tests. Needed confidence that:
- RSI strategy matches Wilder's smoothing formula exactly
- Multi-strategy combination logic works for all methods (OR/AND/PRIORITY/WEIGHTED)
- Transaction cost calculations align with RapidTrader specifications
- Risk management modules enforce constraints correctly
- End-to-end API -> Database flow persists data correctly

**Approach**:
Created 8 new test files with 220 tests covering:
1. **Unit Tests**: Individual component validation (RSI, strategy manager, data loaders, position sizing, transaction costs, risk management)
2. **Integration Tests**: API endpoint -> database persistence -> retrieval flow
3. **Validation Tests**: RapidTrader parameter compatibility and performance targets

**Test Files Created**:
- `tests/test_rsi_strategy.py` (32 tests): RSI calculation accuracy, Wilder's smoothing verification, 2-of-3 confirmation logic
- `tests/test_strategy_manager.py` (26 tests): Signal combination methods, attribution tracking, real MA+RSI interaction
- `tests/test_postgres_loader.py` (18 tests): Config validation, batch loading, metadata queries
- `tests/test_atr_sizer.py` (23 tests): ATR calculation, position size constraints, volatility scaling
- `tests/test_transaction_costs.py` (31 tests): Commission/spread/slippage formulas, effective price calculation
- `tests/test_risk_management.py` (49 tests): Market regime filter, stop loss manager, sector limits, portfolio heat
- `tests/test_integration.py` (14 tests): End-to-end API flows, trade ledger persistence, error handling
- `tests/test_validation.py` (27 tests): RapidTrader parameter validation, performance benchmarks

**Results**:
```
Total tests: 650 passing (220 new + 430 existing)
Test runtime: ~8 seconds
Coverage: Critical path >95%
Performance: Single symbol <500ms, signal calculation <10ms
```

**Key Findings**:
- RSI with pure uptrend/downtrend data needs noise to avoid `avg_loss=0` causing `fillna(50)`
- Mock patching for `YahooDataLoader` must target `src.data.YahooDataLoader` (where defined), not `src.api_portfolio.YahooDataLoader` (lazy import)
- Numpy array comparison `Signal.SELL in signals.values` fails; use `(signals == Signal.SELL).any()`
- Transaction cost formula: `spread = trade_value * (bps/10000) / 2`, `slippage = trade_value * (bps/10000)`
- Calmar ratio returns 0 for monotonically increasing curves (zero drawdown)

**Impact**:
- Production-ready confidence in all Phase 2 components
- RapidTrader parameter compatibility validated
- Performance targets verified: <500ms single symbol, <10ms signal calculation
- Regression prevention for future changes

**Tradeoffs**:
- Test suite takes ~8 seconds to run (acceptable for CI/CD)
- Some performance targets (500 symbol batch <5 min) require production infrastructure to validate

---

## Week 8: UI Modernization (Completed: 2026-02-14)

### Decision: Vite + Vanilla JS Frontend with Brutalist Design

**Date**: 2026-02-14

**Problem**: The Phase 1 UI was a single inline HTML template in `src/ui.py` (~30 lines). It only supported MA crossover strategy on a single symbol. All Phase 2 backend features (RSI, multi-strategy, portfolio batches, execution config, trade ledger) had no UI exposure.

**Alternatives Considered**:
1. **React/Vue/Angular**: Full framework with component ecosystem, but adds significant dependency weight and build complexity for a learning project
2. **HTMX + Jinja2**: Server-rendered approach, minimal JS, but limits interactivity for charts, modals, and real-time updates
3. **Vanilla JS + Vite**: No framework overhead, class-based components, fast build, full control over design

**Decision**: Vanilla JS with Vite build system. No framework dependency keeps the project focused on backend learning while providing a functional, modern frontend.

**What Was Built**:

| Category | Files | Details |
|----------|-------|---------|
| Components | 10 JS modules | Header, StrategySelector, ExecutionConfig, PortfolioMode, ResultsDisplay, EquityCurveChart, PortfolioResults, TradeLedgerModal, SymbolSelector, JobHistory |
| Styles | 8 CSS files | BEM methodology, brutalist aesthetic (yellow/cyan, hard shadows, monospace) |
| Services | 3 JS modules | API client, localStorage abstraction, utility formatters |
| State | 1 JS module | Lightweight key-based subscription state manager |
| Config | 1 JS module | Constants, strategy labels, defaults |
| Build | Vite | ES modules, HMR dev server, API proxy, production bundle |

**Backend Changes Required**:
1. Added `config: Optional[BacktestConfigModel]` to `BacktestRequest` in `src/models.py`
2. Updated `submit_job()` in `src/api.py` to use `run_backtest_enhanced()` when config provided
3. Fixed multi-strategy endpoint trade metrics (were hardcoded to 0) in `src/api_portfolio.py`
4. Rewrote `src/ui.py` to serve SPA from `frontend/dist/`
5. Used `app.mount()` for static files (not `router.mount()`, which doesn't work for `StaticFiles`)

**Build Output**:
- Production bundle: 298KB JS + 31KB CSS
- Build time: <3 seconds
- All 650 existing tests still passing

**Key Technical Lessons**:
- FastAPI's `StaticFiles` mount only works on the `FastAPI` app instance, not on `APIRouter`
- Vite with `root: 'src'` auto-discovers `index.html` in the root; explicit `rollupOptions.input` caused path resolution failures
- Pydantic forward references need `model_rebuild()` when model A references model B defined later in the file

**Tradeoffs**:
- Node.js now required for development (adds a prerequisite)
- No TypeScript (acceptable for project scope)
- No framework means manual DOM management (acceptable for 10 components)
- No SSR or SEO (not needed for a backtesting tool)

---

## Week 8: Equity Curve Storage (Completed: 2026-02-20)

### Decision: Add JSON Columns for Portfolio and Symbol Equity Curves

**Date**: 2026-02-20

**Problem**: Portfolio backtests were storing aggregated metrics (average Sharpe, returns, drawdown) but not the portfolio equity curve itself. Individual symbol equity curves were also not persisted. This prevented visualization of portfolio-level performance over time and comparison of individual symbol trajectories.

**Approach**: Add JSON columns to existing database tables rather than creating new time-series tables.

**Implementation**:
1. Added `portfolio_equity_curve` JSON column to `PortfolioResult` model
2. Added `equity_curve` JSON column to `SymbolResult` model
3. Updated SQLAlchemy models in `src/db.py`
4. Updated schema documentation in `docs/DATA_MODEL.md`

**Schema Changes**:
```sql
ALTER TABLE portfolio_results ADD COLUMN portfolio_equity_curve JSON;
ALTER TABLE symbol_results ADD COLUMN equity_curve JSON;
```

**Format**: JSON arrays of equity values (e.g., `[10000, 10050, 10100, ...]`)

**Impact**:
- Enables portfolio equity curve visualization in UI
- Supports comparison of individual symbol performance curves
- No backend logic changes required (columns nullable, backward compatible)
- Works identically on SQLite and PostgreSQL

**Tradeoffs**:
- Large arrays for multi-year backtests (252+ data points per year)
- JSON columns not optimized for time-series queries (acceptable for current scale)
- Future: Consider TimescaleDB if query performance becomes bottleneck

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

#### Database Persistence - IMPLEMENTED (Week 6)
- **Trigger**: Portfolio results needed persistence across sessions
- **Current status**: Implemented with PostgreSQL (production) and SQLite (local dev)
- **Tables**: portfolio_results, symbol_results, trade_ledger
- **Migration**: Alembic managed

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

## Phase 2.5 - Strategy Import System (Design: 2026-02-21)

### Decision: Add Strategy Preset Library + LLM-Assisted Parameter Extraction

**Date**: 2026-02-21

**Problem**: Testing external strategies (papers, GitHub repos) requires 5-10 minutes of manual parameter extraction. Users must:
1. Read strategy code/paper
2. Identify 10-15 parameters (RSI periods, thresholds, position sizing, risk rules)
3. Manually enter into UI form
4. Repeat for parameter variations

This creates friction and limits strategy exploration velocity.

**User Request Context**: "Should we implement features that allow a strategy to be tested dynamically? Like we linked a paper, a repo, or an explanation and all the necessary params are extracted based on that and used for backtesting"

**Approach - Two Phases**:

**Phase A: Strategy Preset Library** (1-2 weeks)
- JSON-based strategy templates with complete configurations
- UI dropdown selector with categorization (mean reversion, trend following, etc.)
- 10+ initial presets covering common strategies (RapidTrader RSI, Turtle Trader, MA crossovers)
- Metadata includes source URL, author, description, tags
- One-click load into backtest form
- No code execution (pure configuration)

**Phase B: LLM-Assisted Parameter Extraction** (1-2 weeks)
- Import wizard accepting GitHub URL, PDF, text description, or code snippet
- Claude API integration for intelligent parameter extraction
- Confidence scoring (0-1) with quality levels (high/medium/low)
- Lists assumptions and warnings for user review
- Matches to existing presets if >90% similar
- User must review extracted params before execution (no arbitrary code execution)
- Cost: ~$0.03 per extraction, rate limit 10/hour per user

**Technology Choices**:
- **Pydantic models**: Schema validation for presets
- **Claude 3.7 Sonnet**: Best balance of accuracy and cost for extraction
- **JSON storage**: Simple, version-controllable preset format
- **No database (Phase A)**: Static JSON file is sufficient
- **Future database**: User custom presets in Phase 3

**What This Solves**:
- Reduces strategy setup time from 5-10 min → <1 min with presets
- Enables rapid testing of strategies from academic papers
- Creates reusable strategy library
- Facilitates community contributions
- Maintains security (no arbitrary code execution)

**What This Does NOT Solve**:
- Custom strategy implementation (still use BaseStrategy SDK)
- Strategy optimization/hyperparameter tuning (Phase 3)
- Multi-strategy portfolio construction (already supported via StrategyManager)

**Measured Success Criteria**:
- Phase A: 80%+ of common strategies covered by presets
- Phase B: >85% extraction accuracy for supported strategy types
- User review catches 100% of misconfigurations before execution
- Monthly API cost <$50 for expected usage

**Parallelization with Other Work**:
YES - Can run fully in parallel with:
- Frontend testing (Jest setup)
- Production monitoring (Prometheus/Grafana)
- CI/CD pipeline setup

No blocking dependencies. Separate code paths, minimal merge conflicts.

**Complexity Justification**:
Following "complexity receipts" philosophy:
1. **Real pain point**: 5-10 min manual work per strategy
2. **High-value use case**: Testing strategies from papers/repos is core workflow
3. **Measured benefit**: 5-10x speedup in strategy testing velocity
4. **Incremental approach**: Phase A (simple) validates value before Phase B (LLM)
5. **Security first**: No code execution, only configuration extraction

**Alternative Considered**:
Dynamic strategy code loading (paste Python code → execute)
- **Rejected**: Security risk, validation complexity, debugging nightmare
- **Better**: Guide users to implement BaseStrategy (~20 lines of code)

**Design Document**: `docs/STRATEGY_IMPORT_DESIGN.md` (38KB, comprehensive spec)

**Timeline**:
- Design complete: 2026-02-21
- Phase A implementation: TBD (1-2 weeks)
- Phase B implementation: TBD (1-2 weeks after Phase A)
- Can run parallel with frontend tests + monitoring work

---

---

## Phase 3: Engineering Hardening (Planned: 2026-02-28)

Based on external senior engineering review. 11 improvements prioritized to resolve architectural inconsistencies and complete half-finished patterns before adding further features.

---

### Decision: Persist Jobs to Database

**Date**: 2026-02-28 (planned)

**Problem**: Single backtest jobs live in an in-memory Python dict. Portfolio results persist to the database; jobs do not. This inconsistency is the most visible design smell in the codebase — the same API layer has two incompatible state models.

**Decision**: Add a `jobs` table to the existing SQLAlchemy schema. Replace the `jobs = {}` dict in `src/api.py` with DB reads/writes. Generate an Alembic migration.

**Impact**: Job history survives server restarts. Job History UI becomes trustworthy. Unblocks Celery wiring (task status can be persisted properly).

**Tradeoffs**: Small write overhead per job submission. Acceptable given jobs already write results to DB.

---

### Decision: Remove .env from Version Control

**Date**: 2026-02-28 (planned)

**Problem**: `.env` is tracked in git. API keys and database URLs must never be committed regardless of project scope.

**Decision**: Add `.env` to `.gitignore`, remove from git tracking, create `.env.example` with placeholder values.

**Impact**: Eliminates real security risk. One-time fix.

**Tradeoffs**: None. This is strictly a fix.

---

### Decision: Complete Alembic Migration Workflow

**Date**: 2026-02-28 (planned)

**Problem**: Alembic is in `requirements.txt` but migrations are manual scripts, not proper Alembic revisions. Schema changes require manual DB recreation. This is the canonical "right tool, incomplete pattern" signal.

**Decision**: Generate a proper initial migration from the current schema. Wire `migrations/env.py` correctly to `src/db.py` models. Document the workflow in `docs/SETUP.md`.

**Impact**: Schema evolution becomes: `alembic revision --autogenerate` + `alembic upgrade head`. Rollback is `alembic downgrade -1`. No more manual DB recreation.

**Tradeoffs**: Migration files must be kept in sync with model changes. Low ongoing cost.

---

### Decision: Wire Celery End-to-End for Portfolio Backtests

**Date**: 2026-02-28 (planned)

**Problem**: Celery and Redis are in `requirements.txt`, `src/worker.py` has task definitions, but portfolio backtests run synchronously inside the HTTP handler, blocking the FastAPI worker thread. This is the single most impactful incomplete pattern.

**Requires**: DB job persistence (#1 above).

**Decision**: `POST /api/v1/backtest/portfolio` enqueues a Celery task and returns `202 Accepted` with a `batch_id` immediately. Task updates the DB record through `PENDING → RUNNING → COMPLETE / FAILED` transitions. Status is polled via the existing GET endpoint.

**Impact**: Portfolio backtests become non-blocking. Multiple backtests run in parallel. Worker crash leaves job in `FAILED` state rather than hanging. Demonstrates producer/consumer architecture end-to-end.

**Tradeoffs**: Adds operational complexity — Redis must be running. Already a requirement; this makes it a real one rather than a listed dependency.

---

### Decision: Move Rate Limiters to Redis

**Date**: 2026-02-28 (planned)

**Problem**: LLM extraction rate limiter is in-memory. Resets on restart, doesn't work across multiple worker processes. Redis is already in the stack.

**Requires**: Celery wired (#4 above) — Redis already running.

**Decision**: Replace in-memory counter with `INCR` + `EXPIRE` on a Redis key scoped by client IP, TTL 3600s.

**Impact**: Rate limit survives restarts, works correctly with multiple workers.

**Tradeoffs**: Redis becomes a hard dependency for LLM extraction. Already true given Celery. No additional infrastructure cost.

---

### Decision: Pydantic BaseSettings for Configuration

**Date**: 2026-02-28 (planned)

**Problem**: Configuration is scattered `os.environ.get()` calls across `api.py`, `api_portfolio.py`, `api_extraction.py`, `worker.py`, `db.py`. Misconfiguration surfaces mid-request, not at startup.

**Decision**: Create `src/config.py` with a `pydantic_settings.BaseSettings` class. Replace all `os.environ.get()` callsites with `from src.config import settings`.

**Impact**: Misconfiguration fails at startup with a clear `ValidationError`. All configuration is discoverable in one place.

**Tradeoffs**: Adds `pydantic-settings` as a dependency (already likely present transitively). Requires touching multiple files for the migration.

---

### Decision: Active Dependency Probes in Health Check

**Date**: 2026-02-28 (planned)

**Problem**: `GET /api/v1/health` returns `{"status": "ok"}` unconditionally. It cannot detect database failure, Redis unavailability, or degraded data sources.

**Decision**: Rewrite the health endpoint to actively probe database (query), Redis (ping), and yfinance (lightweight request). Return `200` when critical dependencies are healthy, `503` when database or Redis is down. Non-critical dependencies (yfinance, Anthropic API) contribute `"degraded"` status without triggering `503`.

**Impact**: Health check becomes a real operational signal rather than a liveness stub.

**Tradeoffs**: Health endpoint now has latency proportional to dependency response time. Mitigate with short timeouts (500ms) on each probe.

---

### Decision: Structured JSON Logging with Request IDs

**Date**: 2026-02-28 (planned)

**Problem**: Logs are unstructured plaintext. No request correlation. Cannot trace a slow backtest across log lines from different functions or workers.

**Decision**: Add FastAPI middleware that generates a UUID per request and attaches it to request state. Use `python-json-logger` for structured JSON output. Thread `request_id` / `task_id` through backtest engine and Celery task log calls.

**Impact**: Every log line for a request shares a `request_id`. Logs are parseable with `jq`. Worker logs include `task_id` and `batch_id` for correlation.

**Tradeoffs**: Structured logs are less readable in a terminal without tooling. Acceptable tradeoff for any system beyond single-process development.

---

### Decision: Document Architectural Decision Rationale

**Date**: 2026-02-28 (planned)

**Problem**: Non-obvious design choices (vanilla JS, JSON presets, interval-based S&P 500 storage, original in-memory job store) lack documented rationale. Reviewers must guess; the author cannot explain them confidently in interviews.

**Decision**: Add a "Design Decisions" table to `docs/ARCHITECTURE.md` covering the choices above with one-sentence rationale for each.

**Impact**: Every non-obvious decision has a recorded justification. Answers "why" questions without hesitation.

**Tradeoffs**: Documentation requires maintenance when decisions change.

---

### Decision: Replace Wikipedia Playwright Scraper with MediaWiki API

**Date**: 2026-02-28 (planned)

**Problem**: `src/sp500_updater.py` uses Playwright (headless browser) to scrape Wikipedia. Wikipedia has a public structured REST API returning the same data as JSON. Playwright is heavyweight and will silently ingest garbage if the page structure changes.

**Decision**: Replace Playwright with `httpx` + HTML parsing via `lxml`/`beautifulsoup4` against the Wikipedia API. Add column header validation that raises a descriptive error rather than ingesting malformed data. Remove `playwright` from `requirements.txt`.

**Impact**: Removes a heavy dependency. Makes data source brittleness explicit (errors loudly instead of silently).

**Tradeoffs**: Still using Wikipedia as the data source — acknowledged as a pragmatic choice for a personal project (documented in ARCHITECTURE.md rationale table).

---

### Decision: Add Backtest Result Diffing Endpoint

**Date**: 2026-02-28 (planned)

**Problem**: No way to quantify the P&L impact of parameter changes between two backtest runs. Users manually compare JSON responses.

**Decision**: Add `GET /api/v1/backtest/diff?a={batch_id}&b={batch_id}` returning parameter deltas alongside metric deltas. Build a UI panel for side-by-side comparison.

**Impact**: Users can directly see: "changing commission from 1 bps to 5 bps reduced total return by 5%." Requires a stable result schema (forces API contract discipline) and a diff algorithm over structured objects.

**Tradeoffs**: Meaningful only when both backtests use the same symbols and date range. Return a clear error for incompatible comparisons.

---

## Principles

1. **No technology without a trigger**: Add complexity only when measurements show the need
2. **Document the "why"**: Every decision must explain the problem being solved
3. **Show your work**: Include benchmarks, profiler output, or error logs
4. **Admit tradeoffs**: Every technology adds complexity - what's the cost?
5. **Be honest**: If something didn't work, document it so you don't repeat it

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

# Backgrid Implementation Guide

**Version**: 3.0 (RapidTrader Integration)
**Last Updated**: 2026-02-01
**Status**: Phase 1 MVP Complete, Phase 2 RapidTrader Integration Starting

---

## Executive Summary

This guide details the implementation plan to extend Backgrid from a single-strategy MVP to a multi-strategy, portfolio-level backtesting system that can validate [RapidTrader](https://github.com/Thinh-nguyen-03/rapid-trader) trading strategies before live deployment.

### Current State

| Component | Status | Location |
|-----------|--------|----------|
| **MA Crossover Strategy** | Complete | [src/backtest.py](../src/backtest.py) |
| **Yahoo Finance Data** | Complete | [src/data.py](../src/data.py) |
| **FastAPI + Sync Execution** | Complete | [src/api.py](../src/api.py) |
| **PostgreSQL + SQLAlchemy** | Ready | [src/db.py](../src/db.py) |
| **Docker (Redis, PostgreSQL, Celery)** | Ready | [docker-compose.yml](../docker-compose.yml) |

### Target State (RapidTrader Edition)

| Feature | RapidTrader Requirement | Status |
|---------|-------------------------|--------|
| RSI Strategy | Buy RSI < 30, Sell > 55, 2-of-3 confirmation | Complete |
| SMA Strategy | 20/100 configurable periods | Complete |
| Multi-Strategy | Combined signals with priority logic | Complete |
| PostgreSQL Data | Connect to RapidTrader `bars_daily` table | Planned |
| ATR Position Sizing | 5% per trade, ATR-based stops | Planned |
| Transaction Costs | Commission + slippage modeling | Planned |
| Market Filter | SPY 200-SMA bull/bear detection | Planned |
| Sector Limits | Max 30% exposure per sector | Planned |
| 500+ Symbols | Parallel Celery execution | Planned |

---

## Core Principles

### 1. Start Simple, Add Complexity When Needed
- Phase 1 (Complete): Single strategy, synchronous execution
- Phase 2 (Current): Add RapidTrader features incrementally
- Phase 3 (Future): Scale with Celery workers for 500+ symbols

### 2. Document Every Decision with a Receipt
Every major addition to the stack must include:
- What problem you measured
- Profiler output or benchmark
- Alternatives tried
- Impact after adding

### 3. Be Honest in Public
README must reflect **current phase**, not aspirational state.

### 4. Test Before Shipping
- Unit tests for all new strategy code
- Integration tests for API -> Database flow
- Validation tests comparing to RapidTrader historical results

---

## Phase 1: MVP (COMPLETE)

**Status**: Done
**Git Tag**: `phase-1-mvp`

### What Was Built
- FastAPI with 3 endpoints (`/health`, `/jobs`, `/jobs/{id}`)
- MA Crossover strategy (configurable fast/slow periods)
- Yahoo Finance data fetching
- Sharpe ratio, max drawdown, total return metrics
- In-memory result storage (PostgreSQL ready)

### Metrics Achieved
- Latency: 2.66s per backtest (AAPL 2023)
- Tests: 99/99 passing
- Coverage: >95% on critical paths

---

## Phase 2: RapidTrader Integration (CURRENT)

**Estimated Duration**: 5-7 weeks
**Total Effort**: 264-340 hours

### Week 1: RSI Strategy + Base Framework

**Priority**: P0 (Critical)
**Hours**: 16-24

#### Files to Create
```
src/strategies/
  __init__.py
  base.py              # Abstract strategy interface
  rsi_strategy.py      # RSI mean reversion
  ma_strategy.py       # Refactored MA crossover
  strategy_manager.py  # Multi-strategy orchestration
```

#### Implementation Tasks

1. **Base Strategy Interface** (`src/strategies/base.py`)
```python
from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, params: Dict[str, Any]):
        self.params = params

    @abstractmethod
    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Return Series with values: 'buy', 'sell', 'hold'"""
        pass
```

2. **RSI Strategy** (`src/strategies/rsi_strategy.py`)

   RapidTrader parameters:
   - `rsi_period`: 14
   - `oversold_threshold`: 30
   - `overbought_threshold`: 55
   - `confirmation_window`: 3 days
   - `min_confirmation_count`: 2

3. **Refactor MA Strategy** - Move from `src/backtest.py` to `src/strategies/ma_strategy.py`

#### Acceptance Criteria
- [x] RSI calculation matches TA-Lib reference (Wilder's smoothing)
- [x] 2-of-3 confirmation logic working
- [x] All unit tests pass (100% coverage on strategy code)
- [x] Performance: < 10ms for 252 trading days

**Status**: COMPLETE (2026-02-01)

---

### Week 2: Multi-Strategy + PostgreSQL Loader

**Priority**: P0 (Critical)
**Hours**: 32-40

#### Files to Create
```
src/data/
  __init__.py
  base_loader.py       # Abstract data loader
  yahoo_loader.py      # Refactored yfinance
  postgres_loader.py   # RapidTrader database
```

#### Implementation Tasks

1. **Strategy Manager** (`src/strategies/strategy_manager.py`)
   - Signal combination: OR, AND, PRIORITY (SELL > BUY > HOLD)
   - Strategy attribution tracking
   - Weighted voting support

2. **PostgreSQL Loader** (`src/data/postgres_loader.py`)
   - Connect to RapidTrader tables: `bars_daily`, `symbols`, `market_state`
   - Connection pooling (5 connections)
   - Batch loading for 500+ symbols
   - In-memory caching with TTL

3. **Update Models** (`src/models.py`)
```python
class StrategyType(str, Enum):
    MA_CROSSOVER = "ma_crossover"
    RSI = "rsi"
    COMBINED = "combined"
```

#### Acceptance Criteria
- [x] Supports 2+ strategies simultaneously
- [x] All combination methods working (OR, AND, PRIORITY, WEIGHTED)
- [ ] PostgreSQL loader connects to RapidTrader DB
- [ ] Batch loading 5-10x faster than individual queries

---

### Week 3: Position Sizing + Transaction Costs

**Priority**: P0 (Critical)
**Hours**: 36-44

#### Files to Create
```
src/position_sizing/
  __init__.py
  atr_sizer.py         # ATR-based sizing
  fixed_sizer.py       # Fixed fractional

src/execution/
  __init__.py
  transaction_costs.py # Cost modeling
  order_simulator.py   # Fill simulation
```

#### Implementation Tasks

1. **ATR Position Sizing**
   - `atr_period`: 14 (RT_ATR_LOOKBACK)
   - `risk_per_trade`: 5% (RT_PCT_PER_TRADE)
   - `atr_multiplier`: 3.0 (RT_ATR_STOP_K)

2. **Transaction Cost Model**
   - Commission: $0.005/share
   - Spread: 5 bps
   - Slippage: 2 bps + volume impact

3. **Order Execution Simulator**
   - Signals at end-of-day
   - Fills at next day's open

#### Acceptance Criteria
- [ ] ATR calculation matches TA-Lib
- [ ] Position sizes respect all constraints
- [ ] Total costs < 0.5% for liquid stocks

---

### Week 4: Risk Management

**Priority**: P1 (High)
**Hours**: 36-48

#### Files to Create
```
src/risk/
  __init__.py
  market_regime.py     # SPY 200-SMA filter
  stop_loss.py         # ATR-based stops
  sector_limits.py     # Sector concentration
  portfolio_heat.py    # Max risk exposure
```

#### Implementation Tasks

1. **Market Regime Filter**
   - SPY 200-SMA bull/bear detection
   - Block new entries in bear markets

2. **Stop Loss Manager**
   - ATR-based stop prices
   - 1-day cooldown after stop triggered

3. **Sector Limits**
   - Max 30% exposure per sector
   - Query symbol metadata from `symbols` table

#### Acceptance Criteria
- [ ] Market filter blocks trades in bear markets
- [ ] Stop losses trigger correctly
- [ ] Sector limits enforced

---

### Week 5: Portfolio Aggregation

**Priority**: P1 (High)
**Hours**: 56-72

#### Files to Create
```
src/portfolio/
  __init__.py
  portfolio.py         # State tracker
  trade_ledger.py      # Trade history
  metrics.py           # Extended metrics

src/worker.py          # Celery tasks
```

#### Implementation Tasks

1. **Portfolio State Tracker**
   - Positions, capital, sector exposures
   - Realized/unrealized P&L

2. **Trade Ledger**
   - Entry/exit prices, hold period, P&L
   - Strategy attribution

3. **Celery Worker Tasks**
   - Single-symbol backtest task
   - Batch job coordinator
   - Result aggregation

#### Acceptance Criteria
- [ ] Portfolio backtest for 500 symbols < 5 min
- [ ] Trade ledger records all trades
- [ ] Celery workers processing in parallel

---

### Week 6: API & Database Extensions

**Priority**: P1 (High)
**Hours**: 32-40

#### New API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/backtest/portfolio` | POST | Submit portfolio backtest |
| `/api/v1/backtest/portfolio/{id}` | GET | Get portfolio results |
| `/api/v1/backtest/portfolio/{id}/trades` | GET | Get trade ledger |
| `/api/v1/backtest/multi-strategy` | POST | Multi-strategy single symbol |
| `/api/v1/symbols` | GET | List available symbols |

#### New Database Tables (Alembic Migrations)

```sql
CREATE TABLE portfolio_results (
    batch_id UUID PRIMARY KEY,
    symbols TEXT[],
    start_date DATE,
    end_date DATE,
    config JSONB,
    status TEXT,
    created_at TIMESTAMP
);

CREATE TABLE symbol_results (
    id UUID PRIMARY KEY,
    batch_id UUID REFERENCES portfolio_results(batch_id),
    symbol TEXT,
    sharpe REAL,
    max_drawdown REAL,
    total_return REAL,
    trades_count INTEGER,
    win_rate REAL
);

CREATE TABLE trade_ledger (
    id UUID PRIMARY KEY,
    batch_id UUID,
    symbol TEXT,
    entry_date DATE,
    exit_date DATE,
    side TEXT,
    shares INTEGER,
    entry_price REAL,
    exit_price REAL,
    pnl REAL,
    strategy TEXT
);
```

---

### Week 7: Testing & Validation

**Priority**: P0 (Critical)
**Hours**: 40-48

#### Test Categories

1. **Unit Tests**
   - `tests/test_rsi_strategy.py`
   - `tests/test_strategy_manager.py`
   - `tests/test_postgres_loader.py`
   - `tests/test_atr_sizer.py`
   - `tests/test_transaction_costs.py`
   - `tests/test_risk_management.py`

2. **Integration Tests**
   - API -> Celery -> PostgreSQL flow
   - Multi-symbol batch processing

3. **Validation Tests**
   - Compare results with RapidTrader historical performance
   - Verify signal generation matches RapidTrader logic

#### Performance Targets
- 500 symbol batch: < 5 minutes
- Single symbol (cached): < 500ms
- Memory usage: < 2GB for full batch

---

## Phase 3: Scale & Performance (FUTURE)

### Triggers for Phase 3
- 500 symbols taking > 10 minutes
- Memory exceeding 4GB
- Multiple concurrent users needed

### Potential Additions
- **Go gRPC Metrics Service**: If metrics calculation > 50% of runtime
- **TimescaleDB**: If queries slow on 25M+ equity curve rows
- **JWT Authentication**: If multi-user isolation needed

### Complexity Receipt Required
Before adding any Phase 3 technology, document:
```markdown
## Decision: [Technology] (Date: YYYY-MM-DD)

### Problem
[Measured bottleneck with profiler output]

### Evidence
[Benchmark results, query times, memory usage]

### Alternatives Tried
[List at least 2 alternatives and why they weren't sufficient]

### Decision
[What you chose and why]

### Impact
[Before/after metrics]
```

---

## Directory Structure (Final)

```
backgrid/
├── src/
│   ├── __init__.py
│   ├── api.py                    # FastAPI app (extended)
│   ├── backtest.py               # Backtest engine (extended)
│   ├── data.py                   # Legacy yfinance (keep)
│   ├── models.py                 # Pydantic models (extended)
│   ├── db.py                     # SQLAlchemy (extended)
│   ├── ui.py                     # Web UI
│   ├── worker.py                 # Celery worker
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── ma_strategy.py
│   │   ├── rsi_strategy.py
│   │   └── strategy_manager.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── base_loader.py
│   │   ├── yahoo_loader.py
│   │   └── postgres_loader.py
│   ├── position_sizing/
│   │   ├── __init__.py
│   │   ├── atr_sizer.py
│   │   └── fixed_sizer.py
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── transaction_costs.py
│   │   └── order_simulator.py
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── market_regime.py
│   │   ├── stop_loss.py
│   │   ├── sector_limits.py
│   │   └── portfolio_heat.py
│   └── portfolio/
│       ├── __init__.py
│       ├── portfolio.py
│       ├── trade_ledger.py
│       └── metrics.py
├── tests/
├── config/
├── migrations/
├── docker-compose.yml
└── docs/
```

---

## RapidTrader Configuration Reference

Environment variables that Backgrid must match:

```bash
# Database
RT_DB_URL=postgresql://user:pass@host:5432/rapidtrader

# Strategy Parameters
RT_CONFIRM_WINDOW=3              # Signal confirmation window (days)
RT_CONFIRM_MIN_COUNT=2           # Minimum confirmations needed

# Position Sizing
RT_PCT_PER_TRADE=0.05            # 5% per trade
RT_ATR_LOOKBACK=14               # ATR calculation period
RT_ATR_STOP_K=3.0                # Stop loss = 3x ATR

# Risk Management
RT_MAX_EXPOSURE_PER_SECTOR=0.30  # 30% max per sector
RT_COOLDOWN_DAYS_ON_STOP=1       # Days to wait after stop

# Market Filter
RT_MARKET_FILTER_ENABLE=true
RT_MARKET_FILTER_SMA=200
RT_MARKET_FILTER_SYMBOL=SPY
```

---

## RapidTrader Database Schema

### bars_daily
```sql
CREATE TABLE bars_daily (
    symbol TEXT NOT NULL,
    d DATE NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    PRIMARY KEY (symbol, d)
);
```

### symbols
```sql
CREATE TABLE symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    sub_sector TEXT,
    is_active BOOLEAN DEFAULT true,
    date_added DATE
);
```

### market_state
```sql
CREATE TABLE market_state (
    d DATE PRIMARY KEY,
    spy_close REAL,
    spy_sma200 REAL,
    bull_gate BOOLEAN,
    volume_avg_20d REAL,
    volatility_20d REAL
);
```

---

## Testing Strategy

### Phase 2 Testing
- **Unit tests**: Per-module with 100% coverage on strategy code
- **Integration tests**: API -> Celery -> PostgreSQL flow
- **Validation tests**: Compare signals with RapidTrader historical data
- **Performance tests**: 500 symbols < 5 min, single symbol < 500ms

### Complexity Receipt Template
```markdown
## Decision: [Feature] (Date: YYYY-MM-DD)

### Problem
[What wasn't working or what was needed]

### Evidence
[Benchmark, profiler output, or user request]

### Alternatives Tried
1. [Alternative 1]: Result and why not sufficient
2. [Alternative 2]: Result and why not sufficient

### Decision
[What was implemented]

### Impact
[Before/after metrics]
```

---

## Git Commit Hygiene

**Good commits show evolution**:
```
feat: Add RSI strategy with 2-of-3 confirmation

Problem: Need mean-reversion strategy for RapidTrader backtesting
Solution: Implemented RSI with configurable thresholds and confirmation window
Impact: Can now backtest RSI < 30 buy, > 55 sell signals
Files: src/strategies/rsi_strategy.py, tests/test_rsi_strategy.py
```

**Bad commits**:
```
"Add RSI"
"WIP on strategies"
"Various improvements"
```

---

## Success Metrics

### Phase 2 Complete (Week 7)
- [ ] RSI strategy generates correct signals
- [ ] Multi-strategy framework combines SMA + RSI
- [ ] PostgreSQL loader connects to RapidTrader DB
- [ ] ATR position sizing working
- [ ] Transaction costs applied to returns
- [ ] Market regime filter blocks trades in bear markets
- [ ] Stop losses trigger correctly
- [ ] Sector limits enforced
- [ ] Portfolio backtest for 500 symbols < 5 min
- [ ] Trade ledger records all trades
- [ ] All integration tests pass
- [ ] Backtest results validated against RapidTrader historical data

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PostgreSQL schema mismatch | Medium | High | Verify RapidTrader schema before starting |
| Performance issues at 500 symbols | Medium | Medium | Early benchmarking, optimize critical paths |
| RSI calculation differences | Low | High | Validate against TA-Lib reference |
| Backward compatibility breaks | Medium | Medium | Keep old API endpoints, version new ones |

---

## Quick Start Commands

```bash
# Start infrastructure
docker-compose up -d postgres redis

# Run existing tests
pytest tests/ -v

# Start API (development)
python -m uvicorn src.api:app --reload

# Start Celery worker (after Phase 2 Week 5)
celery -A src.worker worker --loglevel=info
```

---

## Common Pitfalls to Avoid

1. **Adding tech before trigger**: Don't add Go/TimescaleDB until profiler proves need
2. **Skipping documentation**: A decision without a receipt is theater
3. **Perfect over shipped**: "Good enough" > "perfect but not deployed"
4. **Not validating against RapidTrader**: Always compare signals with live system
5. **Breaking backward compatibility**: Keep old endpoints working

---

**Final Rule**: If you can't explain a technology addition in 2 minutes with profiler data, you haven't earned it yet.

# API Specification (Phase 3 Complete)

**Base URL**: `http://localhost:8000`
**Auth**: None (single-user mode)
**Rate Limit**: LLM extraction — 10 req/hour per IP (Redis-backed)
**Status**: Phase 3 Engineering Hardening Complete (2026-02-28)

---

## POST /api/v1/jobs

Submit a backtest job (synchronous, returns result immediately).

### Supported Strategies

#### 1. MA Crossover Strategy
```json
{
  "symbol": "AAPL",
  "strategy": "ma_crossover",
  "params": {
    "fast": 10,
    "slow": 30
  },
  "start": "2020-01-01",
  "end": "2023-12-31"
}
```

**Parameters:**
- `fast`: Fast moving average period (integer, min 2)
- `slow`: Slow moving average period (integer, min 2, must be > fast)

**Backward Compatibility:** Also accepts `fast_period` and `slow_period` parameter names.

#### 2. RSI Strategy
```json
{
  "symbol": "AAPL",
  "strategy": "rsi",
  "params": {
    "rsi_period": 14,
    "oversold_threshold": 30,
    "overbought_threshold": 55,
    "confirmation_window": 3,
    "min_confirmation_count": 2
  },
  "start": "2020-01-01",
  "end": "2023-12-31"
}
```

**Parameters:**
- `rsi_period`: RSI calculation period (integer, min 2, default 14)
- `oversold_threshold`: Buy signal threshold (integer, 0-100, default 30)
- `overbought_threshold`: Sell signal threshold (integer, 0-100, default 55)
- `confirmation_window`: Lookback window for confirmation (integer, min 1, default 3)
- `min_confirmation_count`: Required confirmations (integer, min 1, default 2)

**Note:** Uses Wilder's smoothing method (EWM with alpha=1/period) for RSI calculation.

#### 3. Combined Strategy
```json
{
  "symbol": "AAPL",
  "strategy": "combined",
  "params": {
    "strategies": ["ma_crossover", "rsi"],
    "method": "priority",
    "ma_params": {"fast": 10, "slow": 30},
    "rsi_params": {"rsi_period": 14, "oversold_threshold": 30}
  },
  "start": "2020-01-01",
  "end": "2023-12-31"
}
```

**Parameters:**
- `strategies`: List of strategy names to combine (required)
- `method`: Combination method (default "priority")
  - `"or"`: Any BUY triggers buy, any SELL triggers sell
  - `"and"`: All strategies must agree for signal
  - `"priority"`: SELL > BUY > HOLD precedence
  - `"weighted"`: Weighted voting based on strategy weights
- `<strategy_name>_params`: Parameters for each strategy
- `weights` (optional): Dict mapping strategy names to weights for weighted combination

### Response (200 OK)
```json
{
  "job_id": "manual-2025-01-15-123456",
  "status": "completed",
  "sharpe": 1.23,
  "max_drawdown": -0.18,
  "total_return": 0.45,
  "equity_curve": [10000, 10200, 10500, ...],
  "runtime_seconds": 2.3
}
```

### Response (400 Bad Request)
```json
{"error": "Invalid symbol: INVALID"}
```

### Response (500 Internal Error)
```json
{"error": "Failed to fetch data from Yahoo Finance"}
```

---

## GET /api/v1/jobs/{job_id}

Retrieve job result (Phase 2: will support queued/running status).

### Response (200 OK)
```json
{
  "job_id": "manual-2025-01-15-123456",
  "status": "completed",
  "sharpe": 1.23,
  "equity_curve": [...]
}
```

---

## GET /api/v1/health

Health check with active dependency probes.

### Response (200 OK — all critical dependencies healthy)
```json
{
  "status": "ok",
  "phase": 2,
  "timestamp": "2026-02-28T12:00:00Z",
  "dependencies": {
    "database": {"status": "ok", "latency_ms": 1.2},
    "redis": {"status": "ok", "latency_ms": 0.8}
  }
}
```

### Response (503 — database unreachable)
```json
{
  "status": "degraded",
  "phase": 2,
  "timestamp": "2026-02-28T12:00:00Z",
  "dependencies": {
    "database": {"status": "unavailable", "error": "..."},
    "redis": {"status": "ok", "latency_ms": 0.9}
  }
}
```

**Notes:**
- Database failure → `503 Service Unavailable`
- Redis failure → reported as `"unavailable"` in `dependencies` but does not trigger 503
- Every response includes `X-Request-ID` UUID header

---

## Phase 2 Portfolio API (Complete)

All endpoints implemented and tested (Week 6-7):

### POST /api/v1/backtest/portfolio
Submit multi-symbol batch backtest (async).

**Request**:
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "strategy": "rsi",
  "params": {"rsi_period": 14},
  "start": "2023-01-01",
  "end": "2023-12-31"
}
```

**Response** (202 Accepted — returns immediately):
```json
{
  "batch_id": "portfolio-20260228-120000-abc12345",
  "status": "pending",
  "symbols_requested": 3,
  "created_at": "2026-02-28T12:00:00Z"
}
```

Poll `GET /api/v1/backtest/portfolio/{batch_id}` until `status == "completed"`.

### GET /api/v1/backtest/portfolio/{batch_id}
Retrieve portfolio results. `status` transitions: `pending → running → completed / failed`.

### GET /api/v1/backtest/portfolio/{batch_id}/trades
Query trade ledger with optional filters (`symbol`, `strategy`, `limit`, `offset`).

### GET /api/v1/backtest/diff
Compare two portfolio backtest runs by parameter and metric deltas.

**Query params**: `a={batch_id}`, `b={batch_id}`

**Response** (200 OK):
```json
{
  "batch_id_a": "portfolio-...-abc",
  "batch_id_b": "portfolio-...-def",
  "strategy_diff": {
    "params": {
      "rsi_period": {"a": 14, "b": 21}
    }
  },
  "date_range_diff": {},
  "metric_diff": {
    "average_return": {"a": 0.12, "b": 0.09, "delta": -0.03},
    "average_sharpe": {"a": 1.1, "b": 0.8, "delta": -0.3},
    "average_max_drawdown": {"a": -0.08, "b": -0.11, "delta": -0.03},
    "total_trades": {"a": 45, "b": 32, "delta": -13}
  },
  "symbols_a": ["AAPL", "MSFT"],
  "symbols_b": ["AAPL", "MSFT"]
}
```

**Errors**: `400` if `a == b`, `404` if either batch not found.

### POST /api/v1/backtest/multi-strategy
Single symbol with multiple strategies combined.

### GET /api/v1/symbols
List available symbols from data source.

### POST /api/v1/strategy/import
Extract strategy parameters from URL or text using Claude API.
Requires `ENABLE_LLM_EXTRACTION=true` and `ANTHROPIC_API_KEY` env vars.
Rate-limited to 10 requests/hour per IP (Redis-backed).

### POST /api/v1/strategy/import/pdf
Extract strategy parameters from uploaded PDF (max 10MB).

---

## Phase 4 Changes (Future)

- **Auth**: JWT bearer tokens for multi-user isolation
- **Websocket progress**: Real-time portfolio backtest progress events

---

## Python SDK Reference (Phase 2 - Week 2 & 3)

### Data Loaders

All data loaders implement the same interface via `BaseDataLoader`:

```python
from src.data import YahooDataLoader, PostgresDataLoader

# Yahoo Finance (default)
loader = YahooDataLoader(cache_ttl=3600)
df = loader.load("AAPL", "2020-01-01", "2023-12-31")

# Batch loading
dfs = loader.load_batch(["AAPL", "MSFT", "GOOG"], "2020-01-01", "2023-12-31")

# PostgreSQL (RapidTrader)
from src.data import PostgresLoaderConfig
config = PostgresLoaderConfig(
    host="localhost",
    port=5432,
    database="rapidtrader",
    user="user",
    password="password"
)
pg_loader = PostgresDataLoader(config)
df = pg_loader.load("AAPL", "2020-01-01", "2023-12-31")
```

### Strategies

```python
from src.strategies import MAStrategy, RSIStrategy, StrategyManager, CombinationMethod

# Single strategy
ma_strategy = MAStrategy({"fast": 10, "slow": 30})
signals = ma_strategy.calculate_signals(df)

# RSI with RapidTrader parameters
rsi_strategy = RSIStrategy({
    "rsi_period": 14,
    "oversold_threshold": 30,
    "overbought_threshold": 55,
    "confirmation_window": 3,
    "min_confirmation_count": 2
})

# Multi-strategy combination
manager = StrategyManager()
manager.add_strategy("ma", ma_strategy)
manager.add_strategy("rsi", rsi_strategy)
combined_signals = manager.combine_signals(df, method=CombinationMethod.PRIORITY)
```

### Position Sizing

```python
from src.position_sizing import ATRSizer, FixedFractionalSizer

# ATR-based sizing (RapidTrader compatible)
sizer = ATRSizer(
    atr_period=14,
    risk_per_trade=0.05,
    atr_multiplier=3.0
)
result = sizer.calculate(
    df=df,
    equity=100000.0,
    entry_price=150.0
)
# result.shares, result.position_value, result.stop_price

# Fixed fractional sizing
fixed_sizer = FixedFractionalSizer(fraction=0.10)
result = fixed_sizer.calculate(equity=100000.0, entry_price=150.0)
```

### Transaction Costs

```python
from src.execution import TransactionCostModel, OrderSimulator

# Cost model with RapidTrader parameters
costs = TransactionCostModel(
    commission_per_share=0.005,
    min_commission=1.00,
    spread_bps=5.0,
    slippage_bps=2.0
)
total_cost = costs.calculate(shares=100, price=150.0, volume=1000000)

# Order simulation
simulator = OrderSimulator(cost_model=costs, fill_at="next_open")
fill = simulator.execute(order, df, bar_index=10)
```

### Risk Management

```python
from src.risk import (
    MarketRegimeFilter, StopLossManager,
    SectorLimitManager, PortfolioHeatTracker
)

# --- Market Regime Filter ---
regime_filter = MarketRegimeFilter({
    "sma_period": 200,        # SPY 200-SMA (default)
    "buffer_pct": 0.0,        # Dead-band around SMA
    "confirmation_days": 1    # Days price must stay on one side
})
regime = regime_filter.get_regime(spy_df)        # MarketRegime dataclass
can_enter = regime_filter.allows_entry(spy_df, side="long")  # bool

# --- Stop Loss Manager ---
stop_mgr = StopLossManager({
    "atr_multiplier": 3.0,    # Stop distance in ATRs
    "atr_period": 14,
    "cooldown_days": 1,       # Days blocked after stop trigger
    "trailing_enabled": False
})
stop_price = stop_mgr.register_position(
    symbol="AAPL", entry_price=150.0, atr=2.5, df=df
)
result = stop_mgr.check_stop("AAPL", current_price=145.0, current_date=date)
# result.triggered, result.stop_price, result.stop_type

# --- Sector Limit Manager ---
sector_mgr = SectorLimitManager({
    "max_sector_exposure": 0.30,   # 30 % cap per sector
    "warn_threshold_pct": 0.25
})
sector_mgr.add_position("AAPL", sector="Technology", shares=100, market_value=15000.0)
allowed = sector_mgr.allows_entry(
    symbol="MSFT", sector="Technology",
    proposed_value=5000.0, total_portfolio=100000.0
)  # bool
warnings = sector_mgr.check_compliance()  # List[str]

# --- Portfolio Heat Tracker ---
heat_tracker = PortfolioHeatTracker({
    "max_heat_pct": 0.06,     # 6 % of portfolio
    "max_positions": 20
})
risk = heat_tracker.add_position(
    symbol="AAPL", entry_price=150.0, shares=100, stop_price=142.5
)  # float — dollar risk added
report = heat_tracker.get_heat_report(portfolio_value=100000.0)
# report.total_heat, report.heat_pct, report.status (COOL/WARM/HOT/CRITICAL)
can_add = heat_tracker.allows_new_risk(proposed_risk=500.0, portfolio_value=100000.0)
```

### Enhanced Backtest

```python
from src.backtest import run_backtest_enhanced, BacktestConfig
from src.strategies import RSIStrategy
from src.position_sizing import ATRSizer

config = BacktestConfig(
    initial_capital=100000.0,
    position_sizer=ATRSizer(atr_period=14, risk_per_trade=0.05),
    cost_model=TransactionCostModel()
)

results = run_backtest_enhanced(
    df=df,
    strategy=RSIStrategy({"rsi_period": 14}),
    config=config
)
# results.equity_curve, results.trades, results.metrics
```

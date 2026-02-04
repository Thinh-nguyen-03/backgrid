# Data Model

## Data Loader Architecture (Phase 2)

Backgrid uses a pluggable data loader architecture allowing multiple data sources.

### Data Loader Interface

```
BaseDataLoader (Abstract)
├── load(symbol, start, end) -> DataFrame
├── load_batch(symbols, start, end) -> Dict[str, DataFrame]
├── validate(df) -> bool
└── clear_cache() -> None

Implementations:
├── YahooDataLoader     # Yahoo Finance via yfinance
└── PostgresDataLoader  # RapidTrader PostgreSQL database
```

### DataFrame Schema

All loaders return pandas DataFrames with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| Open | float64 | Opening price |
| High | float64 | Highest price |
| Low | float64 | Lowest price |
| Close | float64 | Closing price |
| Volume | int64 | Trading volume |

Index: DatetimeIndex (trading days)

---

## RapidTrader Database Schema

The PostgresDataLoader connects to these RapidTrader tables:

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

CREATE INDEX idx_bars_daily_symbol ON bars_daily(symbol);
CREATE INDEX idx_bars_daily_date ON bars_daily(d);
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

CREATE INDEX idx_symbols_sector ON symbols(sector);
CREATE INDEX idx_symbols_active ON symbols(is_active);
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

## Backgrid Internal Tables (Future)

### Core Tables
- `symbols(symbol_id UUID PK, ticker TEXT UNIQUE, meta JSONB, created_at TIMESTAMPTZ)`
- `strategies(strategy_id TEXT PK, name TEXT, schema_json JSONB, created_at TIMESTAMPTZ)`
- `jobs(job_id UUID PK, user_id UUID, payload_json JSONB, status TEXT, checksum TEXT, submitted_at, started_at, finished_at)`
- `results(job_id UUID PK, metrics_json JSONB, equity_curve_id UUID, trade_log_id UUID, created_at TIMESTAMPTZ)`
- `portfolios(portfolio_id UUID PK, params_json JSONB, weights_json JSONB, metrics_json JSONB, created_at TIMESTAMPTZ)`

### Timescale Hypertables
- `equity_points(job_id UUID, ts TIMESTAMPTZ, equity DOUBLE PRECISION, PRIMARY KEY(job_id, ts))`
- `prices(symbol_id UUID, ts TIMESTAMPTZ, o,h,l,c DOUBLE PRECISION, v BIGINT, PRIMARY KEY(symbol_id, ts))`

### Invariants & Constraints
- `checksum(payload_json)` ensures idempotent submissions; `(checksum, user_id)` unique.
- All timestamps UTC; `ts` is monotonic within a job.
- Results row must exist for any `equity_points` (FK on delete cascade).

---

## Trade Records (Phase 2 - Week 3)

The enhanced backtest engine produces trade records with the following structure:

```python
@dataclass
class TradeRecord:
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime]
    side: str              # "long" or "short"
    shares: int
    entry_price: float
    exit_price: Optional[float]
    pnl: Optional[float]
    costs: float           # Total transaction costs
    strategy: str          # Strategy that generated the signal
```

---

## Position Sizing Results (Phase 2 - Week 3)

Position sizing calculations return:

```python
@dataclass
class PositionSizeResult:
    shares: int            # Number of shares to trade
    position_value: float  # Total position value (shares * price)
    risk_amount: float     # Dollar amount at risk
    stop_price: float      # Stop loss price (ATR-based)
```

---

## Risk Management Data Structures (Phase 2 - Week 4)

### MarketRegime

Returned by `MarketRegimeFilter.get_regime()`.

```python
@dataclass
class MarketRegime:
    state: RegimeState          # BULL | BEAR | NEUTRAL
    sma_value: float            # Current SMA value
    price: float                # Latest close price
    as_of: date                 # Date of the assessment
    regime_duration_days: int   # Trading days in current regime
```

`RegimeState` is an enum: `BULL`, `BEAR`, `NEUTRAL`.

### StopLossResult

Returned by `StopLossManager.check_stop()`.

```python
@dataclass
class StopLossResult:
    symbol: str
    triggered: bool             # True if stop was breached
    stop_price: float           # Current stop level
    current_price: float        # Price that was checked
    stop_type: StopType         # FIXED | TRAILING
    cooldown_until: Optional[date]  # Date cooldown expires (if triggered)
```

`StopType` is an enum: `FIXED`, `TRAILING`.

### SectorExposure

Returned by `SectorLimitManager.get_sector_exposure()`.

```python
@dataclass
class SectorExposure:
    sector: str
    total_value: float          # Sum of market values in this sector
    exposure_pct: float         # Fraction of total portfolio
    max_allowed_pct: float      # Configured limit (default 0.30)
    headroom: float             # Remaining capacity as a fraction
    position_count: int         # Number of open positions in sector
```

### HeatReport

Returned by `PortfolioHeatTracker.get_heat_report()`.

```python
@dataclass
class HeatReport:
    total_heat: float           # Aggregate dollar risk across all positions
    heat_pct: float             # total_heat / portfolio_value
    max_heat: float             # Maximum allowed heat (max_heat_pct * portfolio_value)
    status: HeatStatus          # COOL | WARM | HOT | CRITICAL
    position_count: int         # Number of tracked positions
    max_positions: int          # Configured position limit
```

`HeatStatus` is an enum: `COOL` (<50 % of max), `WARM` (50-75 %), `HOT` (75-100 %), `CRITICAL` (>100 %).

---

## Portfolio Data Structures (Phase 2 - Week 5) - COMPLETE

### PositionState

Represents the state of a single open position. Implemented in [src/portfolio/portfolio.py](../src/portfolio/portfolio.py).

```python
@dataclass
class PositionState:
    symbol: str
    shares: int
    entry_price: float
    entry_date: datetime
    entry_cost: float              # Transaction cost at entry
    sector: Optional[str] = None
    strategy: Optional[str] = None
    stop_price: Optional[float] = None
    current_price: Optional[float] = None

    # Computed properties
    market_value: float            # shares * current_price
    unrealized_pnl: float          # (current - entry) * shares
    unrealized_pnl_pct: float      # (current - entry) / entry
```

### PortfolioSnapshot

Point-in-time snapshot of portfolio state. Implemented in [src/portfolio/portfolio.py](../src/portfolio/portfolio.py).

```python
@dataclass
class PortfolioSnapshot:
    timestamp: datetime
    cash: float
    positions: Dict[str, PositionState]
    realized_pnl: float
    total_transaction_costs: float

    # Computed properties
    total_market_value: float      # Sum of position values
    total_equity: float            # cash + total_market_value
    total_unrealized_pnl: float    # Sum of position unrealized P&L
    position_count: int
    sector_exposures: Dict[str, float]  # sector -> fraction of equity
```

### TradeSummary

Summary statistics for a collection of trades. Implemented in [src/portfolio/trade_ledger.py](../src/portfolio/trade_ledger.py).

```python
@dataclass
class TradeSummary:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float           # gross_profit / gross_loss
    average_win: float
    average_loss: float
    average_trade: float
    largest_win: float
    largest_loss: float
    average_hold_days: float
    total_transaction_costs: float
```

### TradeMetrics

Metrics computed from trade records. Implemented in [src/portfolio/metrics.py](../src/portfolio/metrics.py).

```python
@dataclass
class TradeMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    payoff_ratio: float            # average_win / average_loss
    expectancy: float              # (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
    total_pnl: float
    average_hold_days: float
```

### PortfolioMetrics

Comprehensive portfolio performance metrics. Implemented in [src/portfolio/metrics.py](../src/portfolio/metrics.py).

```python
@dataclass
class PortfolioMetrics:
    total_return: float
    annualized_return: float       # CAGR
    sharpe_ratio: float
    sortino_ratio: float           # Penalizes only downside volatility
    calmar_ratio: float            # Annualized return / max drawdown
    max_drawdown: float
    volatility: float              # Annualized standard deviation
    downside_deviation: float      # Annualized downside std dev
    trading_days: int
```

---

## Celery Worker Tasks (Phase 2 - Week 5) - COMPLETE

Implemented in [src/worker.py](../src/worker.py).

### run_single_backtest

Executes a single-symbol backtest with retry logic.

```python
@app.task(bind=True, max_retries=3, default_retry_delay=5)
def run_single_backtest(
    self,
    symbol: str,           # Stock symbol (e.g., "AAPL")
    strategy: str,         # Strategy name (ma_crossover, rsi, combined)
    params: Dict[str, Any], # Strategy parameters
    start_date: str,       # Start date (YYYY-MM-DD)
    end_date: str,         # End date (YYYY-MM-DD)
    config: Optional[Dict[str, Any]] = None,  # BacktestConfig as dict
) -> Dict[str, Any]:
    # Returns:
    # {
    #     "symbol": str,
    #     "status": "completed" | "error",
    #     "job_id": str,
    #     "sharpe": float,
    #     "max_drawdown": float,
    #     "total_return": float,
    #     "total_trades": int,
    #     "win_rate": float,
    #     "total_transaction_costs": float,
    #     "runtime_seconds": float,
    #     "trades": List[Dict],
    # }
```

### run_portfolio_backtest

Dispatches parallel backtests across multiple symbols using Celery group.

```python
@app.task(bind=True)
def run_portfolio_backtest(
    self,
    symbols: List[str],    # List of stock symbols
    strategy: str,         # Strategy name
    params: Dict[str, Any], # Strategy parameters
    start_date: str,       # Start date (YYYY-MM-DD)
    end_date: str,         # End date (YYYY-MM-DD)
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # Returns:
    # {
    #     "batch_id": str,
    #     "status": "completed",
    #     "symbols_requested": int,
    #     "symbols_completed": int,
    #     "symbols_failed": int,
    #     "failed_symbols": List[str],
    #     "runtime_seconds": float,
    #     "symbol_count": int,
    #     "total_trades": int,
    #     "average_sharpe": float,
    #     "average_return": float,
    #     "average_max_drawdown": float,
    #     "best_symbol": str,
    #     "worst_symbol": str,
    #     "results_by_symbol": Dict[str, Dict],
    # }
```

### aggregate_results

Utility task for combining results from multiple backtests.

```python
@app.task
def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Aggregates sharpe, return, drawdown across symbols
```

### health_check

Worker monitoring task.

```python
@app.task
def health_check() -> Dict[str, Any]:
    # Returns: {"status": "healthy", "timestamp": str, "worker": str}
```

### Celery Configuration

```python
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,           # 5 minute hard limit
    task_soft_time_limit=240,      # 4 minute soft limit
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)

# Windows compatibility: use threads pool instead of prefork
if sys.platform == "win32":
    app.conf.worker_pool = "threads"
```

---

## Caching

### In-Memory Cache

Data loaders implement LRU caching with configurable TTL:

| Setting | Default | Description |
|---------|---------|-------------|
| cache_ttl | 3600 | Cache time-to-live in seconds |
| max_cache_size | 100 | Maximum number of cached datasets |

Cache key format: `{symbol}_{start}_{end}`

### Connection Pooling (PostgreSQL)

PostgresDataLoader uses SQLAlchemy QueuePool:

| Setting | Default | Description |
|---------|---------|-------------|
| pool_size | 5 | Number of connections to maintain |
| max_overflow | 10 | Additional connections when pool exhausted |
| pool_timeout | 30 | Seconds to wait for connection |

---

## Example Migration (Abridged)

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE symbols(
  symbol_id uuid PRIMARY KEY,
  ticker text UNIQUE NOT NULL,
  meta jsonb,
  created_at timestamptz DEFAULT now()
);

-- ... other tables ...

SELECT create_hypertable('equity_points','ts', if_not_exists => TRUE);
SELECT create_hypertable('prices','ts', if_not_exists => TRUE);
```

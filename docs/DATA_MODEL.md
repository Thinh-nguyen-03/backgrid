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

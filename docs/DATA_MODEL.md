# Data Model

## Core Tables
- `symbols(symbol_id UUID PK, ticker TEXT UNIQUE, meta JSONB, created_at TIMESTAMPTZ)`
- `strategies(strategy_id TEXT PK, name TEXT, schema_json JSONB, created_at TIMESTAMPTZ)`
- `jobs(job_id UUID PK, user_id UUID, payload_json JSONB, status TEXT, checksum TEXT, submitted_at, started_at, finished_at)`
- `results(job_id UUID PK, metrics_json JSONB, equity_curve_id UUID, trade_log_id UUID, created_at TIMESTAMPTZ)`
- `portfolios(portfolio_id UUID PK, params_json JSONB, weights_json JSONB, metrics_json JSONB, created_at TIMESTAMPTZ)`

## Timescale Hypertables
- `equity_points(job_id UUID, ts TIMESTAMPTZ, equity DOUBLE PRECISION, PRIMARY KEY(job_id, ts))`
- `prices(symbol_id UUID, ts TIMESTAMPTZ, o,h,l,c DOUBLE PRECISION, v BIGINT, PRIMARY KEY(symbol_id, ts))`

## Invariants & Constraints
- `checksum(payload_json)` ensures idempotent submissions; `(checksum, user_id)` unique.
- All timestamps UTC; `ts` is monotonic within a job.
- Results row must exist for any `equity_points` (FK on delete cascade).

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

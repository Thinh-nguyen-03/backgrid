# API Specification (Phase 2 - Week 1)

**Base URL**: `http://localhost:8000`
**Auth**: None (Phase 3)
**Rate Limit**: None (Phase 2)

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

Health check endpoint.

### Response (200 OK)
```json
{"status": "ok", "phase": 1}
```

---

## Phase 2 Changes (Future)

- **POST /jobs**: Will return immediately with `job_id` and `"status": "queued"`
- **Rate limiting**: 60 req/min per IP
- **Auth**: JWT bearer tokens

## Phase 3 Changes (Future)

- **GET /jobs**: Will include pagination for large result sets
- **User isolation**: Results scoped to authenticated user

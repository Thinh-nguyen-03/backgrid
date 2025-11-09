# API Specification (Phase 1 - MVP)

**Base URL**: `http://localhost:8000`
**Auth**: None (Phase 3)
**Rate Limit**: None (Phase 2)

---

## POST /api/v1/jobs

Submit a backtest job (synchronous, returns result immediately).

### Request
```json
{
  "symbol": "AAPL",
  "strategy": "ma_crossover",
  "params": {"fast": 10, "slow": 30},
  "start": "2020-01-01",
  "end": "2023-12-31"
}
```

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

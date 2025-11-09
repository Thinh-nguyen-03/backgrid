# Testing Strategy

## Test Pyramid
- **Unit (pytest):** data loaders, indicators, strategy rules
- **Integration:** API ↔ queue ↔ worker ↔ DB happy‑path
- **Contract:** gRPC protobuf compatibility tests (Go metrics)
- **Load (Locust):** submit 1k jobs/hour with mixed params
- **Chaos:** kill workers, simulate Redis outage, data API throttling
- **End‑to‑End:** docker compose workflow (sample job to metrics/DB)

## Commands
```bash
pytest -q
pytest -q tests/integration
locust -f tests/load/locustfile.py
make chaos.smoke
```

## Coverage Targets
- Statements ≥ 80%
- Critical paths (orders/accounting) ≥ 90%

## Fixtures
- Deterministic seeds
- Synthetic OHLCV generators
- Golden files for equity curves

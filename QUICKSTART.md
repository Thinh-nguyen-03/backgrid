# Backgrid Quick Start Guide

Get up and running with Backgrid in 5 minutes.

---

## Prerequisites

- Python 3.13+ (tested on 3.13.3)
- Node.js 18+ and npm (for frontend build)
- Git

**Optional (for Docker deployment only):**
- Docker and Docker Compose
- PostgreSQL and Redis will be provisioned via containers

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd backgrid

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies and build
cd frontend && npm install && npm run build && cd ..

# Verify installation
python -c "import fastapi, pandas, sqlalchemy; print('Dependencies OK')"
```

---

## Run Tests

```bash
# Run full test suite (650 tests, ~8 seconds)
pytest tests/

# Run specific test file
pytest tests/test_rsi_strategy.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

**Expected**: 650 tests passing, 0 failures

---

## Start API Server (Local Dev)

```bash
# Uses SQLite by default (no setup required)
uvicorn src.api:app --reload --port 8000
```

Open browser: http://localhost:8000 (Web UI) or http://localhost:8000/docs (Swagger)

---

## Frontend Development

```bash
# Start Vite dev server with hot reload (proxies API to :8000)
cd frontend && npm run dev
# Open http://localhost:5173

# Production build (outputs to frontend/dist/)
cd frontend && npm run build

# Preview production build
cd frontend && npm run preview
```

The Vite dev server at `:5173` proxies all `/api` requests to the FastAPI server at `:8000`.

---

## Example API Usage

### 1. Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### 2. Single Symbol Backtest
```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "ma_crossover",
    "params": {"fast_period": 20, "slow_period": 100},
    "start_date": "2023-01-01"
  }'
```

### 3. Portfolio Backtest
```bash
curl -X POST http://localhost:8000/api/v1/backtest/portfolio \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT", "GOOGL"],
    "strategy": "rsi",
    "start": "2023-01-01"
  }'
```

### 4. Multi-Strategy Backtest
```bash
curl -X POST http://localhost:8000/api/v1/backtest/multi-strategy \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategies": [
      {"type": "ma_crossover", "params": {"fast_period": 20, "slow_period": 100}},
      {"type": "rsi", "params": {}}
    ],
    "combination_method": "priority",
    "start": "2023-01-01"
  }'
```

---

## Available Strategies

### RSI (Mean Reversion)
```json
{
  "strategy": "rsi",
  "params": {
    "rsi_period": 14,
    "oversold_threshold": 30,
    "overbought_threshold": 55,
    "confirmation_window": 3,
    "min_confirmation_count": 2
  }
}
```

### MA Crossover
```json
{
  "strategy": "ma_crossover",
  "params": {
    "fast_period": 20,
    "slow_period": 100
  }
}
```

---

## Configuration Options

### Position Sizing
```json
{
  "position_sizing": "atr",  // or "fixed"
  "atr_period": 14,
  "risk_per_trade": 0.05,
  "atr_multiplier": 3.0
}
```

### Transaction Costs
```json
{
  "enable_transaction_costs": true,
  "commission_per_share": 0.005,
  "spread_bps": 5.0,
  "slippage_bps": 2.0
}
```

### Risk Management
```json
{
  "enable_market_regime_filter": true,
  "enable_stop_loss": true,
  "enable_sector_limits": true,
  "max_sector_exposure": 0.30,
  "max_heat_pct": 0.06
}
```

---

## Deployment Modes

### Local Development (SQLite - Default)
No setup required. Uses `backgrid.db` SQLite file automatically.

```bash
# Configured via .env: DATABASE_URL=sqlite:///./backgrid.db
uvicorn src.api:app --reload --port 8000
```

### Docker Deployment (PostgreSQL + Redis)
Uses PostgreSQL for persistence and Redis for Celery workers.

```bash
# Start all services (API, PostgreSQL, Redis, Celery workers)
docker-compose up

# Access API at http://localhost:8000
```

### Native PostgreSQL (Advanced)
Manually configure PostgreSQL without Docker.

```bash
# Create database
createdb backgrid

# Set environment variable in .env
echo 'DATABASE_URL="postgresql://user:pass@localhost:5432/backgrid"' > .env

# Run migrations
alembic upgrade head

# Start server
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

---

## Celery Workers (Optional - Docker Mode Only)

Celery workers are automatically started in Docker mode. For native setup:

```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery worker
celery -A src.worker worker --loglevel=info --pool=threads

# Terminal 3: Start API server
uvicorn src.api:app --reload
```

**Note**: SQLite mode works without Celery for development/testing.

---

## Project Structure

```
backgrid/
├── src/
│   ├── api.py              # Main FastAPI app + static file mount
│   ├── api_portfolio.py    # Portfolio endpoints
│   ├── backtest.py         # Core backtest engine
│   ├── db.py               # Database models
│   ├── ui.py               # SPA serving from frontend/dist/
│   ├── worker.py           # Celery tasks
│   ├── data/               # Data loaders
│   ├── strategies/         # Trading strategies
│   ├── position_sizing/    # Position sizing
│   ├── execution/          # Transaction costs
│   ├── risk/               # Risk management
│   └── portfolio/          # Portfolio module
├── frontend/
│   ├── src/                # Frontend source (components, styles, services)
│   ├── dist/               # Production build output
│   ├── package.json        # Node dependencies
│   └── vite.config.js      # Build configuration
├── tests/                  # Test suite (650 tests)
├── docs/                   # Documentation
├── alembic/                # Database migrations
└── requirements.txt        # Python dependencies
```

---

## Common Tasks

### Add New Strategy
1. Create `src/strategies/my_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement `calculate_signals(df) -> pd.Series`
4. Add tests in `tests/test_my_strategy.py`

### Run Single Test
```bash
pytest tests/test_rsi_strategy.py::TestRSICalculation::test_rsi_values_bounded_0_to_100 -v
```

### Check Code Style
```bash
# Format with black (if installed)
black src/ tests/

# Lint with flake8 (if installed)
flake8 src/ tests/
```

### View Test Coverage
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # or start htmlcov/index.html on Windows
```

---

## Troubleshooting

### Import Errors
```bash
# Ensure you're in project root
cd /path/to/backgrid

# Add to PYTHONPATH if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Errors
```bash
# Check database URL
echo $DATABASE_URL

# Reset SQLite database
rm backgrid.db test_backgrid.db

# Recreate PostgreSQL database
dropdb backgrid && createdb backgrid
alembic upgrade head
```

### Test Failures
```bash
# Run with verbose output
pytest tests/ -v --tb=short

# Run single failing test
pytest tests/test_file.py::test_name -v
```

---

## Next Steps

1. **Read Documentation**: Start with [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)
2. **Explore Tests**: Look at test files for usage examples
3. **Try Examples**: Run the API examples above
4. **Review Architecture**: Check [ARCHITECTURE.md](docs/ARCHITECTURE.md)
5. **Understand Decisions**: Read [DECISION_LOG.md](docs/DECISION_LOG.md)

---

## Getting Help

- **Documentation**: See `docs/` directory
- **Examples**: See `tests/` for comprehensive usage examples
- **API Docs**: http://localhost:8000/docs (when server running)
- **Phase 2 Handoff**: See [PHASE_2_HANDOFF.md](PHASE_2_HANDOFF.md)

---

## Performance Expectations

- Single symbol backtest: <500ms
- Signal calculation (252 days): <10ms
- Database write: <100ms per symbol
- Test suite execution: ~8 seconds
- API response time: <1 second (with caching)

---

## Success Indicators

✅ All 650 tests passing
✅ API server starts without errors
✅ Health check returns 200 OK
✅ Sample backtest completes successfully
✅ No deprecation warnings in test output

---

**You're ready to go!** 🚀

For detailed information, see [PHASE_2_HANDOFF.md](PHASE_2_HANDOFF.md).

# Setup Guide

Complete setup instructions for local development and deployment.

---

## Requirements

- Python 3.13+ (tested on 3.13.3)
- Node.js 18+ and npm (for frontend build)
- Git

**Optional (for Docker deployment):**
- Docker and Docker Compose
- PostgreSQL and Redis (provisioned via containers)

---

## Quick Start

```bash
# Clone repository
git clone https://github.com/Thinh-nguyen-03/backgrid
cd backgrid

# Install Python dependencies
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npm run build && cd ..

# Start API server
uvicorn src.api:app --reload --port 8000
```

Open browser to http://localhost:8000

---

## Development Setup

### Python Environment

```bash
# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi, pandas, sqlalchemy; print('Dependencies OK')"
```

### Frontend Development

```bash
# Dev mode with hot reload (proxies API to :8000)
cd frontend && npm run dev
# Open http://localhost:5173

# Production build
cd frontend && npm run build
# Output: frontend/dist/ (served by FastAPI at http://localhost:8000)

# Preview production build
cd frontend && npm run preview
```

**Dev workflow:** Run `uvicorn` on port 8000 in one terminal, `npm run dev` in another. The Vite dev server at `:5173` proxies `/api` requests to FastAPI.

### Database Setup

Backgrid supports two database modes:

**SQLite (Default - No Setup Required)**
```bash
# Uses backgrid.db file automatically
# Configured via .env: DATABASE_URL=sqlite:///./backgrid.db
uvicorn src.api:app --reload --port 8000
```

**PostgreSQL (Docker - Recommended for Production)**
```bash
# Start all services (API, PostgreSQL, Redis, Celery workers)
docker-compose up --build -d

# View logs
docker-compose logs -f api workers

# Stop and clean
docker-compose down -v
```

**PostgreSQL (Native Setup)**
```bash
# Create database
createdb backgrid

# Configure .env
echo 'DATABASE_URL="postgresql://user:pass@localhost:5432/backgrid"' > .env

# Run migrations
alembic upgrade head

# Start server
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

### RapidTrader PostgreSQL Integration

To connect to existing RapidTrader database:

```bash
# Set environment variables in .env
RT_DB_HOST=localhost
RT_DB_PORT=5432
RT_DB_NAME=rapidtrader
RT_DB_USER=your_user
RT_DB_PASSWORD=your_password
```

Required tables in PostgreSQL:
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

CREATE TABLE symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    sub_sector TEXT,
    is_active BOOLEAN DEFAULT true,
    date_added DATE
);
```

---

## Running Tests

```bash
# All tests (650 tests, ~10 seconds)
pytest tests/ -v

# Specific test file
pytest tests/test_rsi_strategy.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

**Expected**: 650 tests passing, 0 failures

---

## Starting Services

### API Server

```bash
# Development mode (SQLite, auto-reload)
uvicorn src.api:app --reload --port 8000

# Production mode (PostgreSQL)
export DATABASE_URL="postgresql://user:pass@localhost:5432/backgrid"
uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 4

# Access interactive docs
open http://localhost:8000/docs
```

### Celery Workers (Optional)

Only needed for large batch processing. Docker mode starts workers automatically.

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

## Deployment

### Local Development (Current)

SQLite-based, no infrastructure needed.

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
pytest tests/  # 650 tests, ~10s
uvicorn src.api:app --reload --port 8000
```

### Docker Compose (Recommended)

```bash
# Start all services
docker-compose up --build -d

# View logs
docker-compose logs -f api workers

# Stop
docker-compose down -v
```

### Fly.io Deployment

```bash
# Create app
flyctl launch --name backgrid-demo

# Set secrets
flyctl secrets set \
  DATABASE_URL="postgresql://..." \
  REDIS_URL="redis://..." \
  --app backgrid-demo

# Deploy
flyctl deploy

# Scale workers
flyctl scale count 2 --app backgrid-demo
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///./backgrid.db | Database connection string |
| REDIS_URL | redis://localhost:6379/0 | Redis connection (Celery only) |
| RT_DB_HOST | localhost | RapidTrader PostgreSQL host |
| RT_DB_PORT | 5432 | PostgreSQL port |
| RT_DB_NAME | rapidtrader | Database name |
| RT_DB_USER | - | Database user |
| RT_DB_PASSWORD | - | Database password |
| CACHE_TTL | 3600 | Data cache TTL in seconds |
| RT_MARKET_FILTER_ENABLE | true | Enable market regime filter |
| RT_MARKET_FILTER_SMA | 200 | SMA period for bull/bear detection |
| RT_MARKET_FILTER_SYMBOL | SPY | Reference symbol for regime filter |
| RT_ATR_STOP_K | 3.0 | ATR multiplier for stop-loss |
| RT_COOLDOWN_DAYS_ON_STOP | 1 | Days locked out after stop trigger |
| RT_MAX_EXPOSURE_PER_SECTOR | 0.30 | Max portfolio exposure per sector |

---

## Database Migrations

```bash
# Upgrade to latest schema
alembic upgrade head

# Create new migration (after model changes)
alembic revision --autogenerate -m "description"

# Downgrade one version
alembic downgrade -1
```

---

## IDE Configuration

### VSCode

Recommended extensions:
- Python
- Pylance
- pytest

Settings (`.vscode/settings.json`):
```json
{
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true
}
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

### PostgreSQL Connection Issues

If PostgresDataLoader fails to connect:
- Verify PostgreSQL is running: `docker ps` or `pg_isready -h localhost`
- Check credentials in `.env` file
- Ensure the database and tables exist

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

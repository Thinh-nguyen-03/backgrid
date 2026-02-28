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

# Configure environment
cp .env.example .env   # edit as needed

# Build frontend
cd frontend && npm install && npm run build && cd ..

# Start API server (SQLite tables created automatically on first start)
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
# Tables are created automatically on first API startup via init_db()
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
| REDIS_URL | redis://localhost:6379 | Redis connection (Celery + rate limiting) |
| ANTHROPIC_API_KEY | - | API key for LLM-assisted strategy import |
| ENABLE_LLM_EXTRACTION | false | Enable Claude-powered strategy extraction |

---

## Database Migrations

**SQLite**: Tables are created automatically on startup via `init_db()`. Alembic migrations are not required for SQLite development.

**PostgreSQL**: Run migrations before starting the server.

```bash
# Apply all migrations
alembic upgrade head

# Check current migration state
alembic current

# Create new migration after model changes
alembic revision --autogenerate -m "description"

# Downgrade one revision
alembic downgrade -1
```

Migration chain: `cc616f59a219` (jobs/results) → `add_portfolio_tables_week6` → `add_equity_curves_to_portfolio` (head)

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

- All tests passing (`pytest tests/ -q`)
- API server starts without errors
- Health check returns 200 OK (`curl http://localhost:8000/api/v1/health`)
- Sample backtest completes successfully

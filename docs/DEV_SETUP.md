# Developer Setup

## Requirements
- Python 3.11+
- Docker, docker compose (optional for local PostgreSQL)
- git

## One-Time Setup

```bash
git clone https://github.com/you/backgrid && cd backgrid
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test files
pytest tests/test_strategies.py -v
pytest tests/test_data_loaders.py -v
pytest tests/test_position_sizing.py -v
pytest tests/test_execution.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

## Starting the API

```bash
# Development mode
python -m uvicorn src.api:app --reload

# Production mode
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

## Local Services (Docker)

```bash
docker compose up --build -d           # db, redis, api, workers
docker compose logs -f api workers     # tail logs
docker compose down -v                 # stop & clean
```

## PostgreSQL Setup (RapidTrader Integration)

### Option 1: Connect to Existing RapidTrader Database

Set environment variables to connect to your RapidTrader database:

```bash
# .env file
RT_DB_HOST=localhost
RT_DB_PORT=5432
RT_DB_NAME=rapidtrader
RT_DB_USER=your_user
RT_DB_PASSWORD=your_password
```

Usage in code:

```python
from src.data import PostgresDataLoader, PostgresLoaderConfig

config = PostgresLoaderConfig(
    host=os.getenv("RT_DB_HOST"),
    port=int(os.getenv("RT_DB_PORT")),
    database=os.getenv("RT_DB_NAME"),
    user=os.getenv("RT_DB_USER"),
    password=os.getenv("RT_DB_PASSWORD")
)

loader = PostgresDataLoader(config)
df = loader.load("AAPL", "2020-01-01", "2023-12-31")
```

### Option 2: Local PostgreSQL for Development

```bash
# Start PostgreSQL with Docker
docker run -d \
  --name backgrid-postgres \
  -e POSTGRES_USER=backgrid \
  -e POSTGRES_PASSWORD=backgrid \
  -e POSTGRES_DB=backgrid \
  -p 5432:5432 \
  postgres:15

# Create RapidTrader-compatible tables
psql -h localhost -U backgrid -d backgrid < scripts/create_tables.sql
```

### Required Tables

The PostgresDataLoader expects these tables:

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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| RT_DB_HOST | localhost | PostgreSQL host |
| RT_DB_PORT | 5432 | PostgreSQL port |
| RT_DB_NAME | rapidtrader | Database name |
| RT_DB_USER | - | Database user |
| RT_DB_PASSWORD | - | Database password |
| CACHE_TTL | 3600 | Data cache TTL in seconds |

## Migrations

```bash
alembic upgrade head
```

## Seeding Test Data

```bash
python scripts/seed_symbols.py AAPL MSFT SPY TLT
```

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

## Troubleshooting

### Import Errors

If you see `ImportError: cannot import name 'fetch_ohlcv' from 'src.data'`:
- Ensure you're using the updated package structure (`src/data/` directory, not `src/data.py`)
- The legacy functions are available via `from src.data import fetch_ohlcv`

### Database Connection Issues

If PostgresDataLoader fails to connect:
- Verify PostgreSQL is running: `docker ps` or `pg_isready -h localhost`
- Check credentials in `.env` file
- Ensure the database and tables exist

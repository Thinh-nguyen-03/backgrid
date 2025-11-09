# Developer Setup

## Requirements
- Python 3.11, Go 1.22+
- Docker, docker compose
- Make, git

## One‑Time Setup
```bash
git clone https://github.com/you/backgrid && cd backgrid
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pre-commit install
go mod tidy
cp .env.example .env
```

## Local Services
```bash
docker compose up --build -d           # db, redis, api, workers, metrics, dash
docker compose logs -f api workers     # tail logs
docker compose down -v                 # stop & clean
```

## Migrations
```bash
alembic upgrade head
```

## Seeding Symbols
```bash
python scripts/seed_symbols.py AAPL MSFT SPY TLT
```

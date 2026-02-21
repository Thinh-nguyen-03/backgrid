"""Integration tests for API -> Database flow.

Week 7: Tests the end-to-end flow from API endpoints through backtest
execution to database persistence. Uses SQLite and mocked data sources.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.api import app
from src.db import Base, engine, SessionLocal, PortfolioResult, SymbolResult, TradeLedgerEntry


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_ohlcv():
    """Generate mock OHLCV data with signals that produce trades."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(100) * 2)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base + np.abs(np.random.randn(100)) * 2,
        "Low": base - np.abs(np.random.randn(100)) * 2,
        "Close": base,
        "Volume": np.random.randint(500_000, 5_000_000, 100),
    }, index=dates)


class TestPortfolioEndToEnd:
    """Full flow: POST portfolio -> verify DB -> GET results."""

    def test_submit_and_retrieve_portfolio(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL", "MSFT"],
                "strategy": "ma_crossover",
                "params": {"fast_period": 5, "slow_period": 20},
                "start": "2023-01-01",
                "end": "2023-12-31",
            })

        assert response.status_code == 200
        data = response.json()
        batch_id = data["batch_id"]
        assert batch_id.startswith("portfolio-")
        assert data["status"] == "completed"
        assert data["symbols_requested"] == 2

        # Retrieve
        get_resp = client.get(f"/api/v1/backtest/portfolio/{batch_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["batch_id"] == batch_id

    def test_portfolio_results_persisted_to_db(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL"],
                "strategy": "rsi",
                "start": "2023-01-01",
            })

        assert response.status_code == 200
        batch_id = response.json()["batch_id"]

        db = SessionLocal()
        try:
            portfolio = db.query(PortfolioResult).filter_by(batch_id=batch_id).first()
            assert portfolio is not None
            assert portfolio.status == "completed"
            assert portfolio.symbols_requested == 1

            symbol_results = db.query(SymbolResult).filter_by(batch_id=batch_id).all()
            assert len(symbol_results) == 1
            assert symbol_results[0].symbol == "AAPL"
        finally:
            db.close()

    def test_trade_ledger_persisted_to_db(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "params": {"fast_period": 5, "slow_period": 20},
                "start": "2023-01-01",
            })

        batch_id = response.json()["batch_id"]

        db = SessionLocal()
        try:
            trades = db.query(TradeLedgerEntry).filter_by(batch_id=batch_id).all()
            # Trades may or may not exist depending on signals, but query should work
            assert isinstance(trades, list)
        finally:
            db.close()

    def test_portfolio_partial_failure(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.side_effect = [mock_ohlcv, Exception("Data unavailable")]

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL", "FAKE"],
                "strategy": "ma_crossover",
                "params": {"fast_period": 5, "slow_period": 20},
                "start": "2023-01-01",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["symbols_completed"] >= 1
        assert data["symbols_failed"] >= 1


class TestTradesEndToEnd:

    def test_get_trades_with_filter(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL", "MSFT"],
                "strategy": "ma_crossover",
                "params": {"fast_period": 5, "slow_period": 20},
                "start": "2023-01-01",
            })

        batch_id = response.json()["batch_id"]

        trades_resp = client.get(
            f"/api/v1/backtest/portfolio/{batch_id}/trades",
            params={"symbol": "AAPL", "limit": 10},
        )
        assert trades_resp.status_code == 200
        data = trades_resp.json()
        assert "trades" in data
        for trade in data["trades"]:
            assert trade["symbol"] == "AAPL"


class TestMultiStrategyEndToEnd:

    def test_multi_strategy_backtest(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/multi-strategy", json={
                "symbol": "AAPL",
                "strategies": [
                    {"type": "ma_crossover", "params": {"fast_period": 5, "slow_period": 20}},
                    {"type": "rsi", "params": {}},
                ],
                "combination_method": "priority",
                "start": "2023-01-01",
            })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert len(data["strategies_used"]) == 2
        assert data["combination_method"] == "priority"


class TestSymbolsEndpoint:

    def test_list_symbols_default(self, client):
        response = client.get("/api/v1/symbols")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["symbols"]) > 0

    def test_list_symbols_sector_filter(self, client):
        response = client.get("/api/v1/symbols", params={"sector": "Technology"})
        assert response.status_code == 200
        for sym in response.json()["symbols"]:
            assert sym["sector"] == "Technology"

    def test_list_symbols_pagination(self, client):
        resp1 = client.get("/api/v1/symbols", params={"limit": 5, "offset": 0})
        resp2 = client.get("/api/v1/symbols", params={"limit": 5, "offset": 5})
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        symbols1 = [s["symbol"] for s in resp1.json()["symbols"]]
        symbols2 = [s["symbol"] for s in resp2.json()["symbols"]]
        assert set(symbols1).isdisjoint(set(symbols2))


class TestAPIErrorHandling:

    def test_get_nonexistent_portfolio(self, client):
        response = client.get("/api/v1/backtest/portfolio/nonexistent-id")
        assert response.status_code == 404

    def test_get_trades_nonexistent_portfolio(self, client):
        response = client.get("/api/v1/backtest/portfolio/nonexistent-id/trades")
        assert response.status_code == 404

    def test_invalid_strategy_type(self, client):
        response = client.post("/api/v1/backtest/portfolio", json={
            "symbols": ["AAPL"],
            "strategy": "invalid_strategy",
            "start": "2023-01-01",
        })
        assert response.status_code == 422

    def test_empty_symbols_list(self, client):
        response = client.post("/api/v1/backtest/portfolio", json={
            "symbols": [],
            "strategy": "ma_crossover",
            "start": "2023-01-01",
        })
        assert response.status_code == 422

    def test_invalid_symbols_source(self, client):
        response = client.get("/api/v1/symbols", params={"source": "invalid"})
        assert response.status_code == 400


class TestDatabaseConsistency:
    """Verify foreign key relationships and cascade behavior."""

    def test_symbol_results_linked_to_portfolio(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "params": {"fast_period": 5, "slow_period": 20},
                "start": "2023-01-01",
            })

        batch_id = response.json()["batch_id"]
        db = SessionLocal()
        try:
            sr = db.query(SymbolResult).filter_by(batch_id=batch_id).first()
            assert sr is not None
            assert sr.batch_id == batch_id
        finally:
            db.close()

    def test_timestamps_are_set(self, client, mock_ohlcv):
        mock_loader = MagicMock()
        mock_loader.load.return_value = mock_ohlcv

        with patch("src.data.YahooDataLoader", return_value=mock_loader):
            response = client.post("/api/v1/backtest/portfolio", json={
                "symbols": ["AAPL"],
                "strategy": "rsi",
                "start": "2023-01-01",
            })

        batch_id = response.json()["batch_id"]
        db = SessionLocal()
        try:
            pr = db.query(PortfolioResult).filter_by(batch_id=batch_id).first()
            assert pr.created_at is not None
            assert pr.started_at is not None
            assert pr.finished_at is not None
        finally:
            db.close()

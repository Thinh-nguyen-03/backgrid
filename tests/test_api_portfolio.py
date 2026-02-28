"""Unit tests for portfolio API endpoints."""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient

from src.db import Base, engine, SessionLocal, PortfolioResult, SymbolResult, TradeLedgerEntry
from src.api import app
from src.worker import app as celery_app


@pytest.fixture(scope="module", autouse=True)
def configure_celery():
    """Run Celery tasks synchronously during tests (no worker required)."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False


@pytest.fixture(scope="module")
def test_db():
    """Create test database tables once per module."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Database session with per-test cleanup."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.query(TradeLedgerEntry).delete()
    session.query(SymbolResult).delete()
    session.query(PortfolioResult).delete()
    session.commit()
    session.close()


@pytest.fixture
def client(test_db):
    """Test client."""
    return TestClient(app)


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for mocking."""
    dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
    data = {
        'Open': [100 + i * 0.1 for i in range(100)],
        'High': [105 + i * 0.1 for i in range(100)],
        'Low': [95 + i * 0.1 for i in range(100)],
        'Close': [102 + i * 0.1 for i in range(100)],
        'Volume': [1000000 + i * 10000 for i in range(100)]
    }
    return pd.DataFrame(data, index=dates)


class TestPortfolioBacktestEndpoint:
    """Tests for POST /api/v1/backtest/portfolio"""

    @patch('src.data.YahooDataLoader')
    def test_submit_portfolio_backtest_success(self, mock_loader_class, client, sample_ohlcv_data):
        """Submission returns 202 immediately; task executes synchronously via always_eager."""
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL", "MSFT"],
                "strategy": "ma_crossover",
                "params": {"fast": 10, "slow": 30},
                "start": "2023-01-01",
                "end": "2023-12-31"
            }
        )

        assert response.status_code == 202
        data = response.json()
        assert "batch_id" in data
        assert data["status"] == "pending"
        assert data["symbols_requested"] == 2

    @patch('src.data.YahooDataLoader')
    def test_submit_portfolio_with_config(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "rsi",
                "params": {"rsi_period": 14, "oversold_threshold": 30, "overbought_threshold": 70},
                "start": "2023-01-01",
                "config": {
                    "initial_capital": 50000,
                    "position_sizing": "atr",
                    "risk_per_trade": 0.02
                }
            }
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    def test_submit_portfolio_empty_symbols(self, client):
        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": [],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 422

    def test_submit_portfolio_invalid_strategy(self, client):
        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "invalid_strategy",
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 422

    def test_submit_portfolio_invalid_date_format(self, client):
        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "01/01/2023"
            }
        )

        assert response.status_code == 422

    @patch('src.data.YahooDataLoader')
    def test_submit_portfolio_partial_failure(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        """Partial failure: task runs synchronously, then GET returns actual status."""
        mock_loader = Mock()

        def load_side_effect(symbol, start, end):
            if symbol == "INVALID":
                return pd.DataFrame()
            return sample_ohlcv_data

        mock_loader.load.side_effect = load_side_effect
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL", "INVALID"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 202
        batch_id = response.json()["batch_id"]

        # With task_always_eager, the task already ran. Poll to verify.
        db_session.expire_all()
        portfolio = db_session.query(PortfolioResult).filter(
            PortfolioResult.batch_id == batch_id
        ).first()
        assert portfolio is not None
        assert portfolio.symbols_failed >= 1


class TestGetPortfolioEndpoint:
    """Tests for GET /api/v1/backtest/portfolio/{batch_id}"""

    @patch('src.data.YahooDataLoader')
    def test_get_portfolio_success(self, mock_loader_class, client, sample_ohlcv_data):
        """POST enqueues, task runs synchronously, GET returns completed result."""
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        submit_response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert submit_response.status_code == 202
        batch_id = submit_response.json()["batch_id"]

        response = client.get(f"/api/v1/backtest/portfolio/{batch_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == batch_id
        assert data["status"] == "completed"
        assert "results_by_symbol" in data

    def test_get_portfolio_not_found(self, client):
        response = client.get("/api/v1/backtest/portfolio/nonexistent-batch-id")

        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower()


class TestTradesEndpoint:
    """Tests for GET /api/v1/backtest/portfolio/{batch_id}/trades"""

    @patch('src.data.YahooDataLoader')
    def test_get_trades_success(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        submit_response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert submit_response.status_code == 202
        batch_id = submit_response.json()["batch_id"]

        response = client.get(f"/api/v1/backtest/portfolio/{batch_id}/trades")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == batch_id
        assert "trades" in data
        assert "total_trades" in data

    @patch('src.data.YahooDataLoader')
    def test_get_trades_with_symbol_filter(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        submit_response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL", "MSFT"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert submit_response.status_code == 202
        batch_id = submit_response.json()["batch_id"]

        response = client.get(
            f"/api/v1/backtest/portfolio/{batch_id}/trades",
            params={"symbol": "AAPL"}
        )

        assert response.status_code == 200
        data = response.json()
        for trade in data["trades"]:
            assert trade["symbol"] == "AAPL"

    def test_get_trades_not_found(self, client):
        response = client.get("/api/v1/backtest/portfolio/nonexistent/trades")

        assert response.status_code == 404

    @patch('src.data.YahooDataLoader')
    def test_get_trades_pagination(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        submit_response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert submit_response.status_code == 202
        batch_id = submit_response.json()["batch_id"]

        response = client.get(
            f"/api/v1/backtest/portfolio/{batch_id}/trades",
            params={"limit": 5, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5
        assert data["offset"] == 0


class TestMultiStrategyEndpoint:
    """Tests for POST /api/v1/backtest/multi-strategy"""

    @patch('src.data.YahooDataLoader')
    def test_multi_strategy_success(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/multi-strategy",
            json={
                "symbol": "AAPL",
                "strategies": [
                    {"type": "ma_crossover", "params": {"fast": 10, "slow": 30}},
                    {"type": "rsi", "params": {"rsi_period": 14}}
                ],
                "combination_method": "priority",
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["symbol"] == "AAPL"
        assert len(data["strategies_used"]) == 2
        assert data["combination_method"] == "priority"

    @patch('src.data.YahooDataLoader')
    def test_multi_strategy_or_combination(self, mock_loader_class, client, sample_ohlcv_data):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/multi-strategy",
            json={
                "symbol": "AAPL",
                "strategies": [
                    {"type": "ma_crossover", "params": {"fast": 20, "slow": 50}},
                    {"type": "rsi", "params": {"rsi_period": 14}}
                ],
                "combination_method": "or",
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["combination_method"] == "or"

    def test_multi_strategy_empty_strategies(self, client):
        response = client.post(
            "/api/v1/backtest/multi-strategy",
            json={
                "symbol": "AAPL",
                "strategies": [],
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 422

    def test_multi_strategy_invalid_strategy_type(self, client):
        response = client.post(
            "/api/v1/backtest/multi-strategy",
            json={
                "symbol": "AAPL",
                "strategies": [
                    {"type": "invalid_type", "params": {}}
                ],
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 422

    def test_multi_strategy_missing_type(self, client):
        response = client.post(
            "/api/v1/backtest/multi-strategy",
            json={
                "symbol": "AAPL",
                "strategies": [
                    {"params": {"fast": 10, "slow": 30}}
                ],
                "start": "2023-01-01"
            }
        )

        assert response.status_code == 422


class TestSymbolsEndpoint:
    """Tests for GET /api/v1/symbols"""

    def test_list_symbols_yahoo(self, client):
        response = client.get("/api/v1/symbols", params={"source": "yahoo"})

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "yahoo"
        assert data["total"] > 0
        assert len(data["symbols"]) > 0
        assert "symbol" in data["symbols"][0]

    def test_list_symbols_with_sector_filter(self, client):
        response = client.get(
            "/api/v1/symbols",
            params={"source": "yahoo", "sector": "Technology"}
        )

        assert response.status_code == 200
        data = response.json()
        for symbol in data["symbols"]:
            assert symbol["sector"] == "Technology"

    def test_list_symbols_pagination(self, client):
        response = client.get(
            "/api/v1/symbols",
            params={"source": "yahoo", "limit": 5, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["symbols"]) <= 5

    def test_list_symbols_invalid_source(self, client):
        response = client.get("/api/v1/symbols", params={"source": "invalid"})

        assert response.status_code == 400


class TestPydanticModels:
    """Tests for Pydantic model validation."""

    def test_portfolio_request_symbol_normalization(self, client):
        from src.models import PortfolioBacktestRequest

        request = PortfolioBacktestRequest(
            symbols=["aapl", "msft"],
            strategy="ma_crossover",
            start="2023-01-01"
        )

        assert request.symbols == ["AAPL", "MSFT"]

    def test_portfolio_request_duplicate_removal(self, client):
        from src.models import PortfolioBacktestRequest

        request = PortfolioBacktestRequest(
            symbols=["AAPL", "aapl", "MSFT"],
            strategy="ma_crossover",
            start="2023-01-01"
        )

        assert len(request.symbols) == 2

    def test_backtest_config_validation(self):
        from src.models import BacktestConfigModel

        config = BacktestConfigModel(
            initial_capital=50000,
            position_sizing="atr",
            risk_per_trade=0.02
        )

        assert config.initial_capital == 50000
        assert config.position_sizing == "atr"

    def test_backtest_config_invalid_position_sizing(self):
        from src.models import BacktestConfigModel
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BacktestConfigModel(position_sizing="invalid")

    def test_multi_strategy_request_validation(self):
        from src.models import MultiStrategyRequest

        request = MultiStrategyRequest(
            symbol="AAPL",
            strategies=[
                {"type": "ma_crossover", "params": {"fast": 10, "slow": 30}},
                {"type": "rsi", "params": {}}
            ],
            start="2023-01-01"
        )

        assert request.symbol == "AAPL"
        assert len(request.strategies) == 2


class TestDatabaseIntegration:
    """Tests for database operations."""

    @patch('src.data.YahooDataLoader')
    def test_portfolio_result_persisted(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        """With task_always_eager, task runs synchronously so DB is populated by the time we query."""
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert response.status_code == 202
        batch_id = response.json()["batch_id"]

        db_session.expire_all()
        portfolio = db_session.query(PortfolioResult).filter(
            PortfolioResult.batch_id == batch_id
        ).first()

        assert portfolio is not None
        assert portfolio.status == "completed"

    @patch('src.data.YahooDataLoader')
    def test_symbol_results_persisted(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL", "MSFT"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert response.status_code == 202
        batch_id = response.json()["batch_id"]

        db_session.expire_all()
        symbol_results = db_session.query(SymbolResult).filter(
            SymbolResult.batch_id == batch_id
        ).all()

        assert len(symbol_results) == 2

    @patch('src.data.YahooDataLoader')
    def test_trades_persisted(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        mock_loader = Mock()
        mock_loader.load.return_value = sample_ohlcv_data
        mock_loader_class.return_value = mock_loader

        response = client.post(
            "/api/v1/backtest/portfolio",
            json={
                "symbols": ["AAPL"],
                "strategy": "ma_crossover",
                "start": "2023-01-01"
            }
        )
        assert response.status_code == 202
        batch_id = response.json()["batch_id"]

        db_session.expire_all()
        trades = db_session.query(TradeLedgerEntry).filter(
            TradeLedgerEntry.batch_id == batch_id
        ).all()

        assert isinstance(trades, list)

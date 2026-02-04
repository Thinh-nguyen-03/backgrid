"""Unit tests for portfolio API endpoints (Week 6)"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient

from src.db import Base, engine, SessionLocal, PortfolioResult, SymbolResult, TradeLedgerEntry
from src.api import app


@pytest.fixture(scope="module")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_db):
    """Get database session for each test."""
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
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for mocking."""
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
        """Test successful portfolio backtest submission."""
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

        assert response.status_code == 200
        data = response.json()
        assert "batch_id" in data
        assert data["status"] == "completed"
        assert data["symbols_requested"] == 2
        assert data["symbols_completed"] is not None

    @patch('src.data.YahooDataLoader')
    def test_submit_portfolio_with_config(self, mock_loader_class, client, sample_ohlcv_data):
        """Test portfolio backtest with custom configuration."""
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

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    def test_submit_portfolio_empty_symbols(self, client):
        """Test that empty symbol list returns 422."""
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
        """Test that invalid strategy returns 422."""
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
        """Test that invalid date format returns 422."""
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
    def test_submit_portfolio_partial_failure(self, mock_loader_class, client, sample_ohlcv_data):
        """Test portfolio backtest with some symbol failures."""
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

        assert response.status_code == 200
        data = response.json()
        assert data["symbols_failed"] >= 1


class TestGetPortfolioEndpoint:
    """Tests for GET /api/v1/backtest/portfolio/{batch_id}"""

    @patch('src.data.YahooDataLoader')
    def test_get_portfolio_success(self, mock_loader_class, client, sample_ohlcv_data):
        """Test successful portfolio retrieval."""
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
        batch_id = submit_response.json()["batch_id"]

        response = client.get(f"/api/v1/backtest/portfolio/{batch_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == batch_id
        assert "results_by_symbol" in data

    def test_get_portfolio_not_found(self, client):
        """Test that non-existent batch returns 404."""
        response = client.get("/api/v1/backtest/portfolio/nonexistent-batch-id")

        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower()


class TestTradesEndpoint:
    """Tests for GET /api/v1/backtest/portfolio/{batch_id}/trades"""

    @patch('src.data.YahooDataLoader')
    def test_get_trades_success(self, mock_loader_class, client, sample_ohlcv_data):
        """Test successful trade ledger retrieval."""
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
        batch_id = submit_response.json()["batch_id"]

        response = client.get(f"/api/v1/backtest/portfolio/{batch_id}/trades")

        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == batch_id
        assert "trades" in data
        assert "total_trades" in data

    @patch('src.data.YahooDataLoader')
    def test_get_trades_with_symbol_filter(self, mock_loader_class, client, sample_ohlcv_data):
        """Test trade retrieval with symbol filter."""
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
        """Test that non-existent batch returns 404."""
        response = client.get("/api/v1/backtest/portfolio/nonexistent/trades")

        assert response.status_code == 404

    @patch('src.data.YahooDataLoader')
    def test_get_trades_pagination(self, mock_loader_class, client, sample_ohlcv_data):
        """Test trade ledger pagination."""
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
        """Test successful multi-strategy backtest."""
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
        """Test multi-strategy with OR combination."""
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
        """Test that empty strategies list returns 422."""
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
        """Test that invalid strategy type returns 422."""
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
        """Test that strategy without type returns 422."""
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
        """Test listing symbols from Yahoo source."""
        response = client.get("/api/v1/symbols", params={"source": "yahoo"})

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "yahoo"
        assert data["total"] > 0
        assert len(data["symbols"]) > 0
        assert "symbol" in data["symbols"][0]

    def test_list_symbols_with_sector_filter(self, client):
        """Test listing symbols with sector filter."""
        response = client.get(
            "/api/v1/symbols",
            params={"source": "yahoo", "sector": "Technology"}
        )

        assert response.status_code == 200
        data = response.json()
        for symbol in data["symbols"]:
            assert symbol["sector"] == "Technology"

    def test_list_symbols_pagination(self, client):
        """Test symbol list pagination."""
        response = client.get(
            "/api/v1/symbols",
            params={"source": "yahoo", "limit": 5, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["symbols"]) <= 5

    def test_list_symbols_invalid_source(self, client):
        """Test that invalid source returns 400."""
        response = client.get("/api/v1/symbols", params={"source": "invalid"})

        assert response.status_code == 400


class TestPydanticModels:
    """Tests for Pydantic model validation."""

    def test_portfolio_request_symbol_normalization(self, client):
        """Test that symbols are normalized to uppercase."""
        from src.models import PortfolioBacktestRequest

        request = PortfolioBacktestRequest(
            symbols=["aapl", "msft"],
            strategy="ma_crossover",
            start="2023-01-01"
        )

        assert request.symbols == ["AAPL", "MSFT"]

    def test_portfolio_request_duplicate_removal(self, client):
        """Test that duplicate symbols are removed."""
        from src.models import PortfolioBacktestRequest

        request = PortfolioBacktestRequest(
            symbols=["AAPL", "aapl", "MSFT"],
            strategy="ma_crossover",
            start="2023-01-01"
        )

        assert len(request.symbols) == 2

    def test_backtest_config_validation(self):
        """Test BacktestConfigModel validation."""
        from src.models import BacktestConfigModel

        config = BacktestConfigModel(
            initial_capital=50000,
            position_sizing="atr",
            risk_per_trade=0.02
        )

        assert config.initial_capital == 50000
        assert config.position_sizing == "atr"

    def test_backtest_config_invalid_position_sizing(self):
        """Test that invalid position_sizing raises error."""
        from src.models import BacktestConfigModel
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BacktestConfigModel(position_sizing="invalid")

    def test_multi_strategy_request_validation(self):
        """Test MultiStrategyRequest validation."""
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
        """Test that portfolio results are persisted to database."""
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
        batch_id = response.json()["batch_id"]

        portfolio = db_session.query(PortfolioResult).filter(
            PortfolioResult.batch_id == batch_id
        ).first()

        assert portfolio is not None
        assert portfolio.status == "completed"

    @patch('src.data.YahooDataLoader')
    def test_symbol_results_persisted(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        """Test that symbol results are persisted to database."""
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
        batch_id = response.json()["batch_id"]

        symbol_results = db_session.query(SymbolResult).filter(
            SymbolResult.batch_id == batch_id
        ).all()

        assert len(symbol_results) == 2

    @patch('src.data.YahooDataLoader')
    def test_trades_persisted(self, mock_loader_class, client, sample_ohlcv_data, db_session):
        """Test that trades are persisted to database."""
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
        batch_id = response.json()["batch_id"]

        trades = db_session.query(TradeLedgerEntry).filter(
            TradeLedgerEntry.batch_id == batch_id
        ).all()

        assert isinstance(trades, list)

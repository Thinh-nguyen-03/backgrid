"""Unit tests for FastAPI endpoints"""

import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime

from src.api import app
from src.db import Base, get_db, Job, Result
from src.data import DataFetchError


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with StaticPool so all connections share one DB."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Database session bound to the in-memory engine."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """Test client with the DB dependency overridden to use in-memory SQLite."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for mocking."""
    dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
    data = {
        'Open': [100 + i for i in range(100)],
        'High': [105 + i for i in range(100)],
        'Low': [95 + i for i in range(100)],
        'Close': [102 + i for i in range(100)],
        'Volume': [1000000 + i * 10000 for i in range(100)]
    }
    return pd.DataFrame(data, index=dates)


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["phase"] == 2
        assert "timestamp" in data

    def test_health_check_returns_json(self, client):
        response = client.get("/api/v1/health")

        assert response.headers["content-type"] == "application/json"


class TestSubmitJobEndpoint:
    """Test job submission endpoint"""

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_job_success(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data
        mock_backtest.return_value = {
            "job_id": "manual-20250115-120000",
            "status": "completed",
            "sharpe": 1.23,
            "max_drawdown": -0.18,
            "total_return": 0.45,
            "equity_curve": [10000, 10200, 10500],
            "runtime_seconds": 2.3,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "params": {"fast": 10, "slow": 30},
                "start": "2020-01-01",
                "end": "2020-12-31"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "manual-20250115-120000"
        assert data["status"] == "completed"
        assert data["sharpe"] == 1.23
        assert data["max_drawdown"] == -0.18
        assert data["total_return"] == 0.45
        assert data["equity_curve"] == [10000, 10200, 10500]
        assert data["runtime_seconds"] == 2.3

        mock_fetch.assert_called_once_with(
            symbol="AAPL",
            start="2020-01-01",
            end="2020-12-31"
        )
        mock_backtest.assert_called_once()

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_without_end_date(self, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "params": {"fast": 10, "slow": 30},
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 200
        mock_fetch.assert_called_once_with(
            symbol="AAPL",
            start="2020-01-01",
            end=None
        )

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_default_params(self, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 200

    def test_submit_job_missing_required_fields(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={"symbol": "AAPL"}
        )

        assert response.status_code == 422

    def test_submit_job_invalid_symbol(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "INVALID@SYMBOL",
                "strategy": "ma_crossover",
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 422

    def test_submit_job_invalid_date_format(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "start": "01/01/2020"
            }
        )

        assert response.status_code == 422

    def test_submit_job_invalid_strategy(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "invalid_strategy",
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 422

    def test_submit_job_invalid_params(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "params": {"fast": 30, "slow": 10},
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 422

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_data_fetch_error(self, mock_fetch, client):
        mock_fetch.side_effect = DataFetchError("Symbol not found")

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "INVALID",
                "strategy": "ma_crossover",
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "failed to fetch data" in data["error"].lower()

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_value_error(self, mock_fetch, client):
        mock_fetch.side_effect = ValueError("Invalid date range")

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "start": "2020-01-01",
                "end": "2019-12-31"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_job_backtest_error(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data
        mock_backtest.side_effect = ValueError("Insufficient data for backtest")

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "params": {"fast": 10, "slow": 50},
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "backtest execution failed" in data["error"].lower()

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_job_persists_to_db(self, mock_backtest, mock_fetch, client, db_session, sample_ohlcv_data):
        """Verify that a submitted job is persisted to the database."""
        mock_fetch.return_value = sample_ohlcv_data
        mock_backtest.return_value = {
            "job_id": "test-job-123",
            "status": "completed",
            "sharpe": 1.5,
            "max_drawdown": -0.2,
            "total_return": 0.3,
            "equity_curve": [10000, 11000],
            "runtime_seconds": 1.5,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }

        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 200

        result = db_session.query(Result).filter(Result.job_id == "test-job-123").first()
        assert result is not None
        assert result.sharpe == 1.5


class TestGetJobEndpoint:
    """Test job retrieval endpoint"""

    def test_get_job_success(self, client, db_session):
        """Job pre-inserted into the DB is correctly returned via GET."""
        job = Job(
            job_id="test-job-456",
            symbol="AAPL",
            strategy="ma_crossover",
            params={"fast": 10, "slow": 30},
            start_date="2020-01-01",
            end_date="2020-12-31",
            status="completed",
            created_at=datetime(2025, 1, 15, 12, 0, 0),
        )
        result = Result(
            job_id="test-job-456",
            sharpe=1.2,
            max_drawdown=-0.15,
            total_return=0.25,
            equity_curve=[10000, 10500, 11000],
            runtime_seconds=2.0,
            created_at=datetime(2025, 1, 15, 12, 0, 0),
        )
        db_session.add(job)
        db_session.add(result)
        db_session.commit()

        response = client.get("/api/v1/jobs/test-job-456")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-456"
        assert data["status"] == "completed"
        assert data["sharpe"] == 1.2
        assert data["max_drawdown"] == -0.15
        assert data["total_return"] == 0.25
        assert data["equity_curve"] == [10000, 10500, 11000]
        assert data["runtime_seconds"] == 2.0

    def test_get_job_not_found(self, client):
        response = client.get("/api/v1/jobs/nonexistent-job")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_get_job_returns_json(self, client, db_session):
        job = Job(
            job_id="test-job-789",
            symbol="AAPL",
            strategy="ma_crossover",
            params=None,
            start_date="2020-01-01",
            end_date=None,
            status="completed",
            created_at=datetime(2025, 1, 15, 12, 0, 0),
        )
        result = Result(
            job_id="test-job-789",
            sharpe=1.0,
            max_drawdown=-0.1,
            total_return=0.2,
            equity_curve=[10000],
            runtime_seconds=1.0,
            created_at=datetime(2025, 1, 15, 12, 0, 0),
        )
        db_session.add(job)
        db_session.add(result)
        db_session.commit()

        response = client.get("/api/v1/jobs/test-job-789")

        assert response.headers["content-type"] == "application/json"


class TestIntegration:
    """Integration tests for complete workflows"""

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_and_retrieve_job(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data
        mock_backtest.return_value = {
            "job_id": "integration-test-123",
            "status": "completed",
            "sharpe": 1.8,
            "max_drawdown": -0.12,
            "total_return": 0.35,
            "equity_curve": [10000, 10500, 11000, 11500],
            "runtime_seconds": 1.8,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }

        submit_response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "MSFT",
                "strategy": "ma_crossover",
                "params": {"fast": 5, "slow": 20},
                "start": "2020-01-01",
                "end": "2020-12-31"
            }
        )

        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        get_response = client.get(f"/api/v1/jobs/{job_id}")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["job_id"] == job_id
        assert data["sharpe"] == 1.8
        assert data["max_drawdown"] == -0.12
        assert data["total_return"] == 0.35

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_multiple_jobs_independent(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        mock_fetch.return_value = sample_ohlcv_data

        mock_backtest.return_value = {
            "job_id": "job-1",
            "status": "completed",
            "sharpe": 1.0,
            "max_drawdown": -0.1,
            "total_return": 0.1,
            "equity_curve": [10000, 11000],
            "runtime_seconds": 1.0,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }
        response1 = client.post(
            "/api/v1/jobs",
            json={"symbol": "AAPL", "strategy": "ma_crossover", "start": "2020-01-01"}
        )

        mock_backtest.return_value = {
            "job_id": "job-2",
            "status": "completed",
            "sharpe": 2.0,
            "max_drawdown": -0.2,
            "total_return": 0.2,
            "equity_curve": [10000, 12000],
            "runtime_seconds": 2.0,
            "created_at": datetime(2025, 1, 15, 12, 1, 0)
        }
        response2 = client.post(
            "/api/v1/jobs",
            json={"symbol": "MSFT", "strategy": "ma_crossover", "start": "2020-01-01"}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        job1_data = client.get("/api/v1/jobs/job-1").json()
        job2_data = client.get("/api/v1/jobs/job-2").json()

        assert job1_data["sharpe"] == 1.0
        assert job2_data["sharpe"] == 2.0

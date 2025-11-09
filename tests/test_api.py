"""Unit tests for FastAPI endpoints"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from datetime import datetime

from src.api import app, job_results
from src.data import DataFetchError


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for mocking"""
    dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
    data = {
        'Open': [100 + i for i in range(100)],
        'High': [105 + i for i in range(100)],
        'Low': [95 + i for i in range(100)],
        'Close': [102 + i for i in range(100)],
        'Volume': [1000000 + i * 10000 for i in range(100)]
    }
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture(autouse=True)
def clear_job_results():
    """Clear job results before each test"""
    job_results.clear()
    yield
    job_results.clear()


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check_success(self, client):
        """Test successful health check"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["phase"] == 1
        assert "timestamp" in data

    def test_health_check_returns_json(self, client):
        """Test that health check returns JSON"""
        response = client.get("/api/v1/health")

        assert response.headers["content-type"] == "application/json"


class TestSubmitJobEndpoint:
    """Test job submission endpoint"""

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_job_success(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        """Test successful job submission"""
        # Mock data fetch
        mock_fetch.return_value = sample_ohlcv_data

        # Mock backtest result
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

        # Submit job
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

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "manual-20250115-120000"
        assert data["status"] == "completed"
        assert data["sharpe"] == 1.23
        assert data["max_drawdown"] == -0.18
        assert data["total_return"] == 0.45
        assert data["equity_curve"] == [10000, 10200, 10500]
        assert data["runtime_seconds"] == 2.3

        # Verify mocks were called
        mock_fetch.assert_called_once_with(
            symbol="AAPL",
            start="2020-01-01",
            end="2020-12-31"
        )
        mock_backtest.assert_called_once()

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_without_end_date(self, mock_fetch, client, sample_ohlcv_data):
        """Test job submission without end date"""
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
        """Test job submission with default parameters"""
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
        """Test that missing required fields return 422"""
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL"
                # Missing strategy and start
            }
        )

        assert response.status_code == 422

    def test_submit_job_invalid_symbol(self, client):
        """Test that invalid symbol format returns 422"""
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
        """Test that invalid date format returns 422"""
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "start": "01/01/2020"  # Wrong format
            }
        )

        assert response.status_code == 422

    def test_submit_job_invalid_strategy(self, client):
        """Test that invalid strategy returns 422"""
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
        """Test that invalid strategy params return 422"""
        response = client.post(
            "/api/v1/jobs",
            json={
                "symbol": "AAPL",
                "strategy": "ma_crossover",
                "params": {"fast": 30, "slow": 10},  # fast >= slow
                "start": "2020-01-01"
            }
        )

        assert response.status_code == 422

    @patch('src.api.fetch_ohlcv')
    def test_submit_job_data_fetch_error(self, mock_fetch, client):
        """Test that data fetch errors return 400"""
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
        """Test that value errors return 400"""
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
        """Test that backtest errors return 400"""
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
    def test_submit_job_stores_result(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        """Test that job results are stored in memory"""
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

        # Verify result is stored
        from src.api import job_results
        assert "test-job-123" in job_results
        assert job_results["test-job-123"]["sharpe"] == 1.5


class TestGetJobEndpoint:
    """Test job retrieval endpoint"""

    def test_get_job_success(self, client):
        """Test successful job retrieval"""
        # Pre-populate a job result
        from src.api import job_results
        job_results["test-job-456"] = {
            "job_id": "test-job-456",
            "status": "completed",
            "sharpe": 1.2,
            "max_drawdown": -0.15,
            "total_return": 0.25,
            "equity_curve": [10000, 10500, 11000],
            "runtime_seconds": 2.0,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }

        # Retrieve job
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
        """Test that non-existent job returns 404"""
        response = client.get("/api/v1/jobs/nonexistent-job")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_get_job_returns_json(self, client):
        """Test that get job returns JSON"""
        from src.api import job_results
        job_results["test-job-789"] = {
            "job_id": "test-job-789",
            "status": "completed",
            "sharpe": 1.0,
            "max_drawdown": -0.1,
            "total_return": 0.2,
            "equity_curve": [10000],
            "runtime_seconds": 1.0,
            "created_at": datetime(2025, 1, 15, 12, 0, 0)
        }

        response = client.get("/api/v1/jobs/test-job-789")

        assert response.headers["content-type"] == "application/json"


class TestIntegration:
    """Integration tests for complete workflows"""

    @patch('src.api.fetch_ohlcv')
    @patch('src.api.run_backtest')
    def test_submit_and_retrieve_job(self, mock_backtest, mock_fetch, client, sample_ohlcv_data):
        """Test complete workflow: submit job and retrieve result"""
        # Mock responses
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

        # Submit job
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

        # Retrieve job
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
        """Test that multiple jobs are stored independently"""
        mock_fetch.return_value = sample_ohlcv_data

        # Submit first job
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

        # Submit second job
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

        # Verify both jobs are stored independently
        job1_data = client.get("/api/v1/jobs/job-1").json()
        job2_data = client.get("/api/v1/jobs/job-2").json()

        assert job1_data["sharpe"] == 1.0
        assert job2_data["sharpe"] == 2.0

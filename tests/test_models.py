"""Unit tests for Pydantic models"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from src.models import (
    BacktestRequest,
    BacktestResponse,
    StrategyType,
    JobStatus,
    HealthResponse,
    ErrorResponse
)


class TestBacktestRequest:
    """Test BacktestRequest model validation"""

    def test_valid_request_minimal(self):
        """Test valid request with minimal fields"""
        request = BacktestRequest(
            symbol="AAPL",
            strategy="ma_crossover",
            start="2020-01-01"
        )
        assert request.symbol == "AAPL"
        assert request.strategy == StrategyType.MA_CROSSOVER
        assert request.start == "2020-01-01"
        assert request.end is None
        assert request.params == {"fast": 10, "slow": 30}

    def test_valid_request_full(self):
        """Test valid request with all fields"""
        request = BacktestRequest(
            symbol="MSFT",
            strategy="ma_crossover",
            params={"fast": 5, "slow": 20},
            start="2020-01-01",
            end="2023-12-31"
        )
        assert request.symbol == "MSFT"
        assert request.params["fast"] == 5
        assert request.params["slow"] == 20
        assert request.end == "2023-12-31"

    def test_symbol_uppercase_conversion(self):
        """Test that symbol is converted to uppercase"""
        request = BacktestRequest(
            symbol="aapl",
            strategy="ma_crossover",
            start="2020-01-01"
        )
        assert request.symbol == "AAPL"

    def test_symbol_whitespace_stripped(self):
        """Test that symbol whitespace is stripped"""
        request = BacktestRequest(
            symbol="  AAPL  ",
            strategy="ma_crossover",
            start="2020-01-01"
        )
        assert request.symbol == "AAPL"

    def test_symbol_with_dot_valid(self):
        """Test symbol with dot (e.g., BRK.B) is valid"""
        request = BacktestRequest(
            symbol="BRK.B",
            strategy="ma_crossover",
            start="2020-01-01"
        )
        assert request.symbol == "BRK.B"

    def test_symbol_with_hyphen_valid(self):
        """Test symbol with hyphen is valid"""
        request = BacktestRequest(
            symbol="SPY-X",
            strategy="ma_crossover",
            start="2020-01-01"
        )
        assert request.symbol == "SPY-X"

    def test_invalid_symbol_empty(self):
        """Test that empty symbol raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="",
                strategy="ma_crossover",
                start="2020-01-01"
            )
        assert "symbol" in str(exc_info.value).lower()

    def test_invalid_symbol_special_chars(self):
        """Test that symbol with invalid special characters fails"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL@123",
                strategy="ma_crossover",
                start="2020-01-01"
            )
        assert "alphanumeric" in str(exc_info.value).lower()

    def test_invalid_strategy(self):
        """Test that invalid strategy raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL",
                strategy="invalid_strategy",
                start="2020-01-01"
            )

    def test_invalid_date_format(self):
        """Test that invalid date format raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL",
                strategy="ma_crossover",
                start="01/01/2020"  # Wrong format
            )
        assert "start" in str(exc_info.value).lower()

    def test_invalid_params_fast_slow_reversed(self):
        """Test that fast >= slow raises validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL",
                strategy="ma_crossover",
                params={"fast": 30, "slow": 10},
                start="2020-01-01"
            )
        assert "fast period must be less than slow" in str(exc_info.value).lower()

    def test_invalid_params_negative_values(self):
        """Test that negative params raise validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL",
                strategy="ma_crossover",
                params={"fast": -10, "slow": 30},
                start="2020-01-01"
            )
        assert "positive" in str(exc_info.value).lower()

    def test_invalid_params_non_integer(self):
        """Test that non-integer params raise validation error"""
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(
                symbol="AAPL",
                strategy="ma_crossover",
                params={"fast": "10", "slow": 30},
                start="2020-01-01"
            )
        assert "must be integer" in str(exc_info.value).lower()


class TestBacktestResponse:
    """Test BacktestResponse model"""

    def test_valid_response_completed(self):
        """Test valid completed response"""
        response = BacktestResponse(
            job_id="test-123",
            status=JobStatus.COMPLETED,
            sharpe=1.23,
            max_drawdown=-0.18,
            total_return=0.45,
            equity_curve=[10000, 10200, 10500],
            runtime_seconds=2.3
        )
        assert response.job_id == "test-123"
        assert response.status == JobStatus.COMPLETED
        assert response.sharpe == 1.23
        assert response.max_drawdown == -0.18
        assert len(response.equity_curve) == 3

    def test_valid_response_failed(self):
        """Test valid failed response"""
        response = BacktestResponse(
            job_id="test-456",
            status=JobStatus.FAILED,
            error="Failed to fetch data from Yahoo Finance"
        )
        assert response.status == JobStatus.FAILED
        assert response.error is not None
        assert response.sharpe is None

    def test_valid_response_queued(self):
        """Test valid queued response (Phase 2)"""
        response = BacktestResponse(
            job_id="test-789",
            status=JobStatus.QUEUED
        )
        assert response.status == JobStatus.QUEUED
        assert response.sharpe is None


class TestHealthResponse:
    """Test HealthResponse model"""

    def test_health_response_defaults(self):
        """Test health response with defaults"""
        response = HealthResponse()
        assert response.status == "ok"
        assert response.phase == 1
        assert isinstance(response.timestamp, datetime)

    def test_health_response_custom(self):
        """Test health response with custom values"""
        custom_time = datetime(2025, 1, 15, 12, 0, 0)
        response = HealthResponse(
            status="ok",
            phase=2,
            timestamp=custom_time
        )
        assert response.phase == 2
        assert response.timestamp == custom_time


class TestErrorResponse:
    """Test ErrorResponse model"""

    def test_error_response_minimal(self):
        """Test error response with minimal fields"""
        response = ErrorResponse(error="Something went wrong")
        assert response.error == "Something went wrong"
        assert response.detail is None

    def test_error_response_with_detail(self):
        """Test error response with detail"""
        response = ErrorResponse(
            error="Invalid symbol",
            detail="Symbol XYZ123 not found in Yahoo Finance"
        )
        assert response.error == "Invalid symbol"
        assert response.detail is not None


class TestEnums:
    """Test enum values"""

    def test_strategy_type_values(self):
        """Test StrategyType enum"""
        assert StrategyType.MA_CROSSOVER.value == "ma_crossover"

    def test_job_status_values(self):
        """Test JobStatus enum"""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"

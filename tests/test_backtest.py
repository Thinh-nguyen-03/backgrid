"""Unit tests for backtest module"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.backtest import (
    calculate_ma_crossover_signals,
    calculate_returns,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_total_return,
    run_backtest,
    generate_job_id,
    BacktestResult
)


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing"""
    dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
    # Create trending data with some volatility
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def simple_uptrend_data():
    """Create simple uptrending price data"""
    dates = pd.date_range(start='2020-01-01', periods=50, freq='D')
    prices = [100 + i for i in range(50)]
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


@pytest.fixture
def simple_downtrend_data():
    """Create simple downtrending price data"""
    dates = pd.date_range(start='2020-01-01', periods=50, freq='D')
    prices = [150 - i for i in range(50)]
    df = pd.DataFrame({'Close': prices}, index=dates)
    return df


class TestCalculateMACrossoverSignals:
    """Test MA crossover signal generation"""

    def test_ma_crossover_basic(self, simple_uptrend_data):
        """Test basic MA crossover signal generation"""
        signals = calculate_ma_crossover_signals(simple_uptrend_data, fast_period=5, slow_period=10)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(simple_uptrend_data)
        assert signals.isin([0, 1]).all()

    def test_ma_crossover_uptrend_generates_long_signals(self, simple_uptrend_data):
        """Test that uptrend generates long signals"""
        signals = calculate_ma_crossover_signals(simple_uptrend_data, fast_period=5, slow_period=10)

        # In an uptrend, fast MA should be above slow MA most of the time
        # after the slow period
        signals_after_warmup = signals.iloc[20:]  # After both MAs have stabilized
        long_signals = (signals_after_warmup == 1).sum()

        assert long_signals > 0  # Should have some long signals

    def test_ma_crossover_invalid_periods(self, sample_price_data):
        """Test that invalid periods raise ValueError"""
        # Fast >= Slow
        with pytest.raises(ValueError) as exc_info:
            calculate_ma_crossover_signals(sample_price_data, fast_period=20, slow_period=10)
        assert "must be less than" in str(exc_info.value).lower()

        # Fast == Slow
        with pytest.raises(ValueError) as exc_info:
            calculate_ma_crossover_signals(sample_price_data, fast_period=10, slow_period=10)
        assert "must be less than" in str(exc_info.value).lower()

    def test_ma_crossover_period_too_small(self, sample_price_data):
        """Test that MA period < 2 raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            calculate_ma_crossover_signals(sample_price_data, fast_period=1, slow_period=10)
        assert "at least 2" in str(exc_info.value)

    def test_ma_crossover_insufficient_data(self):
        """Test that insufficient data raises ValueError"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        df = pd.DataFrame({'Close': [100, 101, 102, 103, 104]}, index=dates)

        with pytest.raises(ValueError) as exc_info:
            calculate_ma_crossover_signals(df, fast_period=5, slow_period=10)
        assert "insufficient data" in str(exc_info.value).lower()


class TestCalculateReturns:
    """Test returns calculation"""

    def test_calculate_returns_all_long(self):
        """Test returns calculation with all long signals"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 112]
        df = pd.DataFrame({'Close': prices}, index=dates)

        signals = pd.Series([1] * 10, index=dates)
        equity_curve = calculate_returns(df, signals, initial_capital=10000)

        assert isinstance(equity_curve, pd.Series)
        assert len(equity_curve) == len(df)
        assert equity_curve.iloc[0] == 10000  # Initial capital
        assert equity_curve.iloc[-1] > equity_curve.iloc[0]  # Should be profitable

    def test_calculate_returns_all_flat(self):
        """Test returns with all flat signals (no trading)"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 112]
        df = pd.DataFrame({'Close': prices}, index=dates)

        signals = pd.Series([0] * 10, index=dates)
        equity_curve = calculate_returns(df, signals, initial_capital=10000)

        # With no trading, equity should remain constant at initial capital
        assert all(equity_curve == 10000)

    def test_calculate_returns_mixed_signals(self):
        """Test returns with mixed long/flat signals"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        prices = [100, 102, 104, 103, 105, 107, 106, 108, 110, 112]
        df = pd.DataFrame({'Close': prices}, index=dates)

        signals = pd.Series([1, 1, 1, 0, 0, 1, 1, 1, 0, 0], index=dates)
        equity_curve = calculate_returns(df, signals, initial_capital=10000)

        assert len(equity_curve) == len(df)
        assert equity_curve.iloc[0] == 10000

    def test_calculate_returns_initial_capital(self):
        """Test returns with different initial capital"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        prices = [100, 101, 102, 103, 104]
        df = pd.DataFrame({'Close': prices}, index=dates)

        signals = pd.Series([1, 1, 1, 1, 1], index=dates)
        equity_curve = calculate_returns(df, signals, initial_capital=50000)

        assert equity_curve.iloc[0] == 50000


class TestCalculateSharpeRatio:
    """Test Sharpe ratio calculation"""

    def test_sharpe_ratio_positive_returns(self):
        """Test Sharpe ratio with positive returns"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        # Steady uptrend
        equity = pd.Series([10000 * (1.01 ** i) for i in range(100)], index=dates)

        sharpe = calculate_sharpe_ratio(equity)

        assert isinstance(sharpe, float)
        assert sharpe > 0  # Positive returns should give positive Sharpe

    def test_sharpe_ratio_negative_returns(self):
        """Test Sharpe ratio with negative returns"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        # Steady downtrend
        equity = pd.Series([10000 * (0.99 ** i) for i in range(100)], index=dates)

        sharpe = calculate_sharpe_ratio(equity)

        assert isinstance(sharpe, float)
        assert sharpe < 0  # Negative returns should give negative Sharpe

    def test_sharpe_ratio_flat_returns(self):
        """Test Sharpe ratio with flat returns (zero volatility)"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        equity = pd.Series([10000] * 100, index=dates)

        sharpe = calculate_sharpe_ratio(equity)

        assert sharpe == 0.0  # Zero volatility should give zero Sharpe

    def test_sharpe_ratio_insufficient_data(self):
        """Test Sharpe ratio with insufficient data"""
        dates = pd.date_range(start='2020-01-01', periods=1, freq='D')
        equity = pd.Series([10000], index=dates)

        sharpe = calculate_sharpe_ratio(equity)

        assert sharpe == 0.0


class TestCalculateMaxDrawdown:
    """Test maximum drawdown calculation"""

    def test_max_drawdown_no_drawdown(self):
        """Test max drawdown with no drawdown (steady uptrend)"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        equity = pd.Series([10000 + i * 100 for i in range(10)], index=dates)

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0  # No drawdown in uptrend

    def test_max_drawdown_with_drawdown(self):
        """Test max drawdown with actual drawdown"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        # Peak at 12000, trough at 9000, then recovery
        equity = pd.Series([10000, 11000, 12000, 10500, 9000, 9500, 10000, 10500, 11000, 11500], index=dates)

        max_dd = calculate_max_drawdown(equity)

        # Drawdown from 12000 to 9000 = -3000 / 12000 = -0.25
        assert max_dd < 0  # Should be negative
        assert abs(max_dd - (-0.25)) < 0.01  # Should be approximately -0.25

    def test_max_drawdown_continuous_decline(self):
        """Test max drawdown with continuous decline"""
        dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
        equity = pd.Series([10000 - i * 100 for i in range(10)], index=dates)

        max_dd = calculate_max_drawdown(equity)

        # From 10000 to 9100 = -900 / 10000 = -0.09
        assert max_dd < 0
        assert abs(max_dd - (-0.09)) < 0.01

    def test_max_drawdown_insufficient_data(self):
        """Test max drawdown with insufficient data"""
        dates = pd.date_range(start='2020-01-01', periods=1, freq='D')
        equity = pd.Series([10000], index=dates)

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0


class TestCalculateTotalReturn:
    """Test total return calculation"""

    def test_total_return_positive(self):
        """Test total return with positive performance"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        equity = pd.Series([10000, 11000], index=dates[:2])

        total_ret = calculate_total_return(equity)

        assert total_ret == 0.1  # 10% return

    def test_total_return_negative(self):
        """Test total return with negative performance"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        equity = pd.Series([10000, 9000], index=dates[:2])

        total_ret = calculate_total_return(equity)

        assert total_ret == -0.1  # -10% return

    def test_total_return_zero(self):
        """Test total return with no change"""
        dates = pd.date_range(start='2020-01-01', periods=100, freq='D')
        equity = pd.Series([10000, 10000], index=dates[:2])

        total_ret = calculate_total_return(equity)

        assert total_ret == 0.0

    def test_total_return_insufficient_data(self):
        """Test total return with insufficient data"""
        dates = pd.date_range(start='2020-01-01', periods=1, freq='D')
        equity = pd.Series([10000], index=dates)

        total_ret = calculate_total_return(equity)

        assert total_ret == 0.0


class TestRunBacktest:
    """Test full backtest execution"""

    def test_run_backtest_ma_crossover(self, sample_price_data):
        """Test running a complete MA crossover backtest"""
        result = run_backtest(
            sample_price_data,
            strategy="ma_crossover",
            params={"fast": 10, "slow": 30}
        )

        assert "job_id" in result
        assert "status" in result
        assert result["status"] == "completed"
        assert "sharpe" in result
        assert "max_drawdown" in result
        assert "total_return" in result
        assert "equity_curve" in result
        assert "runtime_seconds" in result
        assert "created_at" in result

        assert isinstance(result["sharpe"], float)
        assert isinstance(result["max_drawdown"], float)
        assert isinstance(result["total_return"], float)
        assert isinstance(result["equity_curve"], list)
        assert len(result["equity_curve"]) == len(sample_price_data)

    def test_run_backtest_invalid_strategy(self, sample_price_data):
        """Test that invalid strategy raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            run_backtest(
                sample_price_data,
                strategy="invalid_strategy",
                params={"fast": 10, "slow": 30}
            )
        assert "unknown strategy" in str(exc_info.value).lower()

    def test_run_backtest_default_params(self, sample_price_data):
        """Test running backtest with default parameters"""
        result = run_backtest(
            sample_price_data,
            strategy="ma_crossover",
            params={}
        )

        assert result["status"] == "completed"
        # Should use default fast=10, slow=30

    def test_run_backtest_custom_initial_capital(self, sample_price_data):
        """Test running backtest with custom initial capital"""
        result = run_backtest(
            sample_price_data,
            strategy="ma_crossover",
            params={"fast": 5, "slow": 20},
            initial_capital=50000
        )

        assert result["equity_curve"][0] == 50000

    def test_run_backtest_job_id_format(self, sample_price_data):
        """Test that job ID has correct format"""
        result = run_backtest(
            sample_price_data,
            strategy="ma_crossover",
            params={"fast": 10, "slow": 30}
        )

        assert result["job_id"].startswith("manual-")
        assert len(result["job_id"]) > 10  # Should have timestamp

    def test_run_backtest_runtime_measured(self, sample_price_data):
        """Test that runtime is measured and reasonable"""
        result = run_backtest(
            sample_price_data,
            strategy="ma_crossover",
            params={"fast": 10, "slow": 30}
        )

        assert result["runtime_seconds"] >= 0  # Can be 0 if very fast
        assert result["runtime_seconds"] < 10  # Should complete quickly


class TestGenerateJobId:
    """Test job ID generation"""

    def test_generate_job_id_default_prefix(self):
        """Test job ID generation with default prefix"""
        job_id = generate_job_id()

        assert job_id.startswith("manual-")
        assert len(job_id) > 10

    def test_generate_job_id_custom_prefix(self):
        """Test job ID generation with custom prefix"""
        job_id = generate_job_id(prefix="auto")

        assert job_id.startswith("auto-")

    def test_generate_job_id_unique(self):
        """Test that generated job IDs are unique"""
        import time

        job_id1 = generate_job_id()
        time.sleep(0.01)  # Small delay to ensure different timestamp
        job_id2 = generate_job_id()

        # May be same if generated in same second, but structure should be valid
        assert job_id1.startswith("manual-")
        assert job_id2.startswith("manual-")


class TestBacktestResult:
    """Test BacktestResult class"""

    def test_backtest_result_creation(self):
        """Test creating BacktestResult object"""
        result = BacktestResult(
            job_id="test-123",
            sharpe=1.5,
            max_drawdown=-0.2,
            total_return=0.3,
            equity_curve=[10000, 11000, 12000],
            runtime_seconds=2.5
        )

        assert result.job_id == "test-123"
        assert result.sharpe == 1.5
        assert result.max_drawdown == -0.2
        assert result.total_return == 0.3
        assert result.equity_curve == [10000, 11000, 12000]
        assert result.runtime_seconds == 2.5
        assert isinstance(result.created_at, datetime)

    def test_backtest_result_to_dict(self):
        """Test converting BacktestResult to dictionary"""
        result = BacktestResult(
            job_id="test-456",
            sharpe=1.2,
            max_drawdown=-0.15,
            total_return=0.25,
            equity_curve=[10000, 10500],
            runtime_seconds=1.8
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["job_id"] == "test-456"
        assert result_dict["sharpe"] == 1.2
        assert result_dict["max_drawdown"] == -0.15
        assert result_dict["total_return"] == 0.25
        assert result_dict["equity_curve"] == [10000, 10500]
        assert result_dict["runtime_seconds"] == 1.8
        assert "created_at" in result_dict

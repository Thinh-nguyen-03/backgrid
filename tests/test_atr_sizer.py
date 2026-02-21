"""Unit tests for ATR-based position sizing.

Week 7: Tests ATR calculation accuracy, position size constraints,
stop price computation, and parameter validation.
"""

import pytest
import pandas as pd
import numpy as np

from src.position_sizing.atr_sizer import ATRPositionSizer
from src.position_sizing.base_sizer import PositionSizeResult


@pytest.fixture
def ohlcv_data():
    """Generate 50-day OHLCV data for ATR calculation."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(50) * 0.5)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base + np.abs(np.random.randn(50)) * 2,
        "Low": base - np.abs(np.random.randn(50)) * 2,
        "Close": base,
        "Volume": np.random.randint(500_000, 5_000_000, 50),
    }, index=dates)


@pytest.fixture
def low_volatility_data():
    """Generate data with very low volatility."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
    base = np.linspace(100, 101, 50)
    return pd.DataFrame({
        "Open": base - 0.01,
        "High": base + 0.05,
        "Low": base - 0.05,
        "Close": base,
        "Volume": [1_000_000] * 50,
    }, index=dates)


@pytest.fixture
def high_volatility_data():
    """Generate data with high volatility."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
    np.random.seed(99)
    base = 100 + np.cumsum(np.random.randn(50) * 5)
    return pd.DataFrame({
        "Open": base * 0.98,
        "High": base * 1.05,
        "Low": base * 0.95,
        "Close": base,
        "Volume": [1_000_000] * 50,
    }, index=dates)


class TestATRSizerDefaults:

    def test_default_atr_period(self):
        sizer = ATRPositionSizer()
        assert sizer.params["atr_period"] == 14

    def test_default_risk_per_trade(self):
        sizer = ATRPositionSizer()
        assert sizer.params["risk_per_trade"] == 0.05

    def test_default_atr_multiplier(self):
        sizer = ATRPositionSizer()
        assert sizer.params["atr_multiplier"] == 3.0

    def test_default_max_position_pct(self):
        sizer = ATRPositionSizer()
        assert sizer.params["max_position_pct"] == 0.25

    def test_custom_params(self):
        sizer = ATRPositionSizer({
            "atr_period": 21,
            "risk_per_trade": 0.02,
            "atr_multiplier": 2.0,
        })
        assert sizer.params["atr_period"] == 21
        assert sizer.params["risk_per_trade"] == 0.02
        assert sizer.params["atr_multiplier"] == 2.0


class TestATRSizerValidation:

    def test_invalid_atr_period(self):
        with pytest.raises(ValueError, match="atr_period"):
            ATRPositionSizer({"atr_period": 0})

    def test_invalid_risk_per_trade_zero(self):
        with pytest.raises(ValueError, match="risk_per_trade"):
            ATRPositionSizer({"risk_per_trade": 0})

    def test_invalid_risk_per_trade_over_one(self):
        with pytest.raises(ValueError, match="risk_per_trade"):
            ATRPositionSizer({"risk_per_trade": 1.5})

    def test_invalid_atr_multiplier(self):
        with pytest.raises(ValueError, match="atr_multiplier"):
            ATRPositionSizer({"atr_multiplier": -1})

    def test_invalid_max_position_pct(self):
        with pytest.raises(ValueError, match="max_position_pct"):
            ATRPositionSizer({"max_position_pct": 0})

    def test_zero_equity_raises(self, ohlcv_data):
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError, match="Equity"):
            sizer.calculate_position_size(0, 100, ohlcv_data)

    def test_zero_price_raises(self, ohlcv_data):
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError, match="Price"):
            sizer.calculate_position_size(10000, 0, ohlcv_data)

    def test_no_dataframe_raises(self):
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError, match="DataFrame"):
            sizer.calculate_position_size(10000, 100, None)

    def test_insufficient_data_raises(self):
        sizer = ATRPositionSizer({"atr_period": 14})
        dates = pd.date_range("2023-01-01", periods=5, freq="D")
        short_df = pd.DataFrame({
            "High": [101] * 5, "Low": [99] * 5, "Close": [100] * 5,
        }, index=dates)
        with pytest.raises(ValueError, match="Insufficient"):
            sizer.calculate_position_size(10000, 100, short_df)


class TestATRCalculation:

    def test_atr_length_matches_input(self, ohlcv_data):
        atr = ATRPositionSizer.calculate_atr(ohlcv_data, 14)
        assert len(atr) == len(ohlcv_data)

    def test_atr_positive_values(self, ohlcv_data):
        atr = ATRPositionSizer.calculate_atr(ohlcv_data, 14)
        valid = atr.dropna()
        assert (valid > 0).all()

    def test_atr_low_vol_smaller_than_high_vol(self, low_volatility_data, high_volatility_data):
        atr_low = ATRPositionSizer.calculate_atr(low_volatility_data, 14).iloc[-1]
        atr_high = ATRPositionSizer.calculate_atr(high_volatility_data, 14).iloc[-1]
        assert atr_low < atr_high

    def test_atr_uses_wilder_smoothing(self, ohlcv_data):
        """Verify ATR uses EWM with alpha=1/period."""
        period = 14
        atr = ATRPositionSizer.calculate_atr(ohlcv_data, period)

        high = ohlcv_data["High"]
        low = ohlcv_data["Low"]
        close = ohlcv_data["Close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        expected = tr.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()

        pd.testing.assert_series_equal(atr, expected, check_names=False)

    def test_get_atr_values_method(self, ohlcv_data):
        sizer = ATRPositionSizer({"atr_period": 14})
        atr = sizer.get_atr_values(ohlcv_data)
        assert len(atr) == len(ohlcv_data)


class TestPositionSizeCalculation:

    def test_returns_position_size_result(self, ohlcv_data):
        sizer = ATRPositionSizer()
        result = sizer.calculate_position_size(100_000, 100, ohlcv_data)
        assert isinstance(result, PositionSizeResult)

    def test_shares_non_negative(self, ohlcv_data):
        sizer = ATRPositionSizer()
        result = sizer.calculate_position_size(100_000, 100, ohlcv_data)
        assert result.shares >= 0

    def test_position_value_within_max(self, ohlcv_data):
        equity = 100_000
        sizer = ATRPositionSizer({"max_position_pct": 0.25})
        result = sizer.calculate_position_size(equity, 100, ohlcv_data)
        assert result.position_value <= equity * 0.25

    def test_stop_price_below_entry(self, ohlcv_data):
        sizer = ATRPositionSizer()
        result = sizer.calculate_position_size(100_000, 100, ohlcv_data)
        assert result.stop_price < 100

    def test_stop_price_uses_atr_multiplier(self, ohlcv_data):
        sizer = ATRPositionSizer({"atr_multiplier": 3.0})
        result = sizer.calculate_position_size(100_000, 100, ohlcv_data)
        atr = ATRPositionSizer.calculate_atr(ohlcv_data, 14).iloc[-1]
        expected_stop = 100 - (atr * 3.0)
        assert abs(result.stop_price - expected_stop) < 0.01

    def test_higher_risk_means_more_shares(self, ohlcv_data):
        sizer_low = ATRPositionSizer({"risk_per_trade": 0.02})
        sizer_high = ATRPositionSizer({"risk_per_trade": 0.10})
        r_low = sizer_low.calculate_position_size(100_000, 100, ohlcv_data)
        r_high = sizer_high.calculate_position_size(100_000, 100, ohlcv_data)
        assert r_high.shares >= r_low.shares

    def test_higher_volatility_means_fewer_shares(self, low_volatility_data, high_volatility_data):
        sizer = ATRPositionSizer()
        price = 100
        r_low = sizer.calculate_position_size(100_000, price, low_volatility_data)
        r_high = sizer.calculate_position_size(100_000, price, high_volatility_data)
        assert r_low.shares >= r_high.shares

    def test_small_equity_may_yield_zero_shares(self, ohlcv_data):
        sizer = ATRPositionSizer()
        result = sizer.calculate_position_size(100, 100, ohlcv_data)
        assert result.shares >= 0

    def test_risk_amount_matches_calculation(self, ohlcv_data):
        sizer = ATRPositionSizer()
        result = sizer.calculate_position_size(100_000, 100, ohlcv_data)
        expected_risk = result.shares * result.risk_per_share
        assert abs(result.risk_amount - expected_risk) < 0.01

    def test_rapidtrader_defaults(self, ohlcv_data):
        """Verify RT parameter compatibility: 5% risk, 14-period ATR, 3x stop."""
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.05,
            "atr_multiplier": 3.0,
        })
        result = sizer.calculate_position_size(100_000, 150, ohlcv_data)
        assert result.shares > 0
        assert result.stop_price > 0
        assert result.risk_amount <= 100_000 * 0.05

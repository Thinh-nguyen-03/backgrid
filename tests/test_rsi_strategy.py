"""Unit tests for RSI strategy implementation.

Week 7: Validates RSI calculation accuracy (Wilder's smoothing),
2-of-3 confirmation logic, parameter validation, and signal generation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.strategies import RSIStrategy, Signal


@pytest.fixture
def ohlcv_data():
    """Generate OHLCV data with known characteristics."""
    dates = pd.date_range(start="2023-01-01", periods=200, freq="D")
    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(200) * 0.5)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base * 1.01,
        "Low": base * 0.99,
        "Close": base,
        "Volume": np.random.randint(500_000, 5_000_000, 200),
    }, index=dates)


@pytest.fixture
def deep_downtrend_data():
    """Generate a steep downtrend to force RSI below 30."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    rng = np.random.RandomState(99)
    # Strong downtrend with some noise to keep avg_loss > 0
    daily_returns = -0.012 + rng.randn(100) * 0.005
    prices = [200.0]
    for r in daily_returns[1:]:
        prices.append(prices[-1] * (1 + r))
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def deep_uptrend_data():
    """Generate a steep uptrend to force RSI above 55."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    rng = np.random.RandomState(99)
    # Strong uptrend with some noise to keep avg_gain and avg_loss both > 0
    daily_returns = 0.012 + rng.randn(100) * 0.005
    prices = [50.0]
    for r in daily_returns[1:]:
        prices.append(prices[-1] * (1 + r))
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def oscillating_data():
    """Create oscillating data that crosses RSI thresholds."""
    dates = pd.date_range(start="2023-01-01", periods=150, freq="D")
    prices = []
    price = 100
    for i in range(150):
        if i % 30 < 15:
            price -= 1.5
        else:
            price += 1.5
        prices.append(max(price, 10))
    return pd.DataFrame({"Close": prices}, index=dates)


class TestRSIDefaultParams:
    """Verify RapidTrader default parameters."""

    def test_default_rsi_period(self):
        strategy = RSIStrategy()
        assert strategy.params["rsi_period"] == 14

    def test_default_oversold_threshold(self):
        strategy = RSIStrategy()
        assert strategy.params["oversold_threshold"] == 30

    def test_default_overbought_threshold(self):
        strategy = RSIStrategy()
        assert strategy.params["overbought_threshold"] == 55

    def test_default_confirmation_window(self):
        strategy = RSIStrategy()
        assert strategy.params["confirmation_window"] == 3

    def test_default_min_confirmation_count(self):
        strategy = RSIStrategy()
        assert strategy.params["min_confirmation_count"] == 2

    def test_custom_params_override_defaults(self):
        strategy = RSIStrategy({"rsi_period": 21, "oversold_threshold": 25})
        assert strategy.params["rsi_period"] == 21
        assert strategy.params["oversold_threshold"] == 25
        assert strategy.params["overbought_threshold"] == 55


class TestRSIParameterValidation:

    def test_rsi_period_must_be_integer(self):
        with pytest.raises(ValueError, match="rsi_period"):
            RSIStrategy({"rsi_period": 2.5})

    def test_rsi_period_minimum(self):
        with pytest.raises(ValueError, match="rsi_period"):
            RSIStrategy({"rsi_period": 1})

    def test_oversold_threshold_range(self):
        with pytest.raises(ValueError, match="oversold_threshold"):
            RSIStrategy({"oversold_threshold": -5})

    def test_overbought_threshold_range(self):
        with pytest.raises(ValueError, match="overbought_threshold"):
            RSIStrategy({"overbought_threshold": 105})

    def test_oversold_must_be_less_than_overbought(self):
        with pytest.raises(ValueError, match="oversold_threshold"):
            RSIStrategy({"oversold_threshold": 60, "overbought_threshold": 40})

    def test_confirmation_window_must_be_positive(self):
        with pytest.raises(ValueError, match="confirmation_window"):
            RSIStrategy({"confirmation_window": 0})

    def test_min_confirmation_cannot_exceed_window(self):
        with pytest.raises(ValueError, match="min_confirmation_count"):
            RSIStrategy({"confirmation_window": 3, "min_confirmation_count": 5})

    def test_valid_edge_params(self):
        strategy = RSIStrategy({
            "rsi_period": 2,
            "oversold_threshold": 0,
            "overbought_threshold": 100,
            "confirmation_window": 1,
            "min_confirmation_count": 1,
        })
        assert strategy.params["rsi_period"] == 2


class TestRSICalculation:
    """Validate RSI values match Wilder's smoothing method."""

    def test_rsi_values_bounded_0_to_100(self, ohlcv_data):
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(ohlcv_data)
        valid = rsi.dropna()
        assert valid.min() >= 0
        assert valid.max() <= 100

    def test_rsi_strong_uptrend_above_50(self, deep_uptrend_data):
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(deep_uptrend_data)
        later_rsi = rsi.iloc[30:]
        assert later_rsi.mean() > 50

    def test_rsi_strong_downtrend_below_50(self, deep_downtrend_data):
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(deep_downtrend_data)
        later_rsi = rsi.iloc[30:]
        assert later_rsi.mean() < 50

    def test_rsi_flat_market_near_50(self):
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        prices = [100.0] * 100
        df = pd.DataFrame({"Close": prices}, index=dates)
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(df)
        assert abs(rsi.iloc[-1] - 50) < 1

    def test_rsi_length_matches_input(self, ohlcv_data):
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(ohlcv_data)
        assert len(rsi) == len(ohlcv_data)

    def test_rsi_uses_ewm_with_correct_alpha(self):
        """Verify Wilder's smoothing uses alpha = 1/period."""
        dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
        np.random.seed(123)
        prices = 100 + np.cumsum(np.random.randn(50) * 2)
        price_series = pd.Series(prices, index=dates)
        df = pd.DataFrame({"Close": price_series}, index=dates)

        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy._calculate_rsi(df["Close"], 14)

        delta = price_series.diff()
        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)
        alpha = 1.0 / 14
        avg_gain = gains.ewm(alpha=alpha, min_periods=14, adjust=False).mean()
        avg_loss = losses.ewm(alpha=alpha, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        expected_rsi = 100 - (100 / (1 + rs))
        expected_rsi = expected_rsi.fillna(50)

        pd.testing.assert_series_equal(rsi, expected_rsi, check_names=False)


class TestRSIConfirmationLogic:
    """Validate the 2-of-3 confirmation mechanism."""

    def test_buy_requires_confirmation(self, deep_downtrend_data):
        strategy = RSIStrategy({
            "confirmation_window": 3,
            "min_confirmation_count": 2,
        })
        signals = strategy.calculate_signals(deep_downtrend_data)
        buy_signals = signals[signals == Signal.BUY]
        if len(buy_signals) > 0:
            rsi = strategy.get_rsi_values(deep_downtrend_data)
            for idx in buy_signals.index[:3]:
                pos = deep_downtrend_data.index.get_loc(idx)
                window_start = max(0, pos - 2)
                rsi_window = rsi.iloc[window_start:pos + 1]
                oversold_count = (rsi_window < 30).sum()
                assert oversold_count >= 2

    def test_sell_requires_confirmation(self, deep_uptrend_data):
        strategy = RSIStrategy({
            "confirmation_window": 3,
            "min_confirmation_count": 2,
        })
        signals = strategy.calculate_signals(deep_uptrend_data)
        sell_signals = signals[signals == Signal.SELL]
        if len(sell_signals) > 0:
            rsi = strategy.get_rsi_values(deep_uptrend_data)
            for idx in sell_signals.index[:3]:
                pos = deep_uptrend_data.index.get_loc(idx)
                window_start = max(0, pos - 2)
                rsi_window = rsi.iloc[window_start:pos + 1]
                overbought_count = (rsi_window > 55).sum()
                assert overbought_count >= 2

    def test_single_spike_no_signal(self):
        """With 3-of-3 confirmation required, a brief oversold period should not trigger."""
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        prices = [100.0] * 100
        prices[50] = 50.0  # single spike down
        df = pd.DataFrame({"Close": prices}, index=dates)

        strategy = RSIStrategy({
            "confirmation_window": 3,
            "min_confirmation_count": 3,
        })
        signals = strategy.calculate_signals(df)
        # Most signals should be HOLD since the single spike can't confirm 3 times
        hold_count = (signals == Signal.HOLD).sum()
        assert hold_count > len(signals) * 0.8

    def test_confirmation_window_1_of_1(self, deep_downtrend_data):
        """With window=1, min_count=1, any single oversold reading triggers buy."""
        strategy = RSIStrategy({
            "confirmation_window": 1,
            "min_confirmation_count": 1,
        })
        signals = strategy.calculate_signals(deep_downtrend_data)
        rsi = strategy.get_rsi_values(deep_downtrend_data)
        oversold_mask = rsi < 30
        warmup = strategy.get_warmup_period()
        oversold_after_warmup = oversold_mask.iloc[warmup:]
        buy_after_warmup = (signals == Signal.BUY).iloc[warmup:]
        assert oversold_after_warmup.sum() == buy_after_warmup.sum()


class TestRSISignalGeneration:

    def test_signals_are_signal_enum(self, ohlcv_data):
        strategy = RSIStrategy()
        signals = strategy.calculate_signals(ohlcv_data)
        unique = set(signals.unique())
        assert unique.issubset({Signal.BUY, Signal.SELL, Signal.HOLD})

    def test_signals_length_matches_input(self, ohlcv_data):
        strategy = RSIStrategy()
        signals = strategy.calculate_signals(ohlcv_data)
        assert len(signals) == len(ohlcv_data)

    def test_insufficient_data_raises(self):
        dates = pd.date_range(start="2023-01-01", periods=5, freq="D")
        df = pd.DataFrame({"Close": [100, 101, 99, 102, 98]}, index=dates)
        strategy = RSIStrategy({"rsi_period": 14})
        with pytest.raises(ValueError, match="Insufficient"):
            strategy.calculate_signals(df)

    def test_missing_close_column_raises(self):
        dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
        df = pd.DataFrame({"Open": range(50)}, index=dates)
        strategy = RSIStrategy()
        with pytest.raises(ValueError):
            strategy.calculate_signals(df)

    def test_warmup_period_calculation(self):
        strategy = RSIStrategy({"rsi_period": 14, "confirmation_window": 3})
        assert strategy.get_warmup_period() == 17

    def test_name_attribute(self):
        assert RSIStrategy.name == "rsi"

    def test_downtrend_generates_buys(self, deep_downtrend_data):
        strategy = RSIStrategy()
        signals = strategy.calculate_signals(deep_downtrend_data)
        assert (signals == Signal.BUY).any()

    def test_uptrend_generates_sells(self, deep_uptrend_data):
        strategy = RSIStrategy()
        signals = strategy.calculate_signals(deep_uptrend_data)
        assert (signals == Signal.SELL).any()

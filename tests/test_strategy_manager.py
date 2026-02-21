"""Unit tests for multi-strategy orchestration.

Week 7: Tests signal combination methods (OR, AND, PRIORITY, WEIGHTED),
strategy attribution, and edge cases.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.strategies import (
    BaseStrategy,
    Signal,
    MAStrategy,
    RSIStrategy,
    StrategyManager,
    CombinationMethod,
)
from src.strategies.strategy_manager import StrategyAttribution, CombinedSignal


@pytest.fixture
def ohlcv_100():
    """100-day OHLCV data for strategy testing."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(100) * 0.5)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base * 1.01,
        "Low": base * 0.99,
        "Close": base,
        "Volume": np.random.randint(500_000, 5_000_000, 100),
    }, index=dates)


class _AlwaysBuyStrategy(BaseStrategy):
    """Test helper: always returns BUY."""
    name = "always_buy"
    def __init__(self):
        super().__init__({})
    def calculate_signals(self, df):
        return pd.Series(Signal.BUY, index=df.index)


class _AlwaysSellStrategy(BaseStrategy):
    """Test helper: always returns SELL."""
    name = "always_sell"
    def __init__(self):
        super().__init__({})
    def calculate_signals(self, df):
        return pd.Series(Signal.SELL, index=df.index)


class _AlwaysHoldStrategy(BaseStrategy):
    """Test helper: always returns HOLD."""
    name = "always_hold"
    def __init__(self):
        super().__init__({})
    def calculate_signals(self, df):
        return pd.Series(Signal.HOLD, index=df.index)


class TestManagerLifecycle:

    def test_empty_manager_has_no_strategies(self):
        mgr = StrategyManager()
        assert len(mgr.strategies) == 0

    def test_add_strategy(self, ohlcv_100):
        mgr = StrategyManager()
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        assert "buy" in mgr.strategies
        assert mgr.weights["buy"] == 1.0

    def test_add_strategy_with_custom_weight(self):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy(), weight=0.7)
        assert mgr.weights["ma"] == 0.7

    def test_add_duplicate_raises(self):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy())
        with pytest.raises(ValueError, match="already exists"):
            mgr.add_strategy("ma", MAStrategy())

    def test_remove_strategy(self):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy())
        mgr.remove_strategy("ma")
        assert "ma" not in mgr.strategies

    def test_remove_nonexistent_raises(self):
        mgr = StrategyManager()
        with pytest.raises(ValueError, match="not found"):
            mgr.remove_strategy("missing")

    def test_calculate_signals_empty_raises(self, ohlcv_100):
        mgr = StrategyManager()
        with pytest.raises(ValueError, match="No strategies"):
            mgr.calculate_signals(ohlcv_100)

    def test_init_with_strategies_dict(self, ohlcv_100):
        mgr = StrategyManager(
            strategies={"ma": MAStrategy()},
            weights={"ma": 0.5},
        )
        assert "ma" in mgr.strategies
        assert mgr.weights["ma"] == 0.5

    def test_warmup_uses_max_strategy(self):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy({"fast_period": 5, "slow_period": 10}))
        mgr.add_strategy("rsi", RSIStrategy({"rsi_period": 14, "confirmation_window": 3}))
        assert mgr.get_warmup_period() == max(10, 14 + 3)

    def test_repr(self):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy())
        assert "StrategyManager" in repr(mgr)
        assert "ma" in repr(mgr)


class TestORCombination:

    def test_any_buy_triggers_buy(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.OR)
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        mgr.add_strategy("hold", _AlwaysHoldStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.BUY).all()

    def test_any_sell_triggers_sell(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.OR)
        mgr.add_strategy("sell", _AlwaysSellStrategy())
        mgr.add_strategy("hold", _AlwaysHoldStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.SELL).all()

    def test_sell_overrides_buy_in_or(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.OR)
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        mgr.add_strategy("sell", _AlwaysSellStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.SELL).all()

    def test_all_hold_stays_hold(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.OR)
        mgr.add_strategy("h1", _AlwaysHoldStrategy())
        mgr.add_strategy("h2", _AlwaysHoldStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.HOLD).all()


class TestANDCombination:

    def test_all_buy_needed(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.AND)
        mgr.add_strategy("b1", _AlwaysBuyStrategy())
        mgr.add_strategy("b2", _AlwaysBuyStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.BUY).all()

    def test_mixed_signals_yield_hold(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.AND)
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        mgr.add_strategy("hold", _AlwaysHoldStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.HOLD).all()

    def test_all_sell_needed(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.AND)
        mgr.add_strategy("s1", _AlwaysSellStrategy())
        mgr.add_strategy("s2", _AlwaysSellStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.SELL).all()


class TestPRIORITYCombination:

    def test_sell_has_highest_priority(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.PRIORITY)
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        mgr.add_strategy("sell", _AlwaysSellStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.SELL).all()

    def test_buy_over_hold(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.PRIORITY)
        mgr.add_strategy("buy", _AlwaysBuyStrategy())
        mgr.add_strategy("hold", _AlwaysHoldStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.BUY).all()


class TestWEIGHTEDCombination:

    def test_weighted_buy_majority(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.WEIGHTED)
        mgr.add_strategy("buy1", _AlwaysBuyStrategy(), weight=2.0)
        mgr.add_strategy("hold", _AlwaysHoldStrategy(), weight=1.0)
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.BUY).all()

    def test_weighted_sell_majority(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.WEIGHTED)
        mgr.add_strategy("sell1", _AlwaysSellStrategy(), weight=2.0)
        mgr.add_strategy("hold", _AlwaysHoldStrategy(), weight=1.0)
        signals = mgr.calculate_signals(ohlcv_100)
        assert (signals == Signal.SELL).all()

    def test_weighted_balanced_yields_hold(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.WEIGHTED)
        mgr.add_strategy("buy", _AlwaysBuyStrategy(), weight=1.0)
        mgr.add_strategy("sell", _AlwaysSellStrategy(), weight=1.0)
        signals = mgr.calculate_signals(ohlcv_100)
        # Weighted sum is 0 for all rows, threshold is 1.0 -> all HOLD
        assert (signals == Signal.HOLD).all()


class TestAttributions:

    def test_return_attributions(self, ohlcv_100):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy())
        signals, attr_df = mgr.calculate_signals(ohlcv_100, return_attributions=True)
        assert "ma_signal" in attr_df.columns
        assert len(attr_df) == len(ohlcv_100)

    def test_get_signal_at_index(self, ohlcv_100):
        mgr = StrategyManager()
        mgr.add_strategy("ma", MAStrategy())
        mgr.add_strategy("rsi", RSIStrategy())
        combined = mgr.get_signal_at_index(ohlcv_100, 50)
        assert isinstance(combined, CombinedSignal)
        assert isinstance(combined.signal, Signal)
        assert len(combined.attributions) == 2


class TestRealStrategyCombination:
    """Combine real MA and RSI strategies."""

    def test_ma_rsi_combined_signals(self, ohlcv_100):
        mgr = StrategyManager(method=CombinationMethod.PRIORITY)
        mgr.add_strategy("ma", MAStrategy({"fast_period": 5, "slow_period": 20}))
        mgr.add_strategy("rsi", RSIStrategy())
        signals = mgr.calculate_signals(ohlcv_100)
        assert len(signals) == len(ohlcv_100)
        unique = set(signals.unique())
        assert unique.issubset({Signal.BUY, Signal.SELL, Signal.HOLD})

    def test_ma_rsi_or_more_signals_than_and(self, ohlcv_100):
        or_mgr = StrategyManager(method=CombinationMethod.OR)
        or_mgr.add_strategy("ma", MAStrategy({"fast_period": 5, "slow_period": 20}))
        or_mgr.add_strategy("rsi", RSIStrategy())
        or_signals = or_mgr.calculate_signals(ohlcv_100)

        and_mgr = StrategyManager(method=CombinationMethod.AND)
        and_mgr.add_strategy("ma", MAStrategy({"fast_period": 5, "slow_period": 20}))
        and_mgr.add_strategy("rsi", RSIStrategy())
        and_signals = and_mgr.calculate_signals(ohlcv_100)

        or_non_hold = (or_signals != Signal.HOLD).sum()
        and_non_hold = (and_signals != Signal.HOLD).sum()
        assert or_non_hold >= and_non_hold

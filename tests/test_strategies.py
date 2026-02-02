"""Unit tests for strategy framework."""

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


@pytest.fixture
def sample_price_data():
    """Create sample price data for testing."""
    dates = pd.date_range(start="2020-01-01", periods=100, freq="D")
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def uptrend_data():
    """Create simple uptrending price data."""
    dates = pd.date_range(start="2020-01-01", periods=50, freq="D")
    prices = [100 + i * 0.5 for i in range(50)]
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def downtrend_data():
    """Create simple downtrending price data."""
    dates = pd.date_range(start="2020-01-01", periods=50, freq="D")
    prices = [150 - i * 0.5 for i in range(50)]
    return pd.DataFrame({"Close": prices}, index=dates)


@pytest.fixture
def oscillating_data():
    """Create oscillating price data for RSI testing."""
    dates = pd.date_range(start="2020-01-01", periods=100, freq="D")
    prices = []
    price = 100
    for i in range(100):
        if i % 20 < 10:
            price += 2
        else:
            price -= 2
        prices.append(price)
    return pd.DataFrame({"Close": prices}, index=dates)


class TestSignalEnum:
    """Test Signal enum."""

    def test_signal_values(self):
        """Test signal enum has expected values."""
        assert Signal.BUY.value == "buy"
        assert Signal.SELL.value == "sell"
        assert Signal.HOLD.value == "hold"

    def test_signal_is_string_enum(self):
        """Test signal enum can be used as string."""
        assert str(Signal.BUY) == "Signal.BUY"
        assert Signal.BUY == "buy"


class TestMAStrategy:
    """Test MA crossover strategy."""

    def test_ma_strategy_default_params(self):
        """Test MA strategy with default parameters."""
        strategy = MAStrategy()
        assert strategy.params["fast_period"] == 10
        assert strategy.params["slow_period"] == 30
        assert strategy.name == "ma_crossover"

    def test_ma_strategy_custom_params(self):
        """Test MA strategy with custom parameters."""
        strategy = MAStrategy({"fast": 5, "slow": 20})
        assert strategy.params["fast_period"] == 5
        assert strategy.params["slow_period"] == 20

    def test_ma_strategy_custom_params_explicit(self):
        """Test MA strategy with explicit parameter names."""
        strategy = MAStrategy({"fast_period": 5, "slow_period": 20})
        assert strategy.params["fast_period"] == 5
        assert strategy.params["slow_period"] == 20

    def test_ma_strategy_signals_basic(self, sample_price_data):
        """Test MA strategy generates valid signals."""
        strategy = MAStrategy({"fast": 5, "slow": 10})
        signals = strategy.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_price_data)
        assert all(s in [Signal.BUY, Signal.SELL, Signal.HOLD] for s in signals)

    def test_ma_strategy_uptrend_buys(self, uptrend_data):
        """Test MA strategy generates buy signals in uptrend."""
        strategy = MAStrategy({"fast": 5, "slow": 10})
        signals = strategy.calculate_signals(uptrend_data)

        buy_count = (signals == Signal.BUY).sum()
        assert buy_count > 0

    def test_ma_strategy_downtrend_sells(self, downtrend_data):
        """Test MA strategy generates sell signals in downtrend."""
        strategy = MAStrategy({"fast": 5, "slow": 10})
        signals = strategy.calculate_signals(downtrend_data)

        sell_count = (signals == Signal.SELL).sum()
        assert sell_count > 0

    def test_ma_strategy_invalid_params_fast_ge_slow(self):
        """Test MA strategy raises error when fast >= slow."""
        with pytest.raises(ValueError) as exc_info:
            MAStrategy({"fast": 20, "slow": 10})
        assert "must be less than" in str(exc_info.value).lower()

    def test_ma_strategy_invalid_params_period_too_small(self):
        """Test MA strategy raises error when period < 2."""
        with pytest.raises(ValueError) as exc_info:
            MAStrategy({"fast": 1, "slow": 10})
        assert ">= 2" in str(exc_info.value)

    def test_ma_strategy_insufficient_data(self):
        """Test MA strategy raises error with insufficient data."""
        dates = pd.date_range(start="2020-01-01", periods=5, freq="D")
        df = pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=dates)

        strategy = MAStrategy({"fast": 5, "slow": 10})
        with pytest.raises(ValueError) as exc_info:
            strategy.calculate_signals(df)
        assert "insufficient" in str(exc_info.value).lower()

    def test_ma_strategy_warmup_period(self):
        """Test MA strategy returns correct warmup period."""
        strategy = MAStrategy({"fast": 5, "slow": 20})
        assert strategy.get_warmup_period() == 20

    def test_ma_strategy_position_signals(self, sample_price_data):
        """Test MA strategy position signals for backward compatibility."""
        strategy = MAStrategy({"fast": 5, "slow": 10})
        positions = strategy.get_position_signals(sample_price_data)

        assert isinstance(positions, pd.Series)
        assert all(p in [0, 1] for p in positions)


class TestRSIStrategy:
    """Test RSI strategy."""

    def test_rsi_strategy_default_params(self):
        """Test RSI strategy with default parameters."""
        strategy = RSIStrategy()
        assert strategy.params["rsi_period"] == 14
        assert strategy.params["oversold_threshold"] == 30
        assert strategy.params["overbought_threshold"] == 55
        assert strategy.params["confirmation_window"] == 3
        assert strategy.params["min_confirmation_count"] == 2
        assert strategy.name == "rsi"

    def test_rsi_strategy_custom_params(self):
        """Test RSI strategy with custom parameters."""
        strategy = RSIStrategy({
            "rsi_period": 7,
            "oversold_threshold": 25,
            "overbought_threshold": 75,
        })
        assert strategy.params["rsi_period"] == 7
        assert strategy.params["oversold_threshold"] == 25
        assert strategy.params["overbought_threshold"] == 75

    def test_rsi_strategy_signals_basic(self, sample_price_data):
        """Test RSI strategy generates valid signals."""
        strategy = RSIStrategy()
        signals = strategy.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_price_data)
        assert all(s in [Signal.BUY, Signal.SELL, Signal.HOLD] for s in signals)

    def test_rsi_calculation_range(self, sample_price_data):
        """Test RSI values are within 0-100 range."""
        strategy = RSIStrategy()
        rsi = strategy.get_rsi_values(sample_price_data)

        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_rsi_strategy_confirmation_logic(self):
        """Test RSI confirmation logic requires min confirmations."""
        dates = pd.date_range(start="2020-01-01", periods=30, freq="D")
        prices = [100] * 14 + [80] * 16

        df = pd.DataFrame({"Close": prices}, index=dates)
        strategy = RSIStrategy({
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
            "confirmation_window": 3,
            "min_confirmation_count": 2,
        })

        signals = strategy.calculate_signals(df)
        assert isinstance(signals, pd.Series)

    def test_rsi_strategy_invalid_params_period(self):
        """Test RSI strategy raises error for invalid period."""
        with pytest.raises(ValueError) as exc_info:
            RSIStrategy({"rsi_period": 1})
        assert ">= 2" in str(exc_info.value)

    def test_rsi_strategy_invalid_params_thresholds(self):
        """Test RSI strategy raises error when oversold >= overbought."""
        with pytest.raises(ValueError) as exc_info:
            RSIStrategy({"oversold_threshold": 70, "overbought_threshold": 30})
        assert "less than" in str(exc_info.value).lower()

    def test_rsi_strategy_invalid_params_threshold_range(self):
        """Test RSI strategy raises error for out of range thresholds."""
        with pytest.raises(ValueError) as exc_info:
            RSIStrategy({"oversold_threshold": -10})
        assert "between 0 and 100" in str(exc_info.value)

    def test_rsi_strategy_invalid_confirmation(self):
        """Test RSI raises error when min_count > window."""
        with pytest.raises(ValueError) as exc_info:
            RSIStrategy({"confirmation_window": 2, "min_confirmation_count": 5})
        assert "cannot exceed" in str(exc_info.value).lower()

    def test_rsi_strategy_warmup_period(self):
        """Test RSI strategy returns correct warmup period."""
        strategy = RSIStrategy({"rsi_period": 14, "confirmation_window": 3})
        assert strategy.get_warmup_period() == 17

    def test_rsi_strategy_insufficient_data(self):
        """Test RSI strategy raises error with insufficient data."""
        dates = pd.date_range(start="2020-01-01", periods=10, freq="D")
        df = pd.DataFrame({"Close": range(100, 110)}, index=dates)

        strategy = RSIStrategy()
        with pytest.raises(ValueError) as exc_info:
            strategy.calculate_signals(df)
        assert "insufficient" in str(exc_info.value).lower()


class TestStrategyManager:
    """Test strategy manager."""

    def test_strategy_manager_empty(self):
        """Test strategy manager with no strategies."""
        manager = StrategyManager()
        assert len(manager.strategies) == 0

    def test_strategy_manager_add_strategy(self):
        """Test adding strategies to manager."""
        manager = StrategyManager()
        manager.add_strategy("ma", MAStrategy())
        manager.add_strategy("rsi", RSIStrategy())

        assert len(manager.strategies) == 2
        assert "ma" in manager.strategies
        assert "rsi" in manager.strategies

    def test_strategy_manager_add_duplicate(self):
        """Test adding duplicate strategy name raises error."""
        manager = StrategyManager()
        manager.add_strategy("ma", MAStrategy())

        with pytest.raises(ValueError) as exc_info:
            manager.add_strategy("ma", MAStrategy())
        assert "already exists" in str(exc_info.value)

    def test_strategy_manager_remove_strategy(self):
        """Test removing strategy from manager."""
        manager = StrategyManager()
        manager.add_strategy("ma", MAStrategy())
        manager.remove_strategy("ma")

        assert len(manager.strategies) == 0

    def test_strategy_manager_remove_nonexistent(self):
        """Test removing nonexistent strategy raises error."""
        manager = StrategyManager()

        with pytest.raises(ValueError) as exc_info:
            manager.remove_strategy("ma")
        assert "not found" in str(exc_info.value)

    def test_strategy_manager_calculate_signals_empty(self):
        """Test calculating signals with no strategies raises error."""
        manager = StrategyManager()
        df = pd.DataFrame({"Close": [100, 101, 102]})

        with pytest.raises(ValueError) as exc_info:
            manager.calculate_signals(df)
        assert "no strategies" in str(exc_info.value).lower()

    def test_strategy_manager_priority_method(self, sample_price_data):
        """Test priority combination method."""
        manager = StrategyManager(method=CombinationMethod.PRIORITY)
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 10}))
        manager.add_strategy("rsi", RSIStrategy())

        signals = manager.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)
        assert len(signals) == len(sample_price_data)
        assert all(s in [Signal.BUY, Signal.SELL, Signal.HOLD] for s in signals)

    def test_strategy_manager_or_method(self, sample_price_data):
        """Test OR combination method."""
        manager = StrategyManager(method=CombinationMethod.OR)
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 10}))

        signals = manager.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)

    def test_strategy_manager_and_method(self, sample_price_data):
        """Test AND combination method."""
        manager = StrategyManager(method=CombinationMethod.AND)
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 10}))

        signals = manager.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)

    def test_strategy_manager_weighted_method(self, sample_price_data):
        """Test weighted combination method."""
        manager = StrategyManager(method=CombinationMethod.WEIGHTED)
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 10}), weight=2.0)
        manager.add_strategy("rsi", RSIStrategy(), weight=1.0)

        signals = manager.calculate_signals(sample_price_data)

        assert isinstance(signals, pd.Series)
        assert manager.weights["ma"] == 2.0
        assert manager.weights["rsi"] == 1.0

    def test_strategy_manager_warmup_period(self):
        """Test manager returns max warmup across strategies."""
        manager = StrategyManager()
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 20}))
        manager.add_strategy("rsi", RSIStrategy())

        warmup = manager.get_warmup_period()
        assert warmup == max(20, 14 + 3)

    def test_strategy_manager_with_attributions(self, sample_price_data):
        """Test calculating signals with attribution tracking."""
        manager = StrategyManager(method=CombinationMethod.PRIORITY)
        manager.add_strategy("ma", MAStrategy({"fast": 5, "slow": 10}))

        signals, attr_df = manager.calculate_signals(
            sample_price_data,
            return_attributions=True
        )

        assert isinstance(signals, pd.Series)
        assert isinstance(attr_df, pd.DataFrame)
        assert "ma_signal" in attr_df.columns

    def test_strategy_manager_init_with_strategies(self, sample_price_data):
        """Test initializing manager with strategies dict."""
        strategies = {
            "ma": MAStrategy({"fast": 5, "slow": 10}),
        }
        manager = StrategyManager(strategies=strategies)

        signals = manager.calculate_signals(sample_price_data)
        assert isinstance(signals, pd.Series)

    def test_strategy_manager_repr(self):
        """Test manager repr string."""
        manager = StrategyManager(method=CombinationMethod.PRIORITY)
        manager.add_strategy("ma", MAStrategy())

        repr_str = repr(manager)
        assert "StrategyManager" in repr_str
        assert "ma" in repr_str
        assert "priority" in repr_str


class TestCombinationMethods:
    """Test signal combination methods in detail."""

    @pytest.fixture
    def signals_fixture(self):
        """Create test signals for combination testing."""
        index = pd.date_range(start="2020-01-01", periods=5, freq="D")
        return {
            "s1": pd.Series([Signal.BUY, Signal.SELL, Signal.HOLD, Signal.BUY, Signal.HOLD], index=index),
            "s2": pd.Series([Signal.HOLD, Signal.SELL, Signal.BUY, Signal.BUY, Signal.SELL], index=index),
        }

    def test_or_combination(self, signals_fixture):
        """Test OR combination: any signal triggers."""
        manager = StrategyManager(method=CombinationMethod.OR)

        result = manager._combine_or(signals_fixture, signals_fixture["s1"].index)

        assert result.iloc[0] == Signal.BUY
        assert result.iloc[1] == Signal.SELL
        assert result.iloc[2] == Signal.BUY
        assert result.iloc[3] == Signal.BUY
        assert result.iloc[4] == Signal.SELL

    def test_and_combination(self, signals_fixture):
        """Test AND combination: all must agree."""
        manager = StrategyManager(method=CombinationMethod.AND)

        result = manager._combine_and(signals_fixture, signals_fixture["s1"].index)

        assert result.iloc[0] == Signal.HOLD
        assert result.iloc[1] == Signal.SELL
        assert result.iloc[2] == Signal.HOLD
        assert result.iloc[3] == Signal.BUY
        assert result.iloc[4] == Signal.HOLD

    def test_priority_sell_overrides_buy(self, signals_fixture):
        """Test priority: SELL overrides BUY."""
        manager = StrategyManager(method=CombinationMethod.PRIORITY)

        result = manager._combine_priority(signals_fixture, signals_fixture["s1"].index)

        assert result.iloc[4] == Signal.SELL


class TestRSICalculationValidation:
    """Validate RSI calculation against known reference values."""

    def test_rsi_known_values_uptrend(self):
        """Test RSI in strong uptrend produces high values (>70)."""
        dates = pd.date_range(start="2020-01-01", periods=30, freq="D")
        # Create uptrend with volatility: mostly gains with few small losses
        np.random.seed(42)
        gains = [100]
        for i in range(29):
            # 90% chance of gain, 10% chance of small loss
            if i % 10 == 5:
                change = 0.99  # Small loss
            else:
                change = 1.03  # Larger gains
            gains.append(gains[-1] * change)

        df = pd.DataFrame({"Close": gains}, index=dates)

        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy.get_rsi_values(df)

        last_rsi = rsi.iloc[-1]
        assert last_rsi > 70, f"RSI in strong uptrend should be >70, got {last_rsi:.2f}"

    def test_rsi_known_values_downtrend(self):
        """Test RSI in strong downtrend produces low values (<30)."""
        dates = pd.date_range(start="2020-01-01", periods=30, freq="D")
        # Create downtrend with volatility: mostly losses with few small gains
        np.random.seed(42)
        losses = [150]
        for i in range(29):
            # 90% chance of loss, 10% chance of small gain
            if i % 10 == 5:
                change = 1.01  # Small gain
            else:
                change = 0.97  # Larger losses
            losses.append(losses[-1] * change)

        df = pd.DataFrame({"Close": losses}, index=dates)

        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy.get_rsi_values(df)

        last_rsi = rsi.iloc[-1]
        assert last_rsi < 30, f"RSI in strong downtrend should be <30, got {last_rsi:.2f}"

    def test_rsi_neutral_market(self):
        """Test RSI in sideways market stays near 50."""
        dates = pd.date_range(start="2020-01-01", periods=50, freq="D")
        prices = [100 + (i % 2) * 2 - 1 for i in range(50)]
        df = pd.DataFrame({"Close": prices}, index=dates)

        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy.get_rsi_values(df)

        mid_rsi = rsi.iloc[30:].mean()
        assert 40 < mid_rsi < 60, f"RSI in flat market should be ~50, got {mid_rsi}"

    def test_rsi_wilder_smoothing_consistency(self):
        """Verify RSI calculation is consistent with Wilder's method."""
        dates = pd.date_range(start="2020-01-01", periods=20, freq="D")
        prices = [100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
                  108, 110, 112, 111, 113, 115, 114, 116, 118, 117]
        df = pd.DataFrame({"Close": prices}, index=dates)

        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy.get_rsi_values(df)

        assert rsi.iloc[-1] > 50


class TestStrategyIntegration:
    """Integration tests for strategy framework."""

    def test_full_backtest_with_rsi(self, sample_price_data):
        """Test running full backtest with RSI strategy."""
        from src.backtest import run_backtest

        result = run_backtest(
            sample_price_data,
            strategy="rsi",
            params={"rsi_period": 14}
        )

        assert result["status"] == "completed"
        assert "sharpe" in result
        assert "max_drawdown" in result
        assert "total_return" in result
        assert len(result["equity_curve"]) == len(sample_price_data)

    def test_full_backtest_with_combined(self, sample_price_data):
        """Test running full backtest with combined strategy."""
        from src.backtest import run_backtest

        result = run_backtest(
            sample_price_data,
            strategy="combined",
            params={"fast": 5, "slow": 10, "rsi_period": 14}
        )

        assert result["status"] == "completed"
        assert "sharpe" in result

    def test_backtest_invalid_strategy(self, sample_price_data):
        """Test backtest with invalid strategy name."""
        from src.backtest import run_backtest

        with pytest.raises(ValueError) as exc_info:
            run_backtest(sample_price_data, strategy="invalid", params={})
        assert "unknown strategy" in str(exc_info.value).lower()


class TestBaseStrategy:
    """Test base strategy class."""

    def test_base_strategy_is_abstract(self):
        """Test BaseStrategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseStrategy()

    def test_strategy_required_columns(self):
        """Test strategy reports required columns."""
        strategy = MAStrategy()
        required = strategy.get_required_columns()
        assert "Close" in required

    def test_strategy_validate_missing_columns(self):
        """Test validation catches missing columns."""
        strategy = MAStrategy()
        df = pd.DataFrame({"Open": [100, 101, 102]})

        with pytest.raises(ValueError) as exc_info:
            strategy.validate_dataframe(df)
        assert "missing" in str(exc_info.value).lower()

    def test_strategy_repr(self):
        """Test strategy repr string."""
        strategy = MAStrategy({"fast": 5, "slow": 15})
        repr_str = repr(strategy)

        assert "MAStrategy" in repr_str
        assert "params" in repr_str

"""RapidTrader signal validation tests.

Week 7: Validates that Backgrid's signal generation and risk management
match RapidTrader's expected behavior for key parameters:
- RSI: period=14, oversold=30, overbought=55, 2-of-3 confirmation
- MA: 20/100 configurable periods
- ATR: 14-period, 3x multiplier for stops
- Sector limits: 30% max per sector
- Market filter: SPY 200-SMA
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.strategies import MAStrategy, RSIStrategy, StrategyManager, CombinationMethod, Signal
from src.position_sizing.atr_sizer import ATRPositionSizer
from src.execution.transaction_costs import TransactionCostModel
from src.risk import (
    MarketRegimeFilter,
    RegimeState,
    StopLossManager,
    SectorLimitManager,
    PortfolioHeatTracker,
    HeatStatus,
)
from src.backtest import run_backtest, run_backtest_enhanced, BacktestConfig
from src.portfolio.metrics import (
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_trade_metrics,
    calculate_portfolio_metrics,
    aggregate_symbol_results,
)


@pytest.fixture
def year_ohlcv():
    """252-day simulated OHLCV mimicking a full trading year."""
    dates = pd.date_range(start="2023-01-01", periods=252, freq="B")
    np.random.seed(42)
    base = 150 + np.cumsum(np.random.randn(252) * 1.5)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base + np.abs(np.random.randn(252)) * 2,
        "Low": base - np.abs(np.random.randn(252)) * 2,
        "Close": base,
        "Volume": np.random.randint(1_000_000, 10_000_000, 252),
    }, index=dates)


@pytest.fixture
def multi_year_ohlcv():
    """500-day OHLCV for testing with longer SMA periods."""
    dates = pd.date_range(start="2022-01-01", periods=500, freq="B")
    np.random.seed(42)
    base = 100 + np.cumsum(np.random.randn(500) * 1.0)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base + np.abs(np.random.randn(500)) * 2,
        "Low": base - np.abs(np.random.randn(500)) * 2,
        "Close": base,
        "Volume": np.random.randint(1_000_000, 10_000_000, 500),
    }, index=dates)


class TestRSIRapidTraderParams:
    """Validate RSI strategy matches RapidTrader configuration."""

    def test_rt_rsi_period_14(self, year_ohlcv):
        strategy = RSIStrategy({"rsi_period": 14})
        rsi = strategy.get_rsi_values(year_ohlcv)
        valid = rsi.iloc[14:]
        assert valid.min() >= 0
        assert valid.max() <= 100

    def test_rt_oversold_30(self, year_ohlcv):
        strategy = RSIStrategy({"oversold_threshold": 30})
        signals = strategy.calculate_signals(year_ohlcv)
        rsi = strategy.get_rsi_values(year_ohlcv)
        buys = signals[signals == Signal.BUY]
        for idx in buys.index[:5]:
            pos = year_ohlcv.index.get_loc(idx)
            start = max(0, pos - 2)
            oversold_in_window = (rsi.iloc[start:pos+1] < 30).sum()
            assert oversold_in_window >= 2

    def test_rt_overbought_55(self, year_ohlcv):
        """RapidTrader uses 55 (not 70) as overbought threshold."""
        strategy = RSIStrategy({"overbought_threshold": 55})
        signals = strategy.calculate_signals(year_ohlcv)
        rsi = strategy.get_rsi_values(year_ohlcv)
        sells = signals[signals == Signal.SELL]
        for idx in sells.index[:5]:
            pos = year_ohlcv.index.get_loc(idx)
            start = max(0, pos - 2)
            overbought_in_window = (rsi.iloc[start:pos+1] > 55).sum()
            assert overbought_in_window >= 2

    def test_rt_confirmation_2_of_3(self, year_ohlcv):
        strategy = RSIStrategy({
            "confirmation_window": 3,
            "min_confirmation_count": 2,
        })
        signals = strategy.calculate_signals(year_ohlcv)
        unique = set(signals.unique())
        assert unique.issubset({Signal.BUY, Signal.SELL, Signal.HOLD})


class TestMARapidTraderParams:
    """Validate MA strategy with RapidTrader-compatible periods."""

    def test_rt_sma_20_100(self, year_ohlcv):
        strategy = MAStrategy({"fast_period": 20, "slow_period": 100})
        signals = strategy.calculate_signals(year_ohlcv)
        assert len(signals) == len(year_ohlcv)
        unique = set(signals.unique())
        assert unique.issubset({Signal.BUY, Signal.SELL, Signal.HOLD})

    def test_sma_crossover_generates_signals(self, year_ohlcv):
        strategy = MAStrategy({"fast_period": 20, "slow_period": 100})
        signals = strategy.calculate_signals(year_ohlcv)
        non_hold = (signals != Signal.HOLD).sum()
        assert non_hold > 0


class TestCombinedStrategy:
    """Validate multi-strategy combination as RapidTrader would use."""

    def test_priority_combination_sell_over_buy(self, year_ohlcv):
        mgr = StrategyManager(method=CombinationMethod.PRIORITY)
        mgr.add_strategy("ma", MAStrategy({"fast_period": 20, "slow_period": 100}))
        mgr.add_strategy("rsi", RSIStrategy())
        signals = mgr.calculate_signals(year_ohlcv)

        ma_signals = MAStrategy({"fast_period": 20, "slow_period": 100}).calculate_signals(year_ohlcv)
        rsi_signals = RSIStrategy().calculate_signals(year_ohlcv)

        for i in range(len(signals)):
            if ma_signals.iloc[i] == Signal.SELL or rsi_signals.iloc[i] == Signal.SELL:
                assert signals.iloc[i] == Signal.SELL

    def test_combined_backtest_runs(self, year_ohlcv):
        result = run_backtest(
            year_ohlcv, "combined",
            {"fast_period": 20, "slow_period": 100},
        )
        assert result["status"] == "completed"
        assert "sharpe" in result
        assert "total_return" in result


class TestATRPositionSizingValidation:
    """Validate ATR sizing matches RapidTrader parameters."""

    def test_rt_atr_14_period(self, year_ohlcv):
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.05,
            "atr_multiplier": 3.0,
        })
        result = sizer.calculate_position_size(100_000, 150.0, year_ohlcv)
        assert result.shares > 0
        assert result.risk_amount <= 100_000 * 0.05

    def test_rt_5_pct_risk_per_trade(self, year_ohlcv):
        sizer = ATRPositionSizer({"risk_per_trade": 0.05})
        result = sizer.calculate_position_size(100_000, 150.0, year_ohlcv)
        assert result.risk_amount <= 5_000 + 1  # small tolerance for rounding

    def test_rt_3x_atr_stop(self, year_ohlcv):
        sizer = ATRPositionSizer({"atr_multiplier": 3.0})
        result = sizer.calculate_position_size(100_000, 150.0, year_ohlcv)
        atr = ATRPositionSizer.calculate_atr(year_ohlcv, 14).iloc[-1]
        expected_stop = 150.0 - (atr * 3.0)
        assert abs(result.stop_price - expected_stop) < 0.01


class TestTransactionCostValidation:
    """Validate costs match RapidTrader parameters."""

    def test_rt_commission_per_share(self):
        model = TransactionCostModel({"commission_per_share": 0.005})
        cost = model.calculate_cost(150.0, 100)
        assert cost.commission >= 0.50

    def test_rt_spread_5_bps(self):
        model = TransactionCostModel({"spread_bps": 5.0})
        cost = model.calculate_cost(150.0, 100)
        # trade_value = 15000, spread = 15000 * (5/10000) / 2 = 0.375
        assert cost.spread_cost > 0

    def test_rt_slippage_2_bps(self):
        model = TransactionCostModel({"slippage_bps": 2.0})
        cost = model.calculate_cost(150.0, 100)
        assert cost.slippage > 0

    def test_rt_cost_under_half_percent(self):
        model = TransactionCostModel({
            "commission_per_share": 0.005,
            "spread_bps": 5.0,
            "slippage_bps": 2.0,
        })
        pct = model.cost_as_percentage(150.0, 100, volume=5_000_000)
        assert pct < 0.005


class TestRiskManagementValidation:
    """Validate risk parameters match RapidTrader configuration."""

    def test_rt_market_filter_spy_200_sma(self, multi_year_ohlcv):
        f = MarketRegimeFilter({"sma_period": 200, "reference_symbol": "SPY"})
        regime = f.get_regime(multi_year_ohlcv)
        assert regime.state in [RegimeState.BULL, RegimeState.BEAR, RegimeState.NEUTRAL]
        assert regime.sma_value > 0

    def test_rt_sector_limit_30_pct(self):
        mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        mgr.add_position("AAPL", "Technology", 100, 20_000)
        allowed = mgr.allows_entry("MSFT", "Technology", 15_000, 100_000)
        # 20k + 15k = 35k > 30k limit
        assert allowed is False

    def test_rt_cooldown_1_day_on_stop(self):
        mgr = StopLossManager({"cooldown_days": 1})
        trigger_date = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, trigger_date, atr=2.0)
        mgr.check_stop("AAPL", 90.0, trigger_date)

        next_day = trigger_date + timedelta(hours=12)
        assert mgr.is_in_cooldown("AAPL", next_day) is True

        two_days_later = trigger_date + timedelta(days=2)
        assert mgr.is_in_cooldown("AAPL", two_days_later) is False

    def test_rt_portfolio_heat_6_pct(self):
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.06})
        tracker.add_position("AAPL", 150, 100, 145)
        tracker.add_position("MSFT", 300, 50, 290)
        assert tracker.allows_new_risk(5_000, 100_000) is True
        assert tracker.allows_new_risk(6_000, 100_000) is False


class TestEnhancedBacktestValidation:
    """Validate enhanced backtest produces consistent results."""

    def test_enhanced_backtest_with_costs(self, year_ohlcv):
        config = BacktestConfig(
            initial_capital=100_000,
            position_sizing="fixed",
            risk_per_trade=0.05,
            enable_transaction_costs=True,
            commission_per_share=0.005,
            spread_bps=5.0,
            slippage_bps=2.0,
        )
        result = run_backtest_enhanced(year_ohlcv, "rsi", {}, config, "AAPL")
        assert result.job_id.startswith("enhanced-")
        assert len(result.equity_curve) == len(year_ohlcv)
        assert result.total_transaction_costs >= 0

    def test_enhanced_backtest_atr_sizing(self, year_ohlcv):
        config = BacktestConfig(
            initial_capital=100_000,
            position_sizing="atr",
            atr_period=14,
            risk_per_trade=0.05,
            atr_multiplier=3.0,
        )
        result = run_backtest_enhanced(year_ohlcv, "ma_crossover",
                                       {"fast_period": 10, "slow_period": 30},
                                       config, "AAPL")
        assert result.total_return is not None
        assert isinstance(result.trades, list)

    def test_enhanced_backtest_trade_records(self, year_ohlcv):
        config = BacktestConfig(initial_capital=100_000)
        result = run_backtest_enhanced(year_ohlcv, "ma_crossover",
                                       {"fast_period": 5, "slow_period": 20},
                                       config, "AAPL")
        for trade in result.trades:
            assert trade.symbol == "AAPL"
            assert trade.shares > 0
            assert trade.entry_price > 0
            assert trade.side == "long"


class TestPortfolioMetricsValidation:
    """Validate portfolio metrics calculations."""

    def test_sortino_ratio_penalizes_downside(self):
        """Sortino should be higher when gains are large but few losses."""
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        good = pd.Series(np.linspace(100, 120, 50), index=dates)
        mixed = pd.Series(
            np.concatenate([np.linspace(100, 110, 25), np.linspace(110, 95, 25)]),
            index=dates,
        )
        sortino_good = calculate_sortino_ratio(good)
        sortino_mixed = calculate_sortino_ratio(mixed)
        assert sortino_good > sortino_mixed

    def test_calmar_ratio(self):
        dates = pd.date_range("2023-01-01", periods=252, freq="B")
        np.random.seed(42)
        # Upward trend with noise to ensure non-zero drawdown
        curve = pd.Series(
            10000 + np.cumsum(np.random.randn(252) * 20 + 5), index=dates
        )
        calmar = calculate_calmar_ratio(curve)
        assert calmar > 0

    def test_portfolio_metrics_complete(self):
        dates = pd.date_range("2023-01-01", periods=252, freq="B")
        np.random.seed(42)
        curve = pd.Series(10000 + np.cumsum(np.random.randn(252) * 50), index=dates)
        metrics = calculate_portfolio_metrics(curve)
        assert metrics.trading_days == 252
        assert metrics.volatility > 0
        assert metrics.max_drawdown <= 0

    def test_aggregate_symbol_results(self):
        results = [
            {"symbol": "AAPL", "sharpe": 1.2, "total_return": 0.15, "max_drawdown": -0.10, "total_trades": 5, "win_rate": 0.6},
            {"symbol": "MSFT", "sharpe": 0.8, "total_return": 0.10, "max_drawdown": -0.12, "total_trades": 3, "win_rate": 0.33},
        ]
        agg = aggregate_symbol_results(results)
        assert agg["symbol_count"] == 2
        assert agg["total_trades"] == 8
        assert agg["average_sharpe"] == pytest.approx(1.0, abs=0.01)
        assert agg["best_symbol"] == "AAPL"
        assert agg["worst_symbol"] == "MSFT"

    def test_empty_results_aggregation(self):
        agg = aggregate_symbol_results([])
        assert agg["symbol_count"] == 0
        assert agg["total_trades"] == 0


class TestPerformanceTargets:
    """Validate performance targets from Week 7 spec."""

    def test_single_symbol_under_500ms(self, year_ohlcv):
        """Single cached symbol backtest should complete in < 500ms."""
        import time
        config = BacktestConfig(initial_capital=100_000)
        start = time.time()
        run_backtest_enhanced(year_ohlcv, "rsi", {}, config, "AAPL")
        elapsed = time.time() - start
        assert elapsed < 0.5

    def test_strategy_signal_under_10ms(self, year_ohlcv):
        """Signal calculation should complete in < 10ms for 252 days."""
        import time
        strategy = RSIStrategy()
        start = time.time()
        strategy.calculate_signals(year_ohlcv)
        elapsed = time.time() - start
        assert elapsed < 0.01

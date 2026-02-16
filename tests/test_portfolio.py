"""Tests for portfolio module: state tracker, trade ledger, and metrics."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.portfolio import (
    PortfolioStateTracker,
    PositionState,
    PortfolioSnapshot,
    TradeLedger,
    TradeSummary,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_annualized_return,
    calculate_profit_factor,
    calculate_trade_metrics,
    calculate_portfolio_metrics,
    TradeMetrics,
    PortfolioMetrics,
)
from src.portfolio.metrics import aggregate_symbol_results, aggregate_equity_curves
from src.backtest import TradeRecord


@pytest.fixture
def sample_equity_curve():
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, 252)
    prices = 10000 * np.cumprod(1 + returns)
    dates = pd.date_range(start="2023-01-01", periods=252, freq="B")
    return pd.Series(prices, index=dates)


@pytest.fixture
def declining_equity_curve():
    np.random.seed(42)
    returns = np.random.normal(-0.002, 0.02, 252)
    prices = 10000 * np.cumprod(1 + returns)
    dates = pd.date_range(start="2023-01-01", periods=252, freq="B")
    return pd.Series(prices, index=dates)


@pytest.fixture
def sample_trades():
    base_date = datetime(2023, 1, 1)
    return [
        TradeRecord(
            symbol="AAPL",
            entry_date=base_date,
            exit_date=base_date + timedelta(days=5),
            side="long",
            shares=100,
            entry_price=150.0,
            exit_price=160.0,
            pnl=1000.0,
            pnl_pct=0.0667,
            strategy="ma_crossover",
            transaction_costs=10.0,
        ),
        TradeRecord(
            symbol="AAPL",
            entry_date=base_date + timedelta(days=10),
            exit_date=base_date + timedelta(days=15),
            side="long",
            shares=100,
            entry_price=162.0,
            exit_price=158.0,
            pnl=-400.0,
            pnl_pct=-0.0247,
            strategy="ma_crossover",
            transaction_costs=10.0,
        ),
        TradeRecord(
            symbol="MSFT",
            entry_date=base_date + timedelta(days=20),
            exit_date=base_date + timedelta(days=30),
            side="long",
            shares=50,
            entry_price=300.0,
            exit_price=320.0,
            pnl=1000.0,
            pnl_pct=0.0667,
            strategy="rsi",
            transaction_costs=8.0,
        ),
        TradeRecord(
            symbol="GOOGL",
            entry_date=base_date + timedelta(days=35),
            exit_date=base_date + timedelta(days=40),
            side="long",
            shares=20,
            entry_price=100.0,
            exit_price=95.0,
            pnl=-100.0,
            pnl_pct=-0.05,
            strategy="rsi",
            transaction_costs=5.0,
        ),
    ]


class TestPositionState:
    def test_creation(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
        )
        assert pos.symbol == "AAPL"
        assert pos.shares == 100
        assert pos.entry_price == 150.0
        assert pos.entry_cost == 5.0

    def test_market_value_no_current_price(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
        )
        assert pos.market_value == 15000.0

    def test_market_value_with_current_price(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
            current_price=160.0,
        )
        assert pos.market_value == 16000.0

    def test_unrealized_pnl(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
            current_price=160.0,
        )
        assert pos.unrealized_pnl == 1000.0

    def test_unrealized_pnl_pct(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
            current_price=165.0,
        )
        assert pos.unrealized_pnl_pct == 0.1

    def test_to_dict(self):
        pos = PositionState(
            symbol="AAPL",
            shares=100,
            entry_price=150.0,
            entry_date=datetime(2023, 1, 1),
            entry_cost=5.0,
            current_price=160.0,
        )
        d = pos.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["market_value"] == 16000.0
        assert d["unrealized_pnl"] == 1000.0


class TestPortfolioSnapshot:
    def test_total_equity(self):
        positions = {
            "AAPL": PositionState(
                symbol="AAPL",
                shares=100,
                entry_price=150.0,
                entry_date=datetime(2023, 1, 1),
                entry_cost=5.0,
                current_price=160.0,
            ),
        }
        snapshot = PortfolioSnapshot(
            timestamp=datetime(2023, 1, 10),
            cash=5000.0,
            positions=positions,
            realized_pnl=0.0,
            total_transaction_costs=5.0,
        )
        assert snapshot.total_equity == 21000.0

    def test_sector_exposures(self):
        positions = {
            "AAPL": PositionState(
                symbol="AAPL",
                shares=100,
                entry_price=150.0,
                entry_date=datetime(2023, 1, 1),
                entry_cost=5.0,
                current_price=160.0,
                sector="Technology",
            ),
            "XOM": PositionState(
                symbol="XOM",
                shares=50,
                entry_price=100.0,
                entry_date=datetime(2023, 1, 1),
                entry_cost=5.0,
                current_price=100.0,
                sector="Energy",
            ),
        }
        snapshot = PortfolioSnapshot(
            timestamp=datetime(2023, 1, 10),
            cash=0.0,
            positions=positions,
            realized_pnl=0.0,
            total_transaction_costs=10.0,
        )
        exposures = snapshot.get_sector_exposures()
        assert "Technology" in exposures
        assert "Energy" in exposures
        assert abs(exposures["Technology"] - 16000 / 21000) < 0.01


class TestPortfolioStateTracker:
    def test_initialization(self):
        tracker = PortfolioStateTracker({"initial_capital": 50000.0})
        assert tracker.cash == 50000.0
        assert tracker.total_equity == 50000.0
        assert len(tracker.positions) == 0

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            PortfolioStateTracker({"initial_capital": -1000})

        with pytest.raises(ValueError):
            PortfolioStateTracker({"max_positions": 0})

        with pytest.raises(ValueError):
            PortfolioStateTracker({"max_sector_exposure": 1.5})

    def test_open_position(self):
        tracker = PortfolioStateTracker({"initial_capital": 10000.0})
        pos = tracker.open_position(
            symbol="AAPL",
            shares=10,
            price=150.0,
            timestamp=datetime(2023, 1, 1),
            transaction_cost=5.0,
        )
        assert pos is not None
        assert pos.symbol == "AAPL"
        assert tracker.cash == 10000.0 - (10 * 150.0) - 5.0
        assert "AAPL" in tracker.positions

    def test_open_position_insufficient_cash(self):
        tracker = PortfolioStateTracker({"initial_capital": 1000.0})
        pos = tracker.open_position(
            symbol="AAPL",
            shares=100,
            price=150.0,
            timestamp=datetime(2023, 1, 1),
        )
        assert pos is None
        assert tracker.cash == 1000.0

    def test_open_position_already_exists(self):
        tracker = PortfolioStateTracker({"initial_capital": 50000.0})
        tracker.open_position("AAPL", 10, 150.0, datetime(2023, 1, 1))
        pos = tracker.open_position("AAPL", 10, 155.0, datetime(2023, 1, 2))
        assert pos is None

    def test_open_position_max_positions(self):
        tracker = PortfolioStateTracker({
            "initial_capital": 100000.0,
            "max_positions": 2,
        })
        tracker.open_position("AAPL", 10, 150.0, datetime(2023, 1, 1))
        tracker.open_position("MSFT", 10, 300.0, datetime(2023, 1, 1))
        pos = tracker.open_position("GOOGL", 10, 100.0, datetime(2023, 1, 1))
        assert pos is None
        assert len(tracker.positions) == 2

    def test_close_position(self):
        tracker = PortfolioStateTracker({"initial_capital": 10000.0})
        tracker.open_position(
            symbol="AAPL",
            shares=10,
            price=150.0,
            timestamp=datetime(2023, 1, 1),
            transaction_cost=5.0,
            strategy="ma_crossover",
        )

        result = tracker.close_position(
            symbol="AAPL",
            price=160.0,
            timestamp=datetime(2023, 1, 10),
            transaction_cost=5.0,
        )

        assert result is not None
        assert result["pnl"] == 100.0
        assert result["strategy"] == "ma_crossover"
        assert "AAPL" not in tracker.positions
        assert tracker.realized_pnl == 100.0

    def test_close_position_not_exists(self):
        tracker = PortfolioStateTracker()
        result = tracker.close_position("AAPL", 160.0, datetime(2023, 1, 10))
        assert result is None

    def test_update_prices(self):
        tracker = PortfolioStateTracker({"initial_capital": 50000.0})
        tracker.open_position("AAPL", 10, 150.0, datetime(2023, 1, 1))
        tracker.open_position("MSFT", 10, 300.0, datetime(2023, 1, 1))

        tracker.update_prices({"AAPL": 160.0, "MSFT": 310.0})

        assert tracker.positions["AAPL"].current_price == 160.0
        assert tracker.positions["MSFT"].current_price == 310.0

    def test_can_open_position(self):
        tracker = PortfolioStateTracker({"initial_capital": 10000.0})
        assert tracker.can_open_position("AAPL", 10, 150.0) is True
        assert tracker.can_open_position("AAPL", 100, 150.0) is False

    def test_get_snapshot(self):
        tracker = PortfolioStateTracker({"initial_capital": 10000.0})
        tracker.open_position("AAPL", 10, 150.0, datetime(2023, 1, 1))
        snapshot = tracker.get_snapshot(datetime(2023, 1, 5))
        assert snapshot.position_count == 1
        assert snapshot.cash == 10000.0 - 1500.0

    def test_reset(self):
        tracker = PortfolioStateTracker({"initial_capital": 10000.0})
        tracker.open_position("AAPL", 10, 150.0, datetime(2023, 1, 1))
        tracker.get_snapshot()

        tracker.reset()

        assert tracker.cash == 10000.0
        assert len(tracker.positions) == 0
        assert tracker.realized_pnl == 0.0


class TestTradeLedger:
    def test_add_trade(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trade(sample_trades[0])
        assert len(ledger) == 1

    def test_add_trades(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        assert len(ledger) == 4

    def test_get_trades_by_symbol(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        aapl_trades = ledger.get_trades_by_symbol("AAPL")
        assert len(aapl_trades) == 2

    def test_get_trades_by_strategy(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        rsi_trades = ledger.get_trades_by_strategy("rsi")
        assert len(rsi_trades) == 2

    def test_get_winning_trades(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        winners = ledger.get_winning_trades()
        assert len(winners) == 2

    def test_get_losing_trades(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        losers = ledger.get_losing_trades()
        assert len(losers) == 2

    def test_get_symbols(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        symbols = ledger.get_symbols()
        assert set(symbols) == {"AAPL", "MSFT", "GOOGL"}

    def test_get_strategies(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        strategies = ledger.get_strategies()
        assert set(strategies) == {"ma_crossover", "rsi"}

    def test_get_summary(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        summary = ledger.get_summary()

        assert summary.total_trades == 4
        assert summary.winning_trades == 2
        assert summary.losing_trades == 2
        assert summary.win_rate == 0.5
        assert summary.total_pnl == 1500.0
        assert summary.gross_profit == 2000.0
        assert summary.gross_loss == 500.0
        assert summary.profit_factor == 4.0

    def test_get_summary_empty(self):
        ledger = TradeLedger()
        summary = ledger.get_summary()
        assert summary.total_trades == 0
        assert summary.win_rate == 0.0

    def test_get_summary_by_symbol(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        summaries = ledger.get_summary_by_symbol()

        assert "AAPL" in summaries
        assert summaries["AAPL"].total_trades == 2
        assert summaries["MSFT"].total_trades == 1

    def test_get_summary_by_strategy(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        summaries = ledger.get_summary_by_strategy()

        assert "ma_crossover" in summaries
        assert "rsi" in summaries
        assert summaries["ma_crossover"].total_trades == 2

    def test_filter_by_date(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        base_date = datetime(2023, 1, 1)
        trades = ledger.get_trades(
            start_date=base_date + timedelta(days=15),
        )
        assert len(trades) == 2

    def test_filter_by_pnl(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        trades = ledger.get_trades(min_pnl=0)
        assert len(trades) == 2

    def test_to_list(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        trade_list = ledger.to_list()
        assert len(trade_list) == 4
        assert all(isinstance(t, dict) for t in trade_list)

    def test_clear(self, sample_trades):
        ledger = TradeLedger()
        ledger.add_trades(sample_trades)
        ledger.clear()
        assert len(ledger) == 0


class TestCalculateSortinoRatio:
    def test_basic_calculation(self, sample_equity_curve):
        sortino = calculate_sortino_ratio(sample_equity_curve)
        assert isinstance(sortino, float)

    def test_short_series(self):
        short_curve = pd.Series([10000, 10100])
        sortino = calculate_sortino_ratio(short_curve)
        assert sortino == 0.0 or isinstance(sortino, float)

    def test_empty_series(self):
        empty_curve = pd.Series([10000])
        sortino = calculate_sortino_ratio(empty_curve)
        assert sortino == 0.0

    def test_no_downside(self):
        increasing = pd.Series([10000, 10100, 10200, 10300, 10400])
        sortino = calculate_sortino_ratio(increasing)
        assert sortino == 0.0

    def test_with_risk_free_rate(self, sample_equity_curve):
        sortino = calculate_sortino_ratio(sample_equity_curve, risk_free_rate=0.02)
        assert isinstance(sortino, float)


class TestCalculateCalmarRatio:
    def test_basic_calculation(self, sample_equity_curve):
        calmar = calculate_calmar_ratio(sample_equity_curve)
        assert isinstance(calmar, float)

    def test_negative_returns(self, declining_equity_curve):
        calmar = calculate_calmar_ratio(declining_equity_curve)
        assert calmar < 0

    def test_no_drawdown(self):
        increasing = pd.Series([10000, 10100, 10200, 10300, 10400])
        calmar = calculate_calmar_ratio(increasing)
        assert calmar == 0.0

    def test_short_series(self):
        short_curve = pd.Series([10000])
        calmar = calculate_calmar_ratio(short_curve)
        assert calmar == 0.0


class TestCalculateAnnualizedReturn:
    def test_positive_return(self):
        curve = pd.Series([10000] + [10000 * 1.001] * 252)
        annual = calculate_annualized_return(curve)
        assert annual > 0

    def test_negative_return(self):
        curve = pd.Series([10000] + [10000 * 0.999] * 252)
        annual = calculate_annualized_return(curve)
        assert annual < 0

    def test_zero_initial(self):
        curve = pd.Series([0, 100, 200])
        annual = calculate_annualized_return(curve)
        assert annual == 0.0

    def test_short_series(self):
        curve = pd.Series([10000])
        annual = calculate_annualized_return(curve)
        assert annual == 0.0


class TestCalculateProfitFactor:
    def test_profitable_trades(self, sample_trades):
        pf = calculate_profit_factor(sample_trades)
        assert pf == 4.0

    def test_empty_trades(self):
        pf = calculate_profit_factor([])
        assert pf == 0.0

    def test_no_losses(self, sample_trades):
        winners_only = [t for t in sample_trades if t.pnl > 0]
        pf = calculate_profit_factor(winners_only)
        assert pf == 0.0


class TestCalculateTradeMetrics:
    def test_basic_metrics(self, sample_trades):
        metrics = calculate_trade_metrics(sample_trades)
        assert metrics.total_trades == 4
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.5

    def test_profit_factor(self, sample_trades):
        metrics = calculate_trade_metrics(sample_trades)
        assert metrics.profit_factor == 4.0

    def test_expectancy(self, sample_trades):
        metrics = calculate_trade_metrics(sample_trades)
        assert metrics.expectancy > 0

    def test_hold_days(self, sample_trades):
        metrics = calculate_trade_metrics(sample_trades)
        assert metrics.average_hold_days > 0

    def test_empty_trades(self):
        metrics = calculate_trade_metrics([])
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0

    def test_to_dict(self, sample_trades):
        metrics = calculate_trade_metrics(sample_trades)
        d = metrics.to_dict()
        assert "total_trades" in d
        assert "profit_factor" in d


class TestCalculatePortfolioMetrics:
    def test_basic_metrics(self, sample_equity_curve):
        metrics = calculate_portfolio_metrics(sample_equity_curve)
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.sortino_ratio, float)
        assert isinstance(metrics.calmar_ratio, float)

    def test_trading_days(self, sample_equity_curve):
        metrics = calculate_portfolio_metrics(sample_equity_curve)
        assert metrics.trading_days == 252

    def test_max_drawdown(self, declining_equity_curve):
        metrics = calculate_portfolio_metrics(declining_equity_curve)
        assert metrics.max_drawdown < 0

    def test_empty_curve(self):
        metrics = calculate_portfolio_metrics(pd.Series([10000]))
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0

    def test_to_dict(self, sample_equity_curve):
        metrics = calculate_portfolio_metrics(sample_equity_curve)
        d = metrics.to_dict()
        assert "sharpe_ratio" in d
        assert "sortino_ratio" in d
        assert "calmar_ratio" in d


class TestAggregateSymbolResults:
    def test_basic_aggregation(self):
        results = [
            {
                "symbol": "AAPL",
                "sharpe": 1.5,
                "total_return": 0.15,
                "max_drawdown": -0.10,
                "total_trades": 10,
                "win_rate": 0.6,
            },
            {
                "symbol": "MSFT",
                "sharpe": 1.2,
                "total_return": 0.12,
                "max_drawdown": -0.08,
                "total_trades": 8,
                "win_rate": 0.55,
            },
        ]
        agg = aggregate_symbol_results(results)

        assert agg["symbol_count"] == 2
        assert agg["total_trades"] == 18
        assert agg["average_sharpe"] == 1.35
        assert agg["average_return"] == 0.135

    def test_empty_results(self):
        agg = aggregate_symbol_results([])
        assert agg["symbol_count"] == 0
        assert agg["total_trades"] == 0

    def test_best_worst_symbol(self):
        results = [
            {"symbol": "AAPL", "sharpe": 1.5, "total_return": 0.20, "max_drawdown": -0.10, "total_trades": 10, "win_rate": 0.6},
            {"symbol": "MSFT", "sharpe": 1.2, "total_return": 0.05, "max_drawdown": -0.08, "total_trades": 8, "win_rate": 0.55},
            {"symbol": "GOOGL", "sharpe": 0.8, "total_return": -0.05, "max_drawdown": -0.15, "total_trades": 5, "win_rate": 0.4},
        ]
        agg = aggregate_symbol_results(results)

        assert agg["best_symbol"] == "AAPL"
        assert agg["worst_symbol"] == "GOOGL"

    def test_results_by_symbol(self):
        results = [
            {"symbol": "AAPL", "sharpe": 1.5, "total_return": 0.15, "max_drawdown": -0.10, "total_trades": 10, "win_rate": 0.6},
        ]
        agg = aggregate_symbol_results(results)

        assert "AAPL" in agg["results_by_symbol"]
        assert agg["results_by_symbol"]["AAPL"]["sharpe"] == 1.5


class TestAggregateEquityCurves:
    def test_equal_curves(self):
        curves = {
            "AAPL": [10000, 11000, 12000],
            "MSFT": [10000, 11000, 12000],
        }
        result = aggregate_equity_curves(curves, 10000.0)
        assert len(result) == 3
        assert result[0] == 10000.0
        assert result[1] == 11000.0
        assert result[2] == 12000.0

    def test_divergent_curves(self):
        curves = {
            "AAPL": [10000, 12000, 14000],
            "MSFT": [10000, 10000, 10000],
        }
        result = aggregate_equity_curves(curves, 10000.0)
        assert result[0] == 10000.0
        assert result[1] == 11000.0  # avg of 1.2 and 1.0 = 1.1
        assert result[2] == 12000.0  # avg of 1.4 and 1.0 = 1.2

    def test_different_starting_capitals(self):
        curves = {
            "AAPL": [20000, 22000],  # +10%
            "MSFT": [5000, 6000],    # +20%
        }
        result = aggregate_equity_curves(curves, 10000.0)
        assert result[0] == 10000.0
        # avg of 1.1 and 1.2 = 1.15
        assert result[1] == 11500.0

    def test_unequal_lengths(self):
        curves = {
            "AAPL": [10000, 11000, 12000, 13000],
            "MSFT": [10000, 10500],
        }
        result = aggregate_equity_curves(curves, 10000.0)
        assert len(result) == 2  # truncated to shortest

    def test_single_symbol(self):
        curves = {"AAPL": [10000, 11000, 12000]}
        result = aggregate_equity_curves(curves, 10000.0)
        assert result == [10000.0, 11000.0, 12000.0]

    def test_empty_input(self):
        assert aggregate_equity_curves({}, 10000.0) == []

    def test_empty_curves_filtered(self):
        curves = {"AAPL": [], "MSFT": []}
        assert aggregate_equity_curves(curves, 10000.0) == []

    def test_single_point_curve_filtered(self):
        curves = {"AAPL": [10000]}
        assert aggregate_equity_curves(curves, 10000.0) == []

    def test_zero_start_filtered(self):
        curves = {
            "AAPL": [0, 100, 200],
            "MSFT": [10000, 11000, 12000],
        }
        result = aggregate_equity_curves(curves, 10000.0)
        assert len(result) == 3
        assert result[0] == 10000.0  # only MSFT used

    def test_custom_initial_capital(self):
        curves = {"AAPL": [10000, 11000]}
        result = aggregate_equity_curves(curves, 50000.0)
        assert result[0] == 50000.0
        assert result[1] == 55000.0

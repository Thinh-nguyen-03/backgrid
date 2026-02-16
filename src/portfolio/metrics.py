"""Extended portfolio metrics: Sortino, Calmar, annualized returns, and trade analysis."""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from ..backtest import TradeRecord

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252


@dataclass
class TradeMetrics:
    """Metrics computed from trade records."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    average_win: float
    average_loss: float
    payoff_ratio: float
    expectancy: float
    total_pnl: float
    average_hold_days: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "payoff_ratio": self.payoff_ratio,
            "expectancy": self.expectancy,
            "total_pnl": self.total_pnl,
            "average_hold_days": self.average_hold_days,
        }


@dataclass
class PortfolioMetrics:
    """Comprehensive portfolio performance metrics."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    volatility: float
    downside_deviation: float
    trading_days: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "downside_deviation": self.downside_deviation,
            "trading_days": self.trading_days,
        }


def calculate_sortino_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate Sortino ratio from equity curve.

    Sortino ratio penalizes only downside volatility, unlike Sharpe which
    penalizes all volatility. This makes it more appropriate for strategies
    that have asymmetric return distributions.

    Args:
        equity_curve: Series of portfolio values over time
        risk_free_rate: Annual risk-free rate
        periods_per_year: Number of periods per year for annualization

    Returns:
        Annualized Sortino ratio
    """
    returns = equity_curve.pct_change().dropna()

    if len(returns) < 2:
        return 0.0

    daily_rf = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf

    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return 0.0

    downside_std = np.sqrt(np.mean(downside_returns ** 2))

    if downside_std == 0:
        return 0.0

    sortino = excess_returns.mean() / downside_std
    sortino_annualized = sortino * np.sqrt(periods_per_year)

    return float(sortino_annualized)


def calculate_calmar_ratio(
    equity_curve: pd.Series,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate Calmar ratio from equity curve.

    Calmar ratio = Annualized Return / Max Drawdown (absolute value)

    This metric is popular among CTAs and trend-following strategies as it
    directly measures return per unit of drawdown risk.

    Args:
        equity_curve: Series of portfolio values over time
        periods_per_year: Number of periods per year for annualization

    Returns:
        Calmar ratio (positive if profitable, negative if losing)
    """
    if len(equity_curve) < 2:
        return 0.0

    total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
    n_periods = len(equity_curve)
    years = n_periods / periods_per_year
    if years == 0:
        return 0.0

    annualized_return = (1 + total_return) ** (1 / years) - 1

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = abs(float(drawdown.min()))

    if max_drawdown == 0:
        return 0.0

    return float(annualized_return / max_drawdown)


def calculate_annualized_return(
    equity_curve: pd.Series,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Calculate annualized return from equity curve.

    Uses compound annual growth rate (CAGR) formula.

    Args:
        equity_curve: Series of portfolio values over time
        periods_per_year: Number of periods per year

    Returns:
        Annualized return as decimal (0.10 = 10%)
    """
    if len(equity_curve) < 2:
        return 0.0

    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]

    if initial <= 0:
        return 0.0

    total_return = final / initial
    n_periods = len(equity_curve)
    years = n_periods / periods_per_year

    if years == 0:
        return 0.0

    annualized = total_return ** (1 / years) - 1
    return float(annualized)


def calculate_profit_factor(trades: List[TradeRecord]) -> float:
    """Calculate profit factor from trade records.

    Profit Factor = Gross Profits / Gross Losses

    Args:
        trades: List of trade records

    Returns:
        Profit factor (>1 is profitable, <1 is losing)
    """
    if not trades:
        return 0.0

    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))

    if gross_loss == 0:
        return 0.0

    return float(gross_profit / gross_loss)


def calculate_trade_metrics(trades: List[TradeRecord]) -> TradeMetrics:
    """Calculate comprehensive metrics from trade records.

    Args:
        trades: List of completed trades

    Returns:
        TradeMetrics dataclass with all computed metrics
    """
    if not trades:
        return TradeMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            average_win=0.0,
            average_loss=0.0,
            payoff_ratio=0.0,
            expectancy=0.0,
            total_pnl=0.0,
            average_hold_days=0.0,
        )

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]

    total_trades = len(trades)
    winning_trades = len(winners)
    losing_trades = len(losers)

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    gross_profit = sum(t.pnl for t in winners)
    gross_loss = abs(sum(t.pnl for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    average_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
    average_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
    payoff_ratio = average_win / average_loss if average_loss > 0 else 0.0

    expectancy = (win_rate * average_win) - ((1 - win_rate) * average_loss)

    total_pnl = sum(t.pnl for t in trades)

    hold_days = []
    for t in trades:
        if t.entry_date and t.exit_date:
            delta = t.exit_date - t.entry_date
            hold_days.append(delta.days)
    average_hold_days = sum(hold_days) / len(hold_days) if hold_days else 0.0

    return TradeMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        average_win=round(average_win, 2),
        average_loss=round(average_loss, 2),
        payoff_ratio=round(payoff_ratio, 4),
        expectancy=round(expectancy, 2),
        total_pnl=round(total_pnl, 2),
        average_hold_days=round(average_hold_days, 1),
    )


def calculate_portfolio_metrics(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> PortfolioMetrics:
    """Calculate comprehensive portfolio metrics from equity curve.

    Args:
        equity_curve: Series of portfolio values over time
        risk_free_rate: Annual risk-free rate for Sharpe/Sortino
        periods_per_year: Number of periods per year

    Returns:
        PortfolioMetrics dataclass with all computed metrics
    """
    if len(equity_curve) < 2:
        return PortfolioMetrics(
            total_return=0.0,
            annualized_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            downside_deviation=0.0,
            trading_days=0,
        )

    returns = equity_curve.pct_change().dropna()
    daily_rf = risk_free_rate / periods_per_year

    total_return = (equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]
    annualized_return = calculate_annualized_return(equity_curve, periods_per_year)

    excess_returns = returns - daily_rf
    volatility = returns.std() * np.sqrt(periods_per_year)
    sharpe_ratio = (excess_returns.mean() / returns.std() * np.sqrt(periods_per_year)) if returns.std() > 0 else 0.0

    sortino_ratio = calculate_sortino_ratio(equity_curve, risk_free_rate, periods_per_year)
    calmar_ratio = calculate_calmar_ratio(equity_curve, periods_per_year)

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown = float(drawdown.min())

    downside_returns = returns[returns < daily_rf]
    downside_deviation = np.sqrt(np.mean((downside_returns - daily_rf) ** 2)) * np.sqrt(periods_per_year) if len(downside_returns) > 0 else 0.0

    return PortfolioMetrics(
        total_return=round(float(total_return), 4),
        annualized_return=round(float(annualized_return), 4),
        sharpe_ratio=round(float(sharpe_ratio), 4),
        sortino_ratio=round(float(sortino_ratio), 4),
        calmar_ratio=round(float(calmar_ratio), 4),
        max_drawdown=round(float(max_drawdown), 4),
        volatility=round(float(volatility), 4),
        downside_deviation=round(float(downside_deviation), 4),
        trading_days=len(equity_curve),
    )


def aggregate_symbol_results(
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate results from multiple single-symbol backtests.

    Used by the Celery worker to combine results from parallel symbol backtests.

    Args:
        results: List of backtest result dicts from individual symbols

    Returns:
        Aggregated portfolio statistics
    """
    if not results:
        return {
            "symbol_count": 0,
            "total_trades": 0,
            "average_sharpe": 0.0,
            "average_return": 0.0,
            "average_max_drawdown": 0.0,
            "best_symbol": None,
            "worst_symbol": None,
            "results_by_symbol": {},
        }

    total_trades = sum(r.get("total_trades", 0) for r in results)
    sharpes = [r.get("sharpe", 0) for r in results]
    returns = [r.get("total_return", 0) for r in results]
    drawdowns = [r.get("max_drawdown", 0) for r in results]

    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0.0
    avg_return = sum(returns) / len(returns) if returns else 0.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else 0.0

    best_idx = returns.index(max(returns)) if returns else 0
    worst_idx = returns.index(min(returns)) if returns else 0

    results_by_symbol = {}
    for r in results:
        symbol = r.get("symbol", "UNKNOWN")
        results_by_symbol[symbol] = {
            "sharpe": r.get("sharpe", 0),
            "total_return": r.get("total_return", 0),
            "max_drawdown": r.get("max_drawdown", 0),
            "total_trades": r.get("total_trades", 0),
            "win_rate": r.get("win_rate", 0),
        }

    return {
        "symbol_count": len(results),
        "total_trades": total_trades,
        "average_sharpe": round(avg_sharpe, 4),
        "average_return": round(avg_return, 4),
        "average_max_drawdown": round(avg_drawdown, 4),
        "best_symbol": results[best_idx].get("symbol") if results else None,
        "worst_symbol": results[worst_idx].get("symbol") if results else None,
        "results_by_symbol": results_by_symbol,
    }


def aggregate_equity_curves(
    curves: Dict[str, List[float]],
    initial_capital: float = 10000.0,
) -> List[float]:
    """Combine per-symbol equity curves into an equal-weighted portfolio curve.

    Normalizes each curve to percentage of starting value, averages across
    symbols at each time step, then scales back to initial_capital.

    Args:
        curves: Mapping of symbol to equity curve values.
        initial_capital: Starting capital for the aggregated curve.

    Returns:
        Aggregated equity curve as list of floats, or empty list if no valid input.
    """
    if not curves:
        return []

    valid = {sym: c for sym, c in curves.items() if c and len(c) >= 2 and c[0] != 0}
    if not valid:
        return []

    min_len = min(len(c) for c in valid.values())
    normalized = []
    for curve in valid.values():
        start = curve[0]
        normalized.append([v / start for v in curve[:min_len]])

    aggregated = []
    n = len(normalized)
    for i in range(min_len):
        avg = sum(norm[i] for norm in normalized) / n
        aggregated.append(round(avg * initial_capital, 2))

    return aggregated

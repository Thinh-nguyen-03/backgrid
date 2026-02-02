"""Core backtesting logic (Phase 1 + Phase 2 Strategy Framework + Week 2-3 Enhancements)"""

import logging
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .strategies import MAStrategy, RSIStrategy, StrategyManager, Signal, CombinationMethod
from .position_sizing import ATRPositionSizer, FixedFractionalSizer, PositionSizeResult
from .execution import TransactionCostModel, OrderSimulator, Order, Fill, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade for the trade ledger."""
    symbol: str
    entry_date: datetime
    exit_date: Optional[datetime]
    side: str
    shares: int
    entry_price: float
    exit_price: Optional[float]
    pnl: float
    pnl_pct: float
    strategy: Optional[str]
    transaction_costs: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "side": self.side,
            "shares": self.shares,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "strategy": self.strategy,
            "transaction_costs": self.transaction_costs
        }


@dataclass
class BacktestResult:
    """Container for backtest results"""
    job_id: str
    sharpe: float
    max_drawdown: float
    total_return: float
    equity_curve: List[float]
    runtime_seconds: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    trades: List[TradeRecord] = field(default_factory=list)
    total_trades: int = 0
    win_rate: float = 0.0
    total_transaction_costs: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "equity_curve": self.equity_curve,
            "runtime_seconds": self.runtime_seconds,
            "created_at": self.created_at,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_transaction_costs": self.total_transaction_costs
        }


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""
    initial_capital: float = 10000.0
    position_sizing: str = "fixed"
    risk_per_trade: float = 0.05
    atr_period: int = 14
    atr_multiplier: float = 3.0
    enable_transaction_costs: bool = True
    commission_per_share: float = 0.005
    spread_bps: float = 5.0
    slippage_bps: float = 2.0
    fill_at: str = "next_open"


def calculate_ma_crossover_signals(
    df: pd.DataFrame,
    fast_period: int,
    slow_period: int
) -> pd.Series:
    """Calculate buy/sell signals using moving average crossover strategy."""
    if fast_period >= slow_period:
        raise ValueError(f"Fast period ({fast_period}) must be less than slow period ({slow_period})")

    if fast_period < 2 or slow_period < 2:
        raise ValueError("MA periods must be at least 2")

    if len(df) < slow_period:
        raise ValueError(
            f"Insufficient data: need at least {slow_period} data points, "
            f"but only have {len(df)}"
        )

    fast_ma = df['Close'].rolling(window=fast_period).mean()
    slow_ma = df['Close'].rolling(window=slow_period).mean()

    signals = pd.Series(0, index=df.index)
    signals[fast_ma > slow_ma] = 1

    return signals


def calculate_returns(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0
) -> pd.Series:
    """Calculate strategy returns based on signals."""
    daily_returns = df['Close'].pct_change()
    strategy_returns = signals.shift(1) * daily_returns
    cumulative_returns = (1 + strategy_returns).cumprod()
    equity_curve = initial_capital * cumulative_returns
    equity_curve = equity_curve.fillna(initial_capital)

    return equity_curve


def calculate_returns_with_costs(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0,
    cost_model: Optional[TransactionCostModel] = None,
    shares_per_trade: int = 100
) -> tuple[pd.Series, float]:
    """Calculate strategy returns with transaction costs.

    Args:
        df: OHLCV DataFrame
        signals: Trading signals (1 = long, 0 = flat)
        initial_capital: Starting capital
        cost_model: Transaction cost model
        shares_per_trade: Number of shares per trade

    Returns:
        Tuple of (equity_curve, total_costs)
    """
    if cost_model is None:
        return calculate_returns(df, signals, initial_capital), 0.0

    equity = initial_capital
    equity_curve = [equity]
    total_costs = 0.0
    position = 0

    for i in range(1, len(df)):
        prev_signal = signals.iloc[i - 1] if i > 0 else 0
        curr_signal = signals.iloc[i]
        price = df['Close'].iloc[i]
        volume = int(df['Volume'].iloc[i]) if 'Volume' in df.columns else None

        if prev_signal == 0 and curr_signal == 1 and position == 0:
            cost = cost_model.calculate_cost(price, shares_per_trade, volume, is_buy=True)
            equity -= cost.total
            total_costs += cost.total
            position = shares_per_trade

        elif prev_signal == 1 and curr_signal == 0 and position > 0:
            cost = cost_model.calculate_cost(price, position, volume, is_buy=False)
            equity -= cost.total
            total_costs += cost.total
            position = 0

        if position > 0:
            daily_return = (price - df['Close'].iloc[i - 1]) / df['Close'].iloc[i - 1]
            position_value = position * df['Close'].iloc[i - 1]
            equity += position_value * daily_return

        equity_curve.append(equity)

    return pd.Series(equity_curve, index=df.index), total_costs


def calculate_sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """Calculate Sharpe ratio from equity curve."""
    returns = equity_curve.pct_change().dropna()

    if len(returns) < 2:
        return 0.0

    daily_rf_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf_rate

    if excess_returns.std() == 0:
        return 0.0

    sharpe = excess_returns.mean() / excess_returns.std()
    sharpe_annualized = sharpe * np.sqrt(periods_per_year)

    return float(sharpe_annualized)


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """Calculate maximum drawdown from equity curve."""
    if len(equity_curve) < 2:
        return 0.0

    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max
    max_dd = float(drawdown.min())

    return max_dd


def calculate_total_return(equity_curve: pd.Series) -> float:
    """Calculate total return from equity curve."""
    if len(equity_curve) < 2:
        return 0.0

    initial_value = equity_curve.iloc[0]
    final_value = equity_curve.iloc[-1]

    if initial_value == 0:
        return 0.0

    total_return = (final_value - initial_value) / initial_value

    return float(total_return)


def _signals_to_positions(signals: pd.Series) -> pd.Series:
    """Convert Signal enum series to numeric position series."""
    positions = pd.Series(0, index=signals.index)
    positions[signals == Signal.BUY] = 1
    return positions


def run_backtest(
    df: pd.DataFrame,
    strategy: str,
    params: Dict[str, Any],
    initial_capital: float = 10000.0
) -> Dict[str, Any]:
    """Run backtest with specified strategy and parameters (legacy interface)."""
    start_time = time.time()

    supported_strategies = ["ma_crossover", "rsi", "combined"]
    if strategy not in supported_strategies:
        raise ValueError(
            f"Unknown strategy: {strategy}. "
            f"Supported strategies: {supported_strategies}"
        )

    if strategy == "ma_crossover":
        strat = MAStrategy(params)
        signals = strat.calculate_signals(df)
        positions = _signals_to_positions(signals)

    elif strategy == "rsi":
        strat = RSIStrategy(params)
        signals = strat.calculate_signals(df)
        positions = _signals_to_positions(signals)

    elif strategy == "combined":
        manager = StrategyManager(method=CombinationMethod.PRIORITY)

        ma_params = {
            k: v for k, v in params.items()
            if k in ("fast", "slow", "fast_period", "slow_period")
        }
        if ma_params:
            manager.add_strategy("ma", MAStrategy(ma_params))

        rsi_params = {
            k: v for k, v in params.items()
            if k in ("rsi_period", "oversold_threshold", "overbought_threshold",
                     "confirmation_window", "min_confirmation_count")
        }
        if rsi_params or not ma_params:
            manager.add_strategy("rsi", RSIStrategy(rsi_params if rsi_params else None))

        if not manager.strategies:
            manager.add_strategy("ma", MAStrategy())
            manager.add_strategy("rsi", RSIStrategy())

        signals = manager.calculate_signals(df)
        positions = _signals_to_positions(signals)

    equity_curve = calculate_returns(df, positions, initial_capital)

    sharpe = calculate_sharpe_ratio(equity_curve)
    max_dd = calculate_max_drawdown(equity_curve)
    total_ret = calculate_total_return(equity_curve)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_id = f"manual-{timestamp}"

    runtime = time.time() - start_time

    logger.info(
        f"Backtest completed: strategy={strategy}, "
        f"sharpe={sharpe:.4f}, runtime={runtime:.2f}s"
    )

    return {
        "job_id": job_id,
        "status": "completed",
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "total_return": round(total_ret, 4),
        "equity_curve": equity_curve.tolist(),
        "runtime_seconds": round(runtime, 2),
        "created_at": datetime.now(timezone.utc)
    }


def run_backtest_enhanced(
    df: pd.DataFrame,
    strategy: str,
    params: Dict[str, Any],
    config: Optional[BacktestConfig] = None,
    symbol: str = "UNKNOWN"
) -> BacktestResult:
    """Run enhanced backtest with position sizing and transaction costs.

    This is the Week 2-3 enhanced backtesting engine that supports:
    - ATR-based and fixed fractional position sizing
    - Transaction cost modeling (commission, spread, slippage)
    - Order execution simulation with fill delays
    - Detailed trade ledger

    Args:
        df: OHLCV DataFrame
        strategy: Strategy name
        params: Strategy parameters
        config: Backtest configuration
        symbol: Stock symbol for trade records

    Returns:
        BacktestResult with detailed metrics and trade history
    """
    start_time = time.time()
    config = config or BacktestConfig()

    supported_strategies = ["ma_crossover", "rsi", "combined"]
    if strategy not in supported_strategies:
        raise ValueError(f"Unknown strategy: {strategy}")

    if strategy == "ma_crossover":
        strat = MAStrategy(params)
        signals = strat.calculate_signals(df)

    elif strategy == "rsi":
        strat = RSIStrategy(params)
        signals = strat.calculate_signals(df)

    elif strategy == "combined":
        manager = StrategyManager(method=CombinationMethod.PRIORITY)
        ma_params = {k: v for k, v in params.items() if k in ("fast", "slow", "fast_period", "slow_period")}
        rsi_params = {k: v for k, v in params.items() if k.startswith("rsi") or k.endswith("threshold") or "confirm" in k}

        if ma_params:
            manager.add_strategy("ma", MAStrategy(ma_params))
        if rsi_params or not ma_params:
            manager.add_strategy("rsi", RSIStrategy(rsi_params if rsi_params else None))
        if not manager.strategies:
            manager.add_strategy("ma", MAStrategy())
            manager.add_strategy("rsi", RSIStrategy())

        signals = manager.calculate_signals(df)

    if config.position_sizing == "atr":
        sizer = ATRPositionSizer({
            "atr_period": config.atr_period,
            "risk_per_trade": config.risk_per_trade,
            "atr_multiplier": config.atr_multiplier
        })
    else:
        sizer = FixedFractionalSizer({"fraction": config.risk_per_trade})

    cost_model = None
    if config.enable_transaction_costs:
        cost_model = TransactionCostModel({
            "commission_per_share": config.commission_per_share,
            "spread_bps": config.spread_bps,
            "slippage_bps": config.slippage_bps
        })

    simulator = OrderSimulator(cost_model=cost_model, fill_at=config.fill_at)

    equity = config.initial_capital
    equity_curve = [equity]
    trades: List[TradeRecord] = []
    position = 0
    entry_price = 0.0
    entry_date = None
    total_costs = 0.0

    for i in range(1, len(df)):
        signal = signals.iloc[i]
        price = df['Close'].iloc[i]
        date = df.index[i]
        if isinstance(date, pd.Timestamp):
            date = date.to_pydatetime()

        if signal == Signal.BUY and position == 0:
            if config.position_sizing == "atr" and i >= config.atr_period:
                size_result = sizer.calculate_position_size(equity, price, df.iloc[:i+1])
                shares = size_result.shares
            else:
                shares = int(equity * config.risk_per_trade / price)

            if shares > 0:
                fill_price = df['Open'].iloc[min(i+1, len(df)-1)] if i+1 < len(df) else price

                if cost_model:
                    volume = int(df['Volume'].iloc[i]) if 'Volume' in df.columns else None
                    cost = cost_model.calculate_cost(fill_price, shares, volume, is_buy=True)
                    total_costs += cost.total
                    equity -= cost.total

                position = shares
                entry_price = fill_price
                entry_date = date

        elif signal == Signal.SELL and position > 0:
            fill_price = df['Open'].iloc[min(i+1, len(df)-1)] if i+1 < len(df) else price

            if cost_model:
                volume = int(df['Volume'].iloc[i]) if 'Volume' in df.columns else None
                cost = cost_model.calculate_cost(fill_price, position, volume, is_buy=False)
                total_costs += cost.total
                equity -= cost.total

            pnl = (fill_price - entry_price) * position
            pnl_pct = (fill_price - entry_price) / entry_price if entry_price > 0 else 0

            trades.append(TradeRecord(
                symbol=symbol,
                entry_date=entry_date,
                exit_date=date,
                side="long",
                shares=position,
                entry_price=entry_price,
                exit_price=fill_price,
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 4),
                strategy=strategy,
                transaction_costs=round(total_costs, 2)
            ))

            equity += pnl
            position = 0
            entry_price = 0.0
            entry_date = None

        if position > 0:
            daily_pnl = (price - df['Close'].iloc[i-1]) * position
            equity += daily_pnl

        equity_curve.append(equity)

    equity_series = pd.Series(equity_curve, index=df.index)
    sharpe = calculate_sharpe_ratio(equity_series)
    max_dd = calculate_max_drawdown(equity_series)
    total_ret = calculate_total_return(equity_series)

    winning_trades = [t for t in trades if t.pnl > 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0.0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job_id = f"enhanced-{timestamp}"

    runtime = time.time() - start_time

    logger.info(
        f"Enhanced backtest completed: strategy={strategy}, "
        f"sharpe={sharpe:.4f}, trades={len(trades)}, costs=${total_costs:.2f}"
    )

    return BacktestResult(
        job_id=job_id,
        sharpe=round(sharpe, 4),
        max_drawdown=round(max_dd, 4),
        total_return=round(total_ret, 4),
        equity_curve=[round(e, 2) for e in equity_curve],
        runtime_seconds=round(runtime, 2),
        trades=trades,
        total_trades=len(trades),
        win_rate=round(win_rate, 4),
        total_transaction_costs=round(total_costs, 2)
    )


def generate_job_id(prefix: str = "manual") -> str:
    """Generate a unique job ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}"

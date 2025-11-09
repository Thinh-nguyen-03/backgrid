"""Core backtesting logic (Phase 1)"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime


class BacktestResult:
    """Container for backtest results"""

    def __init__(
        self,
        job_id: str,
        sharpe: float,
        max_drawdown: float,
        total_return: float,
        equity_curve: List[float],
        runtime_seconds: float,
        created_at: Optional[datetime] = None
    ):
        self.job_id = job_id
        self.sharpe = sharpe
        self.max_drawdown = max_drawdown
        self.total_return = total_return
        self.equity_curve = equity_curve
        self.runtime_seconds = runtime_seconds
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "job_id": self.job_id,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "equity_curve": self.equity_curve,
            "runtime_seconds": self.runtime_seconds,
            "created_at": self.created_at
        }


def calculate_ma_crossover_signals(
    df: pd.DataFrame,
    fast_period: int,
    slow_period: int
) -> pd.Series:
    """
    Calculate buy/sell signals using moving average crossover strategy.

    Args:
        df: DataFrame with 'Close' prices
        fast_period: Fast MA period (e.g., 10)
        slow_period: Slow MA period (e.g., 30)

    Returns:
        Series with signals: 1 (long), 0 (flat), -1 (short/cash for Phase 1)

    Raises:
        ValueError: If parameters are invalid
    """
    if fast_period >= slow_period:
        raise ValueError(f"Fast period ({fast_period}) must be less than slow period ({slow_period})")

    if fast_period < 2 or slow_period < 2:
        raise ValueError("MA periods must be at least 2")

    if len(df) < slow_period:
        raise ValueError(
            f"Insufficient data: need at least {slow_period} data points, "
            f"but only have {len(df)}"
        )

    # Calculate moving averages
    fast_ma = df['Close'].rolling(window=fast_period).mean()
    slow_ma = df['Close'].rolling(window=slow_period).mean()

    # Generate signals: 1 when fast > slow (buy), 0 when fast <= slow (sell)
    signals = pd.Series(0, index=df.index)
    signals[fast_ma > slow_ma] = 1

    return signals


def calculate_returns(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0
) -> pd.Series:
    """
    Calculate strategy returns based on signals.

    Args:
        df: DataFrame with 'Close' prices
        signals: Trading signals (1 = long, 0 = flat)
        initial_capital: Starting capital

    Returns:
        Series of equity curve values
    """
    # Calculate daily returns
    daily_returns = df['Close'].pct_change()

    # Strategy returns = signal (shifted by 1) * daily returns
    # Shift signals to avoid look-ahead bias
    strategy_returns = signals.shift(1) * daily_returns

    # Calculate cumulative returns
    cumulative_returns = (1 + strategy_returns).cumprod()

    # Convert to equity curve
    equity_curve = initial_capital * cumulative_returns

    # Fill NaN values at the beginning with initial capital
    equity_curve = equity_curve.fillna(initial_capital)

    return equity_curve


def calculate_sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio from equity curve.

    Args:
        equity_curve: Series of portfolio values over time
        risk_free_rate: Annual risk-free rate (default 0)
        periods_per_year: Trading periods per year (252 for daily)

    Returns:
        Sharpe ratio (annualized)
    """
    # Calculate daily returns
    returns = equity_curve.pct_change().dropna()

    if len(returns) < 2:
        return 0.0

    # Calculate excess returns (assuming daily risk-free rate is annual_rate / 252)
    daily_rf_rate = risk_free_rate / periods_per_year
    excess_returns = returns - daily_rf_rate

    # Calculate Sharpe ratio
    if excess_returns.std() == 0:
        return 0.0

    sharpe = excess_returns.mean() / excess_returns.std()

    # Annualize
    sharpe_annualized = sharpe * np.sqrt(periods_per_year)

    return float(sharpe_annualized)


def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Calculate maximum drawdown from equity curve.

    Args:
        equity_curve: Series of portfolio values over time

    Returns:
        Maximum drawdown as a negative percentage (e.g., -0.18 for 18% drawdown)
    """
    if len(equity_curve) < 2:
        return 0.0

    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown
    drawdown = (equity_curve - running_max) / running_max

    # Get maximum drawdown (most negative value)
    max_dd = float(drawdown.min())

    return max_dd


def calculate_total_return(equity_curve: pd.Series) -> float:
    """
    Calculate total return from equity curve.

    Args:
        equity_curve: Series of portfolio values over time

    Returns:
        Total return as a percentage (e.g., 0.45 for 45% return)
    """
    if len(equity_curve) < 2:
        return 0.0

    initial_value = equity_curve.iloc[0]
    final_value = equity_curve.iloc[-1]

    if initial_value == 0:
        return 0.0

    total_return = (final_value - initial_value) / initial_value

    return float(total_return)


def run_backtest(
    df: pd.DataFrame,
    strategy: str,
    params: Dict[str, Any],
    initial_capital: float = 10000.0
) -> Dict[str, Any]:
    """
    Run backtest with specified strategy and parameters.

    Args:
        df: OHLCV DataFrame
        strategy: Strategy name (currently only "ma_crossover")
        params: Strategy parameters (e.g., {"fast": 10, "slow": 30})
        initial_capital: Starting capital

    Returns:
        Dictionary with backtest results

    Raises:
        ValueError: If strategy is unknown or parameters are invalid
    """
    import time
    start_time = time.time()

    # Validate strategy
    if strategy != "ma_crossover":
        raise ValueError(f"Unknown strategy: {strategy}. Only 'ma_crossover' is supported in Phase 1")

    # Extract parameters
    fast = params.get("fast", 10)
    slow = params.get("slow", 30)

    # Generate signals
    signals = calculate_ma_crossover_signals(df, fast, slow)

    # Calculate equity curve
    equity_curve = calculate_returns(df, signals, initial_capital)

    # Calculate metrics
    sharpe = calculate_sharpe_ratio(equity_curve)
    max_dd = calculate_max_drawdown(equity_curve)
    total_ret = calculate_total_return(equity_curve)

    # Generate job ID
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    job_id = f"manual-{timestamp}"

    runtime = time.time() - start_time

    return {
        "job_id": job_id,
        "status": "completed",
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "total_return": round(total_ret, 4),
        "equity_curve": equity_curve.tolist(),
        "runtime_seconds": round(runtime, 2),
        "created_at": datetime.utcnow()
    }


def generate_job_id(prefix: str = "manual") -> str:
    """
    Generate a unique job ID.

    Args:
        prefix: Prefix for job ID (e.g., "manual", "auto")

    Returns:
        Job ID in format: prefix-YYYYMMDD-HHMMSS
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}"

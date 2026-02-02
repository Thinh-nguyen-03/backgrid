"""Moving Average Crossover strategy for Backgrid.

Implements classic dual moving average crossover with configurable
fast and slow periods.
"""

from typing import Dict, Any, Optional
import pandas as pd

from .base import BaseStrategy, Signal


class MAStrategy(BaseStrategy):
    """Moving Average Crossover strategy.

    Generates buy signals when fast MA crosses above slow MA,
    and sell signals when fast MA crosses below slow MA.

    Default Parameters:
        fast_period: 10 - Fast moving average period
        slow_period: 30 - Slow moving average period
    """

    name: str = "ma_crossover"

    DEFAULT_PARAMS = {
        "fast_period": 10,
        "slow_period": 30,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        merged = {**self.DEFAULT_PARAMS}
        if params:
            if "fast" in params:
                merged["fast_period"] = params["fast"]
            if "slow" in params:
                merged["slow_period"] = params["slow"]
            if "fast_period" in params:
                merged["fast_period"] = params["fast_period"]
            if "slow_period" in params:
                merged["slow_period"] = params["slow_period"]
        super().__init__(merged)

    def _validate_params(self) -> None:
        """Validate MA strategy parameters."""
        fast = self.params.get("fast_period", 10)
        slow = self.params.get("slow_period", 30)

        if not isinstance(fast, int) or fast < 2:
            raise ValueError("fast_period must be an integer >= 2")

        if not isinstance(slow, int) or slow < 2:
            raise ValueError("slow_period must be an integer >= 2")

        if fast >= slow:
            raise ValueError(
                f"fast_period ({fast}) must be less than slow_period ({slow})"
            )

    def get_warmup_period(self) -> int:
        """MA strategy needs slow_period bars for warmup."""
        return self.params["slow_period"]

    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Calculate MA crossover signals.

        Args:
            df: DataFrame with Close prices

        Returns:
            Series of Signal values
        """
        self.validate_dataframe(df)

        fast_period = self.params["fast_period"]
        slow_period = self.params["slow_period"]

        fast_ma = df["Close"].rolling(window=fast_period).mean()
        slow_ma = df["Close"].rolling(window=slow_period).mean()

        signals = pd.Series(Signal.HOLD, index=df.index)

        long_condition = fast_ma > slow_ma
        signals[long_condition] = Signal.BUY
        signals[~long_condition] = Signal.SELL

        return signals

    def get_position_signals(self, df: pd.DataFrame) -> pd.Series:
        """Calculate position signals (1 for long, 0 for flat).

        This method provides backward compatibility with the original
        backtesting engine which uses numeric position signals.

        Args:
            df: DataFrame with Close prices

        Returns:
            Series with 1 (long) or 0 (flat) values
        """
        self.validate_dataframe(df)

        fast_period = self.params["fast_period"]
        slow_period = self.params["slow_period"]

        fast_ma = df["Close"].rolling(window=fast_period).mean()
        slow_ma = df["Close"].rolling(window=slow_period).mean()

        positions = pd.Series(0, index=df.index)
        positions[fast_ma > slow_ma] = 1

        return positions

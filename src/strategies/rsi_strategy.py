"""RSI mean reversion strategy for Backgrid.

Implements Relative Strength Index with confirmation logic matching
RapidTrader parameters for mean reversion trading.
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal


class RSIStrategy(BaseStrategy):
    """RSI mean reversion strategy with confirmation.

    Generates buy signals when RSI is oversold with confirmation,
    and sell signals when RSI is overbought.

    The 2-of-3 confirmation logic requires that the RSI condition
    (oversold/overbought) be met on at least min_confirmation_count
    of the last confirmation_window bars before generating a signal.

    Default Parameters (RapidTrader):
        rsi_period: 14 - RSI calculation lookback
        oversold_threshold: 30 - Buy when RSI below this
        overbought_threshold: 55 - Sell when RSI above this
        confirmation_window: 3 - Number of bars to check for confirmation
        min_confirmation_count: 2 - Minimum confirmations needed
    """

    name: str = "rsi"

    DEFAULT_PARAMS = {
        "rsi_period": 14,
        "oversold_threshold": 30,
        "overbought_threshold": 55,
        "confirmation_window": 3,
        "min_confirmation_count": 2,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged_params)

    def _validate_params(self) -> None:
        """Validate RSI strategy parameters."""
        rsi_period = self.params.get("rsi_period", 14)
        oversold = self.params.get("oversold_threshold", 30)
        overbought = self.params.get("overbought_threshold", 55)
        window = self.params.get("confirmation_window", 3)
        min_count = self.params.get("min_confirmation_count", 2)

        if not isinstance(rsi_period, int) or rsi_period < 2:
            raise ValueError("rsi_period must be an integer >= 2")

        if not (0 <= oversold <= 100):
            raise ValueError("oversold_threshold must be between 0 and 100")

        if not (0 <= overbought <= 100):
            raise ValueError("overbought_threshold must be between 0 and 100")

        if oversold >= overbought:
            raise ValueError(
                f"oversold_threshold ({oversold}) must be less than "
                f"overbought_threshold ({overbought})"
            )

        if not isinstance(window, int) or window < 1:
            raise ValueError("confirmation_window must be an integer >= 1")

        if not isinstance(min_count, int) or min_count < 1:
            raise ValueError("min_confirmation_count must be an integer >= 1")

        if min_count > window:
            raise ValueError(
                f"min_confirmation_count ({min_count}) cannot exceed "
                f"confirmation_window ({window})"
            )

    def get_warmup_period(self) -> int:
        """RSI needs rsi_period + confirmation_window bars."""
        return self.params["rsi_period"] + self.params["confirmation_window"]

    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI signals with confirmation logic.

        Args:
            df: DataFrame with Close prices

        Returns:
            Series of Signal values
        """
        self.validate_dataframe(df)

        rsi_period = self.params["rsi_period"]
        oversold = self.params["oversold_threshold"]
        overbought = self.params["overbought_threshold"]
        window = self.params["confirmation_window"]
        min_count = self.params["min_confirmation_count"]

        rsi = self._calculate_rsi(df["Close"], rsi_period)

        oversold_mask = rsi < oversold
        overbought_mask = rsi > overbought

        oversold_count = oversold_mask.rolling(window=window).sum()
        overbought_count = overbought_mask.rolling(window=window).sum()

        buy_confirmed = oversold_count >= min_count
        sell_confirmed = overbought_count >= min_count

        signals = pd.Series(Signal.HOLD, index=df.index)
        signals[buy_confirmed] = Signal.BUY
        signals[sell_confirmed] = Signal.SELL

        return signals

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI using Wilder's smoothing method (TA-Lib compatible).

        Uses exponential weighted mean with alpha = 1/period, which matches
        Wilder's original smoothing and TA-Lib implementation.

        Args:
            prices: Series of closing prices
            period: RSI lookback period

        Returns:
            Series of RSI values (0-100 scale)
        """
        delta = prices.diff()

        gains = delta.where(delta > 0, 0.0)
        losses = (-delta).where(delta < 0, 0.0)

        alpha = 1.0 / period
        avg_gain = gains.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
        avg_loss = losses.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)

        rsi = 100 - (100 / (1 + rs))

        rsi = rsi.fillna(50)

        return rsi

    def get_rsi_values(self, df: pd.DataFrame) -> pd.Series:
        """Calculate and return raw RSI values for analysis.

        Args:
            df: DataFrame with Close prices

        Returns:
            Series of RSI values
        """
        self.validate_dataframe(df)
        return self._calculate_rsi(df["Close"], self.params["rsi_period"])

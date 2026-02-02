"""ATR-based position sizing algorithm."""

from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

from .base_sizer import BasePositionSizer, PositionSizeResult


class ATRPositionSizer(BasePositionSizer):
    """ATR-based position sizing for volatility-adjusted risk management.

    Calculates position size based on Average True Range (ATR) to ensure
    consistent risk across different volatility regimes. This approach
    sizes positions smaller for volatile assets and larger for stable ones.

    RapidTrader Parameters:
        atr_period: 14 (RT_ATR_LOOKBACK)
        risk_per_trade: 0.05 (RT_PCT_PER_TRADE) - 5% of equity
        atr_multiplier: 3.0 (RT_ATR_STOP_K) - Stop at 3x ATR

    Example:
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.05,
            "atr_multiplier": 3.0
        })
        result = sizer.calculate_position_size(
            equity=100000,
            price=150.0,
            df=ohlcv_data
        )
    """

    DEFAULT_PARAMS = {
        "atr_period": 14,
        "risk_per_trade": 0.05,
        "atr_multiplier": 3.0,
        "max_position_pct": 0.25,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize ATR position sizer.

        Args:
            params: Configuration parameters:
                - atr_period: ATR calculation period (default 14)
                - risk_per_trade: Fraction of equity to risk per trade (default 0.05)
                - atr_multiplier: Stop distance as multiple of ATR (default 3.0)
                - max_position_pct: Maximum position as fraction of equity (default 0.25)
        """
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged)

    def _validate_params(self) -> None:
        """Validate ATR sizer parameters."""
        atr_period = self.params.get("atr_period", 14)
        risk_per_trade = self.params.get("risk_per_trade", 0.05)
        atr_multiplier = self.params.get("atr_multiplier", 3.0)
        max_position_pct = self.params.get("max_position_pct", 0.25)

        if not isinstance(atr_period, int) or atr_period < 1:
            raise ValueError("atr_period must be a positive integer")

        if not (0 < risk_per_trade <= 1):
            raise ValueError("risk_per_trade must be between 0 and 1")

        if atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be positive")

        if not (0 < max_position_pct <= 1):
            raise ValueError("max_position_pct must be between 0 and 1")

    def calculate_position_size(
        self,
        equity: float,
        price: float,
        df: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> PositionSizeResult:
        """Calculate position size based on ATR.

        Args:
            equity: Current account equity
            price: Current entry price
            df: DataFrame with High, Low, Close columns for ATR calculation

        Returns:
            PositionSizeResult with shares, stop price, and risk details

        Raises:
            ValueError: If df is None or has insufficient data
        """
        if equity <= 0:
            raise ValueError("Equity must be positive")
        if price <= 0:
            raise ValueError("Price must be positive")

        if df is None:
            raise ValueError("DataFrame required for ATR calculation")

        atr_period = self.params["atr_period"]
        risk_per_trade = self.params["risk_per_trade"]
        atr_multiplier = self.params["atr_multiplier"]
        max_position_pct = self.params["max_position_pct"]

        if len(df) < atr_period:
            raise ValueError(
                f"Insufficient data for ATR: need {atr_period} bars, have {len(df)}"
            )

        atr = self.calculate_atr(df, atr_period)
        current_atr = atr.iloc[-1]

        if pd.isna(current_atr) or current_atr <= 0:
            current_atr = price * 0.02

        risk_per_share = current_atr * atr_multiplier
        stop_price = price - risk_per_share

        risk_amount = equity * risk_per_trade
        shares_by_risk = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

        max_position_value = equity * max_position_pct
        max_shares = int(max_position_value / price)

        shares = min(shares_by_risk, max_shares)
        shares = max(shares, 0)

        position_value = shares * price
        actual_risk = shares * risk_per_share

        return PositionSizeResult(
            shares=shares,
            position_value=position_value,
            risk_amount=actual_risk,
            stop_price=stop_price,
            risk_per_share=risk_per_share
        )

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Average True Range using Wilder's smoothing.

        True Range is the maximum of:
        - High - Low
        - abs(High - Previous Close)
        - abs(Low - Previous Close)

        ATR is the exponential moving average of True Range.

        Args:
            df: DataFrame with High, Low, Close columns
            period: ATR lookback period

        Returns:
            Series of ATR values
        """
        high = df['High']
        low = df['Low']
        close = df['Close']

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        alpha = 1.0 / period
        atr = true_range.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

        return atr

    def get_atr_values(self, df: pd.DataFrame) -> pd.Series:
        """Get ATR values for the entire DataFrame.

        Args:
            df: DataFrame with High, Low, Close columns

        Returns:
            Series of ATR values
        """
        return self.calculate_atr(df, self.params["atr_period"])

"""Market regime detection and filtering for risk management."""

import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RegimeState(str, Enum):
    """Market regime states."""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


@dataclass
class MarketRegime:
    """Current market regime information.

    Attributes:
        state: Current regime state (bull/bear/neutral)
        reference_price: Current price of reference instrument
        sma_value: Current SMA value
        above_sma: Whether price is above SMA
        regime_start_date: When current regime began
        days_in_regime: Days since regime started
    """
    state: RegimeState
    reference_price: float
    sma_value: float
    above_sma: bool
    regime_start_date: Optional[datetime] = None
    days_in_regime: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "reference_price": self.reference_price,
            "sma_value": self.sma_value,
            "above_sma": self.above_sma,
            "regime_start_date": self.regime_start_date,
            "days_in_regime": self.days_in_regime
        }


class MarketRegimeFilter:
    """Market regime filter using SMA crossover detection.

    Determines bull/bear market conditions by comparing a reference
    instrument (typically SPY) against its simple moving average.
    When in bear market conditions, new long entries can be blocked.

    RapidTrader Parameters:
        RT_MARKET_FILTER_ENABLE=true
        RT_MARKET_FILTER_SMA=200
        RT_MARKET_FILTER_SYMBOL=SPY

    Example:
        filter = MarketRegimeFilter(sma_period=200, reference_symbol="SPY")
        regime = filter.get_regime(spy_data)
        if filter.allows_entry(spy_data):
            # Proceed with trade
    """

    DEFAULT_PARAMS = {
        "sma_period": 200,
        "reference_symbol": "SPY",
        "buffer_pct": 0.0,
        "confirmation_days": 1,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize market regime filter.

        Args:
            params: Configuration parameters:
                - sma_period: SMA period for regime detection (default 200)
                - reference_symbol: Reference instrument symbol (default SPY)
                - buffer_pct: Buffer zone around SMA (default 0%)
                - confirmation_days: Days needed to confirm regime change (default 1)
        """
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()
        self._current_regime: Optional[RegimeState] = None
        self._regime_start_date: Optional[datetime] = None
        self._confirmation_count: int = 0

    def _validate_params(self) -> None:
        """Validate filter parameters."""
        sma_period = self.params.get("sma_period", 200)
        buffer_pct = self.params.get("buffer_pct", 0.0)
        confirmation_days = self.params.get("confirmation_days", 1)

        if not isinstance(sma_period, int) or sma_period < 1:
            raise ValueError("sma_period must be a positive integer")

        if buffer_pct < 0 or buffer_pct > 0.5:
            raise ValueError("buffer_pct must be between 0 and 0.5")

        if not isinstance(confirmation_days, int) or confirmation_days < 1:
            raise ValueError("confirmation_days must be a positive integer")

    def calculate_sma(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
        """Calculate simple moving average.

        Args:
            df: DataFrame with Close column
            period: SMA period (uses configured period if not provided)

        Returns:
            Series of SMA values
        """
        period = period or self.params["sma_period"]

        if "Close" not in df.columns:
            raise ValueError("DataFrame must contain 'Close' column")

        return df["Close"].rolling(window=period).mean()

    def get_regime(
        self,
        df: pd.DataFrame,
        as_of_date: Optional[datetime] = None
    ) -> MarketRegime:
        """Get current market regime.

        Args:
            df: DataFrame with OHLCV data for reference instrument
            as_of_date: Date to check regime for (default: last date in df)

        Returns:
            MarketRegime with current state information

        Raises:
            ValueError: If insufficient data for SMA calculation
        """
        sma_period = self.params["sma_period"]
        buffer_pct = self.params["buffer_pct"]

        if len(df) < sma_period:
            raise ValueError(
                f"Insufficient data for regime detection: "
                f"need {sma_period} bars, have {len(df)}"
            )

        sma = self.calculate_sma(df)

        if as_of_date is not None:
            if as_of_date not in df.index:
                df_filtered = df[df.index <= as_of_date]
                if len(df_filtered) == 0:
                    raise ValueError(f"No data available before {as_of_date}")
                idx = len(df_filtered) - 1
            else:
                idx = df.index.get_loc(as_of_date)
        else:
            idx = -1

        current_price = float(df["Close"].iloc[idx])
        current_sma = float(sma.iloc[idx])

        if pd.isna(current_sma):
            return MarketRegime(
                state=RegimeState.NEUTRAL,
                reference_price=current_price,
                sma_value=0.0,
                above_sma=True,
                regime_start_date=None,
                days_in_regime=0
            )

        upper_bound = current_sma * (1 + buffer_pct)
        lower_bound = current_sma * (1 - buffer_pct)

        if current_price > upper_bound:
            state = RegimeState.BULL
            above_sma = True
        elif current_price < lower_bound:
            state = RegimeState.BEAR
            above_sma = False
        else:
            state = RegimeState.NEUTRAL
            above_sma = current_price >= current_sma

        regime_start, days_in = self._track_regime_duration(df, sma, state, idx)

        return MarketRegime(
            state=state,
            reference_price=round(current_price, 2),
            sma_value=round(current_sma, 2),
            above_sma=above_sma,
            regime_start_date=regime_start,
            days_in_regime=days_in
        )

    def _track_regime_duration(
        self,
        df: pd.DataFrame,
        sma: pd.Series,
        current_state: RegimeState,
        current_idx: int
    ) -> tuple[Optional[datetime], int]:
        """Track how long current regime has been active.

        Args:
            df: OHLCV DataFrame
            sma: SMA series
            current_state: Current regime state
            current_idx: Current index in DataFrame

        Returns:
            Tuple of (regime_start_date, days_in_regime)
        """
        if current_idx < 0:
            current_idx = len(df) + current_idx

        buffer_pct = self.params["buffer_pct"]
        days_in_regime = 0
        regime_start = None

        for i in range(current_idx, -1, -1):
            if pd.isna(sma.iloc[i]):
                break

            price = df["Close"].iloc[i]
            sma_val = sma.iloc[i]
            upper = sma_val * (1 + buffer_pct)
            lower = sma_val * (1 - buffer_pct)

            if current_state == RegimeState.BULL:
                if price <= upper:
                    break
            elif current_state == RegimeState.BEAR:
                if price >= lower:
                    break
            else:
                if price > upper or price < lower:
                    break

            days_in_regime += 1
            regime_start = df.index[i]
            if isinstance(regime_start, pd.Timestamp):
                regime_start = regime_start.to_pydatetime()

        return regime_start, days_in_regime

    def allows_entry(
        self,
        df: pd.DataFrame,
        as_of_date: Optional[datetime] = None,
        side: str = "long"
    ) -> bool:
        """Check if market regime allows new entries.

        Args:
            df: DataFrame with reference instrument data
            as_of_date: Date to check (default: latest)
            side: Trade side ("long" or "short")

        Returns:
            True if regime allows entry, False otherwise
        """
        try:
            regime = self.get_regime(df, as_of_date)
        except ValueError:
            logger.warning("Insufficient data for regime check, allowing entry")
            return True

        if side == "long":
            return regime.state != RegimeState.BEAR

        elif side == "short":
            return regime.state != RegimeState.BULL

        return True

    def get_regime_series(self, df: pd.DataFrame) -> pd.Series:
        """Get regime state for entire DataFrame.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Series of RegimeState values
        """
        sma_period = self.params["sma_period"]
        buffer_pct = self.params["buffer_pct"]

        if len(df) < sma_period:
            return pd.Series(RegimeState.NEUTRAL, index=df.index)

        sma = self.calculate_sma(df)
        prices = df["Close"]

        upper_bound = sma * (1 + buffer_pct)
        lower_bound = sma * (1 - buffer_pct)

        regimes = pd.Series(RegimeState.NEUTRAL, index=df.index)
        regimes[prices > upper_bound] = RegimeState.BULL
        regimes[prices < lower_bound] = RegimeState.BEAR

        return regimes

    def get_bull_gate_series(self, df: pd.DataFrame) -> pd.Series:
        """Get boolean series indicating if entries are allowed.

        This matches the RapidTrader bull_gate concept where
        True = bull market (entries allowed), False = bear market.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Boolean Series (True = entries allowed)
        """
        regimes = self.get_regime_series(df)
        return regimes != RegimeState.BEAR

    def __repr__(self) -> str:
        return (
            f"MarketRegimeFilter("
            f"sma_period={self.params['sma_period']}, "
            f"reference_symbol={self.params['reference_symbol']})"
        )

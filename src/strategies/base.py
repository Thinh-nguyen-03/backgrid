"""Base strategy interface for Backgrid backtesting engine."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
import pandas as pd


class Signal(str, Enum):
    """Trading signal types.

    BUY: Enter or add to long position
    SELL: Exit long position or enter short
    HOLD: No action, maintain current position
    """
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies.

    Strategies must implement calculate_signals() which processes OHLCV data
    and returns a Series of Signal values indicating trade actions.

    Attributes:
        params: Strategy-specific parameters
        name: Human-readable strategy identifier
    """

    name: str = "base"

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize strategy with parameters.

        Args:
            params: Strategy-specific configuration. Keys and types vary
                   by strategy implementation.
        """
        self.params = params or {}
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate strategy parameters.

        Override in subclass to add strategy-specific validation.
        Raises ValueError if parameters are invalid.
        """
        pass

    @abstractmethod
    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Calculate trading signals from OHLCV data.

        Args:
            df: DataFrame with OHLCV columns. Must contain at minimum:
                - Close: Closing prices
                Additional columns (Open, High, Low, Volume) may be required
                by specific strategy implementations.

        Returns:
            Series indexed same as df with Signal enum values:
            - Signal.BUY: Enter/add to long position
            - Signal.SELL: Exit/reduce position
            - Signal.HOLD: No action

        Raises:
            ValueError: If df is missing required columns or has insufficient data
        """
        pass

    def get_required_columns(self) -> list[str]:
        """Return list of required DataFrame columns for this strategy.

        Returns:
            List of column names required in the input DataFrame.
            Default implementation requires only 'Close'.
        """
        return ["Close"]

    def get_warmup_period(self) -> int:
        """Return number of bars needed before signals can be generated.

        Returns:
            Minimum number of data points required for the strategy
            to produce meaningful signals. Default is 0.
        """
        return 0

    def validate_dataframe(self, df: pd.DataFrame) -> None:
        """Validate input DataFrame has required columns and data.

        Args:
            df: Input DataFrame to validate

        Raises:
            ValueError: If DataFrame is missing columns or has insufficient data
        """
        required = self.get_required_columns()
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        warmup = self.get_warmup_period()
        if len(df) < warmup:
            raise ValueError(
                f"Insufficient data: need at least {warmup} bars, "
                f"but only have {len(df)}"
            )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(params={self.params})"

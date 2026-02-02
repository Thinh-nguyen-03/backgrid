"""Abstract base class for position sizing algorithms."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
import pandas as pd


@dataclass
class PositionSizeResult:
    """Result of position size calculation.

    Attributes:
        shares: Number of shares to trade
        position_value: Total value of the position
        risk_amount: Dollar amount at risk
        stop_price: Calculated stop loss price (if applicable)
        risk_per_share: Risk per share in dollars
    """
    shares: int
    position_value: float
    risk_amount: float
    stop_price: Optional[float] = None
    risk_per_share: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "shares": self.shares,
            "position_value": self.position_value,
            "risk_amount": self.risk_amount,
            "stop_price": self.stop_price,
            "risk_per_share": self.risk_per_share
        }


class BasePositionSizer(ABC):
    """Abstract base class for position sizing algorithms.

    Position sizers calculate the number of shares to trade based on
    account equity, risk parameters, and market data.

    Subclasses must implement:
        - calculate_position_size(): Determine shares to trade
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize position sizer with parameters.

        Args:
            params: Algorithm-specific parameters
        """
        self.params = params or {}
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate parameters. Override in subclasses."""
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        equity: float,
        price: float,
        df: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> PositionSizeResult:
        """Calculate position size for a trade.

        Args:
            equity: Current account equity
            price: Current price of the asset
            df: Optional DataFrame with OHLCV data for volatility calculations
            **kwargs: Additional parameters (e.g., stop_price)

        Returns:
            PositionSizeResult with calculated position details

        Raises:
            ValueError: If inputs are invalid
        """
        pass

    def calculate_max_shares(self, equity: float, price: float) -> int:
        """Calculate maximum shares that can be purchased.

        Args:
            equity: Available equity
            price: Price per share

        Returns:
            Maximum whole shares
        """
        if price <= 0:
            return 0
        return int(equity / price)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(params={self.params})"

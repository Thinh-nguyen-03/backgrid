"""Fixed fractional position sizing algorithm."""

from typing import Optional, Dict, Any
import pandas as pd

from .base_sizer import BasePositionSizer, PositionSizeResult


class FixedFractionalSizer(BasePositionSizer):
    """Fixed fractional position sizing.

    Allocates a fixed percentage of equity to each position.
    Simple and effective for portfolios where equal weighting is desired.

    Parameters:
        fraction: Fraction of equity to allocate (default 0.10 = 10%)
        max_position_pct: Maximum position size as fraction of equity

    Example:
        sizer = FixedFractionalSizer({"fraction": 0.10})
        result = sizer.calculate_position_size(
            equity=100000,
            price=150.0
        )
    """

    DEFAULT_PARAMS = {
        "fraction": 0.10,
        "max_position_pct": 0.25,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize fixed fractional sizer.

        Args:
            params: Configuration parameters:
                - fraction: Fraction of equity per position (default 0.10)
                - max_position_pct: Maximum position size (default 0.25)
        """
        merged = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged)

    def _validate_params(self) -> None:
        """Validate fixed fractional parameters."""
        fraction = self.params.get("fraction", 0.10)
        max_position_pct = self.params.get("max_position_pct", 0.25)

        if not (0 < fraction <= 1):
            raise ValueError("fraction must be between 0 and 1")

        if not (0 < max_position_pct <= 1):
            raise ValueError("max_position_pct must be between 0 and 1")

    def calculate_position_size(
        self,
        equity: float,
        price: float,
        df: Optional[pd.DataFrame] = None,
        **kwargs
    ) -> PositionSizeResult:
        """Calculate position size as fixed fraction of equity.

        Args:
            equity: Current account equity
            price: Current price per share
            df: Not used for fixed fractional sizing
            **kwargs: Optional stop_price for risk calculation

        Returns:
            PositionSizeResult with calculated position details
        """
        if equity <= 0:
            raise ValueError("Equity must be positive")
        if price <= 0:
            raise ValueError("Price must be positive")

        fraction = self.params["fraction"]
        max_position_pct = self.params["max_position_pct"]

        target_value = equity * fraction
        max_value = equity * max_position_pct

        position_value = min(target_value, max_value)
        shares = int(position_value / price)

        actual_value = shares * price

        stop_price = kwargs.get("stop_price")
        risk_amount = 0.0
        risk_per_share = None

        if stop_price is not None and stop_price < price:
            risk_per_share = price - stop_price
            risk_amount = shares * risk_per_share

        return PositionSizeResult(
            shares=shares,
            position_value=actual_value,
            risk_amount=risk_amount,
            stop_price=stop_price,
            risk_per_share=risk_per_share
        )

    def calculate_shares_for_target(
        self,
        equity: float,
        price: float,
        target_weight: float
    ) -> int:
        """Calculate shares to achieve a target portfolio weight.

        Args:
            equity: Total portfolio equity
            price: Price per share
            target_weight: Desired weight (0.0 to 1.0)

        Returns:
            Number of shares to achieve target weight
        """
        if not (0 <= target_weight <= 1):
            raise ValueError("target_weight must be between 0 and 1")

        if price <= 0:
            return 0

        target_value = equity * target_weight
        return int(target_value / price)

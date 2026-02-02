"""Transaction cost modeling for realistic backtesting."""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class CostModel(str, Enum):
    """Available transaction cost models."""
    ZERO = "zero"
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    TIERED = "tiered"


@dataclass
class TransactionCost:
    """Calculated transaction costs for a trade.

    Attributes:
        commission: Broker commission
        spread_cost: Bid-ask spread cost
        slippage: Price slippage cost
        total: Total transaction cost
    """
    commission: float
    spread_cost: float
    slippage: float
    total: float

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "commission": self.commission,
            "spread_cost": self.spread_cost,
            "slippage": self.slippage,
            "total": self.total
        }


class TransactionCostModel:
    """Transaction cost model for backtesting.

    Models realistic trading costs including:
    - Commission: Broker fees per share or per trade
    - Spread: Bid-ask spread as basis points
    - Slippage: Market impact as basis points + volume impact

    RapidTrader Default Costs:
        - Commission: $0.005/share
        - Spread: 5 bps (0.05%)
        - Slippage: 2 bps + volume impact

    Example:
        model = TransactionCostModel({
            "commission_per_share": 0.005,
            "spread_bps": 5,
            "slippage_bps": 2
        })
        cost = model.calculate_cost(
            price=150.0,
            shares=100,
            volume=1000000
        )
    """

    DEFAULT_PARAMS = {
        "commission_per_share": 0.005,
        "min_commission": 1.0,
        "spread_bps": 5.0,
        "slippage_bps": 2.0,
        "volume_impact_factor": 0.1,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize transaction cost model.

        Args:
            params: Cost model parameters:
                - commission_per_share: Commission per share (default $0.005)
                - min_commission: Minimum commission per trade (default $1.00)
                - spread_bps: Bid-ask spread in basis points (default 5)
                - slippage_bps: Base slippage in basis points (default 2)
                - volume_impact_factor: Volume impact multiplier (default 0.1)
        """
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()

    def _validate_params(self) -> None:
        """Validate cost model parameters."""
        if self.params["commission_per_share"] < 0:
            raise ValueError("commission_per_share cannot be negative")
        if self.params["min_commission"] < 0:
            raise ValueError("min_commission cannot be negative")
        if self.params["spread_bps"] < 0:
            raise ValueError("spread_bps cannot be negative")
        if self.params["slippage_bps"] < 0:
            raise ValueError("slippage_bps cannot be negative")

    def calculate_cost(
        self,
        price: float,
        shares: int,
        volume: Optional[int] = None,
        is_buy: bool = True
    ) -> TransactionCost:
        """Calculate total transaction cost for a trade.

        Args:
            price: Trade price per share
            shares: Number of shares traded
            volume: Daily volume for impact calculation (optional)
            is_buy: True for buy orders, False for sell

        Returns:
            TransactionCost with itemized costs
        """
        if price <= 0 or shares <= 0:
            return TransactionCost(
                commission=0.0,
                spread_cost=0.0,
                slippage=0.0,
                total=0.0
            )

        trade_value = price * shares

        commission = max(
            shares * self.params["commission_per_share"],
            self.params["min_commission"]
        )

        spread_bps = self.params["spread_bps"]
        spread_cost = trade_value * (spread_bps / 10000) / 2

        slippage_bps = self.params["slippage_bps"]
        if volume and volume > 0:
            participation_rate = shares / volume
            volume_impact = participation_rate * self.params["volume_impact_factor"] * 10000
            slippage_bps += volume_impact

        slippage = trade_value * (slippage_bps / 10000)

        total = commission + spread_cost + slippage

        return TransactionCost(
            commission=round(commission, 4),
            spread_cost=round(spread_cost, 4),
            slippage=round(slippage, 4),
            total=round(total, 4)
        )

    def calculate_effective_price(
        self,
        price: float,
        shares: int,
        volume: Optional[int] = None,
        is_buy: bool = True
    ) -> float:
        """Calculate effective price after transaction costs.

        For buys, effective price is higher (worse).
        For sells, effective price is lower (worse).

        Args:
            price: Market price per share
            shares: Number of shares
            volume: Daily volume
            is_buy: True for buy, False for sell

        Returns:
            Effective price including costs
        """
        if shares <= 0:
            return price

        cost = self.calculate_cost(price, shares, volume, is_buy)
        cost_per_share = cost.total / shares

        if is_buy:
            return price + cost_per_share
        else:
            return price - cost_per_share

    def calculate_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        shares: int,
        entry_volume: Optional[int] = None,
        exit_volume: Optional[int] = None
    ) -> float:
        """Calculate total cost for a round-trip trade (buy + sell).

        Args:
            entry_price: Entry price per share
            exit_price: Exit price per share
            shares: Number of shares
            entry_volume: Volume at entry
            exit_volume: Volume at exit

        Returns:
            Total round-trip cost in dollars
        """
        entry_cost = self.calculate_cost(entry_price, shares, entry_volume, is_buy=True)
        exit_cost = self.calculate_cost(exit_price, shares, exit_volume, is_buy=False)

        return entry_cost.total + exit_cost.total

    def cost_as_percentage(
        self,
        price: float,
        shares: int,
        volume: Optional[int] = None
    ) -> float:
        """Calculate transaction cost as percentage of trade value.

        Args:
            price: Trade price
            shares: Number of shares
            volume: Daily volume

        Returns:
            Cost as decimal percentage (e.g., 0.005 for 0.5%)
        """
        if price <= 0 or shares <= 0:
            return 0.0

        cost = self.calculate_cost(price, shares, volume)
        trade_value = price * shares

        return cost.total / trade_value

    @classmethod
    def zero_cost(cls) -> "TransactionCostModel":
        """Create a zero-cost model for testing."""
        return cls({
            "commission_per_share": 0.0,
            "min_commission": 0.0,
            "spread_bps": 0.0,
            "slippage_bps": 0.0,
            "volume_impact_factor": 0.0
        })

    def __repr__(self) -> str:
        return f"TransactionCostModel(params={self.params})"

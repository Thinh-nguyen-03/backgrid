"""Portfolio heat tracking for aggregate risk exposure management."""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class HeatStatus(str, Enum):
    """Portfolio heat status levels."""
    COOL = "cool"
    WARM = "warm"
    HOT = "hot"
    CRITICAL = "critical"


@dataclass
class PositionRisk:
    """Risk information for a single position.

    Attributes:
        symbol: Stock symbol
        entry_price: Position entry price
        current_price: Current market price
        shares: Number of shares
        stop_price: Stop loss price
        risk_per_share: Dollar risk per share
        total_risk: Total dollar risk for position
        risk_pct: Risk as percentage of portfolio
    """
    symbol: str
    entry_price: float
    current_price: float
    shares: int
    stop_price: float
    risk_per_share: float
    total_risk: float
    risk_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "shares": self.shares,
            "stop_price": self.stop_price,
            "risk_per_share": self.risk_per_share,
            "total_risk": self.total_risk,
            "risk_pct": self.risk_pct
        }


@dataclass
class HeatReport:
    """Portfolio heat report.

    Attributes:
        status: Current heat status
        total_heat_value: Total dollar amount at risk
        total_heat_pct: Total risk as percentage of portfolio
        max_heat_pct: Maximum allowed heat percentage
        capacity_remaining: Dollar amount of risk capacity remaining
        position_count: Number of open positions
        positions: List of position risk details
        timestamp: Report generation timestamp
    """
    status: HeatStatus
    total_heat_value: float
    total_heat_pct: float
    max_heat_pct: float
    capacity_remaining: float
    position_count: int
    positions: List[PositionRisk] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "total_heat_value": self.total_heat_value,
            "total_heat_pct": self.total_heat_pct,
            "max_heat_pct": self.max_heat_pct,
            "capacity_remaining": self.capacity_remaining,
            "position_count": self.position_count,
            "positions": [p.to_dict() for p in self.positions],
            "timestamp": self.timestamp
        }


class PortfolioHeatTracker:
    """Tracks aggregate portfolio risk exposure (heat).

    Portfolio heat measures the total capital at risk across all
    open positions. This helps ensure the portfolio doesn't take
    on excessive aggregate risk.

    Heat calculation:
        For each position: risk = shares * (entry_price - stop_price)
        Total heat = sum of all position risks

    Status thresholds:
        COOL: < 50% of max heat
        WARM: 50-75% of max heat
        HOT: 75-100% of max heat
        CRITICAL: > 100% of max heat

    Example:
        tracker = PortfolioHeatTracker(max_heat_pct=0.06)
        tracker.add_position("AAPL", entry=150, shares=100, stop=145)
        tracker.add_position("MSFT", entry=300, shares=50, stop=290)

        report = tracker.get_heat_report(portfolio_value=100000)
        if tracker.allows_new_risk(proposed_risk=1000, portfolio_value=100000):
            # Proceed with trade
    """

    DEFAULT_PARAMS = {
        "max_heat_pct": 0.06,
        "warm_threshold": 0.50,
        "hot_threshold": 0.75,
        "critical_threshold": 1.00,
        "max_positions": 20,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize portfolio heat tracker.

        Args:
            params: Configuration parameters:
                - max_heat_pct: Maximum portfolio heat as fraction (default 0.06 = 6%)
                - warm_threshold: Threshold for WARM status (default 0.50)
                - hot_threshold: Threshold for HOT status (default 0.75)
                - critical_threshold: Threshold for CRITICAL status (default 1.00)
                - max_positions: Maximum number of positions (default 20)
        """
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()

        self._positions: Dict[str, Dict[str, float]] = {}

    def _validate_params(self) -> None:
        """Validate heat tracker parameters."""
        max_heat = self.params.get("max_heat_pct", 0.06)
        max_positions = self.params.get("max_positions", 20)

        if not (0 < max_heat <= 1):
            raise ValueError("max_heat_pct must be between 0 and 1")

        if not isinstance(max_positions, int) or max_positions < 1:
            raise ValueError("max_positions must be a positive integer")

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        shares: int,
        stop_price: float,
        current_price: Optional[float] = None
    ) -> float:
        """Add or update a position for heat tracking.

        Args:
            symbol: Stock symbol
            entry_price: Position entry price
            shares: Number of shares
            stop_price: Stop loss price
            current_price: Current market price (defaults to entry_price)

        Returns:
            Position risk amount
        """
        if shares <= 0:
            if symbol in self._positions:
                del self._positions[symbol]
            return 0.0

        if stop_price >= entry_price:
            logger.warning(
                f"Stop price ({stop_price}) >= entry price ({entry_price}) for {symbol}"
            )
            stop_price = entry_price * 0.95

        risk_per_share = entry_price - stop_price
        total_risk = risk_per_share * shares

        self._positions[symbol] = {
            "entry_price": entry_price,
            "current_price": current_price or entry_price,
            "shares": shares,
            "stop_price": stop_price,
            "risk_per_share": risk_per_share,
            "total_risk": total_risk
        }

        logger.debug(
            f"Position added for heat: {symbol}, "
            f"risk=${total_risk:,.2f}"
        )

        return total_risk

    def update_position(
        self,
        symbol: str,
        current_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> None:
        """Update position values.

        Args:
            symbol: Stock symbol
            current_price: New current price
            stop_price: New stop price
        """
        if symbol not in self._positions:
            return

        pos = self._positions[symbol]

        if current_price is not None:
            pos["current_price"] = current_price

        if stop_price is not None:
            pos["stop_price"] = stop_price
            pos["risk_per_share"] = pos["entry_price"] - stop_price
            pos["total_risk"] = pos["risk_per_share"] * pos["shares"]

    def remove_position(self, symbol: str) -> None:
        """Remove a position from heat tracking.

        Args:
            symbol: Stock symbol
        """
        if symbol in self._positions:
            del self._positions[symbol]
            logger.debug(f"Position removed from heat: {symbol}")

    def get_total_heat(self) -> float:
        """Calculate total portfolio heat (risk).

        Returns:
            Total dollar amount at risk
        """
        return sum(p["total_risk"] for p in self._positions.values())

    def get_heat_pct(self, portfolio_value: float) -> float:
        """Calculate heat as percentage of portfolio.

        Args:
            portfolio_value: Total portfolio value

        Returns:
            Heat as decimal percentage
        """
        if portfolio_value <= 0:
            return 0.0

        total_heat = self.get_total_heat()
        return total_heat / portfolio_value

    def get_heat_status(self, portfolio_value: float) -> HeatStatus:
        """Get current heat status level.

        Args:
            portfolio_value: Total portfolio value

        Returns:
            HeatStatus enum value
        """
        heat_pct = self.get_heat_pct(portfolio_value)
        max_heat = self.params["max_heat_pct"]

        heat_ratio = heat_pct / max_heat if max_heat > 0 else 0

        if heat_ratio >= self.params["critical_threshold"]:
            return HeatStatus.CRITICAL
        elif heat_ratio >= self.params["hot_threshold"]:
            return HeatStatus.HOT
        elif heat_ratio >= self.params["warm_threshold"]:
            return HeatStatus.WARM
        else:
            return HeatStatus.COOL

    def get_heat_report(self, portfolio_value: float) -> HeatReport:
        """Generate comprehensive heat report.

        Args:
            portfolio_value: Total portfolio value

        Returns:
            HeatReport with detailed information
        """
        total_heat = self.get_total_heat()
        heat_pct = self.get_heat_pct(portfolio_value)
        max_heat_pct = self.params["max_heat_pct"]
        status = self.get_heat_status(portfolio_value)

        max_heat_value = portfolio_value * max_heat_pct
        capacity = max(0, max_heat_value - total_heat)

        positions = []
        for symbol, pos in self._positions.items():
            positions.append(PositionRisk(
                symbol=symbol,
                entry_price=pos["entry_price"],
                current_price=pos["current_price"],
                shares=int(pos["shares"]),
                stop_price=pos["stop_price"],
                risk_per_share=round(pos["risk_per_share"], 2),
                total_risk=round(pos["total_risk"], 2),
                risk_pct=round(pos["total_risk"] / portfolio_value, 4) if portfolio_value > 0 else 0
            ))

        positions.sort(key=lambda x: x.total_risk, reverse=True)

        return HeatReport(
            status=status,
            total_heat_value=round(total_heat, 2),
            total_heat_pct=round(heat_pct, 4),
            max_heat_pct=max_heat_pct,
            capacity_remaining=round(capacity, 2),
            position_count=len(self._positions),
            positions=positions
        )

    def allows_new_risk(
        self,
        proposed_risk: float,
        portfolio_value: float
    ) -> bool:
        """Check if additional risk can be taken.

        Args:
            proposed_risk: Dollar amount of proposed new risk
            portfolio_value: Total portfolio value

        Returns:
            True if new risk is allowed, False otherwise
        """
        if portfolio_value <= 0:
            return False

        max_positions = self.params["max_positions"]
        if len(self._positions) >= max_positions:
            logger.info(
                f"Max positions ({max_positions}) reached"
            )
            return False

        current_heat = self.get_total_heat()
        new_heat = current_heat + proposed_risk
        new_heat_pct = new_heat / portfolio_value

        max_heat_pct = self.params["max_heat_pct"]

        if new_heat_pct > max_heat_pct:
            logger.info(
                f"Heat limit exceeded: current={current_heat/portfolio_value:.1%}, "
                f"proposed={new_heat_pct:.1%}, max={max_heat_pct:.0%}"
            )
            return False

        return True

    def get_max_new_risk(self, portfolio_value: float) -> float:
        """Calculate maximum additional risk that can be taken.

        Args:
            portfolio_value: Total portfolio value

        Returns:
            Maximum dollar amount of new risk allowed
        """
        max_heat = portfolio_value * self.params["max_heat_pct"]
        current_heat = self.get_total_heat()
        return max(0, max_heat - current_heat)

    def get_position_count(self) -> int:
        """Get number of tracked positions.

        Returns:
            Position count
        """
        return len(self._positions)

    def get_max_positions(self) -> int:
        """Get maximum allowed positions.

        Returns:
            Max positions limit
        """
        return self.params["max_positions"]

    def get_positions_available(self) -> int:
        """Get number of position slots available.

        Returns:
            Number of slots remaining
        """
        return max(0, self.params["max_positions"] - len(self._positions))

    def clear_positions(self) -> None:
        """Clear all tracked positions."""
        self._positions.clear()

    def get_largest_risk_position(self) -> Optional[str]:
        """Get symbol with largest risk.

        Returns:
            Symbol with highest risk, or None if no positions
        """
        if not self._positions:
            return None

        return max(
            self._positions.items(),
            key=lambda x: x[1]["total_risk"]
        )[0]

    def __repr__(self) -> str:
        return (
            f"PortfolioHeatTracker("
            f"max_heat={self.params['max_heat_pct']:.0%}, "
            f"positions={len(self._positions)})"
        )

"""Sector concentration limits for portfolio risk management."""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SectorExposure:
    """Exposure information for a single sector.

    Attributes:
        sector: Sector name
        exposure_value: Total dollar value exposed to sector
        exposure_pct: Percentage of portfolio in sector
        symbol_count: Number of positions in sector
        symbols: List of symbols in sector
        limit_pct: Maximum allowed exposure percentage
        within_limit: Whether exposure is within limit
        available_capacity: Dollar amount still available for sector
    """
    sector: str
    exposure_value: float
    exposure_pct: float
    symbol_count: int
    symbols: List[str]
    limit_pct: float
    within_limit: bool
    available_capacity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sector": self.sector,
            "exposure_value": self.exposure_value,
            "exposure_pct": self.exposure_pct,
            "symbol_count": self.symbol_count,
            "symbols": self.symbols,
            "limit_pct": self.limit_pct,
            "within_limit": self.within_limit,
            "available_capacity": self.available_capacity
        }


@dataclass
class Position:
    """Position information for sector tracking.

    Attributes:
        symbol: Stock symbol
        sector: Sector classification
        shares: Number of shares
        market_value: Current market value
        entry_date: Position entry date
    """
    symbol: str
    sector: str
    shares: int
    market_value: float
    entry_date: Optional[datetime] = None


class SectorLimitManager:
    """Manages sector concentration limits for portfolio risk.

    Tracks portfolio exposure by sector and enforces maximum
    concentration limits to ensure diversification.

    RapidTrader Parameters:
        RT_MAX_EXPOSURE_PER_SECTOR=0.30  (30% max per sector)

    Example:
        manager = SectorLimitManager(max_sector_exposure=0.30)
        manager.add_position("AAPL", "Technology", 100, 15000)
        manager.add_position("MSFT", "Technology", 50, 20000)

        if manager.allows_entry("GOOGL", "Technology", 10000, total_portfolio=100000):
            # Proceed with trade
    """

    DEFAULT_PARAMS = {
        "max_sector_exposure": 0.30,
        "default_sector": "Unknown",
        "warn_threshold_pct": 0.25,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize sector limit manager.

        Args:
            params: Configuration parameters:
                - max_sector_exposure: Max exposure per sector as fraction (default 0.30)
                - default_sector: Sector for symbols without classification (default "Unknown")
                - warn_threshold_pct: Threshold to warn about approaching limit (default 0.25)
        """
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()

        self._positions: Dict[str, Position] = {}
        self._sector_overrides: Dict[str, float] = {}

    def _validate_params(self) -> None:
        """Validate sector limit parameters."""
        max_exposure = self.params.get("max_sector_exposure", 0.30)
        warn_threshold = self.params.get("warn_threshold_pct", 0.25)

        if not (0 < max_exposure <= 1):
            raise ValueError("max_sector_exposure must be between 0 and 1")

        if not (0 < warn_threshold <= 1):
            raise ValueError("warn_threshold_pct must be between 0 and 1")

    def set_sector_limit(self, sector: str, limit_pct: float) -> None:
        """Set custom limit for a specific sector.

        Args:
            sector: Sector name
            limit_pct: Maximum exposure as fraction (0-1)
        """
        if not (0 < limit_pct <= 1):
            raise ValueError("limit_pct must be between 0 and 1")

        self._sector_overrides[sector] = limit_pct
        logger.info(f"Set custom limit for {sector}: {limit_pct:.0%}")

    def get_sector_limit(self, sector: str) -> float:
        """Get maximum exposure limit for a sector.

        Args:
            sector: Sector name

        Returns:
            Maximum exposure as fraction
        """
        return self._sector_overrides.get(
            sector,
            self.params["max_sector_exposure"]
        )

    def add_position(
        self,
        symbol: str,
        sector: str,
        shares: int,
        market_value: float,
        entry_date: Optional[datetime] = None
    ) -> None:
        """Add or update a position.

        Args:
            symbol: Stock symbol
            sector: Sector classification
            shares: Number of shares
            market_value: Current market value
            entry_date: Position entry date
        """
        if shares <= 0:
            if symbol in self._positions:
                del self._positions[symbol]
            return

        sector = sector or self.params["default_sector"]

        self._positions[symbol] = Position(
            symbol=symbol,
            sector=sector,
            shares=shares,
            market_value=market_value,
            entry_date=entry_date
        )

        logger.debug(
            f"Position added: {symbol} in {sector}, "
            f"value=${market_value:,.2f}"
        )

    def update_position_value(self, symbol: str, market_value: float) -> None:
        """Update market value for an existing position.

        Args:
            symbol: Stock symbol
            market_value: New market value
        """
        if symbol in self._positions:
            self._positions[symbol].market_value = market_value

    def remove_position(self, symbol: str) -> None:
        """Remove a position.

        Args:
            symbol: Stock symbol
        """
        if symbol in self._positions:
            del self._positions[symbol]
            logger.debug(f"Position removed: {symbol}")

    def get_total_portfolio_value(self) -> float:
        """Calculate total portfolio value from positions.

        Returns:
            Total market value of all positions
        """
        return sum(p.market_value for p in self._positions.values())

    def get_sector_exposure(
        self,
        sector: str,
        total_portfolio: Optional[float] = None
    ) -> SectorExposure:
        """Get exposure information for a sector.

        Args:
            sector: Sector name
            total_portfolio: Total portfolio value (calculates from positions if not provided)

        Returns:
            SectorExposure with detailed information
        """
        if total_portfolio is None:
            total_portfolio = self.get_total_portfolio_value()

        if total_portfolio <= 0:
            total_portfolio = 1.0

        sector_positions = [
            p for p in self._positions.values()
            if p.sector == sector
        ]

        exposure_value = sum(p.market_value for p in sector_positions)
        exposure_pct = exposure_value / total_portfolio
        limit_pct = self.get_sector_limit(sector)

        available = max(0, (limit_pct * total_portfolio) - exposure_value)

        return SectorExposure(
            sector=sector,
            exposure_value=round(exposure_value, 2),
            exposure_pct=round(exposure_pct, 4),
            symbol_count=len(sector_positions),
            symbols=[p.symbol for p in sector_positions],
            limit_pct=limit_pct,
            within_limit=exposure_pct <= limit_pct,
            available_capacity=round(available, 2)
        )

    def get_all_sector_exposures(
        self,
        total_portfolio: Optional[float] = None
    ) -> Dict[str, SectorExposure]:
        """Get exposure information for all sectors.

        Args:
            total_portfolio: Total portfolio value

        Returns:
            Dictionary mapping sector to SectorExposure
        """
        sectors = set(p.sector for p in self._positions.values())
        return {
            sector: self.get_sector_exposure(sector, total_portfolio)
            for sector in sectors
        }

    def allows_entry(
        self,
        symbol: str,
        sector: str,
        proposed_value: float,
        total_portfolio: float
    ) -> bool:
        """Check if a new position would exceed sector limits.

        Args:
            symbol: Stock symbol
            sector: Sector of the stock
            proposed_value: Value of proposed position
            total_portfolio: Total portfolio value (including cash)

        Returns:
            True if entry is allowed, False if it would exceed limit
        """
        if total_portfolio <= 0:
            return False

        sector = sector or self.params["default_sector"]
        exposure = self.get_sector_exposure(sector, total_portfolio)

        new_exposure_value = exposure.exposure_value + proposed_value
        new_exposure_pct = new_exposure_value / total_portfolio

        limit_pct = self.get_sector_limit(sector)

        if new_exposure_pct > limit_pct:
            logger.info(
                f"Sector limit exceeded for {sector}: "
                f"current={exposure.exposure_pct:.1%}, "
                f"proposed={new_exposure_pct:.1%}, "
                f"limit={limit_pct:.0%}"
            )
            return False

        warn_threshold = self.params["warn_threshold_pct"]
        if new_exposure_pct > warn_threshold:
            logger.warning(
                f"Approaching sector limit for {sector}: "
                f"{new_exposure_pct:.1%} of {limit_pct:.0%} limit"
            )

        return True

    def get_available_capacity(
        self,
        sector: str,
        total_portfolio: float
    ) -> float:
        """Get remaining capacity for a sector.

        Args:
            sector: Sector name
            total_portfolio: Total portfolio value

        Returns:
            Dollar amount available for additional positions
        """
        exposure = self.get_sector_exposure(sector, total_portfolio)
        return exposure.available_capacity

    def get_max_position_size(
        self,
        sector: str,
        total_portfolio: float,
        max_single_position_pct: float = 0.10
    ) -> float:
        """Get maximum allowed position size for a sector.

        Args:
            sector: Sector name
            total_portfolio: Total portfolio value
            max_single_position_pct: Max single position as fraction of portfolio

        Returns:
            Maximum position value allowed
        """
        available = self.get_available_capacity(sector, total_portfolio)
        single_max = total_portfolio * max_single_position_pct
        return min(available, single_max)

    def check_compliance(self, total_portfolio: Optional[float] = None) -> List[str]:
        """Check all sectors for limit compliance.

        Args:
            total_portfolio: Total portfolio value

        Returns:
            List of warning/violation messages
        """
        messages = []
        exposures = self.get_all_sector_exposures(total_portfolio)

        for sector, exposure in exposures.items():
            if not exposure.within_limit:
                messages.append(
                    f"VIOLATION: {sector} at {exposure.exposure_pct:.1%} "
                    f"exceeds {exposure.limit_pct:.0%} limit"
                )
            elif exposure.exposure_pct >= self.params["warn_threshold_pct"]:
                messages.append(
                    f"WARNING: {sector} at {exposure.exposure_pct:.1%} "
                    f"approaching {exposure.limit_pct:.0%} limit"
                )

        return messages

    def clear_positions(self) -> None:
        """Clear all tracked positions."""
        self._positions.clear()

    def get_position_count(self) -> int:
        """Get total number of positions.

        Returns:
            Number of positions
        """
        return len(self._positions)

    def get_sector_count(self) -> int:
        """Get number of unique sectors.

        Returns:
            Number of unique sectors
        """
        return len(set(p.sector for p in self._positions.values()))

    def __repr__(self) -> str:
        return (
            f"SectorLimitManager("
            f"max_exposure={self.params['max_sector_exposure']:.0%}, "
            f"positions={len(self._positions)})"
        )

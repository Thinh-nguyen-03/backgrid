"""Portfolio state tracking for multi-symbol backtesting."""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """State of a single position."""
    symbol: str
    shares: int
    entry_price: float
    entry_date: datetime
    entry_cost: float
    sector: Optional[str] = None
    strategy: Optional[str] = None
    stop_price: Optional[float] = None
    current_price: Optional[float] = None

    @property
    def market_value(self) -> float:
        price = self.current_price if self.current_price else self.entry_price
        return self.shares * price

    @property
    def unrealized_pnl(self) -> float:
        if self.current_price is None:
            return 0.0
        return (self.current_price - self.entry_price) * self.shares

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.current_price is None:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "shares": self.shares,
            "entry_price": self.entry_price,
            "entry_date": self.entry_date,
            "entry_cost": self.entry_cost,
            "sector": self.sector,
            "strategy": self.strategy,
            "stop_price": self.stop_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
        }


@dataclass
class PortfolioSnapshot:
    """Point-in-time snapshot of portfolio state."""
    timestamp: datetime
    cash: float
    positions: Dict[str, PositionState]
    realized_pnl: float
    total_transaction_costs: float

    @property
    def total_market_value(self) -> float:
        return sum(p.market_value for p in self.positions.values())

    @property
    def total_equity(self) -> float:
        return self.cash + self.total_market_value

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def position_count(self) -> int:
        return len(self.positions)

    def get_sector_exposures(self) -> Dict[str, float]:
        exposures: Dict[str, float] = {}
        total = self.total_equity
        if total == 0:
            return exposures
        for pos in self.positions.values():
            sector = pos.sector or "Unknown"
            exposures[sector] = exposures.get(sector, 0.0) + pos.market_value
        return {k: v / total for k, v in exposures.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cash": self.cash,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
            "realized_pnl": self.realized_pnl,
            "total_transaction_costs": self.total_transaction_costs,
            "total_market_value": self.total_market_value,
            "total_equity": self.total_equity,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "position_count": self.position_count,
            "sector_exposures": self.get_sector_exposures(),
        }


class PortfolioStateTracker:
    """Tracks portfolio state across multiple symbols during backtesting."""

    DEFAULT_PARAMS = {
        "initial_capital": 10000.0,
        "max_positions": 20,
        "max_sector_exposure": 0.30,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()

        self._initial_capital = float(self.params["initial_capital"])
        self._max_positions = int(self.params["max_positions"])
        self._max_sector_exposure = float(self.params["max_sector_exposure"])

        self._cash = self._initial_capital
        self._positions: Dict[str, PositionState] = {}
        self._realized_pnl = 0.0
        self._total_costs = 0.0
        self._snapshots: List[PortfolioSnapshot] = []

    def _validate_params(self) -> None:
        if self.params["initial_capital"] <= 0:
            raise ValueError("initial_capital must be positive")
        if self.params["max_positions"] <= 0:
            raise ValueError("max_positions must be positive")
        if not 0 < self.params["max_sector_exposure"] <= 1:
            raise ValueError("max_sector_exposure must be between 0 and 1")

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> Dict[str, PositionState]:
        return self._positions.copy()

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

    @property
    def total_equity(self) -> float:
        return self._cash + sum(p.market_value for p in self._positions.values())

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._positions.values())

    def can_open_position(
        self,
        symbol: str,
        shares: int,
        price: float,
        sector: Optional[str] = None,
        transaction_cost: float = 0.0,
    ) -> bool:
        if symbol in self._positions:
            return False
        if len(self._positions) >= self._max_positions:
            return False
        required_capital = shares * price + transaction_cost
        if required_capital > self._cash:
            return False
        if sector:
            current_exposure = self._get_sector_exposure(sector)
            new_exposure = (current_exposure * self.total_equity + shares * price) / (
                self.total_equity + shares * price - required_capital + self._cash
            )
            if new_exposure > self._max_sector_exposure:
                return False
        return True

    def _get_sector_exposure(self, sector: str) -> float:
        total = self.total_equity
        if total == 0:
            return 0.0
        sector_value = sum(
            p.market_value for p in self._positions.values() if p.sector == sector
        )
        return sector_value / total

    def open_position(
        self,
        symbol: str,
        shares: int,
        price: float,
        timestamp: datetime,
        transaction_cost: float = 0.0,
        sector: Optional[str] = None,
        strategy: Optional[str] = None,
        stop_price: Optional[float] = None,
    ) -> Optional[PositionState]:
        if symbol in self._positions:
            logger.warning(f"Position already exists for {symbol}")
            return None
        if len(self._positions) >= self._max_positions:
            logger.warning(f"Max positions reached ({self._max_positions})")
            return None

        cost = shares * price + transaction_cost
        if cost > self._cash:
            logger.warning(f"Insufficient cash for {symbol}: need {cost}, have {self._cash}")
            return None

        self._cash -= cost
        self._total_costs += transaction_cost

        position = PositionState(
            symbol=symbol,
            shares=shares,
            entry_price=price,
            entry_date=timestamp,
            entry_cost=transaction_cost,
            sector=sector,
            strategy=strategy,
            stop_price=stop_price,
            current_price=price,
        )
        self._positions[symbol] = position

        logger.debug(f"Opened position: {symbol} {shares}@{price}")
        return position

    def close_position(
        self,
        symbol: str,
        price: float,
        timestamp: datetime,
        transaction_cost: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        if symbol not in self._positions:
            logger.warning(f"No position to close for {symbol}")
            return None

        position = self._positions.pop(symbol)
        proceeds = position.shares * price - transaction_cost
        pnl = (price - position.entry_price) * position.shares
        total_costs = position.entry_cost + transaction_cost

        self._cash += proceeds
        self._realized_pnl += pnl
        self._total_costs += transaction_cost

        logger.debug(f"Closed position: {symbol} PnL={pnl:.2f}")

        return {
            "symbol": symbol,
            "shares": position.shares,
            "entry_price": position.entry_price,
            "entry_date": position.entry_date,
            "exit_price": price,
            "exit_date": timestamp,
            "pnl": pnl,
            "pnl_pct": (price - position.entry_price) / position.entry_price if position.entry_price > 0 else 0,
            "transaction_costs": total_costs,
            "strategy": position.strategy,
            "sector": position.sector,
        }

    def update_prices(self, prices: Dict[str, float]) -> None:
        for symbol, price in prices.items():
            if symbol in self._positions:
                self._positions[symbol].current_price = price

    def get_snapshot(self, timestamp: Optional[datetime] = None) -> PortfolioSnapshot:
        ts = timestamp or datetime.now()
        snapshot = PortfolioSnapshot(
            timestamp=ts,
            cash=self._cash,
            positions=self._positions.copy(),
            realized_pnl=self._realized_pnl,
            total_transaction_costs=self._total_costs,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def get_equity_curve(self) -> List[float]:
        return [s.total_equity for s in self._snapshots]

    def reset(self) -> None:
        self._cash = self._initial_capital
        self._positions.clear()
        self._realized_pnl = 0.0
        self._total_costs = 0.0
        self._snapshots.clear()

"""Order execution simulator for backtesting."""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd

from .transaction_costs import TransactionCostModel, TransactionCost


class OrderSide(str, Enum):
    """Order side (buy or sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order execution status."""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    """Represents a trading order.

    Attributes:
        symbol: Stock ticker symbol
        side: Buy or sell
        shares: Number of shares
        signal_price: Price when signal was generated
        signal_date: Date when signal was generated
        order_type: Market, limit, etc.
        limit_price: Limit price (if applicable)
    """
    symbol: str
    side: OrderSide
    shares: int
    signal_price: float
    signal_date: datetime
    order_type: str = "market"
    limit_price: Optional[float] = None
    strategy: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "shares": self.shares,
            "signal_price": self.signal_price,
            "signal_date": self.signal_date,
            "order_type": self.order_type,
            "limit_price": self.limit_price,
            "strategy": self.strategy
        }


@dataclass
class Fill:
    """Represents an order fill (execution).

    Attributes:
        order: The original order
        fill_price: Actual execution price
        fill_date: Date of execution
        shares_filled: Number of shares filled
        transaction_cost: Associated transaction costs
        status: Fill status
    """
    order: Order
    fill_price: float
    fill_date: datetime
    shares_filled: int
    transaction_cost: TransactionCost
    status: OrderStatus = OrderStatus.FILLED

    @property
    def effective_price(self) -> float:
        """Get effective price including costs."""
        if self.shares_filled <= 0:
            return self.fill_price

        cost_per_share = self.transaction_cost.total / self.shares_filled

        if self.order.side == OrderSide.BUY:
            return self.fill_price + cost_per_share
        else:
            return self.fill_price - cost_per_share

    @property
    def total_value(self) -> float:
        """Get total fill value (excluding costs)."""
        return self.fill_price * self.shares_filled

    @property
    def total_cost(self) -> float:
        """Get total cost including transaction fees."""
        if self.order.side == OrderSide.BUY:
            return self.total_value + self.transaction_cost.total
        else:
            return self.total_value - self.transaction_cost.total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.order.symbol,
            "side": self.order.side.value,
            "shares_filled": self.shares_filled,
            "fill_price": self.fill_price,
            "effective_price": self.effective_price,
            "fill_date": self.fill_date,
            "transaction_cost": self.transaction_cost.total,
            "status": self.status.value,
            "strategy": self.order.strategy
        }


class OrderSimulator:
    """Simulates order execution for backtesting.

    Models realistic order execution including:
    - Signal-to-fill delay (signals at EOD, fills at next open)
    - Transaction costs (commission, spread, slippage)
    - Fill price determination

    RapidTrader Execution Model:
        - Signals generated at end-of-day
        - Orders filled at next day's open price
        - Transaction costs applied to fills

    Example:
        simulator = OrderSimulator(
            cost_model=TransactionCostModel(),
            fill_at="next_open"
        )

        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 1, 15)
        )

        fill = simulator.execute_order(
            order=order,
            df=ohlcv_data,
            signal_idx=10
        )
    """

    def __init__(
        self,
        cost_model: Optional[TransactionCostModel] = None,
        fill_at: str = "next_open"
    ):
        """Initialize order simulator.

        Args:
            cost_model: Transaction cost model to use
            fill_at: Fill price logic:
                - "next_open": Fill at next bar's open (default)
                - "close": Fill at signal bar's close
                - "vwap": Approximate VWAP (average of OHLC)
        """
        self.cost_model = cost_model or TransactionCostModel()
        self.fill_at = fill_at
        self._fills: List[Fill] = []

    def execute_order(
        self,
        order: Order,
        df: pd.DataFrame,
        signal_idx: int
    ) -> Optional[Fill]:
        """Execute an order against historical data.

        Args:
            order: Order to execute
            df: DataFrame with OHLCV data
            signal_idx: Index in df where signal was generated

        Returns:
            Fill object if order was executed, None if couldn't fill
        """
        if signal_idx < 0 or signal_idx >= len(df):
            return None

        fill_price, fill_idx = self._determine_fill_price(df, signal_idx)

        if fill_price is None or fill_idx is None:
            return self._create_rejected_fill(order, "No fill price available")

        fill_date = df.index[fill_idx]
        if isinstance(fill_date, pd.Timestamp):
            fill_date = fill_date.to_pydatetime()

        volume = None
        if 'Volume' in df.columns:
            volume = int(df['Volume'].iloc[fill_idx])

        transaction_cost = self.cost_model.calculate_cost(
            price=fill_price,
            shares=order.shares,
            volume=volume,
            is_buy=(order.side == OrderSide.BUY)
        )

        fill = Fill(
            order=order,
            fill_price=fill_price,
            fill_date=fill_date,
            shares_filled=order.shares,
            transaction_cost=transaction_cost,
            status=OrderStatus.FILLED
        )

        self._fills.append(fill)
        return fill

    def _determine_fill_price(
        self,
        df: pd.DataFrame,
        signal_idx: int
    ) -> tuple[Optional[float], Optional[int]]:
        """Determine fill price based on fill_at strategy.

        Args:
            df: OHLCV DataFrame
            signal_idx: Index where signal was generated

        Returns:
            Tuple of (fill_price, fill_bar_index)
        """
        if self.fill_at == "next_open":
            fill_idx = signal_idx + 1
            if fill_idx >= len(df):
                return None, None
            return float(df['Open'].iloc[fill_idx]), fill_idx

        elif self.fill_at == "close":
            return float(df['Close'].iloc[signal_idx]), signal_idx

        elif self.fill_at == "vwap":
            fill_idx = signal_idx + 1
            if fill_idx >= len(df):
                fill_idx = signal_idx

            bar = df.iloc[fill_idx]
            vwap = (bar['Open'] + bar['High'] + bar['Low'] + bar['Close']) / 4
            return float(vwap), fill_idx

        else:
            raise ValueError(f"Unknown fill_at strategy: {self.fill_at}")

    def _create_rejected_fill(self, order: Order, reason: str) -> Fill:
        """Create a rejected fill."""
        return Fill(
            order=order,
            fill_price=0.0,
            fill_date=order.signal_date,
            shares_filled=0,
            transaction_cost=TransactionCost(0, 0, 0, 0),
            status=OrderStatus.REJECTED
        )

    def simulate_trades(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        symbol: str,
        shares_per_trade: int = 100,
        strategy: Optional[str] = None
    ) -> List[Fill]:
        """Simulate trades based on a signal series.

        Args:
            df: OHLCV DataFrame
            signals: Series with Signal values (BUY, SELL, HOLD)
            symbol: Stock ticker symbol
            shares_per_trade: Shares per trade
            strategy: Strategy name for attribution

        Returns:
            List of Fill objects
        """
        from src.strategies import Signal

        fills = []
        position = 0

        for i in range(len(signals)):
            signal = signals.iloc[i]
            price = df['Close'].iloc[i]
            date = df.index[i]

            if isinstance(date, pd.Timestamp):
                date = date.to_pydatetime()

            if signal == Signal.BUY and position == 0:
                order = Order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    shares=shares_per_trade,
                    signal_price=price,
                    signal_date=date,
                    strategy=strategy
                )
                fill = self.execute_order(order, df, i)
                if fill and fill.status == OrderStatus.FILLED:
                    fills.append(fill)
                    position = shares_per_trade

            elif signal == Signal.SELL and position > 0:
                order = Order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    shares=position,
                    signal_price=price,
                    signal_date=date,
                    strategy=strategy
                )
                fill = self.execute_order(order, df, i)
                if fill and fill.status == OrderStatus.FILLED:
                    fills.append(fill)
                    position = 0

        return fills

    def get_fills(self) -> List[Fill]:
        """Get all executed fills."""
        return self._fills.copy()

    def clear_fills(self) -> None:
        """Clear fill history."""
        self._fills.clear()

    def get_fill_summary(self) -> Dict[str, Any]:
        """Get summary statistics for all fills."""
        if not self._fills:
            return {
                "total_fills": 0,
                "total_volume": 0,
                "total_costs": 0.0,
                "avg_cost_per_fill": 0.0
            }

        total_costs = sum(f.transaction_cost.total for f in self._fills)
        total_volume = sum(f.shares_filled for f in self._fills)

        return {
            "total_fills": len(self._fills),
            "total_volume": total_volume,
            "total_costs": round(total_costs, 2),
            "avg_cost_per_fill": round(total_costs / len(self._fills), 4)
        }

    def __repr__(self) -> str:
        return f"OrderSimulator(fill_at='{self.fill_at}', fills={len(self._fills)})"

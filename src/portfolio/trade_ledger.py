"""Trade ledger for tracking and analyzing trade history."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable

from ..backtest import TradeRecord

logger = logging.getLogger(__name__)


@dataclass
class TradeSummary:
    """Summary statistics for a collection of trades."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float
    average_win: float
    average_loss: float
    average_trade: float
    largest_win: float
    largest_loss: float
    average_hold_days: float
    total_transaction_costs: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "average_trade": self.average_trade,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "average_hold_days": self.average_hold_days,
            "total_transaction_costs": self.total_transaction_costs,
        }


class TradeLedger:
    """Maintains a ledger of all trades for analysis and reporting."""

    def __init__(self):
        self._trades: List[TradeRecord] = []

    def add_trade(self, trade: TradeRecord) -> None:
        self._trades.append(trade)
        logger.debug(
            f"Added trade: {trade.symbol} {trade.side} "
            f"PnL={trade.pnl:.2f}"
        )

    def add_trades(self, trades: List[TradeRecord]) -> None:
        for trade in trades:
            self.add_trade(trade)

    def get_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        side: Optional[str] = None,
        min_pnl: Optional[float] = None,
        max_pnl: Optional[float] = None,
    ) -> List[TradeRecord]:
        result = self._trades

        if symbol:
            result = [t for t in result if t.symbol == symbol]
        if strategy:
            result = [t for t in result if t.strategy == strategy]
        if side:
            result = [t for t in result if t.side == side]
        if start_date:
            result = [t for t in result if t.entry_date and t.entry_date >= start_date]
        if end_date:
            result = [t for t in result if t.exit_date and t.exit_date <= end_date]
        if min_pnl is not None:
            result = [t for t in result if t.pnl >= min_pnl]
        if max_pnl is not None:
            result = [t for t in result if t.pnl <= max_pnl]

        return result

    def get_trades_by_symbol(self, symbol: str) -> List[TradeRecord]:
        return self.get_trades(symbol=symbol)

    def get_trades_by_strategy(self, strategy: str) -> List[TradeRecord]:
        return self.get_trades(strategy=strategy)

    def get_winning_trades(self) -> List[TradeRecord]:
        return [t for t in self._trades if t.pnl > 0]

    def get_losing_trades(self) -> List[TradeRecord]:
        return [t for t in self._trades if t.pnl < 0]

    def get_symbols(self) -> List[str]:
        return list(set(t.symbol for t in self._trades))

    def get_strategies(self) -> List[str]:
        return list(set(t.strategy for t in self._trades if t.strategy))

    def get_summary(
        self,
        trades: Optional[List[TradeRecord]] = None,
    ) -> TradeSummary:
        trades = trades if trades is not None else self._trades

        if not trades:
            return TradeSummary(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                profit_factor=0.0,
                average_win=0.0,
                average_loss=0.0,
                average_trade=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                average_hold_days=0.0,
                total_transaction_costs=0.0,
            )

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]

        total_trades = len(trades)
        winning_trades = len(winners)
        losing_trades = len(losers)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        gross_profit = sum(t.pnl for t in winners)
        gross_loss = abs(sum(t.pnl for t in losers))
        total_pnl = gross_profit - gross_loss

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        average_win = gross_profit / winning_trades if winning_trades > 0 else 0.0
        average_loss = gross_loss / losing_trades if losing_trades > 0 else 0.0
        average_trade = total_pnl / total_trades if total_trades > 0 else 0.0

        largest_win = max((t.pnl for t in winners), default=0.0)
        largest_loss = abs(min((t.pnl for t in losers), default=0.0))

        hold_days = []
        for t in trades:
            if t.entry_date and t.exit_date:
                delta = t.exit_date - t.entry_date
                hold_days.append(delta.days)
        average_hold_days = sum(hold_days) / len(hold_days) if hold_days else 0.0

        total_costs = sum(t.transaction_costs for t in trades)

        return TradeSummary(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=round(win_rate, 4),
            total_pnl=round(total_pnl, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 4),
            average_win=round(average_win, 2),
            average_loss=round(average_loss, 2),
            average_trade=round(average_trade, 2),
            largest_win=round(largest_win, 2),
            largest_loss=round(largest_loss, 2),
            average_hold_days=round(average_hold_days, 1),
            total_transaction_costs=round(total_costs, 2),
        )

    def get_summary_by_symbol(self) -> Dict[str, TradeSummary]:
        result = {}
        for symbol in self.get_symbols():
            trades = self.get_trades_by_symbol(symbol)
            result[symbol] = self.get_summary(trades)
        return result

    def get_summary_by_strategy(self) -> Dict[str, TradeSummary]:
        result = {}
        for strategy in self.get_strategies():
            trades = self.get_trades_by_strategy(strategy)
            result[strategy] = self.get_summary(trades)
        return result

    def to_list(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._trades]

    def clear(self) -> None:
        self._trades.clear()

    def __len__(self) -> int:
        return len(self._trades)

    def __iter__(self):
        return iter(self._trades)

"""Stop loss management with ATR-based stops and cooldown periods."""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class StopType(str, Enum):
    """Types of stop loss triggers."""
    ATR = "atr"
    PERCENT = "percent"
    FIXED = "fixed"
    TRAILING = "trailing"


@dataclass
class StopLossResult:
    """Result of stop loss check.

    Attributes:
        triggered: Whether stop was triggered
        stop_type: Type of stop that triggered
        stop_price: The stop price level
        current_price: Current market price
        loss_amount: Dollar amount of loss
        loss_pct: Percentage loss
        in_cooldown: Whether symbol is in cooldown period
        cooldown_end_date: When cooldown ends (if applicable)
    """
    triggered: bool
    stop_type: Optional[StopType]
    stop_price: float
    current_price: float
    loss_amount: float = 0.0
    loss_pct: float = 0.0
    in_cooldown: bool = False
    cooldown_end_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered": self.triggered,
            "stop_type": self.stop_type.value if self.stop_type else None,
            "stop_price": self.stop_price,
            "current_price": self.current_price,
            "loss_amount": self.loss_amount,
            "loss_pct": self.loss_pct,
            "in_cooldown": self.in_cooldown,
            "cooldown_end_date": self.cooldown_end_date
        }


@dataclass
class StopLossState:
    """State tracking for a single position's stop loss.

    Attributes:
        symbol: Stock symbol
        entry_price: Position entry price
        entry_date: Position entry date
        stop_price: Current stop price
        trailing_high: Highest price since entry (for trailing stops)
        stop_type: Type of stop being used
    """
    symbol: str
    entry_price: float
    entry_date: datetime
    stop_price: float
    trailing_high: float
    stop_type: StopType


class StopLossManager:
    """Manages stop losses for positions with cooldown periods.

    Provides ATR-based stop loss calculation and tracking with
    configurable cooldown periods after stops are triggered.

    RapidTrader Parameters:
        RT_ATR_STOP_K=3.0  (stop at 3x ATR below entry)
        RT_COOLDOWN_DAYS_ON_STOP=1

    Example:
        manager = StopLossManager({
            "atr_multiplier": 3.0,
            "cooldown_days": 1
        })

        stop_price = manager.calculate_stop_price(entry_price=100, atr=2.5)
        result = manager.check_stop(symbol, current_price=95, stop_price=97.5)
    """

    DEFAULT_PARAMS = {
        "atr_multiplier": 3.0,
        "atr_period": 14,
        "cooldown_days": 1,
        "trailing_enabled": False,
        "trailing_activation_pct": 0.05,
        "trailing_distance_pct": 0.03,
    }

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """Initialize stop loss manager.

        Args:
            params: Configuration parameters:
                - atr_multiplier: Stop distance as multiple of ATR (default 3.0)
                - atr_period: ATR calculation period (default 14)
                - cooldown_days: Days to wait after stop triggered (default 1)
                - trailing_enabled: Enable trailing stops (default False)
                - trailing_activation_pct: Profit % to activate trailing (default 5%)
                - trailing_distance_pct: Trail distance as % (default 3%)
        """
        self.params = {**self.DEFAULT_PARAMS, **(params or {})}
        self._validate_params()

        self._position_states: Dict[str, StopLossState] = {}
        self._cooldown_symbols: Dict[str, datetime] = {}
        self._stop_history: List[Dict[str, Any]] = []

    def _validate_params(self) -> None:
        """Validate stop loss parameters."""
        atr_mult = self.params.get("atr_multiplier", 3.0)
        atr_period = self.params.get("atr_period", 14)
        cooldown = self.params.get("cooldown_days", 1)

        if atr_mult <= 0:
            raise ValueError("atr_multiplier must be positive")

        if not isinstance(atr_period, int) or atr_period < 1:
            raise ValueError("atr_period must be a positive integer")

        if not isinstance(cooldown, int) or cooldown < 0:
            raise ValueError("cooldown_days must be a non-negative integer")

    def calculate_atr(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.Series:
        """Calculate Average True Range using Wilder's smoothing.

        Args:
            df: DataFrame with High, Low, Close columns
            period: ATR period (uses configured period if not provided)

        Returns:
            Series of ATR values
        """
        period = period or self.params["atr_period"]

        high = df['High']
        low = df['Low']
        close = df['Close']

        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        alpha = 1.0 / period
        atr = true_range.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

        return atr

    def calculate_stop_price(
        self,
        entry_price: float,
        atr: Optional[float] = None,
        df: Optional[pd.DataFrame] = None,
        stop_type: StopType = StopType.ATR
    ) -> float:
        """Calculate stop loss price.

        Args:
            entry_price: Position entry price
            atr: Current ATR value (required for ATR stop)
            df: DataFrame for ATR calculation (alternative to atr param)
            stop_type: Type of stop to calculate

        Returns:
            Stop loss price

        Raises:
            ValueError: If required parameters are missing
        """
        if entry_price <= 0:
            raise ValueError("entry_price must be positive")

        if stop_type == StopType.ATR:
            if atr is None and df is None:
                raise ValueError("ATR stop requires atr value or DataFrame")

            if atr is None:
                atr_series = self.calculate_atr(df)
                atr = float(atr_series.iloc[-1])

            if pd.isna(atr) or atr <= 0:
                atr = entry_price * 0.02

            multiplier = self.params["atr_multiplier"]
            stop_price = entry_price - (atr * multiplier)

        elif stop_type == StopType.PERCENT:
            stop_pct = self.params.get("stop_percent", 0.05)
            stop_price = entry_price * (1 - stop_pct)

        elif stop_type == StopType.FIXED:
            stop_amount = self.params.get("stop_amount", entry_price * 0.05)
            stop_price = entry_price - stop_amount

        else:
            raise ValueError(f"Unknown stop type: {stop_type}")

        return max(stop_price, 0.01)

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        entry_date: datetime,
        atr: Optional[float] = None,
        df: Optional[pd.DataFrame] = None,
        stop_type: StopType = StopType.ATR
    ) -> float:
        """Register a new position for stop loss tracking.

        Args:
            symbol: Stock symbol
            entry_price: Position entry price
            entry_date: Position entry date
            atr: Current ATR value
            df: DataFrame for ATR calculation
            stop_type: Type of stop to use

        Returns:
            Calculated stop price
        """
        stop_price = self.calculate_stop_price(entry_price, atr, df, stop_type)

        self._position_states[symbol] = StopLossState(
            symbol=symbol,
            entry_price=entry_price,
            entry_date=entry_date,
            stop_price=stop_price,
            trailing_high=entry_price,
            stop_type=stop_type
        )

        logger.info(
            f"Registered stop for {symbol}: entry={entry_price:.2f}, "
            f"stop={stop_price:.2f}"
        )

        return stop_price

    def update_trailing_stop(
        self,
        symbol: str,
        current_price: float
    ) -> Optional[float]:
        """Update trailing stop based on current price.

        Args:
            symbol: Stock symbol
            current_price: Current market price

        Returns:
            New stop price if updated, None otherwise
        """
        if symbol not in self._position_states:
            return None

        state = self._position_states[symbol]

        if not self.params["trailing_enabled"]:
            return state.stop_price

        activation_pct = self.params["trailing_activation_pct"]
        trail_pct = self.params["trailing_distance_pct"]

        profit_pct = (current_price - state.entry_price) / state.entry_price

        if profit_pct >= activation_pct:
            if current_price > state.trailing_high:
                state.trailing_high = current_price
                new_stop = current_price * (1 - trail_pct)

                if new_stop > state.stop_price:
                    state.stop_price = new_stop
                    logger.debug(
                        f"Trailing stop updated for {symbol}: {new_stop:.2f}"
                    )

        return state.stop_price

    def check_stop(
        self,
        symbol: str,
        current_price: float,
        current_date: Optional[datetime] = None,
        stop_price: Optional[float] = None
    ) -> StopLossResult:
        """Check if stop loss is triggered.

        Args:
            symbol: Stock symbol
            current_price: Current market price
            current_date: Current date (for cooldown tracking)
            stop_price: Override stop price (uses registered if not provided)

        Returns:
            StopLossResult with trigger status
        """
        current_date = current_date or datetime.now()

        in_cooldown, cooldown_end = self._check_cooldown(symbol, current_date)
        if in_cooldown:
            return StopLossResult(
                triggered=False,
                stop_type=None,
                stop_price=0.0,
                current_price=current_price,
                in_cooldown=True,
                cooldown_end_date=cooldown_end
            )

        if stop_price is None:
            if symbol in self._position_states:
                state = self._position_states[symbol]
                stop_price = state.stop_price
                stop_type = state.stop_type
                entry_price = state.entry_price
            else:
                return StopLossResult(
                    triggered=False,
                    stop_type=None,
                    stop_price=0.0,
                    current_price=current_price
                )
        else:
            stop_type = StopType.ATR
            entry_price = stop_price / (1 - self.params["atr_multiplier"] * 0.02)

        triggered = current_price <= stop_price

        if triggered:
            loss_amount = entry_price - current_price
            loss_pct = loss_amount / entry_price if entry_price > 0 else 0

            self._record_stop_trigger(symbol, current_date, current_price, stop_price)
            self._start_cooldown(symbol, current_date)

            logger.info(
                f"Stop triggered for {symbol}: price={current_price:.2f}, "
                f"stop={stop_price:.2f}, loss={loss_pct:.2%}"
            )
        else:
            loss_amount = 0.0
            loss_pct = 0.0

        return StopLossResult(
            triggered=triggered,
            stop_type=stop_type if triggered else None,
            stop_price=stop_price,
            current_price=current_price,
            loss_amount=round(loss_amount, 2),
            loss_pct=round(loss_pct, 4)
        )

    def _check_cooldown(
        self,
        symbol: str,
        current_date: datetime
    ) -> tuple[bool, Optional[datetime]]:
        """Check if symbol is in cooldown period.

        Args:
            symbol: Stock symbol
            current_date: Current date

        Returns:
            Tuple of (is_in_cooldown, cooldown_end_date)
        """
        if symbol not in self._cooldown_symbols:
            return False, None

        cooldown_end = self._cooldown_symbols[symbol]

        if current_date >= cooldown_end:
            del self._cooldown_symbols[symbol]
            return False, None

        return True, cooldown_end

    def _start_cooldown(self, symbol: str, trigger_date: datetime) -> None:
        """Start cooldown period for a symbol.

        Args:
            symbol: Stock symbol
            trigger_date: Date stop was triggered
        """
        cooldown_days = self.params["cooldown_days"]
        cooldown_end = trigger_date + timedelta(days=cooldown_days)
        self._cooldown_symbols[symbol] = cooldown_end

        logger.info(
            f"Cooldown started for {symbol}: "
            f"until {cooldown_end.strftime('%Y-%m-%d')}"
        )

    def _record_stop_trigger(
        self,
        symbol: str,
        trigger_date: datetime,
        trigger_price: float,
        stop_price: float
    ) -> None:
        """Record stop trigger in history.

        Args:
            symbol: Stock symbol
            trigger_date: Date stop was triggered
            trigger_price: Price at which stop triggered
            stop_price: The stop price level
        """
        self._stop_history.append({
            "symbol": symbol,
            "trigger_date": trigger_date,
            "trigger_price": trigger_price,
            "stop_price": stop_price,
            "slippage": stop_price - trigger_price
        })

    def is_in_cooldown(self, symbol: str, current_date: Optional[datetime] = None) -> bool:
        """Check if symbol is currently in cooldown.

        Args:
            symbol: Stock symbol
            current_date: Date to check (default: now)

        Returns:
            True if in cooldown, False otherwise
        """
        current_date = current_date or datetime.now()
        in_cooldown, _ = self._check_cooldown(symbol, current_date)
        return in_cooldown

    def get_cooldown_end(self, symbol: str) -> Optional[datetime]:
        """Get cooldown end date for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Cooldown end date or None if not in cooldown
        """
        return self._cooldown_symbols.get(symbol)

    def clear_position(self, symbol: str) -> None:
        """Clear position state (after exit).

        Args:
            symbol: Stock symbol
        """
        if symbol in self._position_states:
            del self._position_states[symbol]

    def get_stop_history(self) -> List[Dict[str, Any]]:
        """Get history of stop triggers.

        Returns:
            List of stop trigger records
        """
        return self._stop_history.copy()

    def clear_state(self) -> None:
        """Clear all state (positions, cooldowns, history)."""
        self._position_states.clear()
        self._cooldown_symbols.clear()
        self._stop_history.clear()

    def __repr__(self) -> str:
        return (
            f"StopLossManager("
            f"atr_multiplier={self.params['atr_multiplier']}, "
            f"cooldown_days={self.params['cooldown_days']})"
        )

"""Strategy manager for multi-strategy orchestration."""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import pandas as pd

from .base import BaseStrategy, Signal


class CombinationMethod(str, Enum):
    """Methods for combining signals from multiple strategies.

    OR: Any BUY triggers buy, any SELL triggers sell
    AND: All strategies must agree for signal
    PRIORITY: SELL > BUY > HOLD precedence
    WEIGHTED: Weighted voting based on strategy weights
    """
    OR = "or"
    AND = "and"
    PRIORITY = "priority"
    WEIGHTED = "weighted"


@dataclass
class StrategyAttribution:
    """Tracks which strategy generated each signal.

    Attributes:
        strategy_name: Name of the strategy
        signal: Signal generated
        weight: Weight used in combination
    """
    strategy_name: str
    signal: Signal
    weight: float = 1.0


@dataclass
class CombinedSignal:
    """Result of combining multiple strategy signals.

    Attributes:
        signal: Final combined signal
        attributions: List of contributing strategy signals
    """
    signal: Signal
    attributions: list[StrategyAttribution] = field(default_factory=list)


class StrategyManager:
    """Orchestrates multiple strategies and combines their signals.

    Supports various combination methods for aggregating signals from
    multiple trading strategies into a unified signal stream.

    Attributes:
        strategies: Dictionary mapping strategy names to instances
        weights: Dictionary mapping strategy names to weights
        method: Signal combination method
    """

    def __init__(
        self,
        strategies: Optional[Dict[str, BaseStrategy]] = None,
        weights: Optional[Dict[str, float]] = None,
        method: CombinationMethod = CombinationMethod.PRIORITY
    ):
        """Initialize strategy manager.

        Args:
            strategies: Dictionary of strategy name to strategy instance
            weights: Dictionary of strategy name to weight (default 1.0)
            method: How to combine signals from multiple strategies
        """
        self.strategies: Dict[str, BaseStrategy] = strategies or {}
        self.weights: Dict[str, float] = weights or {}
        self.method = method

        for name in self.strategies:
            if name not in self.weights:
                self.weights[name] = 1.0

    def add_strategy(
        self,
        name: str,
        strategy: BaseStrategy,
        weight: float = 1.0
    ) -> None:
        """Add a strategy to the manager.

        Args:
            name: Unique identifier for the strategy
            strategy: Strategy instance
            weight: Weight for weighted combination (default 1.0)
        """
        if name in self.strategies:
            raise ValueError(f"Strategy '{name}' already exists")
        self.strategies[name] = strategy
        self.weights[name] = weight

    def remove_strategy(self, name: str) -> None:
        """Remove a strategy from the manager.

        Args:
            name: Strategy identifier to remove
        """
        if name not in self.strategies:
            raise ValueError(f"Strategy '{name}' not found")
        del self.strategies[name]
        del self.weights[name]

    def get_warmup_period(self) -> int:
        """Return maximum warmup period across all strategies."""
        if not self.strategies:
            return 0
        return max(s.get_warmup_period() for s in self.strategies.values())

    def calculate_signals(
        self,
        df: pd.DataFrame,
        return_attributions: bool = False
    ) -> pd.Series | tuple[pd.Series, pd.DataFrame]:
        """Calculate combined signals from all strategies.

        Args:
            df: DataFrame with OHLCV data
            return_attributions: If True, also return attribution DataFrame

        Returns:
            Series of combined Signal values, optionally with attributions
        """
        if not self.strategies:
            raise ValueError("No strategies configured")

        strategy_signals: Dict[str, pd.Series] = {}
        for name, strategy in self.strategies.items():
            strategy_signals[name] = strategy.calculate_signals(df)

        combined = self._combine_signals(strategy_signals, df.index)

        if return_attributions:
            attr_df = pd.DataFrame(strategy_signals)
            attr_df.columns = [f"{name}_signal" for name in strategy_signals]
            return combined, attr_df

        return combined

    def _combine_signals(
        self,
        strategy_signals: Dict[str, pd.Series],
        index: pd.Index
    ) -> pd.Series:
        """Combine signals using configured method.

        Args:
            strategy_signals: Dictionary of strategy name to signal Series
            index: DatetimeIndex for result Series

        Returns:
            Combined signal Series
        """
        if self.method == CombinationMethod.OR:
            return self._combine_or(strategy_signals, index)
        elif self.method == CombinationMethod.AND:
            return self._combine_and(strategy_signals, index)
        elif self.method == CombinationMethod.PRIORITY:
            return self._combine_priority(strategy_signals, index)
        elif self.method == CombinationMethod.WEIGHTED:
            return self._combine_weighted(strategy_signals, index)
        else:
            raise ValueError(f"Unknown combination method: {self.method}")

    def _combine_or(
        self,
        strategy_signals: Dict[str, pd.Series],
        index: pd.Index
    ) -> pd.Series:
        """OR combination: any BUY -> BUY, any SELL -> SELL.

        Priority: SELL > BUY > HOLD when both present.
        """
        result = pd.Series(Signal.HOLD, index=index)

        for signals in strategy_signals.values():
            result[signals == Signal.BUY] = Signal.BUY

        for signals in strategy_signals.values():
            result[signals == Signal.SELL] = Signal.SELL

        return result

    def _combine_and(
        self,
        strategy_signals: Dict[str, pd.Series],
        index: pd.Index
    ) -> pd.Series:
        """AND combination: all must agree for non-HOLD signal."""
        result = pd.Series(Signal.HOLD, index=index)

        if not strategy_signals:
            return result

        signal_list = list(strategy_signals.values())

        all_buy = pd.Series(True, index=index)
        all_sell = pd.Series(True, index=index)

        for signals in signal_list:
            all_buy = all_buy & (signals == Signal.BUY)
            all_sell = all_sell & (signals == Signal.SELL)

        result[all_buy] = Signal.BUY
        result[all_sell] = Signal.SELL

        return result

    def _combine_priority(
        self,
        strategy_signals: Dict[str, pd.Series],
        index: pd.Index
    ) -> pd.Series:
        """Priority combination: SELL > BUY > HOLD.

        If any strategy says SELL, result is SELL.
        Otherwise if any says BUY, result is BUY.
        Otherwise HOLD.
        """
        result = pd.Series(Signal.HOLD, index=index)

        for signals in strategy_signals.values():
            result[signals == Signal.BUY] = Signal.BUY

        for signals in strategy_signals.values():
            result[signals == Signal.SELL] = Signal.SELL

        return result

    def _combine_weighted(
        self,
        strategy_signals: Dict[str, pd.Series],
        index: pd.Index
    ) -> pd.Series:
        """Weighted voting combination.

        BUY = +1, HOLD = 0, SELL = -1
        Weighted sum determines final signal.
        """
        result = pd.Series(Signal.HOLD, index=index)

        votes = pd.Series(0.0, index=index)
        total_weight = sum(self.weights.values())

        for name, signals in strategy_signals.items():
            weight = self.weights.get(name, 1.0)
            signal_values = signals.map({
                Signal.BUY: 1.0,
                Signal.HOLD: 0.0,
                Signal.SELL: -1.0
            })
            votes += signal_values * weight

        threshold = total_weight * 0.5

        result[votes >= threshold] = Signal.BUY
        result[votes <= -threshold] = Signal.SELL

        return result

    def get_signal_at_index(
        self,
        df: pd.DataFrame,
        idx: int
    ) -> CombinedSignal:
        """Get combined signal with attribution at specific index.

        Args:
            df: DataFrame with OHLCV data
            idx: Index position to get signal for

        Returns:
            CombinedSignal with attributions
        """
        attributions = []
        for name, strategy in self.strategies.items():
            signals = strategy.calculate_signals(df)
            signal = signals.iloc[idx]
            attributions.append(StrategyAttribution(
                strategy_name=name,
                signal=signal,
                weight=self.weights.get(name, 1.0)
            ))

        combined_signals = self.calculate_signals(df)
        final_signal = combined_signals.iloc[idx]

        return CombinedSignal(signal=final_signal, attributions=attributions)

    def __repr__(self) -> str:
        strategy_names = list(self.strategies.keys())
        return (
            f"StrategyManager(strategies={strategy_names}, "
            f"method={self.method.value})"
        )

"""Strategy framework for Backgrid backtesting engine.

This module provides the base strategy interface and concrete implementations
for various trading strategies including MA Crossover and RSI mean reversion.
"""

from .base import BaseStrategy, Signal
from .ma_strategy import MAStrategy
from .rsi_strategy import RSIStrategy
from .strategy_manager import StrategyManager, CombinationMethod

__all__ = [
    "BaseStrategy",
    "Signal",
    "MAStrategy",
    "RSIStrategy",
    "StrategyManager",
    "CombinationMethod",
]

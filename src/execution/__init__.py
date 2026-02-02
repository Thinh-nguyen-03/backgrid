"""Execution module for Backgrid backtesting engine.

This module provides transaction cost modeling and order execution simulation
for realistic backtesting of trading strategies.
"""

from .transaction_costs import TransactionCostModel, TransactionCost
from .order_simulator import OrderSimulator, Order, Fill, OrderSide

__all__ = [
    "TransactionCostModel",
    "TransactionCost",
    "OrderSimulator",
    "Order",
    "Fill",
    "OrderSide",
]

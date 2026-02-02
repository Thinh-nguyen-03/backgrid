"""Risk management module for Backgrid backtesting engine.

This module provides risk management components for portfolio backtesting:
- Market regime filtering (SPY 200-SMA bull/bear detection)
- Stop loss management (ATR-based stops with cooldown)
- Sector concentration limits
- Portfolio heat tracking (max risk exposure)

RapidTrader Configuration:
    RT_MARKET_FILTER_ENABLE=true
    RT_MARKET_FILTER_SMA=200
    RT_MARKET_FILTER_SYMBOL=SPY
    RT_MAX_EXPOSURE_PER_SECTOR=0.30
    RT_COOLDOWN_DAYS_ON_STOP=1
"""

from .market_regime import (
    MarketRegime,
    MarketRegimeFilter,
    RegimeState,
)

from .stop_loss import (
    StopLossManager,
    StopLossResult,
    StopType,
)

from .sector_limits import (
    SectorLimitManager,
    SectorExposure,
)

from .portfolio_heat import (
    PortfolioHeatTracker,
    HeatStatus,
)

__all__ = [
    "MarketRegime",
    "MarketRegimeFilter",
    "RegimeState",
    "StopLossManager",
    "StopLossResult",
    "StopType",
    "SectorLimitManager",
    "SectorExposure",
    "PortfolioHeatTracker",
    "HeatStatus",
]

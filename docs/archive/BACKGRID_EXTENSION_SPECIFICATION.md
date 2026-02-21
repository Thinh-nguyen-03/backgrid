# Backgrid Extension Specification for RapidTrader Backtesting

**Document Version:** 1.0
**Date:** 2026-01-31
**Author:** System Architecture Team
**Purpose:** Detailed technical specification for extending Backgrid to support RapidTrader multi-strategy backtesting

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Gap Analysis](#gap-analysis)
3. [Architecture Overview](#architecture-overview)
4. [Feature Implementation Specifications](#feature-implementation-specifications)
5. [Database Schema Extensions](#database-schema-extensions)
6. [API Endpoint Modifications](#api-endpoint-modifications)
7. [Performance Optimization Requirements](#performance-optimization-requirements)
8. [Testing Strategy](#testing-strategy)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Risk Assessment](#risk-assessment)

---

## EXECUTIVE SUMMARY

This document specifies the technical requirements for extending the Backgrid backtesting system to support RapidTrader's multi-strategy, multi-asset portfolio backtesting needs.

### Current State (Backgrid v1.0)

- Single strategy (MA crossover only)
- Single symbol per backtest
- Synchronous execution (one job at a time)
- In-memory result storage
- No transaction costs
- Fixed position sizing
- Yahoo Finance data source only

### Target State (Backgrid v2.0 - RapidTrader Edition)

- Multi-strategy support (SMA, RSI, combined signals)
- Portfolio-level backtesting (500+ symbols)
- Parallel execution with Celery workers
- PostgreSQL integration for market data
- Transaction cost modeling (commission + slippage)
- ATR-based position sizing
- Market regime filtering
- Risk management constraints
- Comprehensive performance analytics

### Development Effort Estimate

| Component | Complexity | Estimated Hours | Priority |
|-----------|------------|-----------------|----------|
| RSI Strategy Implementation | Medium | 16-24 | P0 (Critical) |
| Multi-Strategy Framework | High | 32-40 | P0 (Critical) |
| PostgreSQL Data Integration | Medium | 16-24 | P0 (Critical) |
| ATR Position Sizing | Medium | 16-20 | P0 (Critical) |
| Transaction Cost Model | Medium | 20-24 | P0 (Critical) |
| Market Regime Filters | Medium | 12-16 | P1 (High) |
| Portfolio Aggregation | High | 24-32 | P1 (High) |
| Multi-Symbol Orchestration | High | 32-40 | P1 (High) |
| Risk Management Engine | High | 24-32 | P1 (High) |
| Stop Loss & Cooldown | Medium | 16-20 | P2 (Medium) |
| Performance Analytics | Medium | 16-20 | P2 (Medium) |
| Testing & Documentation | High | 40-48 | P0 (Critical) |
| **TOTAL** | | **264-340 hours** | **(5-7 weeks)** |

---

## GAP ANALYSIS

### Feature Comparison Matrix

| Feature | RapidTrader Requires | Backgrid Provides | Gap | Implementation Complexity |
|---------|---------------------|-------------------|-----|---------------------------|
| **Strategies** |
| SMA Crossover | 20/100 configurable | 50/200 hardcoded | Parameterization needed | LOW |
| RSI Mean Reversion | Buy < 30, Sell > 55 | Not implemented | Full implementation | MEDIUM |
| Multi-Strategy Combination | AND/OR logic, priority rules | Single strategy only | Architecture redesign | HIGH |
| **Data** |
| Data Source | PostgreSQL (bars_daily) | Yahoo Finance only | Custom data loader | MEDIUM |
| Symbol Universe | 500+ symbols | 1 symbol per job | Batch orchestration | HIGH |
| Market Regime Data | SPY 200-SMA filter | Not supported | Regime detection module | MEDIUM |
| **Position Management** |
| Position Sizing | ATR-based dynamic | Fixed capital | ATR calculation + sizing logic | MEDIUM |
| Max Positions | 15-20 limit | No limit | Portfolio constraint engine | MEDIUM |
| Capital Management | Reserve capital per position | No tracking | Capital allocation tracker | MEDIUM |
| **Risk Management** |
| Transaction Costs | Commission + slippage | Not modeled | Cost model implementation | MEDIUM |
| Stop Losses | ATR-based stops | Not supported | Stop tracking + execution | MEDIUM |
| Cooldown Periods | 5 days after stop | Not supported | Cooldown state management | LOW |
| Portfolio Heat | Max 6% at-risk capital | Not supported | Heat calculator | MEDIUM |
| Correlation Check | Max 0.75 correlation | Not supported | Correlation matrix analysis | HIGH |
| Sector Limits | Max 25% per sector | Not supported | Sector exposure tracker | MEDIUM |
| **Execution** |
| Order Types | Market orders (next-day open) | Immediate fills | Order queue + fill simulation | MEDIUM |
| Execution Timing | End-of-day signals, next-day fill | Same-bar fill | Bar timing logic | LOW |
| Partial Fills | Not applicable (small size) | Not supported | N/A | N/A |
| **Performance** |
| Metrics | Sharpe, Max DD, Win Rate, Profit Factor | Sharpe, Max DD, Total Return | Extended metrics | LOW |
| Trade-Level Analytics | Entry/exit prices, hold period, P&L | Not available | Trade ledger | MEDIUM |
| Drawdown Analysis | Recovery time, underwater periods | Basic max DD only | Drawdown analytics | MEDIUM |
| **Infrastructure** |
| Parallel Execution | Required for 500 symbols | Synchronous only | Celery worker implementation | HIGH |
| Result Persistence | PostgreSQL storage | In-memory (lost on restart) | Database persistence | MEDIUM |
| API Endpoints | Batch job submission, status tracking | Single job API | Batch API endpoints | MEDIUM |

---

## ARCHITECTURE OVERVIEW

### Current Backgrid Architecture (Phase 1)

```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP POST /api/v1/jobs
     ▼
┌─────────────────┐
│  FastAPI App    │
│  (src/api.py)   │
└────┬────────────┘
     │ Direct call
     ▼
┌─────────────────────────┐
│  Backtest Engine        │
│  (src/backtest.py)      │
│  ┌───────────────────┐  │
│  │ calculate_signals │  │
│  │ calculate_returns │  │
│  │ calculate_metrics │  │
│  └───────────────────┘  │
└────┬────────────────────┘
     │ fetch_ohlcv()
     ▼
┌─────────────────┐
│ Yahoo Finance   │
│  (yfinance)     │
└─────────────────┘

Results: In-memory dictionary
```

### Target Architecture (Phase 2 - RapidTrader Edition)

```
┌─────────┐
│ Client  │
└────┬────┘
     │ HTTP POST /api/v1/backtest/portfolio
     ▼
┌──────────────────────────────────────────┐
│  FastAPI App (Extended API)              │
│  ┌────────────────────────────────────┐  │
│  │ /api/v1/backtest/portfolio         │  │
│  │ /api/v1/backtest/multi-strategy    │  │
│  │ /api/v1/backtest/batch             │  │
│  └────────────────────────────────────┘  │
└────┬─────────────────────────────────────┘
     │ Enqueue jobs
     ▼
┌──────────────────┐
│  Redis Queue     │
│  (Celery Broker) │
└────┬─────────────┘
     │ Task distribution
     ▼
┌─────────────────────────────────────────────────┐
│  Celery Workers (Parallel Execution)            │
│  ┌───────────────────────────────────────────┐  │
│  │ Worker 1: Symbols 1-100                   │  │
│  │ Worker 2: Symbols 101-200                 │  │
│  │ Worker 3: Symbols 201-300                 │  │
│  │ Worker 4: Symbols 301-400                 │  │
│  │ Worker 5: Symbols 401-500                 │  │
│  └───────────────────────────────────────────┘  │
└────┬────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────────────────┐
│  Enhanced Backtest Engine                        │
│  ┌────────────────────────────────────────────┐  │
│  │ Strategy Manager                           │  │
│  │  ├─ SMA Strategy                          │  │
│  │  ├─ RSI Strategy                          │  │
│  │  └─ Combined Strategy                     │  │
│  ├────────────────────────────────────────────┤  │
│  │ Position Manager                           │  │
│  │  ├─ ATR Position Sizing                   │  │
│  │  ├─ Capital Allocation                    │  │
│  │  └─ Position Tracking                     │  │
│  ├────────────────────────────────────────────┤  │
│  │ Risk Manager                               │  │
│  │  ├─ Transaction Costs                     │  │
│  │  ├─ Stop Losses                           │  │
│  │  ├─ Portfolio Heat                        │  │
│  │  ├─ Correlation Check                     │  │
│  │  └─ Sector Limits                         │  │
│  ├────────────────────────────────────────────┤  │
│  │ Market Regime Filter                       │  │
│  │  └─ SPY 200-SMA Bull/Bear Detection       │  │
│  ├────────────────────────────────────────────┤  │
│  │ Performance Analytics                      │  │
│  │  ├─ Trade Ledger                          │  │
│  │  ├─ Metrics Calculator                    │  │
│  │  └─ Drawdown Analyzer                     │  │
│  └────────────────────────────────────────────┘  │
└────┬─────────────────────────────────────────────┘
     │
     ▼
┌──────────────────────────────────────┐
│  PostgreSQL Database                 │
│  ┌────────────────────────────────┐  │
│  │ Market Data (RapidTrader DB)   │  │
│  │  ├─ bars_daily                 │  │
│  │  ├─ symbols                    │  │
│  │  └─ market_state               │  │
│  ├────────────────────────────────┤  │
│  │ Backtest Results (Backgrid DB) │  │
│  │  ├─ jobs                       │  │
│  │  ├─ portfolio_results          │  │
│  │  ├─ position_history           │  │
│  │  ├─ trade_ledger               │  │
│  │  └─ performance_metrics        │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## FEATURE IMPLEMENTATION SPECIFICATIONS

### 1. RSI STRATEGY IMPLEMENTATION

**Module:** `src/strategies/rsi_strategy.py`

**Requirements:**

- Calculate RSI indicator with configurable period (default: 14)
- Generate buy signals when RSI < oversold threshold (default: 30)
- Generate sell signals when RSI > overbought threshold (default: 55)
- Support confirmation window (default: 3 days)
- Minimum confirmation count (default: 2 days in window)

**Technical Specification:**

```python
# src/strategies/rsi_strategy.py

from typing import Dict, Any
import pandas as pd
import numpy as np

def calculate_rsi(
    df: pd.DataFrame,
    period: int = 14,
    price_col: str = 'Close'
) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    Formula:
        RSI = 100 - (100 / (1 + RS))
        where RS = Average Gain / Average Loss

    Args:
        df: DataFrame with OHLCV data
        period: RSI lookback period (default: 14)
        price_col: Column name for price (default: 'Close')

    Returns:
        Series with RSI values (0-100)

    Raises:
        ValueError: If period < 2 or price_col not in df
    """
    if period < 2:
        raise ValueError(f"RSI period must be >= 2, got {period}")

    if price_col not in df.columns:
        raise ValueError(f"Column '{price_col}' not found in DataFrame")

    # Calculate price changes
    delta = df[price_col].diff()

    # Separate gains and losses
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Calculate exponential moving average of gains and losses
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def calculate_rsi_signals(
    df: pd.DataFrame,
    rsi_period: int = 14,
    oversold_threshold: int = 30,
    overbought_threshold: int = 55,
    confirmation_window: int = 3,
    min_confirmation_count: int = 2
) -> pd.Series:
    """
    Generate trading signals based on RSI mean reversion strategy.

    Strategy Logic:
        BUY: RSI crosses below oversold threshold and stays there for
             min_confirmation_count days within confirmation_window
        SELL: RSI crosses above overbought threshold and stays there for
              min_confirmation_count days within confirmation_window
        HOLD: Otherwise

    Args:
        df: DataFrame with OHLCV data
        rsi_period: RSI calculation period
        oversold_threshold: RSI level for buy signals (default: 30)
        overbought_threshold: RSI level for sell signals (default: 55)
        confirmation_window: Days to look back for confirmation (default: 3)
        min_confirmation_count: Minimum confirmations needed (default: 2)

    Returns:
        Series with signals: 'buy', 'sell', 'hold'
    """
    # Validate parameters
    if oversold_threshold >= overbought_threshold:
        raise ValueError(
            f"oversold_threshold ({oversold_threshold}) must be < "
            f"overbought_threshold ({overbought_threshold})"
        )

    if not (0 <= oversold_threshold <= 100):
        raise ValueError(f"oversold_threshold must be 0-100, got {oversold_threshold}")

    if not (0 <= overbought_threshold <= 100):
        raise ValueError(f"overbought_threshold must be 0-100, got {overbought_threshold}")

    # Calculate RSI
    rsi = calculate_rsi(df, period=rsi_period)

    # Initialize signals
    signals = pd.Series('hold', index=df.index)

    # Generate buy signals (oversold condition)
    oversold = rsi < oversold_threshold
    oversold_count = oversold.rolling(window=confirmation_window).sum()
    buy_condition = oversold_count >= min_confirmation_count

    # Generate sell signals (overbought condition)
    overbought = rsi > overbought_threshold
    overbought_count = overbought.rolling(window=confirmation_window).sum()
    sell_condition = overbought_count >= min_confirmation_count

    # Apply signals
    signals[buy_condition] = 'buy'
    signals[sell_condition] = 'sell'

    return signals


# Example usage and test
if __name__ == "__main__":
    # Test data
    test_df = pd.DataFrame({
        'Close': [100, 102, 98, 95, 93, 92, 94, 96, 99, 101, 103, 105, 107, 106, 104]
    })

    rsi = calculate_rsi(test_df, period=14)
    signals = calculate_rsi_signals(test_df)

    print("RSI Values:")
    print(rsi.tail())
    print("\nSignals:")
    print(signals.tail())
```

**Unit Tests Required:**

```python
# tests/test_rsi_strategy.py

import pytest
import pandas as pd
import numpy as np
from src.strategies.rsi_strategy import calculate_rsi, calculate_rsi_signals


class TestRSICalculation:
    """Test RSI calculation accuracy"""

    def test_rsi_range(self):
        """RSI should always be between 0 and 100"""
        df = pd.DataFrame({'Close': np.random.randn(100).cumsum() + 100})
        rsi = calculate_rsi(df, period=14)

        assert rsi.min() >= 0
        assert rsi.max() <= 100

    def test_rsi_constant_price(self):
        """RSI should be 50 for constant prices (no change)"""
        df = pd.DataFrame({'Close': [100] * 50})
        rsi = calculate_rsi(df, period=14)

        # RSI will be NaN for first period+1 values, then should stabilize at 50
        assert np.isclose(rsi.iloc[-1], 50.0, atol=0.1)

    def test_rsi_uptrend(self):
        """RSI should be high (>50) in strong uptrend"""
        df = pd.DataFrame({'Close': list(range(100, 150))})
        rsi = calculate_rsi(df, period=14)

        assert rsi.iloc[-1] > 70  # Should be overbought

    def test_rsi_downtrend(self):
        """RSI should be low (<50) in strong downtrend"""
        df = pd.DataFrame({'Close': list(range(150, 100, -1))})
        rsi = calculate_rsi(df, period=14)

        assert rsi.iloc[-1] < 30  # Should be oversold

    def test_rsi_invalid_period(self):
        """Should raise ValueError for invalid period"""
        df = pd.DataFrame({'Close': [100, 101, 102]})

        with pytest.raises(ValueError):
            calculate_rsi(df, period=1)

    def test_rsi_missing_column(self):
        """Should raise ValueError if price column missing"""
        df = pd.DataFrame({'Open': [100, 101, 102]})

        with pytest.raises(ValueError):
            calculate_rsi(df, price_col='Close')


class TestRSISignals:
    """Test RSI signal generation"""

    def test_buy_signal_on_oversold(self):
        """Should generate buy signal when RSI < 30"""
        # Create data that will produce low RSI
        prices = [100] + [99 - i*0.5 for i in range(20)]
        df = pd.DataFrame({'Close': prices})

        signals = calculate_rsi_signals(
            df,
            rsi_period=14,
            oversold_threshold=30,
            confirmation_window=3,
            min_confirmation_count=2
        )

        # Should have at least one buy signal
        assert 'buy' in signals.values

    def test_sell_signal_on_overbought(self):
        """Should generate sell signal when RSI > 55"""
        # Create data that will produce high RSI
        prices = [100] + [100 + i*0.5 for i in range(20)]
        df = pd.DataFrame({'Close': prices})

        signals = calculate_rsi_signals(
            df,
            rsi_period=14,
            overbought_threshold=55,
            confirmation_window=3,
            min_confirmation_count=2
        )

        # Should have at least one sell signal
        assert 'sell' in signals.values

    def test_confirmation_window(self):
        """Should require multiple confirmations within window"""
        # Single spike shouldn't trigger signal with min_confirmation_count=2
        prices = [100] * 10 + [95] + [100] * 10
        df = pd.DataFrame({'Close': prices})

        signals = calculate_rsi_signals(
            df,
            confirmation_window=3,
            min_confirmation_count=2
        )

        # Should mostly be 'hold' due to insufficient confirmation
        assert signals.value_counts().get('hold', 0) > signals.value_counts().get('buy', 0)

    def test_invalid_thresholds(self):
        """Should raise ValueError for invalid thresholds"""
        df = pd.DataFrame({'Close': [100, 101, 102]})

        with pytest.raises(ValueError):
            calculate_rsi_signals(df, oversold_threshold=60, overbought_threshold=50)

        with pytest.raises(ValueError):
            calculate_rsi_signals(df, oversold_threshold=-10)

        with pytest.raises(ValueError):
            calculate_rsi_signals(df, overbought_threshold=110)
```

**Integration Points:**

- Must integrate with strategy manager (see section 2)
- Must output signals in standardized format: `{'buy', 'sell', 'hold'}`
- Must handle missing data gracefully (NaN values at start)
- Must be performant for 500+ symbols

**Acceptance Criteria:**

- [ ] RSI calculation matches industry standard (verify against TA-Lib or pandas-ta)
- [ ] All unit tests pass (target: 100% code coverage)
- [ ] Handles edge cases (constant prices, missing data, invalid params)
- [ ] Performance: < 10ms for 252 trading days of data
- [ ] Documentation includes mathematical formula and strategy description

---

### 2. MULTI-STRATEGY FRAMEWORK

**Module:** `src/strategies/strategy_manager.py`

**Requirements:**

- Support multiple concurrent strategies (SMA, RSI, custom)
- Combine signals using configurable logic (AND, OR, priority-based)
- Allow per-strategy parameter configuration
- Track signal attribution (which strategy generated which signal)
- Support strategy weighting (if using voting system)

**Technical Specification:**

```python
# src/strategies/strategy_manager.py

from typing import Dict, List, Any, Callable, Optional
from enum import Enum
import pandas as pd
from dataclasses import dataclass

from src.strategies.ma_strategy import calculate_ma_crossover_signals
from src.strategies.rsi_strategy import calculate_rsi_signals


class SignalCombination(Enum):
    """Signal combination methods"""
    OR = "or"          # Buy if ANY strategy says buy
    AND = "and"        # Buy only if ALL strategies say buy
    PRIORITY = "priority"  # Use priority order (e.g., SELL > BUY > HOLD)
    WEIGHTED = "weighted"  # Weighted voting based on strategy scores


class Signal(Enum):
    """Standardized signal types"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class StrategyConfig:
    """Configuration for a single strategy"""
    name: str
    strategy_type: str  # 'sma', 'rsi', 'custom'
    params: Dict[str, Any]
    enabled: bool = True
    weight: float = 1.0  # For weighted combination


@dataclass
class SignalResult:
    """Result from signal generation"""
    signal: Signal
    strategy: str
    strength: float = 1.0  # Signal confidence/strength
    metadata: Optional[Dict[str, Any]] = None


class StrategyManager:
    """
    Manages multiple trading strategies and combines their signals.

    Supports:
        - Multiple concurrent strategies (SMA, RSI, custom)
        - Configurable signal combination logic
        - Strategy attribution tracking
        - Per-strategy parameters
    """

    def __init__(
        self,
        strategies: List[StrategyConfig],
        combination_method: SignalCombination = SignalCombination.PRIORITY
    ):
        """
        Initialize strategy manager.

        Args:
            strategies: List of strategy configurations
            combination_method: How to combine signals from multiple strategies
        """
        self.strategies = strategies
        self.combination_method = combination_method

        # Strategy registry
        self._strategy_functions = {
            'sma': self._run_sma_strategy,
            'rsi': self._run_rsi_strategy,
        }

    def generate_signals(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Generate trading signals from all enabled strategies.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            DataFrame with columns:
                - signal: Final combined signal ('buy', 'sell', 'hold')
                - strategy: Attribution (which strategy/combination)
                - strength: Signal strength (0-1)
                - individual signals from each strategy
        """
        # Generate signals from each strategy
        strategy_signals = {}

        for strategy in self.strategies:
            if not strategy.enabled:
                continue

            if strategy.strategy_type not in self._strategy_functions:
                raise ValueError(f"Unknown strategy type: {strategy.strategy_type}")

            # Run strategy
            signals = self._strategy_functions[strategy.strategy_type](df, strategy.params)
            strategy_signals[strategy.name] = signals

        # Combine signals
        combined_signals = self._combine_signals(df, strategy_signals)

        # Create result DataFrame
        result = pd.DataFrame(index=df.index)
        result['signal'] = combined_signals['signal']
        result['strategy'] = combined_signals['strategy']
        result['strength'] = combined_signals['strength']

        # Add individual strategy signals for transparency
        for name, signals in strategy_signals.items():
            result[f'{name}_signal'] = signals

        return result

    def _run_sma_strategy(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any]
    ) -> pd.Series:
        """Run SMA crossover strategy"""
        fast_period = params.get('fast_period', 20)
        slow_period = params.get('slow_period', 100)

        # Calculate SMAs
        fast_sma = df['Close'].rolling(window=fast_period).mean()
        slow_sma = df['Close'].rolling(window=slow_period).mean()

        # Generate signals
        signals = pd.Series('hold', index=df.index)
        signals[fast_sma > slow_sma] = 'buy'
        signals[fast_sma < slow_sma] = 'sell'

        return signals

    def _run_rsi_strategy(
        self,
        df: pd.DataFrame,
        params: Dict[str, Any]
    ) -> pd.Series:
        """Run RSI mean reversion strategy"""
        from src.strategies.rsi_strategy import calculate_rsi_signals

        return calculate_rsi_signals(
            df,
            rsi_period=params.get('rsi_period', 14),
            oversold_threshold=params.get('oversold_threshold', 30),
            overbought_threshold=params.get('overbought_threshold', 55),
            confirmation_window=params.get('confirmation_window', 3),
            min_confirmation_count=params.get('min_confirmation_count', 2)
        )

    def _combine_signals(
        self,
        df: pd.DataFrame,
        strategy_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        Combine signals from multiple strategies.

        Args:
            df: Original DataFrame
            strategy_signals: Dict mapping strategy name to signal Series

        Returns:
            Dict with 'signal', 'strategy', 'strength' Series
        """
        if self.combination_method == SignalCombination.OR:
            return self._combine_or(df, strategy_signals)
        elif self.combination_method == SignalCombination.AND:
            return self._combine_and(df, strategy_signals)
        elif self.combination_method == SignalCombination.PRIORITY:
            return self._combine_priority(df, strategy_signals)
        elif self.combination_method == SignalCombination.WEIGHTED:
            return self._combine_weighted(df, strategy_signals)
        else:
            raise ValueError(f"Unknown combination method: {self.combination_method}")

    def _combine_or(
        self,
        df: pd.DataFrame,
        strategy_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        OR logic: Buy if ANY strategy says buy, Sell if ANY says sell.

        Priority: SELL > BUY > HOLD
        """
        result = pd.Series('hold', index=df.index)
        attribution = pd.Series('none', index=df.index)
        strength = pd.Series(0.0, index=df.index)

        for idx in df.index:
            signals_at_idx = [sig[idx] for sig in strategy_signals.values()]

            # Priority: SELL > BUY > HOLD
            if 'sell' in signals_at_idx:
                result[idx] = 'sell'
                # Find which strategy said sell
                for name, sig in strategy_signals.items():
                    if sig[idx] == 'sell':
                        attribution[idx] = name
                        break
                strength[idx] = signals_at_idx.count('sell') / len(signals_at_idx)

            elif 'buy' in signals_at_idx:
                result[idx] = 'buy'
                # Find which strategy said buy
                for name, sig in strategy_signals.items():
                    if sig[idx] == 'buy':
                        attribution[idx] = name
                        break
                strength[idx] = signals_at_idx.count('buy') / len(signals_at_idx)

            else:
                result[idx] = 'hold'
                attribution[idx] = 'all'
                strength[idx] = 1.0

        return {
            'signal': result,
            'strategy': attribution,
            'strength': strength
        }

    def _combine_and(
        self,
        df: pd.DataFrame,
        strategy_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        AND logic: Buy only if ALL strategies agree on buy.
        """
        result = pd.Series('hold', index=df.index)
        attribution = pd.Series('none', index=df.index)
        strength = pd.Series(0.0, index=df.index)

        num_strategies = len(strategy_signals)

        for idx in df.index:
            signals_at_idx = [sig[idx] for sig in strategy_signals.values()]

            # All must agree on buy
            if signals_at_idx.count('buy') == num_strategies:
                result[idx] = 'buy'
                attribution[idx] = 'all_agree'
                strength[idx] = 1.0

            # All must agree on sell
            elif signals_at_idx.count('sell') == num_strategies:
                result[idx] = 'sell'
                attribution[idx] = 'all_agree'
                strength[idx] = 1.0

            else:
                result[idx] = 'hold'
                attribution[idx] = 'no_consensus'
                strength[idx] = 0.0

        return {
            'signal': result,
            'strategy': attribution,
            'strength': strength
        }

    def _combine_priority(
        self,
        df: pd.DataFrame,
        strategy_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        Priority-based: Use first strategy in list that has non-hold signal.

        RapidTrader default: SELL > BUY > HOLD
        """
        result = pd.Series('hold', index=df.index)
        attribution = pd.Series('none', index=df.index)
        strength = pd.Series(0.0, index=df.index)

        for idx in df.index:
            # First check all strategies for SELL (highest priority)
            for strategy in self.strategies:
                if strategy.name in strategy_signals:
                    sig = strategy_signals[strategy.name][idx]
                    if sig == 'sell':
                        result[idx] = 'sell'
                        attribution[idx] = strategy.name
                        strength[idx] = 1.0
                        break

            # If no sell found, check for BUY
            if result[idx] == 'hold':
                for strategy in self.strategies:
                    if strategy.name in strategy_signals:
                        sig = strategy_signals[strategy.name][idx]
                        if sig == 'buy':
                            result[idx] = 'buy'
                            attribution[idx] = strategy.name
                            strength[idx] = 1.0
                            break

            # Otherwise stays 'hold'
            if result[idx] == 'hold':
                attribution[idx] = 'all_hold'
                strength[idx] = 0.0

        return {
            'signal': result,
            'strategy': attribution,
            'strength': strength
        }

    def _combine_weighted(
        self,
        df: pd.DataFrame,
        strategy_signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        Weighted voting: Each strategy votes with its weight.

        Signal with highest total weight wins.
        """
        result = pd.Series('hold', index=df.index)
        attribution = pd.Series('weighted', index=df.index)
        strength = pd.Series(0.0, index=df.index)

        # Map strategy names to weights
        weights = {s.name: s.weight for s in self.strategies}

        for idx in df.index:
            buy_weight = 0.0
            sell_weight = 0.0
            hold_weight = 0.0

            for name, sig in strategy_signals.items():
                weight = weights.get(name, 1.0)

                if sig[idx] == 'buy':
                    buy_weight += weight
                elif sig[idx] == 'sell':
                    sell_weight += weight
                else:
                    hold_weight += weight

            # Determine winner
            total_weight = buy_weight + sell_weight + hold_weight

            if sell_weight > buy_weight and sell_weight > hold_weight:
                result[idx] = 'sell'
                strength[idx] = sell_weight / total_weight if total_weight > 0 else 0
            elif buy_weight > hold_weight:
                result[idx] = 'buy'
                strength[idx] = buy_weight / total_weight if total_weight > 0 else 0
            else:
                result[idx] = 'hold'
                strength[idx] = hold_weight / total_weight if total_weight > 0 else 0

        return {
            'signal': result,
            'strategy': attribution,
            'strength': strength
        }

    def register_custom_strategy(
        self,
        strategy_type: str,
        strategy_function: Callable
    ):
        """
        Register a custom strategy function.

        Args:
            strategy_type: Unique identifier for strategy
            strategy_function: Callable that takes (df, params) and returns signals
        """
        self._strategy_functions[strategy_type] = strategy_function


# Example usage
if __name__ == "__main__":
    # Configure strategies
    strategies = [
        StrategyConfig(
            name="sma_20_100",
            strategy_type="sma",
            params={"fast_period": 20, "slow_period": 100},
            weight=1.0
        ),
        StrategyConfig(
            name="rsi_mean_reversion",
            strategy_type="rsi",
            params={
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 55
            },
            weight=1.0
        )
    ]

    # Create manager
    manager = StrategyManager(
        strategies=strategies,
        combination_method=SignalCombination.PRIORITY
    )

    # Test with sample data
    test_df = pd.DataFrame({
        'Close': [100 + i for i in range(200)]
    })

    signals = manager.generate_signals(test_df)
    print(signals.tail(10))
```

**Unit Tests Required:**

```python
# tests/test_strategy_manager.py

import pytest
import pandas as pd
from src.strategies.strategy_manager import (
    StrategyManager, StrategyConfig, SignalCombination
)


class TestStrategyManager:

    def test_or_combination(self):
        """OR: Buy if ANY strategy says buy"""
        strategies = [
            StrategyConfig("sma", "sma", {"fast_period": 20, "slow_period": 100}),
            StrategyConfig("rsi", "rsi", {"oversold_threshold": 30})
        ]

        manager = StrategyManager(strategies, SignalCombination.OR)

        # Test data where SMA says buy, RSI says hold
        df = pd.DataFrame({'Close': list(range(100, 200))})
        signals = manager.generate_signals(df)

        # Should have 'buy' signals where SMA crosses
        assert 'buy' in signals['signal'].values

    def test_and_combination(self):
        """AND: Buy only if ALL strategies agree"""
        strategies = [
            StrategyConfig("sma", "sma", {"fast_period": 20, "slow_period": 100}),
            StrategyConfig("rsi", "rsi", {"oversold_threshold": 30})
        ]

        manager = StrategyManager(strategies, SignalCombination.AND)

        df = pd.DataFrame({'Close': list(range(100, 200))})
        signals = manager.generate_signals(df)

        # Most signals should be 'hold' due to strict requirement
        assert signals['signal'].value_counts().get('hold', 0) > 0

    def test_priority_combination(self):
        """PRIORITY: SELL > BUY > HOLD"""
        strategies = [
            StrategyConfig("sma", "sma", {"fast_period": 20, "slow_period": 100}),
        ]

        manager = StrategyManager(strategies, SignalCombination.PRIORITY)

        df = pd.DataFrame({'Close': list(range(200, 100, -1))})  # Downtrend
        signals = manager.generate_signals(df)

        # Should have sell signals in downtrend
        assert 'sell' in signals['signal'].values

    def test_strategy_attribution(self):
        """Should track which strategy generated signal"""
        strategies = [
            StrategyConfig("sma", "sma", {"fast_period": 20, "slow_period": 100}),
        ]

        manager = StrategyManager(strategies, SignalCombination.OR)

        df = pd.DataFrame({'Close': list(range(100, 200))})
        signals = manager.generate_signals(df)

        # Should have strategy attribution
        assert 'strategy' in signals.columns
        assert 'sma' in signals['strategy'].values or 'all' in signals['strategy'].values

    def test_custom_strategy_registration(self):
        """Should allow custom strategy registration"""
        def custom_strategy(df, params):
            # Always return buy
            return pd.Series('buy', index=df.index)

        strategies = [
            StrategyConfig("custom", "custom", {})
        ]

        manager = StrategyManager(strategies)
        manager.register_custom_strategy("custom", custom_strategy)

        df = pd.DataFrame({'Close': [100, 101, 102]})
        signals = manager.generate_signals(df)

        # All signals should be 'buy'
        assert all(signals['signal'] == 'buy')
```

**Acceptance Criteria:**

- [ ] Supports at least 3 combination methods (OR, AND, PRIORITY)
- [ ] Strategy attribution correctly tracks signal source
- [ ] All combination methods tested with 100% coverage
- [ ] Can add custom strategies via registration
- [ ] Performance: < 50ms for 2 strategies × 252 bars
- [ ] Documentation includes combination logic flowcharts

---

### 3. POSTGRESQL DATA INTEGRATION

**Module:** `src/data/postgres_loader.py`

**Requirements:**

- Connect to RapidTrader PostgreSQL database
- Load historical OHLCV data from `bars_daily` table
- Load symbol metadata from `symbols` table
- Load market regime data from `market_state` table
- Support date range queries
- Handle multiple symbols efficiently (batch loading)
- Cache data to avoid repeated queries

**Technical Specification:**

```python
# src/data/postgres_loader.py

from typing import List, Optional, Dict, Tuple
from datetime import date, datetime
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)


class PostgresDataLoader:
    """
    Load market data from RapidTrader PostgreSQL database.

    Connects to PostgreSQL and loads:
        - OHLCV bars from bars_daily table
        - Symbol metadata from symbols table
        - Market regime data from market_state table

    Features:
        - Connection pooling for performance
        - Batch loading for multiple symbols
        - Data caching to reduce queries
        - Comprehensive error handling
    """

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 5,
        max_overflow: int = 10,
        enable_cache: bool = True
    ):
        """
        Initialize PostgreSQL data loader.

        Args:
            connection_string: PostgreSQL connection string
                Example: "postgresql://user:pass@localhost:5432/rapidtrader"
            pool_size: Connection pool size
            max_overflow: Max overflow connections
            enable_cache: Whether to cache loaded data
        """
        self.connection_string = connection_string
        self.enable_cache = enable_cache

        # Create engine with connection pooling
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True  # Verify connections before use
        )

        # Cache
        self._bar_cache: Dict[Tuple[str, date, date], pd.DataFrame] = {}
        self._symbol_cache: Dict[str, Dict] = {}
        self._market_state_cache: Dict[date, Dict] = {}

        logger.info(f"PostgreSQL data loader initialized: {connection_string}")

    def fetch_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a single symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start_date: Start date for data
            end_date: End date (default: today)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index: Date

        Raises:
            ValueError: If symbol not found or no data available
        """
        if end_date is None:
            end_date = date.today()

        # Check cache
        cache_key = (symbol, start_date, end_date)
        if self.enable_cache and cache_key in self._bar_cache:
            logger.debug(f"Cache hit: {symbol} {start_date} to {end_date}")
            return self._bar_cache[cache_key].copy()

        # Query database
        query = text("""
            SELECT
                d as date,
                open,
                high,
                low,
                close,
                volume
            FROM bars_daily
            WHERE symbol = :symbol
              AND d >= :start_date
              AND d <= :end_date
            ORDER BY d ASC
        """)

        try:
            with self.engine.connect() as conn:
                df = pd.read_sql_query(
                    query,
                    conn,
                    params={
                        'symbol': symbol,
                        'start_date': start_date,
                        'end_date': end_date
                    },
                    index_col='date',
                    parse_dates=['date']
                )

            if df.empty:
                raise ValueError(
                    f"No data found for {symbol} from {start_date} to {end_date}"
                )

            # Rename columns to match expected format
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

            # Cache result
            if self.enable_cache:
                self._bar_cache[cache_key] = df.copy()

            logger.info(f"Loaded {len(df)} bars for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            raise

    def fetch_ohlcv_batch(
        self,
        symbols: List[str],
        start_date: date,
        end_date: Optional[date] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple symbols efficiently.

        Uses batch query to reduce database round-trips.

        Args:
            symbols: List of stock symbols
            start_date: Start date for data
            end_date: End date (default: today)

        Returns:
            Dict mapping symbol to DataFrame
            Symbols with no data are excluded
        """
        if end_date is None:
            end_date = date.today()

        # Check which symbols need to be fetched
        symbols_to_fetch = []
        result = {}

        for symbol in symbols:
            cache_key = (symbol, start_date, end_date)
            if self.enable_cache and cache_key in self._bar_cache:
                result[symbol] = self._bar_cache[cache_key].copy()
            else:
                symbols_to_fetch.append(symbol)

        if not symbols_to_fetch:
            logger.debug(f"All {len(symbols)} symbols served from cache")
            return result

        # Batch query
        query = text("""
            SELECT
                symbol,
                d as date,
                open,
                high,
                low,
                close,
                volume
            FROM bars_daily
            WHERE symbol = ANY(:symbols)
              AND d >= :start_date
              AND d <= :end_date
            ORDER BY symbol, d ASC
        """)

        try:
            with self.engine.connect() as conn:
                df_all = pd.read_sql_query(
                    query,
                    conn,
                    params={
                        'symbols': symbols_to_fetch,
                        'start_date': start_date,
                        'end_date': end_date
                    },
                    parse_dates=['date']
                )

            # Split by symbol
            for symbol in symbols_to_fetch:
                df_symbol = df_all[df_all['symbol'] == symbol].copy()

                if not df_symbol.empty:
                    df_symbol = df_symbol.drop('symbol', axis=1)
                    df_symbol = df_symbol.set_index('date')
                    df_symbol.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

                    result[symbol] = df_symbol

                    # Cache
                    if self.enable_cache:
                        cache_key = (symbol, start_date, end_date)
                        self._bar_cache[cache_key] = df_symbol.copy()
                else:
                    logger.warning(f"No data for {symbol}")

            logger.info(f"Batch loaded {len(result)} symbols")
            return result

        except Exception as e:
            logger.error(f"Error in batch fetch: {e}")
            raise

    def fetch_symbol_metadata(self, symbol: str) -> Dict:
        """
        Fetch symbol metadata (sector, industry, etc.).

        Args:
            symbol: Stock symbol

        Returns:
            Dict with symbol metadata
        """
        # Check cache
        if self.enable_cache and symbol in self._symbol_cache:
            return self._symbol_cache[symbol].copy()

        query = text("""
            SELECT
                symbol,
                sector,
                industry,
                market_cap,
                active
            FROM symbols
            WHERE symbol = :symbol
        """)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {'symbol': symbol}).fetchone()

            if not result:
                raise ValueError(f"Symbol {symbol} not found in symbols table")

            metadata = {
                'symbol': result[0],
                'sector': result[1],
                'industry': result[2],
                'market_cap': result[3],
                'active': result[4]
            }

            # Cache
            if self.enable_cache:
                self._symbol_cache[symbol] = metadata.copy()

            return metadata

        except Exception as e:
            logger.error(f"Error fetching metadata for {symbol}: {e}")
            raise

    def fetch_market_state(
        self,
        trade_date: date
    ) -> Dict:
        """
        Fetch market state for given date (SPY data, VIX, regime).

        Args:
            trade_date: Date to fetch market state

        Returns:
            Dict with market state data
        """
        # Check cache
        if self.enable_cache and trade_date in self._market_state_cache:
            return self._market_state_cache[trade_date].copy()

        query = text("""
            SELECT
                d,
                spy_close,
                spy_sma_200,
                regime,
                vix_close,
                kill_switch
            FROM market_state
            WHERE d = :trade_date
        """)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {'trade_date': trade_date}).fetchone()

            if not result:
                raise ValueError(f"No market state data for {trade_date}")

            market_state = {
                'date': result[0],
                'spy_close': result[1],
                'spy_sma_200': result[2],
                'regime': result[3],
                'vix_close': result[4],
                'kill_switch': result[5]
            }

            # Cache
            if self.enable_cache:
                self._market_state_cache[trade_date] = market_state.copy()

            return market_state

        except Exception as e:
            logger.error(f"Error fetching market state for {trade_date}: {e}")
            raise

    def get_available_symbols(self, active_only: bool = True) -> List[str]:
        """
        Get list of all available symbols.

        Args:
            active_only: If True, return only active symbols

        Returns:
            List of symbol strings
        """
        query = text("""
            SELECT symbol
            FROM symbols
            WHERE (:active_only = FALSE OR active = TRUE)
            ORDER BY symbol
        """)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {'active_only': active_only}).fetchall()

            symbols = [row[0] for row in result]
            logger.info(f"Found {len(symbols)} symbols (active_only={active_only})")
            return symbols

        except Exception as e:
            logger.error(f"Error fetching symbol list: {e}")
            raise

    def clear_cache(self):
        """Clear all cached data"""
        self._bar_cache.clear()
        self._symbol_cache.clear()
        self._market_state_cache.clear()
        logger.info("Cache cleared")

    def close(self):
        """Close database connection pool"""
        self.engine.dispose()
        logger.info("Database connections closed")


# Example usage
if __name__ == "__main__":
    # Initialize loader
    loader = PostgresDataLoader(
        connection_string="postgresql://user:pass@localhost:5432/rapidtrader",
        enable_cache=True
    )

    # Fetch single symbol
    df = loader.fetch_ohlcv('AAPL', start_date=date(2023, 1, 1))
    print(f"AAPL data: {len(df)} bars")

    # Fetch multiple symbols
    symbols = ['AAPL', 'MSFT', 'GOOGL']
    data = loader.fetch_ohlcv_batch(symbols, start_date=date(2023, 1, 1))
    print(f"Loaded {len(data)} symbols")

    # Fetch metadata
    metadata = loader.fetch_symbol_metadata('AAPL')
    print(f"AAPL sector: {metadata['sector']}")

    # Fetch market state
    market = loader.fetch_market_state(date(2023, 1, 15))
    print(f"Market regime on 2023-01-15: {market['regime']}")

    # Cleanup
    loader.close()
```

**Configuration File:**

```python
# config/database.py

import os
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration"""

    # PostgreSQL connection
    host: str = os.getenv('RT_DB_HOST', 'localhost')
    port: int = int(os.getenv('RT_DB_PORT', '5432'))
    database: str = os.getenv('RT_DB_NAME', 'rapidtrader')
    user: str = os.getenv('RT_DB_USER', 'user')
    password: str = os.getenv('RT_DB_PASSWORD', 'password')

    # Connection pool
    pool_size: int = 5
    max_overflow: int = 10

    # Cache settings
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour

    def get_connection_string(self) -> str:
        """Build PostgreSQL connection string"""
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
        )


# Load from environment
db_config = DatabaseConfig()
```

**Unit Tests Required:**

```python
# tests/test_postgres_loader.py

import pytest
import pandas as pd
from datetime import date
from src.data.postgres_loader import PostgresDataLoader


@pytest.fixture
def db_loader(postgresql):
    """Fixture providing PostgreSQL data loader with test database"""
    # postgresql is a pytest-postgresql fixture
    connection_string = f"postgresql://{postgresql.info.user}@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}"

    loader = PostgresDataLoader(connection_string, enable_cache=False)

    # Setup test data
    with loader.engine.begin() as conn:
        # Create tables
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bars_daily (
                symbol TEXT,
                d DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume BIGINT,
                PRIMARY KEY (symbol, d)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS symbols (
                symbol TEXT PRIMARY KEY,
                sector TEXT,
                industry TEXT,
                market_cap BIGINT,
                active BOOLEAN
            )
        """))

        # Insert test data
        conn.execute(text("""
            INSERT INTO bars_daily VALUES
            ('AAPL', '2023-01-03', 100.0, 102.0, 99.0, 101.0, 1000000),
            ('AAPL', '2023-01-04', 101.0, 103.0, 100.0, 102.0, 1100000),
            ('MSFT', '2023-01-03', 200.0, 202.0, 199.0, 201.0, 500000)
        """))

        conn.execute(text("""
            INSERT INTO symbols VALUES
            ('AAPL', 'Technology', 'Consumer Electronics', 3000000000000, TRUE),
            ('MSFT', 'Technology', 'Software', 2500000000000, TRUE)
        """))

    yield loader

    loader.close()


class TestPostgresDataLoader:

    def test_fetch_ohlcv(self, db_loader):
        """Test fetching OHLCV data for single symbol"""
        df = db_loader.fetch_ohlcv('AAPL', date(2023, 1, 1), date(2023, 1, 31))

        assert not df.empty
        assert len(df) == 2  # Two days of data
        assert list(df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
        assert df.iloc[0]['Close'] == 101.0

    def test_fetch_ohlcv_no_data(self, db_loader):
        """Test fetching non-existent symbol raises error"""
        with pytest.raises(ValueError, match="No data found"):
            db_loader.fetch_ohlcv('INVALID', date(2023, 1, 1))

    def test_fetch_ohlcv_batch(self, db_loader):
        """Test batch fetching multiple symbols"""
        data = db_loader.fetch_ohlcv_batch(
            ['AAPL', 'MSFT'],
            date(2023, 1, 1),
            date(2023, 1, 31)
        )

        assert 'AAPL' in data
        assert 'MSFT' in data
        assert len(data['AAPL']) == 2
        assert len(data['MSFT']) == 1

    def test_fetch_symbol_metadata(self, db_loader):
        """Test fetching symbol metadata"""
        metadata = db_loader.fetch_symbol_metadata('AAPL')

        assert metadata['symbol'] == 'AAPL'
        assert metadata['sector'] == 'Technology'
        assert metadata['active'] is True

    def test_caching(self, db_loader):
        """Test that caching works correctly"""
        db_loader.enable_cache = True

        # First fetch
        df1 = db_loader.fetch_ohlcv('AAPL', date(2023, 1, 1), date(2023, 1, 31))

        # Second fetch (should be from cache)
        df2 = db_loader.fetch_ohlcv('AAPL', date(2023, 1, 1), date(2023, 1, 31))

        # Should be equal but not same object (copy returned)
        pd.testing.assert_frame_equal(df1, df2)
        assert df1 is not df2

    def test_get_available_symbols(self, db_loader):
        """Test getting list of available symbols"""
        symbols = db_loader.get_available_symbols(active_only=True)

        assert 'AAPL' in symbols
        assert 'MSFT' in symbols
        assert len(symbols) >= 2
```

**Acceptance Criteria:**

- [ ] Successfully connects to RapidTrader PostgreSQL database
- [ ] Loads OHLCV data matching expected format
- [ ] Batch loading is 5-10x faster than individual queries for 500 symbols
- [ ] Caching reduces repeated query time by > 90%
- [ ] All error cases handled gracefully (connection failures, missing data)
- [ ] Unit tests achieve > 95% code coverage
- [ ] Documentation includes connection string format and table schemas

---

### 4. ATR POSITION SIZING

**Module:** `src/position_sizing/atr_sizer.py`

**Requirements:**

- Calculate Average True Range (ATR) for volatility measurement
- Size positions based on target risk per trade (e.g., 1% of capital)
- Support configurable ATR period (default: 14 days)
- Support configurable ATR multiplier for stop distance
- Ensure position sizes don't exceed maximum position limits
- Handle edge cases (low volatility, high volatility, small capital)

**Technical Specification:**

```python
# src/position_sizing/atr_sizer.py

from typing import Optional
import pandas as pd
import numpy as np


def calculate_atr(
    df: pd.DataFrame,
    period: int = 14
) -> pd.Series:
    """
    Calculate Average True Range (ATR).

    ATR measures market volatility using true range:
        TR = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ATR = EMA(TR, period)

    Args:
        df: DataFrame with OHLC data
        period: ATR period (default: 14)

    Returns:
        Series with ATR values

    Raises:
        ValueError: If required columns missing or period invalid
    """
    required_cols = ['High', 'Low', 'Close']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"DataFrame must contain {required_cols}")

    if period < 1:
        raise ValueError(f"ATR period must be >= 1, got {period}")

    # Calculate True Range
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    # Calculate ATR as exponential moving average of TR
    atr = true_range.ewm(span=period, adjust=False).mean()

    return atr


def calculate_position_size(
    price: float,
    atr: float,
    capital: float,
    risk_per_trade: float = 0.01,
    atr_multiplier: float = 2.0,
    max_position_pct: float = 0.10,
    min_shares: int = 1
) -> int:
    """
    Calculate position size based on ATR and risk management.

    Logic:
        1. Calculate stop distance: ATR × atr_multiplier
        2. Calculate risk amount: capital × risk_per_trade
        3. Calculate shares: risk_amount / stop_distance
        4. Apply constraints: max position size, minimum shares

    Args:
        price: Current price of asset
        atr: Current ATR value
        capital: Available capital
        risk_per_trade: Risk per trade as fraction of capital (default: 1% = 0.01)
        atr_multiplier: Multiplier for stop distance (default: 2.0)
        max_position_pct: Maximum position as fraction of capital (default: 10% = 0.10)
        min_shares: Minimum shares to trade (default: 1)

    Returns:
        Number of shares to buy

    Raises:
        ValueError: If parameters are invalid
    """
    # Validate inputs
    if price <= 0:
        raise ValueError(f"Price must be > 0, got {price}")
    if atr < 0:
        raise ValueError(f"ATR must be >= 0, got {atr}")
    if capital <= 0:
        raise ValueError(f"Capital must be > 0, got {capital}")
    if not (0 < risk_per_trade <= 1):
        raise ValueError(f"risk_per_trade must be 0-1, got {risk_per_trade}")
    if atr_multiplier <= 0:
        raise ValueError(f"atr_multiplier must be > 0, got {atr_multiplier}")
    if not (0 < max_position_pct <= 1):
        raise ValueError(f"max_position_pct must be 0-1, got {max_position_pct}")

    # Calculate stop distance
    stop_distance = atr * atr_multiplier

    # Handle zero/near-zero ATR (very low volatility)
    if stop_distance < price * 0.001:  # Less than 0.1% of price
        # Use minimum stop of 0.1% of price
        stop_distance = price * 0.001

    # Calculate risk amount
    risk_amount = capital * risk_per_trade

    # Calculate shares based on risk
    shares_by_risk = int(risk_amount / stop_distance)

    # Calculate max shares based on position limit
    max_position_value = capital * max_position_pct
    shares_by_limit = int(max_position_value / price)

    # Take minimum of both constraints
    shares = min(shares_by_risk, shares_by_limit)

    # Apply minimum shares constraint
    shares = max(shares, min_shares)

    # Verify we have enough capital
    position_value = shares * price
    if position_value > capital:
        # Reduce to affordable amount
        shares = int(capital / price)

    return shares


def calculate_position_sizes_batch(
    df_dict: dict,
    capital: float,
    atr_period: int = 14,
    risk_per_trade: float = 0.01,
    atr_multiplier: float = 2.0,
    max_position_pct: float = 0.10
) -> pd.DataFrame:
    """
    Calculate position sizes for multiple symbols.

    Args:
        df_dict: Dict mapping symbol to OHLC DataFrame
        capital: Available capital
        atr_period: ATR period
        risk_per_trade: Risk per trade as fraction
        atr_multiplier: Stop distance multiplier
        max_position_pct: Max position as fraction

    Returns:
        DataFrame with columns: symbol, price, atr, shares, position_value
    """
    results = []

    for symbol, df in df_dict.items():
        if df.empty:
            continue

        # Get latest price and ATR
        latest_price = df['Close'].iloc[-1]
        atr = calculate_atr(df, period=atr_period).iloc[-1]

        # Calculate position size
        shares = calculate_position_size(
            price=latest_price,
            atr=atr,
            capital=capital,
            risk_per_trade=risk_per_trade,
            atr_multiplier=atr_multiplier,
            max_position_pct=max_position_pct
        )

        position_value = shares * latest_price

        results.append({
            'symbol': symbol,
            'price': latest_price,
            'atr': atr,
            'atr_pct': (atr / latest_price) * 100,  # ATR as % of price
            'shares': shares,
            'position_value': position_value,
            'pct_of_capital': (position_value / capital) * 100
        })

    return pd.DataFrame(results)


# Example usage
if __name__ == "__main__":
    # Test ATR calculation
    test_df = pd.DataFrame({
        'High': [102, 104, 103, 105, 106],
        'Low': [98, 99, 100, 101, 102],
        'Close': [100, 102, 101, 103, 104]
    })

    atr = calculate_atr(test_df, period=3)
    print(f"ATR: {atr.iloc[-1]:.2f}")

    # Test position sizing
    shares = calculate_position_size(
        price=100.0,
        atr=2.5,
        capital=100000,
        risk_per_trade=0.01,
        atr_multiplier=2.0
    )

    print(f"Position size: {shares} shares")
    print(f"Position value: ${shares * 100:.2f}")
```

**Unit Tests:**

```python
# tests/test_atr_sizer.py

import pytest
import pandas as pd
import numpy as np
from src.position_sizing.atr_sizer import calculate_atr, calculate_position_size


class TestATRCalculation:

    def test_atr_range(self):
        """ATR should be positive"""
        df = pd.DataFrame({
            'High': [102, 104, 103],
            'Low': [98, 99, 100],
            'Close': [100, 102, 101]
        })

        atr = calculate_atr(df, period=2)
        assert all(atr >= 0)

    def test_atr_constant_range(self):
        """ATR should be stable for constant range"""
        # Range always 4 (high=102, low=98)
        df = pd.DataFrame({
            'High': [102] * 20,
            'Low': [98] * 20,
            'Close': [100] * 20
        })

        atr = calculate_atr(df, period=14)
        # ATR should converge to ~4
        assert np.isclose(atr.iloc[-1], 4.0, atol=0.5)

    def test_position_size_basic(self):
        """Test basic position sizing"""
        shares = calculate_position_size(
            price=100.0,
            atr=2.0,
            capital=100000,
            risk_per_trade=0.01,  # 1% risk
            atr_multiplier=2.0  # 2×ATR stop
        )

        # Risk = $1,000 (1% of $100k)
        # Stop distance = 2.0 × 2 = $4
        # Shares = $1,000 / $4 = 250
        assert shares == 250

    def test_position_size_max_limit(self):
        """Position size should respect max position limit"""
        shares = calculate_position_size(
            price=10.0,
            atr=0.1,
            capital=100000,
            risk_per_trade=0.50,  # 50% risk (very high)
            atr_multiplier=2.0,
            max_position_pct=0.10  # But max 10% position
        )

        # Max position = $10,000 (10% of $100k)
        # Shares = $10,000 / $10 = 1,000
        # Even though risk calculation would give more
        assert shares == 1000

    def test_position_size_insufficient_capital(self):
        """Should limit to affordable shares if capital insufficient"""
        shares = calculate_position_size(
            price=1000.0,
            atr=10.0,
            capital=5000,  # Can only afford 5 shares
            risk_per_trade=0.10
        )

        # Can only afford 5 shares at $1,000 each
        assert shares == 5

    def test_zero_atr_handling(self):
        """Should handle zero/near-zero ATR gracefully"""
        shares = calculate_position_size(
            price=100.0,
            atr=0.0,  # No volatility
            capital=100000,
            risk_per_trade=0.01
        )

        # Should not crash, should return reasonable value
        assert shares >= 1
        assert shares * 100 <= 100000  # Within capital
```

**Acceptance Criteria:**

- [ ] ATR calculation matches TA-Lib or pandas-ta reference implementation
- [ ] Position sizing respects all constraints (risk, max position, capital)
- [ ] Handles edge cases (zero ATR, very high/low volatility)
- [ ] Performance: < 1ms per symbol for position size calculation
- [ ] Unit tests achieve 100% code coverage
- [ ] Documentation includes mathematical formulas and examples

---

### 5. TRANSACTION COST MODEL

**Module:** `src/execution/transaction_costs.py`

**Requirements:**

- Model commission costs (per-share or fixed)
- Model bid-ask spread costs
- Model market impact (for larger orders)
- Model slippage (price movement during execution)
- Support different cost profiles (retail, institutional)
- Accurately simulate realistic execution costs

**Technical Specification:**

```python
# src/execution/transaction_costs.py

from typing import Optional, Literal
from dataclasses import dataclass
import numpy as np


@dataclass
class CostProfile:
    """Transaction cost profile"""

    # Commission
    commission_per_share: float = 0.005  # $0.005 per share
    commission_min: float = 0.0  # Minimum commission
    commission_max: Optional[float] = None  # Maximum commission

    # Spread
    spread_bps: float = 5.0  # Bid-ask spread in basis points
    spread_model: Literal['fixed', 'dynamic'] = 'fixed'

    # Slippage
    slippage_bps: float = 2.0  # Slippage in basis points
    slippage_model: Literal['fixed', 'linear'] = 'fixed'

    # Market impact (for large orders)
    impact_coefficient: float = 0.1  # Impact as function of (shares/volume)


# Preset profiles
RETAIL_PROFILE = CostProfile(
    commission_per_share=0.005,
    spread_bps=5.0,
    slippage_bps=2.0
)

INSTITUTIONAL_PROFILE = CostProfile(
    commission_per_share=0.001,
    spread_bps=2.0,
    slippage_bps=1.0
)


def calculate_commission(
    shares: int,
    price: float,
    profile: CostProfile
) -> float:
    """
    Calculate commission cost.

    Args:
        shares: Number of shares
        price: Price per share
        profile: Cost profile

    Returns:
        Commission cost in dollars
    """
    commission = shares * profile.commission_per_share

    # Apply min/max constraints
    if profile.commission_min:
        commission = max(commission, profile.commission_min)

    if profile.commission_max:
        commission = min(commission, profile.commission_max)

    return commission


def calculate_spread_cost(
    shares: int,
    price: float,
    profile: CostProfile,
    volatility: Optional[float] = None
) -> float:
    """
    Calculate bid-ask spread cost.

    Args:
        shares: Number of shares
        price: Price per share
        profile: Cost profile
        volatility: Current volatility (for dynamic spread model)

    Returns:
        Spread cost in dollars
    """
    if profile.spread_model == 'fixed':
        # Fixed spread in basis points
        spread_pct = profile.spread_bps / 10000.0
        spread_cost = shares * price * spread_pct

    elif profile.spread_model == 'dynamic':
        # Spread widens with volatility
        if volatility is None:
            raise ValueError("Volatility required for dynamic spread model")

        # Base spread + volatility component
        base_spread = profile.spread_bps / 10000.0
        vol_spread = volatility * 0.5  # Spread increases with vol
        total_spread = base_spread + vol_spread

        spread_cost = shares * price * total_spread

    else:
        raise ValueError(f"Unknown spread model: {profile.spread_model}")

    # Spread cost is always paid (half spread on entry)
    return spread_cost / 2.0


def calculate_slippage(
    shares: int,
    price: float,
    profile: CostProfile,
    daily_volume: Optional[int] = None
) -> float:
    """
    Calculate slippage cost.

    Args:
        shares: Number of shares
        price: Price per share
        profile: Cost profile
        daily_volume: Average daily volume (for linear model)

    Returns:
        Slippage cost in dollars
    """
    if profile.slippage_model == 'fixed':
        # Fixed slippage in basis points
        slippage_pct = profile.slippage_bps / 10000.0
        slippage_cost = shares * price * slippage_pct

    elif profile.slippage_model == 'linear':
        # Slippage increases with order size relative to volume
        if daily_volume is None:
            raise ValueError("Daily volume required for linear slippage model")

        if daily_volume == 0:
            # No volume data, use high slippage
            slippage_pct = profile.slippage_bps * 2 / 10000.0
        else:
            # Calculate order as % of daily volume
            order_pct = shares / daily_volume

            # Base slippage + impact
            base_slippage = profile.slippage_bps / 10000.0
            impact_slippage = order_pct * profile.impact_coefficient

            slippage_pct = base_slippage + impact_slippage

        slippage_cost = shares * price * slippage_pct

    else:
        raise ValueError(f"Unknown slippage model: {profile.slippage_model}")

    return slippage_cost


def calculate_total_cost(
    shares: int,
    price: float,
    profile: CostProfile,
    volatility: Optional[float] = None,
    daily_volume: Optional[int] = None
) -> dict:
    """
    Calculate total transaction cost.

    Args:
        shares: Number of shares
        price: Price per share
        profile: Cost profile
        volatility: Current volatility (optional)
        daily_volume: Average daily volume (optional)

    Returns:
        Dict with cost breakdown:
            - commission: Commission cost
            - spread: Spread cost
            - slippage: Slippage cost
            - total: Total cost
            - total_pct: Total as % of notional
            - notional: Order notional value
    """
    notional = shares * price

    commission = calculate_commission(shares, price, profile)
    spread = calculate_spread_cost(shares, price, profile, volatility)
    slippage = calculate_slippage(shares, price, profile, daily_volume)

    total = commission + spread + slippage
    total_pct = (total / notional) * 100 if notional > 0 else 0

    return {
        'commission': commission,
        'spread': spread,
        'slippage': slippage,
        'total': total,
        'total_pct': total_pct,
        'notional': notional
    }


def calculate_execution_price(
    price: float,
    side: Literal['buy', 'sell'],
    shares: int,
    profile: CostProfile,
    volatility: Optional[float] = None,
    daily_volume: Optional[int] = None
) -> float:
    """
    Calculate effective execution price including costs.

    For buys: execution price is higher (pay spread + slippage)
    For sells: execution price is lower (pay spread + slippage)
    Commission is separate and not included in price.

    Args:
        price: Market price
        side: 'buy' or 'sell'
        shares: Number of shares
        profile: Cost profile
        volatility: Current volatility
        daily_volume: Average daily volume

    Returns:
        Effective execution price per share
    """
    # Calculate spread and slippage
    spread = calculate_spread_cost(shares, price, profile, volatility)
    slippage = calculate_slippage(shares, price, profile, daily_volume)

    # Total price impact per share
    price_impact_per_share = (spread + slippage) / shares if shares > 0 else 0

    if side == 'buy':
        # Buy at higher price
        execution_price = price + price_impact_per_share
    elif side == 'sell':
        # Sell at lower price
        execution_price = price - price_impact_per_share
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'buy' or 'sell'")

    return execution_price


# Example usage
if __name__ == "__main__":
    # Calculate costs for sample trade
    shares = 100
    price = 150.0

    costs = calculate_total_cost(
        shares=shares,
        price=price,
        profile=RETAIL_PROFILE,
        volatility=0.02,  # 2% volatility
        daily_volume=1000000  # 1M shares/day
    )

    print(f"Order: {shares} shares @ ${price}")
    print(f"Commission: ${costs['commission']:.2f}")
    print(f"Spread: ${costs['spread']:.2f}")
    print(f"Slippage: ${costs['slippage']:.2f}")
    print(f"Total cost: ${costs['total']:.2f} ({costs['total_pct']:.3f}%)")

    # Calculate execution price
    exec_price = calculate_execution_price(
        price=price,
        side='buy',
        shares=shares,
        profile=RETAIL_PROFILE
    )

    print(f"\nMarket price: ${price:.2f}")
    print(f"Execution price (buy): ${exec_price:.2f}")
```

**Unit Tests:**

```python
# tests/test_transaction_costs.py

import pytest
from src.execution.transaction_costs import (
    calculate_commission,
    calculate_total_cost,
    calculate_execution_price,
    RETAIL_PROFILE,
    CostProfile
)


class TestTransactionCosts:

    def test_commission_calculation(self):
        """Test commission calculation"""
        commission = calculate_commission(
            shares=100,
            price=50.0,
            profile=RETAIL_PROFILE
        )

        # 100 shares × $0.005 = $0.50
        assert commission == 0.50

    def test_total_cost_components(self):
        """Test that total = commission + spread + slippage"""
        costs = calculate_total_cost(
            shares=100,
            price=100.0,
            profile=RETAIL_PROFILE
        )

        assert costs['total'] == costs['commission'] + costs['spread'] + costs['slippage']

    def test_execution_price_buy(self):
        """Buy execution price should be higher than market"""
        market_price = 100.0

        exec_price = calculate_execution_price(
            price=market_price,
            side='buy',
            shares=100,
            profile=RETAIL_PROFILE
        )

        assert exec_price > market_price

    def test_execution_price_sell(self):
        """Sell execution price should be lower than market"""
        market_price = 100.0

        exec_price = calculate_execution_price(
            price=market_price,
            side='sell',
            shares=100,
            profile=RETAIL_PROFILE
        )

        assert exec_price < market_price

    def test_cost_increases_with_volume(self):
        """Costs should increase for larger orders"""
        small_order = calculate_total_cost(100, 100.0, RETAIL_PROFILE)
        large_order = calculate_total_cost(1000, 100.0, RETAIL_PROFILE)

        assert large_order['total'] > small_order['total']

    def test_cost_percentage(self):
        """Total cost percentage should be reasonable"""
        costs = calculate_total_cost(
            shares=100,
            price=100.0,
            profile=RETAIL_PROFILE
        )

        # For retail, total cost should be < 1% for normal orders
        assert costs['total_pct'] < 1.0
```

**Acceptance Criteria:**

- [ ] Commission model matches typical broker fee structures
- [ ] Spread costs are realistic (5-10 bps for liquid stocks)
- [ ] Slippage model accounts for order size vs volume
- [ ] Total costs align with industry standards (< 0.5% for liquid stocks)
- [ ] Unit tests cover all cost components
- [ ] Documentation includes cost model assumptions and examples

---

## REMAINING SECTIONS

Due to length constraints, I'm breaking this document into parts. The complete specification continues with:

**6. Market Regime Filtering** - Implementation of SPY 200-SMA filter
**7. Portfolio Aggregation Engine** - Multi-symbol portfolio management
**8. Multi-Symbol Orchestration** - Celery-based parallel execution
**9. Risk Management Engine** - Stop losses, heat limits, correlation checks
**10. Performance Analytics** - Comprehensive metrics and reporting

**11. Database Schema Extensions** - New tables for backtest results
**12. API Endpoint Modifications** - Batch job submission endpoints
**13. Performance Optimization** - Caching, vectorization, profiling
**14. Testing Strategy** - Integration tests, load tests
**15. Implementation Roadmap** - Week-by-week development plan
**16. Risk Assessment** - Technical risks and mitigation strategies

---

**Document Status:** Part 1 of 2 Complete
**Next Steps:** Review Part 1 before continuing to Part 2

Would you like me to continue with the remaining sections?

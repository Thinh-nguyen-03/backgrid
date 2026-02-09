# Strategy SDK

**Phase 2 Complete** - RSI and MA strategies fully implemented and tested

Backgrid strategies are **pure, pluggable modules** that generate trading signals from price data.

## Current Implementation (Phase 2)

### BaseStrategy Interface

All strategies inherit from `BaseStrategy`:

```python
from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    def __init__(self, params: dict):
        self.params = params
        self._validate_params()
    
    @abstractmethod
    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Calculate trading signals from OHLCV data.
        
        Args:
            df: DataFrame with OHLCV columns
        
        Returns:
            Series of Signal values (BUY, SELL, HOLD)
        """
        pass
    
    @abstractmethod
    def get_warmup_period(self) -> int:
        """Return number of bars needed before signals are valid."""
        pass
    
    def _validate_params(self) -> None:
        """Validate strategy parameters."""
        pass
```

## Implemented Strategies

### 1. MA Crossover Strategy

Fast/slow moving average crossover.

```python
from src.strategies import MAStrategy, Signal

strategy = MAStrategy({
    "fast_period": 20,   # or "fast"
    "slow_period": 100   # or "slow"
})

signals = strategy.calculate_signals(df)
```

**Default Parameters** (RapidTrader compatible):
- `fast_period`: 20
- `slow_period`: 100

**Warmup Period**: `slow_period` bars

### 2. RSI Strategy

Mean reversion with 2-of-3 confirmation logic.

```python
from src.strategies import RSIStrategy

strategy = RSIStrategy({
    "rsi_period": 14,
    "oversold_threshold": 30,
    "overbought_threshold": 55,
    "confirmation_window": 3,
    "min_confirmation_count": 2
})

signals = strategy.calculate_signals(df)

# Get raw RSI values
rsi = strategy.get_rsi_values(df)
```

**Default Parameters** (RapidTrader compatible):
- `rsi_period`: 14 (Wilder's smoothing)
- `oversold_threshold`: 30
- `overbought_threshold`: 55
- `confirmation_window`: 3
- `min_confirmation_count`: 2

**Warmup Period**: `rsi_period + confirmation_window` bars

**RSI Calculation**: Uses Wilder's smoothing method (`ewm(alpha=1/period, adjust=False)`)

### 3. Multi-Strategy Combination

Combine multiple strategies with different methods.

```python
from src.strategies import StrategyManager, CombinationMethod

manager = StrategyManager(method=CombinationMethod.PRIORITY)
manager.add_strategy("ma", MAStrategy({"fast": 20, "slow": 100}))
manager.add_strategy("rsi", RSIStrategy())

signals = manager.calculate_signals(df)

# Get attribution
signals, attributions = manager.calculate_signals(df, return_attributions=True)
```

**Combination Methods**:
- `OR`: Any BUY triggers buy, any SELL triggers sell
- `AND`: All strategies must agree
- `PRIORITY`: SELL > BUY > HOLD precedence
- `WEIGHTED`: Weighted voting (requires weights parameter)

## Signal Enum

All strategies return signals using the `Signal` enum:

```python
from src.strategies import Signal

Signal.BUY   # Enter/add to position
Signal.SELL  # Exit/reduce position
Signal.HOLD  # No action
```

## Adding New Strategies

1. Create new file in `src/strategies/`
2. Inherit from `BaseStrategy`
3. Implement `calculate_signals()` and `get_warmup_period()`
4. Add parameter validation in `_validate_params()`
5. Add default parameters in `DEFAULT_PARAMS` class variable
6. Write tests in `tests/test_your_strategy.py`

Example:

```python
from .base import BaseStrategy, Signal
import pandas as pd

class MyStrategy(BaseStrategy):
    name: str = "my_strategy"
    
    DEFAULT_PARAMS = {
        "period": 20,
        "threshold": 0.5
    }
    
    def __init__(self, params=None):
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged_params)
    
    def _validate_params(self):
        if self.params["period"] < 2:
            raise ValueError("period must be >= 2")
    
    def get_warmup_period(self) -> int:
        return self.params["period"]
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        self.validate_dataframe(df)
        # Your logic here
        signals = pd.Series(Signal.HOLD, index=df.index)
        return signals
```

## Testing Strategies

Required tests:
- Default parameters match specification
- Parameter validation (invalid inputs raise errors)
- Signal generation correctness
- Warmup period calculation
- DataFrame validation (missing columns, insufficient data)

See `tests/test_rsi_strategy.py` for comprehensive example (32 tests).

## Future Extensions (Phase 3)

- Event-driven context (`ctx`) with portfolio state
- Order placement helpers
- Resource limits (memory, runtime)
- Custom indicators library

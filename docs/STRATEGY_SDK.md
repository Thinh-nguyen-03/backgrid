# Strategy SDK

Backgrid strategies are **pure, pluggable modules** that generate trading signals from price data.

## BaseStrategy Interface

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

**Default Parameters**:
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

**Default Parameters**:
- `rsi_period`: 14 (Wilder's smoothing)
- `oversold_threshold`: 30
- `overbought_threshold`: 55
- `confirmation_window`: 3
- `min_confirmation_count`: 2

**Warmup Period**: `rsi_period + confirmation_window` bars

**RSI Calculation**: Uses Wilder's smoothing (`ewm(alpha=1/period, adjust=False)`)

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

Minimal example:

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
        signals = pd.Series(Signal.HOLD, index=df.index)
        # your signal logic here
        return signals
```

Extended example — MA crossover with N-day confirmation (illustrates rolling confirmation pattern):

```python
from .base import BaseStrategy, Signal
import pandas as pd

class MAConfirmedStrategy(BaseStrategy):
    """MA crossover requiring N consecutive days of agreement before signaling."""

    name: str = "ma_confirmed"

    DEFAULT_PARAMS = {
        "fast_period": 20,
        "slow_period": 100,
        "confirmation_days": 2
    }

    def __init__(self, params=None):
        merged_params = {**self.DEFAULT_PARAMS, **(params or {})}
        super().__init__(merged_params)

    def get_warmup_period(self) -> int:
        return self.params["slow_period"] + self.params["confirmation_days"]

    def calculate_signals(self, df: pd.DataFrame) -> pd.Series:
        self.validate_dataframe(df)
        fast_ma = df["Close"].rolling(window=self.params["fast_period"]).mean()
        slow_ma = df["Close"].rolling(window=self.params["slow_period"]).mean()
        conf = self.params["confirmation_days"]

        bullish_count = (fast_ma > slow_ma).astype(int).rolling(window=conf).sum()

        signals = pd.Series(Signal.HOLD, index=df.index)
        signals[bullish_count >= conf] = Signal.BUY
        signals[bullish_count == 0] = Signal.SELL
        return signals
```

## Testing Strategies

Required tests:
- Default parameters match specification
- Parameter validation (invalid inputs raise errors)
- Signal generation correctness
- Warmup period calculation
- DataFrame validation (missing columns, insufficient data)

See [tests/test_rsi_strategy.py](../tests/test_rsi_strategy.py) for a comprehensive example (32 tests).

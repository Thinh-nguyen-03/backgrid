# Strategy SDK

Backgrid strategies are **pure, pluggable modules** that emit orders from incoming bars.

## Interface
```python
class BaseStrategy:
    def __init__(self, params: dict): self.params = params
    def on_start(self, ctx): pass              # init state
    def on_data(self, bar, ctx): raise NotImplementedError  # one bar at a time
    def on_finish(self, ctx): pass             # finalize
```
`ctx` exposes:
- `portfolio` (positions, equity, PnL)
- `orders` (buy/sell, target position helpers)
- `clock` (timestamp, bar index, random seeded RNG)
- `symbols` (universe metadata)
- `log()` (structured logs)

## Example — Moving Average Crossover
```python
class MACrossover(BaseStrategy):
    def on_start(self, ctx):
        p = self.params
        self.fast = int(p.get("fast", 10))
        self.slow = int(p.get("slow", 30))
        self.window = []

    def on_data(self, bar, ctx):
        self.window.append(bar.close)
        if len(self.window) < self.slow:
            return
        fast = sum(self.window[-self.fast:])/self.fast
        slow = sum(self.window[-self.slow:])/self.slow
        long = ctx.portfolio.is_long(bar.symbol)
        if fast > slow and not long:
            qty = ctx.portfolio.target_weight_q(bar.symbol, 0.95)
            ctx.orders.buy(bar.symbol, qty=qty, note="gc-fast>slow")
        elif fast < slow and long:
            ctx.orders.sell_all(bar.symbol, note="gc-fast<slow")
```

## Resource Limits
- Max runtime per job: 60s (configurable)
- Memory limit: 512 MB (cgroup)
- No outbound network; whitelisted stdlib only
- Deterministic RNG from `seed` for replayability

## Adding a Strategy
1. Create a new Python module in `libs/strategy/`.
2. Export `def get_strategy() -> Type[BaseStrategy]`.
3. Add schema to `strategies` table and unit tests.

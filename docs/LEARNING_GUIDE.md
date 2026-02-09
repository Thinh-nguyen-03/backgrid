# Learning Guide (Reference)

**Phase 2 Complete** - All Phase 1-2 concepts implemented and tested

**Note**: This is a reference, not a prerequisite. Learn concepts as you need them.

---

## Phase 2 Concepts (Implemented ✅)

1. ✅ **OHLCV data** (Phase 1)
2. ✅ **Moving averages** (Phase 1)
3. ✅ **Look-ahead bias** (Phase 1)
4. ✅ **Sharpe ratio** (Phase 1)
5. ✅ **RSI & confirmation logic** (Phase 2 Week 2)
6. ✅ **ATR position sizing** (Phase 2 Week 3)
7. ✅ **Transaction cost modeling** (Phase 2 Week 3)
8. ✅ **Market regime detection** (Phase 2 Week 4)
9. ✅ **Stop losses & portfolio heat** (Phase 2 Week 4)
10. ✅ **Celery** (Phase 2 Week 5)
11. ✅ **PostgreSQL** (Phase 2 Week 6)
12. ✅ **Portfolio backtesting** (Phase 2 Week 6)
13. ✅ **Multi-strategy combination** (Phase 2 Week 6)
14. ✅ **Comprehensive testing** (Phase 2 Week 7)

## Phase 3 Concepts (Not Yet Needed)

15. **Profiling** (needed when bottlenecks identified)
16. **gRPC** (needed when metrics calculation >50% runtime)
17. **TimescaleDB** (needed when PostgreSQL queries >500ms)
18. **JWT** (needed for multi-user isolation)

---

## Quick Reference

### Key Formulas

```python
# Returns
daily_return = (price_today - price_yesterday) / price_yesterday

# Sharpe Ratio
sharpe = (annual_return - risk_free_rate) / volatility

# Max Drawdown
running_max = np.maximum.accumulate(equity)
drawdown = (equity - running_max) / running_max
max_dd = np.min(drawdown)
```

### Key Risk Formulas

```python
# ATR (Wilder's smoothing, alpha = 1 / period)
true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
atr = ewm(true_range, alpha=1/period, min_periods=period, adjust=False)

# RSI (Wilder's smoothing)
delta = prices.diff()
gains = delta.where(delta > 0, 0.0)
losses = (-delta).where(delta < 0, 0.0)
avg_gain = gains.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
avg_loss = losses.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))

# Transaction Costs
spread_cost = trade_value * (spread_bps / 10000) / 2
slippage_cost = trade_value * (slippage_bps / 10000)
commission = max(shares * commission_per_share, min_commission)
total_cost = spread_cost + slippage_cost + commission

# Stop price
stop_price = entry_price - (atr * multiplier)   # long positions

# Portfolio heat
heat = sum((entry_price_i - stop_price_i) * shares_i for each open position)
heat_pct = heat / portfolio_value

# Sector exposure
sector_pct = sum(market_value_i for positions in sector) / portfolio_value
```

### Common Pitfalls

1. **Look-ahead bias**: Using future data in signals
2. **Survivorship bias**: Only testing on stocks that still exist
3. **Overfitting**: Too many parameters on limited data
4. **Regime blindness**: Running trend-following strategies in bear markets without a regime filter
5. **Ignoring transaction costs**: Strategies that look good gross often fail net of commissions and slippage

---

## Resources (When You Get Stuck)

- **Investopedia**: Basic finance terms
- **"Quantitative Trading" by Ernest Chan**: Strategy ideas
- **FastAPI docs**: API design
- **Celery docs**: Distributed tasks

**Don't read cover-to-cover. Use as reference.**

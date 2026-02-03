# Learning Guide (Reference)

**Note**: This is a reference, not a prerequisite. Learn concepts as you need them.

---

## Priority Order for Backgrid

1. **OHLCV data** (needed Phase 1)
2. **Moving averages** (needed Phase 1)
3. **Look-ahead bias** (needed Phase 1)
4. **Sharpe ratio** (needed Phase 1)
5. **RSI & confirmation logic** (needed Phase 2 Week 2)
6. **ATR position sizing** (needed Phase 2 Week 3)
7. **Transaction cost modeling** (needed Phase 2 Week 3)
8. **Market regime detection** (needed Phase 2 Week 4)
9. **Stop losses & portfolio heat** (needed Phase 2 Week 4)
10. **Celery** (needed Phase 2 Week 5+)
11. **PostgreSQL** (needed Phase 2 Week 5+)
12. **Profiling** (needed Phase 3)
13. **gRPC** (needed Phase 3)
14. **TimescaleDB** (needed Phase 3)
15. **JWT** (needed Phase 3)

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
atr = ewm(true_range, alpha=1/period, adjust=False)

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

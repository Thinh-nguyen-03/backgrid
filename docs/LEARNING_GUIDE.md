# Learning Guide (Reference)

**Note**: This is a reference, not a prerequisite. Learn concepts as you need them.

---

## Priority Order for Backgrid

1. **OHLCV data** (needed Phase 1)
2. **Moving averages** (needed Phase 1)
3. **Look-ahead bias** (needed Phase 1)
4. **Sharpe ratio** (needed Phase 1)
5. **Celery** (needed Phase 2)
6. **PostgreSQL** (needed Phase 2)
7. **Profiling** (needed Phase 3)
8. **gRPC** (needed Phase 3)
9. **TimescaleDB** (needed Phase 3)
10. **JWT** (needed Phase 3)

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

### Common Pitfalls

1. **Look-ahead bias**: Using future data in signals
2. **Survivorship bias**: Only testing on stocks that still exist
3. **Overfitting**: Too many parameters on limited data

---

## Resources (When You Get Stuck)

- **Investopedia**: Basic finance terms
- **"Quantitative Trading" by Ernest Chan**: Strategy ideas
- **FastAPI docs**: API design
- **Celery docs**: Distributed tasks

**Don't read cover-to-cover. Use as reference.**

# Portfolio Equity Curve Implementation Plan

## Overview
Add aggregated equity curve visualization for portfolio batch backtests to help users understand combined performance across multiple symbols.

## Current State
- Portfolio batch backtests run each symbol independently
- Individual equity curves are calculated but not stored
- Only aggregated metrics (avg sharpe, avg return, avg drawdown) are returned
- Frontend displays table of results but no visual performance tracking

## Proposed Solution

### Backend Changes

#### 1. Database Schema Updates
**File**: `src/db.py` (models section)

Add equity curve storage to PortfolioResult model:
```python
class PortfolioResult(Base):
    # ... existing fields ...
    portfolio_equity_curve = Column(JSON, nullable=True)  # Aggregated curve
    metadata = Column(JSON, nullable=True)  # Store additional info
```

Add to SymbolResult model:
```python
class SymbolResult(Base):
    # ... existing fields ...
    equity_curve = Column(JSON, nullable=True)  # Individual symbol curve
```

**Migration**: Create Alembic migration to add new columns (SQLite compatible)

#### 2. Portfolio Aggregation Logic
**File**: `src/api_portfolio.py` - `_run_portfolio_backtest_sync()`

Current flow:
1. Run backtest for each symbol
2. Extract metrics (sharpe, return, drawdown)
3. Store individual results
4. Calculate averages

Enhanced flow:
1. Run backtest for each symbol
2. **Store equity_curve** in symbol result
3. Extract metrics
4. **Aggregate equity curves** into portfolio curve
5. Calculate portfolio-level metrics from aggregated curve
6. Store both individual and aggregated curves

**Aggregation Method**: Equal-weighted combination
- Normalize each symbol's equity curve to starting capital
- Average all curves at each timestamp
- Result represents portfolio value if capital split equally

#### 3. API Response Updates
**File**: `src/api_portfolio.py` - `get_portfolio_backtest()`

Add to response:
```python
return {
    # ... existing fields ...
    "portfolio_equity_curve": portfolio.portfolio_equity_curve,
    "symbol_equity_curves": {
        symbol: result.equity_curve
        for symbol, result in results_by_symbol.items()
    }
}
```

### Frontend Changes

#### 1. Chart Integration
**File**: `frontend/src/components/PortfolioResults.js`

Add chart container to render:
```javascript
render(data) {
    // ... existing code ...

    this.container.innerHTML = `
        ${summary}
        ${failedHtml}
        <div id="portfolioChartContainer"></div>
        ${tableHtml}
        ${logButtons}
    `;

    // Render equity curve if available
    if (data.portfolio_equity_curve) {
        const chartEl = document.getElementById('portfolioChartContainer');
        this.equityCurveChart = new EquityCurveChart(chartEl);
        this.equityCurveChart.render(
            data.portfolio_equity_curve,
            'Portfolio Equity'
        );
    }
}
```

#### 2. Multi-Line Chart Option (Future Enhancement)
Add ability to overlay individual symbol curves on portfolio chart for comparison

## Implementation Steps

### Phase 1: Backend (Estimated: 4-6 hours)
1. Create Alembic migration for new columns (30 min)
2. Update models.py with new fields (15 min)
3. Implement equity curve aggregation function (1-2 hours)
4. Update `_run_portfolio_backtest_sync()` to store curves (1 hour)
5. Update `get_portfolio_backtest()` response (30 min)
6. Write unit tests for aggregation logic (1-2 hours)

### Phase 2: Frontend (Estimated: 1-2 hours)
1. Update PortfolioResults.js to render chart (30 min)
2. Add CSS styling if needed (15 min)
3. Test with real data (15-30 min)
4. Handle edge cases (empty curves, single symbol, etc.) (30 min)

### Phase 3: Testing & Validation (Estimated: 1 hour)
1. End-to-end test with multiple symbols
2. Verify chart renders correctly
3. Test dark mode compatibility
4. Validate performance with large datasets

## Technical Considerations

### Performance
- **Database**: SQLite JSON columns are efficient for read-heavy operations
- **Network**: Equity curves can be large arrays (252+ data points per year)
- **Mitigation**: Consider compression or pagination for very long backtests (5+ years)

### Data Consistency
- All symbols must have overlapping date ranges for accurate aggregation
- Handle missing data gracefully (forward-fill or skip timestamps)
- Validate curve lengths match before aggregation

### Edge Cases
- Single symbol portfolio (no aggregation needed)
- Symbols with different date ranges
- Failed symbol backtests (exclude from aggregation)
- Empty or null equity curves

## Alternative Approaches Considered

### 1. Calculate on-demand (Rejected)
- **Pro**: No storage overhead
- **Con**: Requires re-running backtests or storing raw trade data

### 2. Client-side aggregation (Rejected)
- **Pro**: No backend changes
- **Con**: Requires sending all individual curves (large payload)

### 3. Separate aggregation service (Overkill)
- **Pro**: Microservice separation
- **Con**: Over-engineered for current scale

## Rollout Plan

1. **Development**: Implement in feature branch
2. **Migration**: Apply Alembic migration to add columns
3. **Testing**: Run against test data with multiple symbols
4. **Deployment**: Deploy backend and frontend together
5. **Validation**: Verify equity curves render correctly

## Success Metrics
- Portfolio equity curves render within 2 seconds
- Database queries remain under 500ms
- No regression in existing portfolio batch functionality
- User feedback positive on visualization value

## Future Enhancements
- Multi-line chart showing all symbols overlaid
- Interactive legend to toggle individual symbols
- Export portfolio curve data as CSV
- Compare multiple portfolio batches side-by-side
- Weighted aggregation (market cap, equal risk, etc.)

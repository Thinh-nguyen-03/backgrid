# UI Modernization Plan - Phase 2 Feature Integration

**STATUS: IMPLEMENTED (2026-02-14)** - Phases 0-4 complete. Phase 5 (optional) deferred.

## Context

Phase 2 of Backgrid is complete with all backend functionality implemented and tested (650 tests passing). However, the UI has not been updated since Phase 1 and only supports single-symbol MA crossover backtesting. The current UI is a single-page vanilla JavaScript application with a "brutalist industrial pop" design aesthetic.

**Current UI capabilities:**
- Single symbol backtesting with MA crossover strategy only
- Basic KPI display (Sharpe, Total Return, Max Drawdown, Runtime)
- Hardcoded strategy dropdown with 3 options (only MA works)
- Disabled execution parameters (marked as "P2")
- Placeholder chart area (marked as "PHASE 2 CHART AREA")
- No portfolio management, multi-strategy, or trade ledger viewing

**Phase 2 Backend Features Not in UI:**
1. **RSI Strategy** - Fully implemented with 2-of-3 confirmation logic
2. **Multi-Strategy Backtesting** - OR/AND/PRIORITY/WEIGHTED combination methods
3. **Portfolio Backtesting** - Run multiple symbols in batch with aggregate results
4. **Advanced Position Sizing** - ATR-based volatility sizing
5. **Transaction Cost Modeling** - Commission, spread, slippage configuration
6. **Risk Management** - Market regime filter, stop losses, sector limits, portfolio heat
7. **Trade Ledger** - Detailed trade history with filtering
8. **Symbol Management** - Browse available symbols from Yahoo or PostgreSQL
9. **Extended Metrics** - Win rate, total trades, transaction costs (available in portfolio/multi-strategy responses). Note: Sortino, Calmar, and profit factor are NOT yet computed or returned by any endpoint.

**Design Constraints:**
- Must preserve the existing "brutalist industrial pop" aesthetic (yellow/cyan accents, hard shadows, sharp corners, monospace fonts)
- Follow modern big tech frontend architecture best practices:
  - Separate HTML, CSS, and JavaScript into modular files
  - Component-based structure with reusable modules
  - Build tooling with bundler (Vite recommended for speed)
  - CSS organization using methodology (BEM or similar)
  - ES6 modules for JavaScript
  - Environment-based configuration
  - Development server with hot reload

## Implementation Plan

### 1. Enable Execution Parameters Section

**Current State:** Grayed out and disabled with "P2" badge

**Changes:**
- Remove disabled state and opacity styling from "Execution (P2)" section
- Update badge from "Execution (P2)" to "Execution Setup"
- Replace static disabled inputs with functional controls:
  - Initial Capital: number input (default: 10000)
  - Position Sizing: dropdown (Fixed Fractional, ATR-based)
  - Enable Transaction Costs: checkbox (default: true)
  - Commission per share: number input (default: 0.005)
  - Spread (bps): number input (default: 5.0)
  - Slippage (bps): number input (default: 2.0)
- Add conditional display: show ATR-specific inputs when "ATR-based" selected:
  - Risk per trade (%): number input (default: 5)
  - ATR period: number input (default: 14)
  - ATR multiplier: number input (default: 3.0)

**Files:** `src/templates/index.html`

---

### 2. Update Strategy Selection to Support RSI and Multi-Strategy

**Current State:** Dropdown with 3 fake options, only MA crossover works

**Changes:**
- Replace hardcoded dropdown with functional strategy selection:
  - "Moving Average Crossover" (existing)
  - "RSI Mean Reversion" (new - Phase 2)
  - "Combined Strategies" (new - Phase 2)
- For MA strategy: show Fast/Slow period inputs (existing)
- For RSI strategy: show new inputs (param names must match backend validators):
  - RSI Period → `rsi_period` (default: 14)
  - Oversold Threshold → `oversold_threshold` (default: 30)
  - Overbought Threshold → `overbought_threshold` (default: 55)
  - Confirmation Window → `confirmation_window` (default: 3)
  - Min Confirmations → `min_confirmations` (default: 2)
- For Combined strategy: show multi-strategy configuration panel:
  - "Add Strategy" button to add MA or RSI strategies
  - Each added strategy shows its specific parameters
  - Combination method dropdown: OR / AND / PRIORITY / WEIGHTED
  - If WEIGHTED selected: show weight input per strategy
  - "Remove" button per strategy

**Files:** `src/templates/index.html`

---

### 3. Add Portfolio Backtesting Mode

**Current State:** Only single symbol supported

**Changes:**
- Add new top-level mode toggle in Universe Setup section:
  - Radio buttons or segmented control: "Single Symbol" / "Portfolio Batch"
- When "Single Symbol" selected (default): show existing ticker input
- When "Portfolio Batch" selected: replace with:
  - Multi-line textarea for symbols (one per line or comma-separated)
  - "Browse Symbols" button to open symbol selector modal
  - Symbol count indicator (e.g., "5 symbols entered")
- Symbol selector modal (overlay):
  - Fetches from `/api/v1/symbols` endpoint
  - Shows table with: Symbol, Name, Sector checkboxes
  - Filter by sector dropdown
  - "Select All" / "Clear All" buttons
  - Pagination controls (limit/offset)
  - "Add Selected" button to populate textarea

**Files:** `src/templates/index.html`

---

### 4. Update Submit Logic for New API Endpoints

**Current State:** Only calls `POST /api/v1/jobs` with hardcoded ma_crossover

**Changes:**
- Detect backtesting mode (single vs portfolio)
- Build appropriate request payload based on selected strategy:
  - MA: `{strategy: "ma_crossover", params: {fast, slow}}`
  - RSI: `{strategy: "rsi", params: {rsi_period, oversold_threshold, overbought_threshold, confirmation_window, min_confirmations}}`
  - Combined: `{strategies: [...], combination_method: "or|and|priority|weighted"}`
- Call appropriate endpoint:
  - Single symbol (MA or RSI) → `POST /api/v1/jobs` (existing, but see Backend Prerequisites)
  - Single symbol multi-strategy → `POST /api/v1/backtest/multi-strategy`
  - Portfolio batch → `POST /api/v1/backtest/portfolio`
- Include BacktestConfigModel in request for execution parameters:
  ```javascript
  config: {
    initial_capital: 10000,
    position_sizing: "atr",
    risk_per_trade: 0.05,
    atr_period: 14,
    atr_multiplier: 3.0,
    enable_transaction_costs: true,
    commission_per_share: 0.005,
    spread_bps: 5.0,
    slippage_bps: 2.0,
    fill_at: "next_open"
  }
  ```
- **Important:** The legacy `POST /api/v1/jobs` endpoint does NOT currently accept `config`. Only `POST /api/v1/backtest/portfolio` and `POST /api/v1/backtest/multi-strategy` support it. The backend must be updated to add `config` support to the legacy endpoint before the UI can send execution parameters for single-symbol backtests (see Backend Prerequisites section).

**Files:** `src/templates/index.html`

---

### 5. Enhance Results Display for Single Symbol

**Current State:** Shows 4 KPI cards (Sharpe, Return, Drawdown, Runtime)

**Changes:**
- Keep existing 4 KPI cards
- **Note on available fields by endpoint:**
  - `POST /api/v1/jobs` (legacy) returns: `sharpe`, `max_drawdown`, `total_return`, `equity_curve`, `runtime_seconds` only. Does NOT include `total_trades`, `win_rate`, or extended metrics.
  - `POST /api/v1/backtest/multi-strategy` returns the above plus: `total_trades`, `win_rate`, `strategies_used`, `combination_method`. However, `total_trades` and `win_rate` are currently hardcoded to 0 in the backend (see Backend Prerequisites).
  - `POST /api/v1/backtest/portfolio` per-symbol results (`SymbolResultModel`) include: `sharpe`, `max_drawdown`, `total_return`, `total_trades`, `win_rate`, `total_transaction_costs`.
  - **Sortino, Calmar, Profit Factor, Expectancy, and Payoff Ratio do NOT exist in any response model.** These would require backend changes to add (see Backend Prerequisites).
- For now, add KPI cards only for fields that actually exist in the response:
  - Total Trades (new card, portfolio/multi-strategy only)
  - Win Rate % (new card, portfolio/multi-strategy only)
  - Transaction Costs (new card, portfolio only)
- Conditionally show cards based on which endpoint was called
- Use responsive grid that adjusts columns based on viewport
- Style: Keep brutalist card design with hard shadows

**Files:** `src/templates/index.html`

---

### 6. Add Portfolio Results Display

**Current State:** No portfolio results view

**Changes:**
- When portfolio backtest completes, show:
  - **Summary Card** (yellow accent, primary):
    - Symbols Completed / Symbols Requested
    - Average Sharpe, Average Return, Average Drawdown
    - Best Symbol / Worst Symbol
    - Total Trades across portfolio
  - **Per-Symbol Results Table**:
    - Columns: Symbol, Status, Sharpe, Return, Drawdown, Trades, Win Rate, Tx Costs
    - Color-coded by performance (green/red for return)
    - Click symbol row to expand details
    - Sort by column headers
    - Hard border styling, monospace font for numbers
  - **Failed Symbols** (if any):
    - Red card with list of failed symbols and error reasons
- Add "View Trade Ledger" button to open trade ledger modal

**Files:** `src/templates/index.html`

---

### 7. Implement Trade Ledger Modal

**Current State:** No trade viewing capability

**Changes:**
- Create modal overlay (brutalist design):
  - Full-width table showing trades
  - Columns: Entry Date, Exit Date, Symbol, Side, Shares, Entry Price, Exit Price, P&L, P&L %, Strategy, Tx Costs
  - Filters panel at top:
    - Symbol filter (dropdown)
    - Strategy filter (dropdown)
    - Date range filter (flatpickr)
    - Min/Max P&L filter
  - Pagination controls (limit/offset)
  - Export to CSV button
- Fetch from `GET /api/v1/backtest/portfolio/{batch_id}/trades` with query params
- Style: Black header bar with yellow text, bordered rows, monospace numbers
- "Close" button (X) in top-right corner

**Files:** `src/templates/index.html`

---

### 8. Add Equity Curve Chart (Phase 2 Chart Area)

**Current State:** Placeholder with "PHASE 2 CHART AREA" text

**Changes:**
- Integrate a lightweight charting library (consider Chart.js or Plotly.js from CDN - no build step)
- Recommendation: **Chart.js** (simpler, smaller, fits vanilla JS approach)
- Display equity curve from `equity_curve` field in response
- Chart styling to match brutalist theme:
  - Sharp grid lines (no rounded corners)
  - Bold line for equity curve
  - Yellow/cyan color scheme
  - Hard border around chart container
  - No animations (instant render)
- For portfolio backtests: show combined equity curve or allow symbol selection
- Add toggle: Linear / Log scale
- Hover tooltip showing date and equity value

**Files:** `src/templates/index.html`

**External dependency:** Chart.js CDN (similar to existing flatpickr CDN approach)

---

### 9. Add Job History / Recent Backtests Section

**Current State:** Results shown only for latest job, no history

**Changes:**
- Add collapsible "Recent Backtests" panel in sidebar or below results
- Store last 10 backtest results in browser localStorage
- Each entry shows:
  - Timestamp
  - Mode (Single / Portfolio)
  - Strategy type
  - Symbol(s) preview
  - Quick metrics (Sharpe, Return)
  - "Load" button to restore results
- Style: Minimal list with hard borders, monospace timestamps
- "Clear History" button

**Files:** `src/templates/index.html`

---

### 10. Add Risk Management Configuration (Optional Advanced Panel)

**Current State:** No risk management controls

**Changes:**
- Add collapsible "Advanced Risk Controls" section (collapsed by default)
- Controls:
  - Market Regime Filter: checkbox (enable SPY 200-SMA filter)
  - Stop Loss: checkbox + ATR multiplier input (default: 3.0)
  - Stop Loss Cooldown Days: number input (default: 1)
  - Sector Limits: checkbox + max percentage input (default: 30%)
  - Max Positions: number input (default: 20)
  - Portfolio Heat Limit: number input (default: 6%)
- These would be passed in the `config` object to the API
- Style: Dashed border section, gray badge "Advanced (Optional)"

**Files:** `src/templates/index.html`

**Note:** This is optional and can be deferred if time is limited. Backend supports it via BacktestConfigModel but it's not critical for basic Phase 2 UI.

---

### 11. Update Header Version Badge

**Current State:** Shows "v0.1.0"

**Changes:**
- Update to "v2.0.0" or "Phase 2" to reflect completion of Phase 2
- Update styling if needed (currently yellow on black)

**Files:** `src/templates/index.html`

---

### 12. Add Loading States and Progress Indicators

**Current State:** Simple "PROCESSING..." text during submit

**Changes:**
- For single symbol: keep existing loading state
- For portfolio batches: add progress indication if possible
  - Show "Processing N symbols..." message
  - Optionally add animated progress bar (CSS-only animation)
  - Update message when complete: "Completed: X/Y symbols"
- Error handling improvements:
  - Show specific error messages from API
  - Partial failure handling for portfolio (some symbols succeed, some fail)
  - Retry button for failed requests

**Files:** `src/templates/index.html`

---

### 13. Mobile Responsiveness Improvements (Optional)

**Current State:** Fixed 450px sidebar, not mobile-optimized

**Changes (if time permits):**
- Add CSS media queries for screens <768px:
  - Sidebar defaults to collapsed on mobile
  - Stack form sections vertically
  - Full-width KPI cards
  - Scrollable tables with horizontal scroll
- Keep brutalist aesthetic on mobile
- Test on mobile viewport sizes

**Files:** `src/templates/index.html`

**Note:** This is optional and can be deferred. Desktop-first approach is acceptable for trading backtester.

---

## New Frontend Architecture

Following modern big tech practices, the UI will be restructured into a modular frontend application:

### Directory Structure
```
frontend/
├── src/
│   ├── index.html              # Main HTML template (minimal, loads bundles)
│   ├── main.js                 # Application entry point
│   │
│   ├── styles/
│   │   ├── main.css            # Global styles and CSS variables
│   │   ├── components/         # Component-specific styles
│   │   │   ├── header.css
│   │   │   ├── sidebar.css
│   │   │   ├── forms.css
│   │   │   ├── cards.css
│   │   │   ├── modals.css
│   │   │   └── tables.css
│   │   └── utilities.css       # Utility classes
│   │
│   ├── components/
│   │   ├── Header.js           # App header with branding
│   │   ├── Sidebar.js          # Configuration sidebar
│   │   ├── BacktestForm.js     # Main form logic
│   │   ├── StrategySelector.js # Strategy selection component
│   │   ├── PortfolioMode.js    # Portfolio mode toggle and config
│   │   ├── ExecutionConfig.js  # Execution parameters form
│   │   ├── ResultsDisplay.js   # Results rendering logic
│   │   ├── KPICard.js          # KPI card component
│   │   ├── EquityCurveChart.js # Chart.js wrapper
│   │   ├── PortfolioResults.js # Portfolio results table
│   │   ├── TradeLedgerModal.js # Trade ledger modal
│   │   ├── SymbolSelector.js   # Symbol browser modal
│   │   └── JobHistory.js       # Recent backtests history
│   │
│   ├── services/
│   │   ├── api.js              # API client (fetch wrappers)
│   │   ├── storage.js          # localStorage abstraction
│   │   └── utils.js            # Utility functions (formatters, validators)
│   │
│   ├── state/
│   │   └── AppState.js         # Application state manager (lightweight)
│   │
│   └── config/
│       └── constants.js        # Configuration constants
│
├── public/
│   └── assets/                 # Static assets if needed
│
├── dist/                       # Build output (gitignored)
│
├── package.json                # Node dependencies
├── vite.config.js              # Vite build configuration
└── .env.example                # Environment variables template
```

### Technology Stack

**Build Tool:** Vite
- Fast HMR (Hot Module Replacement)
- ES modules native support
- Zero-config TypeScript support (optional)
- Optimized production builds
- Development server with proxy support

**JavaScript:** ES6+ Modules (Vanilla JS)
- No framework dependencies (React/Vue/Angular)
- Modern class-based components
- Event-driven architecture
- Custom element-like pattern for components

**CSS:** Modular CSS with BEM methodology
- Block Element Modifier naming convention
- Component-scoped styles
- CSS custom properties for theming
- No CSS preprocessor needed (modern CSS features)

**External Libraries (CDN or npm):**
- Chart.js for equity curves
- Flatpickr for date pickers
- (Optional) Day.js for date utilities

### Component Architecture Pattern

Each component follows this structure:
```javascript
// Example: components/KPICard.js
export class KPICard {
  constructor(container, options = {}) {
    this.container = container;
    this.options = options;
  }

  render(data) {
    this.container.innerHTML = this.template(data);
    this.attachEvents();
  }

  template(data) {
    return `
      <div class="kpi-card ${data.primary ? 'kpi-card--primary' : ''}">
        <div class="kpi-card__label">${data.label}</div>
        <div class="kpi-card__value">${data.value}</div>
      </div>
    `;
  }

  attachEvents() {
    // Event listeners
  }
}
```

### State Management

Lightweight state manager without external dependencies:
```javascript
// state/AppState.js
export class AppState {
  constructor() {
    this.state = {
      mode: 'single',  // 'single' | 'portfolio'
      strategy: 'ma_crossover',
      results: null,
      history: []
    };
    this.listeners = [];
  }

  setState(updates) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  subscribe(listener) {
    this.listeners.push(listener);
  }

  notify() {
    this.listeners.forEach(fn => fn(this.state));
  }
}
```

### API Service Layer

Centralized API client:
```javascript
// services/api.js
const API_BASE = '/api/v1';

export class BacktestAPI {
  static async submitSingleBacktest(payload) {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  static async submitPortfolioBacktest(payload) {
    const res = await fetch(`${API_BASE}/backtest/portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  // ... other methods
}
```

### Integration with FastAPI Backend

Update `src/ui.py` to serve the built frontend:
```python
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

router = APIRouter()

# Serve static assets
router.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@router.get("/")
async def serve_spa():
    """Serve the SPA index.html"""
    return FileResponse("frontend/dist/index.html")

# Catch-all route for SPA routing (if needed later)
@router.get("/{full_path:path}")
async def catch_all(full_path: str):
    # For SPA routing, always serve index.html for non-API routes
    if not full_path.startswith("api/"):
        return FileResponse("frontend/dist/index.html")
```

### Development Workflow

```bash
# Install dependencies
cd frontend && npm install

# Development mode (hot reload)
npm run dev
# Vite dev server runs on http://localhost:5173
# FastAPI runs on http://localhost:8000
# Vite proxies API requests to FastAPI

# Production build
npm run build
# Outputs to frontend/dist/

# Preview production build
npm run preview
```

### Vite Configuration

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite';

export default defineConfig({
  root: 'src',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    // Note: with root set to 'src', input paths are relative to 'src/'
    rollupOptions: {
      input: {
        main: './index.html'
      }
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
});
```

**Bug fix note:** The existing `frontend/vite.config.js` has `root: 'src'` but `rollupOptions.input.main` set to `'./src/index.html'`. Since `root` already points to `src/`, the input should be `'./index.html'`. This must be fixed in the actual file as well.

### Package.json

```json
{
  "name": "backgrid-frontend",
  "version": "2.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  },
  "dependencies": {
    "chart.js": "^4.4.0",
    "flatpickr": "^4.6.13"
  }
}
```

### Migration Strategy

1. **Phase 1:** Set up new frontend structure
   - Create `frontend/` directory
   - Initialize npm project
   - Configure Vite
   - Extract existing CSS into modular files
   - Extract existing JS into component files
   - Maintain current functionality (no new features yet)

2. **Phase 2:** Add Phase 2 features incrementally
   - Follow the 13 implementation steps from original plan
   - Each feature built as a component

3. **Phase 3:** Update FastAPI integration
   - Modify `src/ui.py` to serve built frontend
   - Update Docker configuration if needed
   - Update documentation

## Verification Plan

After implementation, verify the following end-to-end workflows:

### Test Case 1: Single Symbol RSI Strategy
1. Select "Single Symbol" mode
2. Enter symbol: AAPL
3. Select "RSI Mean Reversion" strategy
4. Set RSI parameters (14, 30, 55, 3, 2)
5. Enable transaction costs
6. Submit backtest
7. Verify results display with extended metrics
8. Verify equity curve chart renders
9. Check browser console for errors

### Test Case 2: Portfolio MA Crossover
1. Select "Portfolio Batch" mode
2. Click "Browse Symbols"
3. Select 5 symbols (AAPL, MSFT, GOOGL, AMZN, TSLA)
4. Select "Moving Average Crossover" strategy
5. Set parameters (fast=10, slow=30)
6. Submit portfolio backtest
7. Verify summary card shows aggregate metrics
8. Verify per-symbol results table displays
9. Click "View Trade Ledger"
10. Verify trade ledger modal opens and displays trades
11. Test filters in trade ledger (symbol, date range)

### Test Case 3: Multi-Strategy Combined
1. Select "Single Symbol" mode
2. Enter symbol: AAPL
3. Select "Combined Strategies"
4. Add MA strategy (10, 30)
5. Add RSI strategy (14, 30, 55)
6. Select combination method: AND
7. Enable ATR position sizing
8. Submit backtest
9. Verify results show strategy attribution (if displayed)
10. Verify equity curve renders

### Test Case 4: Error Handling
1. Submit backtest with invalid symbol
2. Verify error message displays clearly
3. Submit portfolio with mix of valid/invalid symbols
4. Verify partial results display with failed symbols listed

### Test Case 5: Browser Compatibility
1. Test in Chrome (primary)
2. Test in Firefox
3. Test in Edge
4. Verify date picker works across browsers
5. Verify chart.js renders correctly

### Test Case 6: Job History
1. Run 3 different backtests
2. Verify they appear in "Recent Backtests" history
3. Click "Load" on a previous backtest
4. Verify results restore correctly
5. Click "Clear History"
6. Verify history clears

## Design Consistency Checklist

Ensure all new UI elements maintain the brutalist aesthetic:
- [ ] All new inputs have `border: 3px solid` with hard shadows
- [ ] No rounded corners (`border-radius: 0`)
- [ ] Yellow (`#FDE047`) and cyan (`#06B6D4`) accent colors used appropriately
- [ ] Monospace font (`JetBrains Mono`) for all data/numbers
- [ ] Space Grotesk font for headings/labels (bold, uppercase)
- [ ] Hard shadows (`6px 6px 0px`) on interactive elements
- [ ] Hover effects use cyan shadow and text color
- [ ] Active states use translate(3px, 3px) with shadow removal
- [ ] Modals/overlays have thick borders and hard shadows
- [ ] All text labels are uppercase where appropriate

## Technical Notes

### API Integration Summary
- **Single symbol legacy:** `POST /api/v1/jobs` → returns BacktestResponse
- **Multi-strategy:** `POST /api/v1/backtest/multi-strategy` → returns MultiStrategyResponse
- **Portfolio:** `POST /api/v1/backtest/portfolio` → returns PortfolioBacktestResponse (with batch_id)
- **Portfolio results:** `GET /api/v1/backtest/portfolio/{batch_id}` → cached results
- **Trade ledger:** `GET /api/v1/backtest/portfolio/{batch_id}/trades?symbol=&strategy=&limit=1000&offset=0`
- **Symbols list:** `GET /api/v1/symbols?source=yahoo&limit=100&offset=0&sector=`

### Request Payload Structure
```javascript
// BacktestConfigModel (optional, for execution parameters)
{
  initial_capital: 10000.0,
  position_sizing: "atr",  // or "fixed"
  risk_per_trade: 0.05,
  atr_period: 14,
  atr_multiplier: 3.0,
  enable_transaction_costs: true,
  commission_per_share: 0.005,
  spread_bps: 5.0,
  slippage_bps: 2.0,
  fill_at: "next_open"  // or "close", "vwap"
}

// Single symbol request (POST /api/v1/jobs)
// NOTE: This endpoint does NOT currently accept 'config'. See Backend Prerequisites.
{
  symbol: "AAPL",
  strategy: "ma_crossover",  // or "rsi"
  start: "2020-01-01",
  end: "2023-12-31",
  params: {fast: 10, slow: 30}  // MA params
}

// RSI params (key names must match backend validators in models.py)
{
  params: {
    rsi_period: 14,
    oversold_threshold: 30,
    overbought_threshold: 55,
    confirmation_window: 3,
    min_confirmations: 2
  }
}

// Multi-strategy request (POST /api/v1/backtest/multi-strategy)
{
  symbol: "AAPL",
  strategies: [
    {type: "ma_crossover", params: {fast: 10, slow: 30}, weight: 0.5, name: "Fast MA"},
    {type: "rsi", params: {rsi_period: 14, oversold_threshold: 30, overbought_threshold: 55}, weight: 0.5, name: "RSI"}
  ],
  combination_method: "weighted",  // or "or", "and", "priority"
  start: "2020-01-01",
  end: "2023-12-31",
  config: {...}
}

// Portfolio request (POST /api/v1/backtest/portfolio)
{
  symbols: ["AAPL", "MSFT", "GOOGL"],
  strategy: "ma_crossover",
  params: {fast: 10, slow: 30},
  start: "2020-01-01",
  end: "2023-12-31",
  config: {...}
}
```

### Response Structure Examples

These examples reflect the actual Pydantic models in `src/models.py`.

```javascript
// BacktestResponse (POST /api/v1/jobs - single symbol legacy)
// Note: Does NOT include total_trades, win_rate, sortino, calmar, or profit_factor
{
  job_id: "manual-20260207-...",
  status: "completed",
  sharpe: 1.23,
  max_drawdown: -0.15,         // negative value
  total_return: 0.45,
  equity_curve: [10000, 10100, ...],
  runtime_seconds: 2.5,
  error: null,
  created_at: "2026-02-07T12:00:00Z"
}

// MultiStrategyResponse (POST /api/v1/backtest/multi-strategy)
{
  job_id: "multistrat-20260207-...",
  status: "completed",
  symbol: "AAPL",
  strategies_used: ["Fast MA", "RSI"],
  combination_method: "weighted",
  sharpe: 1.23,
  max_drawdown: -0.15,
  total_return: 0.45,
  total_trades: 0,             // NOTE: currently hardcoded to 0 in backend
  win_rate: 0.0,               // NOTE: currently hardcoded to 0.0 in backend
  equity_curve: [10000, 10100, ...],
  runtime_seconds: 2.5,
  error: null,
  created_at: "2026-02-07T12:00:00Z"
}

// PortfolioBacktestResponse (POST /api/v1/backtest/portfolio)
{
  batch_id: "portfolio-20260207-...",
  status: "completed",
  symbols_requested: 5,
  symbols_completed: 4,
  symbols_failed: 1,
  failed_symbols: ["INVALID"],
  symbol_count: 4,
  total_trades: 125,
  average_sharpe: 1.1,
  average_return: 0.35,
  average_max_drawdown: -0.18,
  best_symbol: "AAPL",
  worst_symbol: "MSFT",
  runtime_seconds: 12.3,
  results_by_symbol: {
    "AAPL": {
      symbol: "AAPL",
      status: "completed",
      sharpe: 1.5,
      max_drawdown: -0.12,
      total_return: 0.50,
      total_trades: 30,
      win_rate: 0.60,
      total_transaction_costs: 45.50,
      error: null
    },
    "MSFT": {...}
  },
  error: null,
  created_at: "2026-02-07T12:00:00Z"
}

// TradeLedgerResponse (GET /api/v1/backtest/portfolio/{batch_id}/trades)
{
  batch_id: "portfolio-20260207-...",
  total_trades: 125,
  trades: [
    {
      id: "portfolio-20260207-abc12345-AAPL-0",
      symbol: "AAPL",
      entry_date: "2020-01-15T00:00:00Z",
      exit_date: "2020-02-01T00:00:00Z",
      side: "long",
      shares: 100,
      entry_price: 150.0,
      exit_price: 155.0,
      pnl: 500.0,
      pnl_pct: 0.033,
      strategy: "ma_crossover",
      transaction_costs: 15.0
    },
    ...
  ],
  offset: 0,
  limit: 1000
}

// SymbolListResponse (GET /api/v1/symbols)
{
  total: 25,
  symbols: [
    {symbol: "AAPL", name: "Apple Inc.", sector: "Technology", industry: null, is_active: true},
    {symbol: "MSFT", name: "Microsoft Corporation", sector: "Technology", industry: null, is_active: true},
    ...
  ],
  source: "yahoo"
}
```

## Backend Prerequisites

**STATUS: P0 and P1 COMPLETE (2026-02-14)**

### P0: Required for Core UI Functionality - DONE

**1. Add `config` field to `BacktestRequest` and `submit_job` endpoint** - COMPLETED
- Added `config: Optional[BacktestConfigModel]` to `BacktestRequest` in `src/models.py`
- Updated `submit_job()` in `src/api.py` to use `run_backtest_enhanced()` when config provided
- Added `BacktestRequest.model_rebuild()` for forward reference resolution

**2. Fix `vite.config.js` rollup input path** - COMPLETED
- Removed explicit `rollupOptions.input` entirely; Vite auto-discovers `index.html` in root

### P1: Required for Full Feature Parity - DONE

**3. Compute `total_trades` and `win_rate` in multi-strategy endpoint** - COMPLETED
- Updated `src/api_portfolio.py` to use `run_backtest_enhanced` and compute actual trade metrics

### P2: Optional Extended Metrics - NOT IMPLEMENTED

**4. Add extended metrics to response models (optional)** - DEFERRED
- Sortino, Calmar, Profit Factor, Expectancy, Payoff Ratio not added to response models
- The UI only renders cards for metrics present in the response, so this is not a blocker

---

## Frontend Scaffold Status

**STATUS: FULLY IMPLEMENTED (2026-02-14)**

The `frontend/` directory is fully built with all components, styles, services, and configuration:
- `package.json` - Vite, Chart.js, Flatpickr
- `vite.config.js` - Configured with API proxy (path bug fixed)
- `src/index.html` - Main HTML shell
- `src/main.js` - Application entry point
- `src/components/` - 10 component modules
- `src/styles/` - 8 CSS files (BEM methodology)
- `src/services/` - API client, storage, utils
- `src/state/` - AppState manager
- `src/config/` - Constants and defaults
- `dist/` - Production build output (298KB JS + 31KB CSS)

---

## Error Response Format Handling

The frontend must handle multiple error response formats from the backend:

### Format 1: Custom HTTP errors (from exception handler in `src/api.py`)
```javascript
// Status: 400, 404, 500
{ "error": "Failed to fetch data: No data found for symbol XYZ" }
```

### Format 2: FastAPI/Pydantic validation errors (422 Unprocessable Entity)
```javascript
// Status: 422
{
  "detail": [
    {
      "loc": ["body", "symbol"],
      "msg": "String should have at least 1 character",
      "type": "string_too_short"
    }
  ]
}
```

### Frontend error handling strategy
```javascript
async function handleAPIError(response) {
  const body = await response.json();
  if (response.status === 422 && body.detail) {
    // Validation error: extract first message
    const msg = body.detail.map(e => e.msg).join('; ');
    return `Validation error: ${msg}`;
  }
  // Custom error
  return body.error || body.detail || 'Unknown error';
}
```

---

## localStorage Schema for Job History

### Key
`backgrid_job_history`

### Schema (v1)
```javascript
{
  version: 1,
  entries: [
    {
      id: "manual-20260207-...",       // job_id or batch_id
      timestamp: "2026-02-07T12:00:00Z",
      mode: "single",                  // "single" | "portfolio" | "multi-strategy"
      strategy: "ma_crossover",        // strategy type
      symbols: ["AAPL"],               // array, even for single
      sharpe: 1.23,                    // summary metric
      total_return: 0.45,              // summary metric
      max_drawdown: -0.15,             // summary metric
      // Do NOT store equity_curve or full results (too large)
      // Store only enough to render the history list
    }
  ]
}
```

### Constraints
- Maximum 10 entries (FIFO eviction)
- Estimated size per entry: ~200 bytes
- Total max: ~2KB (well within localStorage limits)
- On schema version mismatch, clear and reset

---

## Jinja2 to Static File Migration

### Current serving (`src/ui.py`)
```python
# Uses Jinja2Templates to serve src/templates/index.html
templates = Jinja2Templates(directory="src/templates")

@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
```

### Migration steps
1. **Development phase:** Keep `src/ui.py` unchanged. Use Vite dev server (`localhost:5173`) for frontend development with API proxy to FastAPI (`localhost:8000`). The old Jinja template continues to work at `localhost:8000/` during this phase.
2. **Integration phase:** Once the new frontend is functional:
   - Run `npm run build` in `frontend/` to produce `frontend/dist/`
   - Update `src/ui.py` to serve static files from `frontend/dist/` instead of Jinja templates
   - The old `src/templates/index.html` can be preserved as `src/templates/index.html.bak` for reference, then deleted once the new UI is verified
3. **Cleanup:** Remove `Jinja2Templates` dependency from `src/ui.py`. The new `ui.py` only needs `FileResponse` and `StaticFiles`.

### Both-worlds development
During development, both can coexist:
- `localhost:8000/` serves old Jinja UI (for comparison/fallback)
- `localhost:5173/` serves new Vite UI (proxies API calls to `:8000`)

---

## Implementation Approach

### Step-by-Step Migration Process

**Step 0: Project Setup (scaffold exists, needs fixes)**
1. ~~Create `frontend/` directory structure~~ (already exists)
2. ~~Initialize npm project~~ (already exists)
3. ~~Install Vite and dependencies~~ (already in package.json, run `npm install`)
4. Fix `vite.config.js` rollup input path bug
5. Verify Vite dev server starts with `npm run dev`

**Step 1: Extract and Modularize Existing Code**
1. Create `src/index.html` with minimal structure (loads bundles)
2. Extract CSS into modular files:
   - `styles/main.css` - CSS variables, reset, layout
   - `styles/components/header.css` - Header styles
   - `styles/components/sidebar.css` - Sidebar and form styles
   - `styles/components/cards.css` - KPI card styles
3. Extract JavaScript into component classes:
   - `components/Header.js` - Header and menu toggle
   - `components/Sidebar.js` - Sidebar management
   - `components/BacktestForm.js` - Form submission logic
   - `components/ResultsDisplay.js` - Results rendering
4. Create `services/api.js` for API calls
5. Create `main.js` as entry point that initializes components
6. Test that existing functionality works with new structure

**Step 2: Add Phase 2 Features (Following Original Plan)**
Once modularized, add new features as separate components:
1. Create `ExecutionConfig.js` component (Step 1 from original plan)
2. Create `StrategySelector.js` component (Step 2)
3. Create `PortfolioMode.js` component (Step 3)
4. Update `BacktestForm.js` for new API logic (Step 4)
5. Enhance `ResultsDisplay.js` with extended metrics (Step 5)
6. Create `PortfolioResults.js` component (Step 6)
7. Create `TradeLedgerModal.js` component (Step 7)
8. Create `EquityCurveChart.js` component (Step 8)
9. Create `JobHistory.js` component (Step 9)
10. Create `RiskConfig.js` component (Step 10 - optional)
11. Update version badge in Header component (Step 11)
12. Add loading states across components (Step 12)
13. Add mobile responsive CSS (Step 13 - optional)

**Step 3: Build and Integration**
1. Run `npm run build` to create production bundle
2. Update `src/ui.py` to serve from `frontend/dist/`
3. Update `.gitignore` to exclude `frontend/node_modules/` and `frontend/dist/`
4. Update documentation with new development workflow
5. Add `frontend/README.md` with setup instructions

## Estimated Complexity

**Project Setup (New):** ~2-3 hours
- Setting up Vite, npm, directory structure
- Initial configuration and tooling

**Code Migration:** ~4-6 hours
- Extracting existing code into modular structure
- Converting to ES6 modules and component classes
- Testing that existing functionality works

**Feature Implementation:** ~20-30 hours (same as original)
- **Simple components:** ExecutionConfig, StrategySelector, version badge (~4-6 hours)
- **Moderate components:** PortfolioMode, API logic, ResultsDisplay enhancements, JobHistory (~10-14 hours)
- **Complex components:** TradeLedgerModal, EquityCurveChart, PortfolioResults (~6-10 hours)
- **Optional:** RiskConfig, mobile responsive (~4-6 hours)

**Total Estimated Time:** ~26-39 hours (including setup and migration)

**Implementation Order (all phases 0-4 COMPLETE as of 2026-02-14):**

**Phase 0: Backend Prerequisites** - COMPLETE
1. Added `config` field to `BacktestRequest`, wired `submit_job` to `run_backtest_enhanced`
2. Fixed `frontend/vite.config.js` (removed explicit rollup input)
3. Fixed multi-strategy endpoint trade metrics

**Phase 1: Setup & Migration** - COMPLETE
4. Ran `npm install`, created all source files from scratch
5. Created 8 modular CSS files with BEM methodology
6. Created 10 component classes + services + state + config
7. Verified via Vite dev server and production build
8. Rewrote `src/ui.py` to serve SPA from `frontend/dist/`

**Phase 2: Core Features** - COMPLETE
9. ExecutionConfig component with position sizing and transaction costs
10. StrategySelector component with MA, RSI, and Combined modes
11. Form submission logic in `main.js` with 3 API paths
12. ResultsDisplay with conditional KPI cards
13. EquityCurveChart with Chart.js and linear/log toggle
14. Header with v2.0.0 badge

**Phase 3: Portfolio Features** - COMPLETE
15. PortfolioMode component with single/portfolio toggle
16. SymbolSelector modal with sector filtering
17. Portfolio batch submission via BacktestAPI
18. PortfolioResults with summary card and per-symbol table
19. TradeLedgerModal with pagination, filters, CSV export

**Phase 4: Enhanced UX** - COMPLETE
20. Multi-strategy builder with add/remove strategies and weight inputs
21. JobHistory component with localStorage (max 10 entries, versioned schema)
22. Loading states and progress messages

**Phase 5: Optional** - NOT IMPLEMENTED
23. RiskConfig component (deferred)
24. Mobile responsive styles (deferred)
25. Backend extended metrics (deferred)

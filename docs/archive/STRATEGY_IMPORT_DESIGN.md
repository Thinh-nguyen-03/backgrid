# Strategy Import & Preset System - Design Document

**Status**: Design Phase
**Target**: Phase 2.5 (Between current Phase 2 and future Phase 3)
**Estimated Effort**: 1-2 weeks
**Dependencies**: None (can run in parallel with monitoring/testing initiatives)

## Problem Statement

**Current Workflow Pain Points:**
1. Testing external strategies (papers, GitHub repos) requires manual parameter extraction
2. Users must read source code, identify 10-15 parameters, manually enter into UI
3. Testing parameter variations requires repetitive form filling
4. No reusable strategy configurations for common approaches
5. Time to test external strategy: 5-10 minutes of manual work

**Success Metrics:**
- Reduce external strategy setup time from 5-10 minutes to <1 minute
- 80%+ of common strategies covered by presets
- LLM extraction accuracy >85% for supported strategy types
- User review step catches 100% of misinterpretations before execution

---

## Phase A: Strategy Preset Library

### Overview

A JSON-based strategy template system allowing one-click loading of complete strategy configurations including:
- Strategy type and parameters
- Position sizing settings
- Risk management rules
- Multi-strategy combinations
- Metadata (source, author, paper reference)

### Requirements

**Functional Requirements:**
1. **FR-A1**: System shall store strategy presets as JSON configurations
2. **FR-A2**: UI shall display preset selector dropdown with categorized options
3. **FR-A3**: Selecting preset shall populate all form fields (strategy, params, position sizing, risk)
4. **FR-A4**: Users can edit preset-loaded values before running backtest
5. **FR-A5**: System shall validate preset schema on load
6. **FR-A6**: Presets shall include metadata (description, source URL, tags)
7. **FR-A7**: Backend shall expose `/api/v1/presets` endpoint for preset management
8. **FR-A8**: Future: Users can save custom presets (Phase 3)

**Non-Functional Requirements:**
1. **NFR-A1**: Preset load time <100ms
2. **NFR-A2**: No code execution (pure configuration)
3. **NFR-A3**: Backward compatible with existing API
4. **NFR-A4**: Presets versioned to handle schema evolution

### Data Model

#### Preset Schema (JSON)

```json
{
  "schema_version": "1.0",
  "presets": [
    {
      "id": "rapidtrader-rsi-mean-reversion",
      "name": "RapidTrader RSI Mean Reversion",
      "description": "RSI mean reversion with SPY regime filter, ATR position sizing, and sector limits. Designed for S&P 500 stocks.",
      "category": "mean_reversion",
      "tags": ["rsi", "mean_reversion", "risk_managed"],
      "source": {
        "type": "github",
        "url": "https://github.com/Thinh-nguyen-03/rapid-trader",
        "author": "Thinh Nguyen",
        "date": "2024-03-15"
      },
      "config": {
        "mode": "portfolio",
        "date_range": {
          "start": "2023-01-01",
          "end": "2024-12-31"
        },
        "strategy": {
          "type": "rsi",
          "params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 55,
            "confirmation_window": 3,
            "min_confirmation_count": 2
          }
        },
        "position_sizing": {
          "method": "atr",
          "base_risk_per_trade": 0.05,
          "atr_period": 14,
          "atr_multiplier": 2.0,
          "max_position_size": 0.20,
          "min_shares": 1
        },
        "transaction_costs": {
          "commission_per_share": 0.0,
          "spread_bps": 5.0,
          "slippage_bps": 3.0
        },
        "risk_management": {
          "market_regime_filter": {
            "enabled": true,
            "benchmark_symbol": "SPY",
            "sma_period": 200,
            "buffer_pct": 0.02
          },
          "sector_limits": {
            "enabled": true,
            "max_per_sector": 0.30,
            "overrides": {
              "Technology": 0.35,
              "Healthcare": 0.25
            }
          },
          "stop_loss": {
            "enabled": true,
            "method": "atr",
            "atr_multiplier": 2.0,
            "cooldown_days": 1
          },
          "portfolio_heat": {
            "enabled": false,
            "max_heat": 0.50
          }
        }
      }
    }
  ]
}
```

#### Multi-Strategy Preset Example

```json
{
  "id": "rapidtrader-combined",
  "name": "RapidTrader Combined (RSI + MA)",
  "description": "Multi-strategy combination using PRIORITY method: RSI for mean reversion, MA crossover for trend following",
  "category": "multi_strategy",
  "config": {
    "strategy": {
      "type": "multi_strategy",
      "combination_method": "PRIORITY",
      "strategies": [
        {
          "name": "rsi",
          "type": "rsi",
          "params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 55
          }
        },
        {
          "name": "ma_crossover",
          "type": "ma_crossover",
          "params": {
            "fast_period": 20,
            "slow_period": 100
          }
        }
      ]
    }
  }
}
```

#### Preset Categories

```python
class PresetCategory(str, Enum):
    MEAN_REVERSION = "mean_reversion"
    TREND_FOLLOWING = "trend_following"
    MOMENTUM = "momentum"
    MULTI_STRATEGY = "multi_strategy"
    VOLATILITY = "volatility"
    CUSTOM = "custom"
```

### Backend Implementation

#### File Structure

```
src/
├── strategies/
│   ├── presets.py          # Preset loader and validator
│   └── preset_data.json    # Preset definitions
├── api_presets.py          # New API router for presets
└── models.py               # Add PresetResponse models
```

#### Core Components

**1. Preset Loader (`src/strategies/presets.py`)**

```python
"""Strategy preset management for Backgrid."""

from typing import Dict, List, Optional
from pathlib import Path
import json
from pydantic import BaseModel, Field, validator

class PresetSource(BaseModel):
    """Source information for strategy preset."""
    type: str  # "github", "paper", "book", "custom"
    url: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None

class PresetConfig(BaseModel):
    """Complete strategy configuration."""
    mode: str  # "single" or "portfolio"
    date_range: Optional[Dict[str, str]] = None
    strategy: Dict  # Strategy type and params
    position_sizing: Optional[Dict] = None
    transaction_costs: Optional[Dict] = None
    risk_management: Optional[Dict] = None

class StrategyPreset(BaseModel):
    """Strategy preset definition."""
    id: str
    name: str
    description: str
    category: str
    tags: List[str] = Field(default_factory=list)
    source: Optional[PresetSource] = None
    config: PresetConfig

    @validator('id')
    def validate_id(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("id must be alphanumeric with hyphens/underscores")
        return v

class PresetLibrary:
    """Manages strategy preset loading and validation."""

    def __init__(self, preset_file: Optional[Path] = None):
        if preset_file is None:
            preset_file = Path(__file__).parent / "preset_data.json"
        self.preset_file = preset_file
        self._presets: Dict[str, StrategyPreset] = {}
        self._load_presets()

    def _load_presets(self) -> None:
        """Load presets from JSON file."""
        if not self.preset_file.exists():
            self._presets = {}
            return

        with open(self.preset_file, 'r') as f:
            data = json.load(f)

        schema_version = data.get("schema_version", "1.0")
        if schema_version != "1.0":
            raise ValueError(f"Unsupported preset schema version: {schema_version}")

        for preset_data in data.get("presets", []):
            preset = StrategyPreset(**preset_data)
            self._presets[preset.id] = preset

    def get_preset(self, preset_id: str) -> Optional[StrategyPreset]:
        """Get preset by ID."""
        return self._presets.get(preset_id)

    def list_presets(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[StrategyPreset]:
        """List all presets with optional filtering."""
        presets = list(self._presets.values())

        if category:
            presets = [p for p in presets if p.category == category]

        if tag:
            presets = [p for p in presets if tag in p.tags]

        return presets

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return sorted(set(p.category for p in self._presets.values()))

    def validate_preset(self, preset: StrategyPreset) -> List[str]:
        """Validate preset configuration against current system capabilities.

        Returns:
            List of validation warnings (empty if fully compatible)
        """
        warnings = []

        # Validate strategy type
        supported_strategies = ["ma_crossover", "rsi", "multi_strategy"]
        strategy_type = preset.config.strategy.get("type")
        if strategy_type not in supported_strategies:
            warnings.append(f"Unsupported strategy type: {strategy_type}")

        # Validate position sizing method
        if preset.config.position_sizing:
            method = preset.config.position_sizing.get("method")
            if method not in ["fixed_fractional", "atr"]:
                warnings.append(f"Unsupported position sizing method: {method}")

        # Validate risk management features
        if preset.config.risk_management:
            rm = preset.config.risk_management

            # Market regime filter requires market_regime module
            if rm.get("market_regime_filter", {}).get("enabled"):
                # Check if feature is available
                pass  # Will be available in Phase 2

            # Portfolio heat tracking
            if rm.get("portfolio_heat", {}).get("enabled"):
                # Check if feature is available
                pass  # Will be available in Phase 2

        return warnings

# Global preset library instance
preset_library = PresetLibrary()
```

**2. API Router (`src/api_presets.py`)**

```python
"""Preset management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .strategies.presets import preset_library, StrategyPreset

router = APIRouter(prefix="/api/v1/presets", tags=["presets"])

class PresetListResponse(BaseModel):
    """Response for preset listing."""
    presets: List[StrategyPreset]
    total: int
    categories: List[str]

class PresetDetailResponse(BaseModel):
    """Response for single preset with validation."""
    preset: StrategyPreset
    warnings: List[str]
    compatible: bool

@router.get("", response_model=PresetListResponse)
async def list_presets(
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """List all available strategy presets.

    Query Parameters:
    - category: Filter by preset category (mean_reversion, trend_following, etc.)
    - tag: Filter by tag (rsi, ma, risk_managed, etc.)

    Returns:
    - List of presets with metadata
    - Total count
    - Available categories
    """
    presets = preset_library.list_presets(category=category, tag=tag)
    categories = preset_library.get_categories()

    return PresetListResponse(
        presets=presets,
        total=len(presets),
        categories=categories
    )

@router.get("/{preset_id}", response_model=PresetDetailResponse)
async def get_preset(preset_id: str):
    """Get preset by ID with validation.

    Path Parameters:
    - preset_id: Unique preset identifier

    Returns:
    - Complete preset configuration
    - Validation warnings (if any)
    - Compatibility status
    """
    preset = preset_library.get_preset(preset_id)

    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")

    warnings = preset_library.validate_preset(preset)
    compatible = len(warnings) == 0

    return PresetDetailResponse(
        preset=preset,
        warnings=warnings,
        compatible=compatible
    )
```

**3. Integration with Main API (`src/api.py`)**

```python
# Add preset router
from .api_presets import router as preset_router

app.include_router(preset_router)
```

#### Initial Preset Data (`src/strategies/preset_data.json`)

Start with 8-10 presets covering common strategies:

1. **RapidTrader RSI Mean Reversion** (as shown above)
2. **RapidTrader Combined (RSI + MA)**
3. **Turtle Trader Breakout**
4. **Simple MA Crossover (Golden Cross)**
5. **RSI Basic (No Risk Management)**
6. **Momentum Rotation**
7. **Conservative Mean Reversion** (wider thresholds)
8. **Aggressive Trend Following** (tight stops)

### Frontend Implementation

#### Component Structure

```
frontend/src/
├── components/
│   ├── PresetSelector.js       # New component
│   └── StrategySelector.js     # Modified to integrate presets
├── services/
│   └── api.js                  # Add preset API calls
└── state/
    └── AppState.js             # Add preset state
```

#### Preset Selector Component

**File: `frontend/src/components/PresetSelector.js`**

```javascript
/**
 * Strategy preset selector component.
 * Allows users to load pre-configured strategy templates.
 */

export class PresetSelector {
  constructor(container, appState) {
    this.container = container;
    this.appState = appState;
    this.presets = [];
    this.categories = [];
    this.onPresetLoad = null; // Callback when preset is loaded
  }

  async init() {
    await this.loadPresets();
    this.render();
    this.attachEventListeners();
  }

  async loadPresets() {
    try {
      const response = await fetch('/api/v1/presets');
      const data = await response.json();
      this.presets = data.presets;
      this.categories = data.categories;
    } catch (error) {
      console.error('Failed to load presets:', error);
      this.presets = [];
    }
  }

  render() {
    const selectedCategory = this.appState.state.presetCategory || 'all';
    const filteredPresets = selectedCategory === 'all'
      ? this.presets
      : this.presets.filter(p => p.category === selectedCategory);

    this.container.innerHTML = `
      <div class="preset-selector">
        <div class="preset-selector__header">
          <label for="preset-category">Strategy Presets</label>
          <select id="preset-category" class="preset-selector__category">
            <option value="all">All Categories</option>
            ${this.categories.map(cat => `
              <option value="${cat}" ${cat === selectedCategory ? 'selected' : ''}>
                ${this.formatCategoryName(cat)}
              </option>
            `).join('')}
          </select>
        </div>

        <div class="preset-selector__grid">
          <div class="preset-card preset-card--blank">
            <div class="preset-card__content">
              <h4>Custom Strategy</h4>
              <p>Configure your own strategy parameters</p>
            </div>
            <button class="preset-card__button" data-preset-id="">
              Start from Scratch
            </button>
          </div>

          ${filteredPresets.map(preset => this.renderPresetCard(preset)).join('')}
        </div>
      </div>
    `;
  }

  renderPresetCard(preset) {
    return `
      <div class="preset-card" data-preset-id="${preset.id}">
        <div class="preset-card__header">
          <h4 class="preset-card__title">${preset.name}</h4>
          ${preset.tags.map(tag => `
            <span class="preset-card__tag">${tag}</span>
          `).join('')}
        </div>

        <div class="preset-card__content">
          <p class="preset-card__description">${preset.description}</p>

          ${preset.source ? `
            <div class="preset-card__source">
              <small>
                Source: ${preset.source.author || 'Unknown'}
                ${preset.source.url ? `
                  <a href="${preset.source.url}" target="_blank" rel="noopener">
                    <svg class="icon-external">...</svg>
                  </a>
                ` : ''}
              </small>
            </div>
          ` : ''}
        </div>

        <div class="preset-card__footer">
          <button class="preset-card__button" data-preset-id="${preset.id}">
            Load Preset
          </button>
          <button class="preset-card__preview" data-preset-id="${preset.id}">
            Preview Config
          </button>
        </div>
      </div>
    `;
  }

  formatCategoryName(category) {
    return category
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  attachEventListeners() {
    // Category filter
    const categorySelect = this.container.querySelector('#preset-category');
    if (categorySelect) {
      categorySelect.addEventListener('change', (e) => {
        this.appState.setState({ presetCategory: e.target.value });
        this.render();
        this.attachEventListeners();
      });
    }

    // Load preset buttons
    const loadButtons = this.container.querySelectorAll('.preset-card__button');
    loadButtons.forEach(button => {
      button.addEventListener('click', async (e) => {
        const presetId = e.target.dataset.presetId;
        if (presetId) {
          await this.loadPreset(presetId);
        } else {
          this.clearPreset();
        }
      });
    });

    // Preview buttons
    const previewButtons = this.container.querySelectorAll('.preset-card__preview');
    previewButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        const presetId = e.target.dataset.presetId;
        this.previewPreset(presetId);
      });
    });
  }

  async loadPreset(presetId) {
    try {
      const response = await fetch(`/api/v1/presets/${presetId}`);
      const data = await response.json();

      if (!data.compatible && data.warnings.length > 0) {
        const proceed = confirm(
          `Warning: This preset has compatibility issues:\n\n${data.warnings.join('\n')}\n\nLoad anyway?`
        );
        if (!proceed) return;
      }

      // Map preset config to app state
      const config = data.preset.config;
      this.appState.setState({
        mode: config.mode,
        strategy: config.strategy.type,
        strategyParams: config.strategy.params,
        positionSizing: config.position_sizing,
        transactionCosts: config.transaction_costs,
        riskManagement: config.risk_management,
        loadedPreset: presetId,
        loadedPresetName: data.preset.name
      });

      // Show success notification
      this.showNotification(`Loaded preset: ${data.preset.name}`, 'success');

      // Trigger callback if set
      if (this.onPresetLoad) {
        this.onPresetLoad(data.preset);
      }

      // Scroll to strategy form
      document.querySelector('.strategy-form')?.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
      console.error('Failed to load preset:', error);
      this.showNotification('Failed to load preset', 'error');
    }
  }

  clearPreset() {
    this.appState.setState({
      loadedPreset: null,
      loadedPresetName: null
    });
    this.showNotification('Starting from scratch', 'info');
  }

  previewPreset(presetId) {
    const preset = this.presets.find(p => p.id === presetId);
    if (!preset) return;

    // Show modal with full config
    const modal = document.createElement('div');
    modal.className = 'modal modal--preset-preview';
    modal.innerHTML = `
      <div class="modal__overlay"></div>
      <div class="modal__content">
        <div class="modal__header">
          <h3>${preset.name}</h3>
          <button class="modal__close">&times;</button>
        </div>
        <div class="modal__body">
          <pre><code>${JSON.stringify(preset.config, null, 2)}</code></pre>
        </div>
        <div class="modal__footer">
          <button class="btn btn--primary" data-action="load">Load Preset</button>
          <button class="btn btn--secondary" data-action="close">Close</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Event listeners for modal
    modal.querySelector('.modal__close').addEventListener('click', () => modal.remove());
    modal.querySelector('[data-action="close"]').addEventListener('click', () => modal.remove());
    modal.querySelector('[data-action="load"]').addEventListener('click', () => {
      modal.remove();
      this.loadPreset(presetId);
    });
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification--${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.classList.add('notification--visible');
    }, 10);

    setTimeout(() => {
      notification.classList.remove('notification--visible');
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }
}
```

#### CSS Styling

**File: `frontend/src/styles/preset-selector.css`**

```css
/* Preset Selector Component */
.preset-selector {
  margin-bottom: 2rem;
}

.preset-selector__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.preset-selector__header label {
  font-size: 1.125rem;
  font-weight: 600;
}

.preset-selector__category {
  padding: 0.5rem 1rem;
  border: 2px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-mono);
  cursor: pointer;
}

.preset-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
}

/* Preset Card */
.preset-card {
  border: 2px solid var(--color-border);
  background: var(--color-bg);
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, box-shadow 0.2s;
}

.preset-card:hover {
  transform: translateY(-2px);
  box-shadow: 4px 4px 0 var(--color-accent);
}

.preset-card--blank {
  background: linear-gradient(135deg, var(--color-bg) 0%, var(--color-bg-alt) 100%);
}

.preset-card__header {
  margin-bottom: 0.75rem;
}

.preset-card__title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.preset-card__tag {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  margin-right: 0.25rem;
  margin-bottom: 0.25rem;
  background: var(--color-accent);
  color: var(--color-bg);
  font-size: 0.75rem;
  font-family: var(--font-mono);
}

.preset-card__content {
  flex: 1;
  margin-bottom: 1rem;
}

.preset-card__description {
  font-size: 0.875rem;
  line-height: 1.4;
  color: var(--color-text-muted);
  margin-bottom: 0.75rem;
}

.preset-card__source {
  font-size: 0.75rem;
  color: var(--color-text-muted);
}

.preset-card__source a {
  color: var(--color-accent);
  text-decoration: none;
  margin-left: 0.25rem;
}

.preset-card__footer {
  display: flex;
  gap: 0.5rem;
}

.preset-card__button {
  flex: 1;
  padding: 0.75rem;
  border: 2px solid var(--color-border);
  background: var(--color-accent);
  color: var(--color-bg);
  font-family: var(--font-mono);
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.preset-card__button:hover {
  background: var(--color-accent-hover);
}

.preset-card__preview {
  padding: 0.75rem;
  border: 2px solid var(--color-border);
  background: transparent;
  color: var(--color-text);
  font-family: var(--font-mono);
  cursor: pointer;
}

/* Notification */
.notification {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  padding: 1rem 1.5rem;
  border: 2px solid var(--color-border);
  background: var(--color-bg);
  box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.2);
  font-family: var(--font-mono);
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.3s, transform 0.3s;
  z-index: 1000;
}

.notification--visible {
  opacity: 1;
  transform: translateY(0);
}

.notification--success {
  border-color: var(--color-success);
}

.notification--error {
  border-color: var(--color-error);
}

.notification--info {
  border-color: var(--color-accent);
}
```

#### Integration with Main App

**File: `frontend/src/main.js`**

```javascript
import { PresetSelector } from './components/PresetSelector.js';

// Initialize preset selector before strategy form
const presetContainer = document.getElementById('preset-selector-container');
const presetSelector = new PresetSelector(presetContainer, appState);
await presetSelector.init();

// Callback to update strategy form when preset loads
presetSelector.onPresetLoad = (preset) => {
  strategySelector.updateFromPreset(preset.config);
  executionConfig.updateFromPreset(preset.config);
  portfolioMode.updateFromPreset(preset.config);
};
```

### Testing Strategy

#### Backend Tests

**File: `tests/test_presets.py`**

```python
"""Tests for strategy preset system."""

import pytest
from src.strategies.presets import PresetLibrary, StrategyPreset

class TestPresetLibrary:
    def test_load_presets_from_file(self):
        """Test loading presets from JSON file."""
        library = PresetLibrary()
        assert len(library._presets) >= 8  # At least 8 initial presets

    def test_get_preset_by_id(self):
        """Test retrieving preset by ID."""
        library = PresetLibrary()
        preset = library.get_preset("rapidtrader-rsi-mean-reversion")
        assert preset is not None
        assert preset.name == "RapidTrader RSI Mean Reversion"

    def test_list_presets_no_filter(self):
        """Test listing all presets."""
        library = PresetLibrary()
        presets = library.list_presets()
        assert len(presets) >= 8

    def test_list_presets_filter_by_category(self):
        """Test filtering presets by category."""
        library = PresetLibrary()
        presets = library.list_presets(category="mean_reversion")
        assert len(presets) > 0
        assert all(p.category == "mean_reversion" for p in presets)

    def test_list_presets_filter_by_tag(self):
        """Test filtering presets by tag."""
        library = PresetLibrary()
        presets = library.list_presets(tag="rsi")
        assert len(presets) > 0
        assert all("rsi" in p.tags for p in presets)

    def test_validate_preset_compatible(self):
        """Test validation of compatible preset."""
        library = PresetLibrary()
        preset = library.get_preset("rapidtrader-rsi-mean-reversion")
        warnings = library.validate_preset(preset)
        assert len(warnings) == 0

    def test_validate_preset_unsupported_strategy(self):
        """Test validation catches unsupported strategy type."""
        preset = StrategyPreset(
            id="test-invalid",
            name="Test Invalid",
            description="Test",
            category="test",
            config={
                "strategy": {"type": "unsupported_strategy"}
            }
        )
        library = PresetLibrary()
        warnings = library.validate_preset(preset)
        assert len(warnings) > 0
        assert any("Unsupported strategy type" in w for w in warnings)

class TestPresetAPI:
    def test_list_presets_endpoint(self, client):
        """Test GET /api/v1/presets endpoint."""
        response = client.get("/api/v1/presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert "total" in data
        assert "categories" in data
        assert data["total"] >= 8

    def test_list_presets_filter_category(self, client):
        """Test filtering presets by category."""
        response = client.get("/api/v1/presets?category=mean_reversion")
        assert response.status_code == 200
        data = response.json()
        assert all(p["category"] == "mean_reversion" for p in data["presets"])

    def test_get_preset_by_id(self, client):
        """Test GET /api/v1/presets/{id} endpoint."""
        response = client.get("/api/v1/presets/rapidtrader-rsi-mean-reversion")
        assert response.status_code == 200
        data = response.json()
        assert "preset" in data
        assert "warnings" in data
        assert "compatible" in data
        assert data["preset"]["id"] == "rapidtrader-rsi-mean-reversion"

    def test_get_preset_not_found(self, client):
        """Test 404 for non-existent preset."""
        response = client.get("/api/v1/presets/nonexistent")
        assert response.status_code == 404
```

#### Frontend Tests (Jest)

**File: `frontend/tests/PresetSelector.test.js`**

```javascript
import { PresetSelector } from '../src/components/PresetSelector.js';

describe('PresetSelector', () => {
  let container;
  let appState;
  let presetSelector;

  beforeEach(() => {
    container = document.createElement('div');
    appState = { state: {}, setState: jest.fn() };
    presetSelector = new PresetSelector(container, appState);

    // Mock fetch
    global.fetch = jest.fn();
  });

  test('loads presets on init', async () => {
    fetch.mockResolvedValueOnce({
      json: async () => ({
        presets: [
          { id: 'test-1', name: 'Test 1', category: 'mean_reversion', tags: [] }
        ],
        categories: ['mean_reversion']
      })
    });

    await presetSelector.init();

    expect(fetch).toHaveBeenCalledWith('/api/v1/presets');
    expect(presetSelector.presets).toHaveLength(1);
  });

  test('renders preset cards', async () => {
    presetSelector.presets = [
      {
        id: 'test-1',
        name: 'Test Preset',
        category: 'mean_reversion',
        description: 'Test description',
        tags: ['rsi']
      }
    ];

    presetSelector.render();

    expect(container.querySelector('.preset-card')).toBeTruthy();
    expect(container.textContent).toContain('Test Preset');
  });

  test('loads preset on button click', async () => {
    const mockPreset = {
      preset: {
        id: 'test-1',
        name: 'Test',
        config: {
          mode: 'portfolio',
          strategy: { type: 'rsi', params: {} }
        }
      },
      warnings: [],
      compatible: true
    };

    fetch.mockResolvedValueOnce({ json: async () => mockPreset });

    await presetSelector.loadPreset('test-1');

    expect(fetch).toHaveBeenCalledWith('/api/v1/presets/test-1');
    expect(appState.setState).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'portfolio',
        strategy: 'rsi'
      })
    );
  });
});
```

### Migration Path

**Week 1: Backend Foundation**
- Day 1-2: Implement PresetLibrary class and validation
- Day 3: Create initial 8 presets in JSON
- Day 4: Implement API endpoints
- Day 5: Write backend tests (target: 30 tests)

**Week 2: Frontend Integration**
- Day 1-2: Build PresetSelector component
- Day 3: Integrate with StrategySelector
- Day 4: Add CSS styling
- Day 5: Frontend tests + end-to-end testing

**Week 3: Polish & Documentation**
- Day 1: Documentation (STRATEGY_IMPORT_DESIGN.md, API.md update)
- Day 2: User guide for creating presets
- Day 3: Community preset contribution guide
- Day 4: Performance testing
- Day 5: Deploy to staging

---

## Phase B: LLM-Assisted Parameter Extraction

### Overview

An AI-powered strategy import system that extracts trading strategy parameters from:
- GitHub repository URLs
- Research paper PDFs
- Plain text descriptions
- Code snippets

Uses Claude API to parse content and generate strategy configurations with confidence scoring and human review.

### Requirements

**Functional Requirements:**
1. **FR-B1**: System shall accept GitHub URL, PDF upload, or text input
2. **FR-B2**: System shall extract strategy type, parameters, and logic using LLM
3. **FR-B3**: System shall return confidence score (0-1) for extraction accuracy
4. **FR-B4**: System shall list ambiguities and assumptions made
5. **FR-B5**: User must review and confirm extracted params before execution
6. **FR-B6**: System shall map extracted config to existing strategy presets if match >90%
7. **FR-B7**: System shall save successful extractions as custom presets
8. **FR-B8**: System shall track extraction accuracy metrics for improvement

**Non-Functional Requirements:**
1. **NFR-B1**: Extraction time <30 seconds for typical inputs
2. **NFR-B2**: No storage of API keys in database (use environment variables)
3. **NFR-B3**: No arbitrary code execution (config-only output)
4. **NFR-B4**: Rate limit: 10 extractions per hour per user (prevent API abuse)
5. **NFR-B5**: Extraction accuracy target: >85% for supported strategy types

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  StrategyImportWizard Component                       │ │
│  │  1. Input Selection (URL/PDF/Text)                    │ │
│  │  2. Content Preview                                   │ │
│  │  3. Extraction Progress                               │ │
│  │  4. Review & Edit                                     │ │
│  │  5. Confirm & Load                                    │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  POST /api/v1/strategy/import                         │ │
│  │  - Validate input                                     │ │
│  │  - Fetch content (GitHub, PDF, text)                  │ │
│  │  - Call LLM extraction service                        │ │
│  │  - Validate extracted config                          │ │
│  │  - Return config + confidence + warnings              │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM Extraction Service                     │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  StrategyExtractor Class                              │ │
│  │  - GitHub content fetcher                             │ │
│  │  - PDF text parser                                    │ │
│  │  - Prompt engineering for extraction                  │ │
│  │  - Claude API client                                  │ │
│  │  - Response validation                                │ │
│  │  - Confidence scoring                                 │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Claude API                              │
│  - Model: claude-3-7-sonnet-20250219                       │
│  - Max tokens: 4096                                         │
│  - Temperature: 0.0 (deterministic)                         │
└─────────────────────────────────────────────────────────────┘
```

### Data Model

#### Import Request Schema

```python
class StrategyImportRequest(BaseModel):
    """Request to import strategy from external source."""

    source_type: Literal["github_url", "pdf", "text", "code_snippet"]
    content: str  # URL, base64 PDF, or text content

    # Optional hints to guide extraction
    hints: Optional[Dict[str, Any]] = Field(default_factory=dict)
    # Example: {"expected_strategy_type": "rsi", "language": "python"}

    # Save as custom preset after successful extraction
    save_as_preset: bool = False
    preset_name: Optional[str] = None

class StrategyImportResponse(BaseModel):
    """Response from strategy import with extracted config."""

    # Extracted configuration
    config: PresetConfig

    # Confidence and quality metrics
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_quality: Literal["high", "medium", "low"]

    # Warnings and ambiguities
    warnings: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)

    # Best matching preset (if any)
    matched_preset_id: Optional[str] = None
    match_similarity: Optional[float] = None

    # Original source info
    source_info: Dict[str, Any]

    # Extraction metadata
    extraction_id: str  # For tracking and feedback
    extracted_at: datetime
```

### Backend Implementation

#### File Structure

```
src/
├── extraction/
│   ├── __init__.py
│   ├── extractor.py          # Main StrategyExtractor class
│   ├── content_fetcher.py    # GitHub, PDF fetching
│   ├── prompts.py            # LLM prompts for extraction
│   ├── validator.py          # Validate extracted configs
│   └── similarity.py         # Match to existing presets
├── api_extraction.py         # New API router
└── models.py                 # Add import request/response models
```

#### Strategy Extractor

**File: `src/extraction/extractor.py`**

```python
"""LLM-powered strategy parameter extraction."""

import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import anthropic
import os

from .content_fetcher import ContentFetcher
from .prompts import EXTRACTION_PROMPTS
from .validator import ConfigValidator
from .similarity import find_similar_preset
from ..strategies.presets import PresetConfig

class StrategyExtractor:
    """Extracts trading strategy parameters using LLM."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.content_fetcher = ContentFetcher()
        self.validator = ConfigValidator()

    def extract_from_source(
        self,
        source_type: str,
        content: str,
        hints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract strategy config from external source.

        Args:
            source_type: "github_url", "pdf", "text", or "code_snippet"
            content: URL, base64 PDF, or text content
            hints: Optional hints to guide extraction

        Returns:
            Dictionary with extracted config, confidence, warnings, etc.
        """
        # Step 1: Fetch and prepare content
        prepared_content, source_info = self._prepare_content(source_type, content)

        # Step 2: Extract parameters using LLM
        extraction_result = self._extract_with_llm(
            prepared_content,
            source_type,
            hints or {}
        )

        # Step 3: Validate extracted configuration
        validation_result = self.validator.validate(extraction_result["config"])

        # Step 4: Calculate confidence score
        confidence = self._calculate_confidence(
            extraction_result,
            validation_result
        )

        # Step 5: Find similar existing presets
        matched_preset, similarity = find_similar_preset(extraction_result["config"])

        # Step 6: Determine extraction quality
        quality = self._determine_quality(confidence, validation_result)

        return {
            "config": extraction_result["config"],
            "confidence": confidence,
            "extraction_quality": quality,
            "warnings": validation_result["warnings"],
            "assumptions": extraction_result["assumptions"],
            "matched_preset_id": matched_preset.id if matched_preset else None,
            "match_similarity": similarity,
            "source_info": source_info,
            "extraction_id": self._generate_extraction_id(),
            "extracted_at": datetime.utcnow().isoformat()
        }

    def _prepare_content(
        self,
        source_type: str,
        content: str
    ) -> Tuple[str, Dict[str, Any]]:
        """Fetch and prepare content for extraction."""
        if source_type == "github_url":
            prepared, info = self.content_fetcher.fetch_github(content)
        elif source_type == "pdf":
            prepared, info = self.content_fetcher.parse_pdf(content)
        elif source_type in ["text", "code_snippet"]:
            prepared = content
            info = {"type": source_type, "length": len(content)}
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        return prepared, info

    def _extract_with_llm(
        self,
        content: str,
        source_type: str,
        hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use Claude to extract strategy parameters."""

        # Select appropriate prompt template
        prompt = EXTRACTION_PROMPTS[source_type].format(
            content=content,
            hints=json.dumps(hints, indent=2)
        )

        # Call Claude API
        response = self.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=4096,
            temperature=0.0,  # Deterministic
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Parse response
        response_text = response.content[0].text

        # Extract JSON from response (handles markdown code blocks)
        extraction_data = self._parse_llm_response(response_text)

        return extraction_data

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response and extract JSON config."""
        # Handle markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        else:
            json_str = response_text.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}")

        # Validate required fields
        required_fields = ["config", "assumptions"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"LLM response missing required fields: {missing}")

        return data

    def _calculate_confidence(
        self,
        extraction_result: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for extraction.

        Factors:
        - LLM reported confidence
        - Validation warnings count
        - Completeness of extracted config
        - Ambiguity count
        """
        # Base confidence from LLM
        llm_confidence = extraction_result.get("llm_confidence", 0.5)

        # Penalty for validation warnings
        warning_penalty = len(validation_result["warnings"]) * 0.05

        # Penalty for assumptions/ambiguities
        assumption_penalty = len(extraction_result["assumptions"]) * 0.03

        # Completeness bonus
        config = extraction_result["config"]
        completeness_score = 0.0

        # Check required fields
        if config.get("strategy"):
            completeness_score += 0.3
        if config.get("position_sizing"):
            completeness_score += 0.2
        if config.get("risk_management"):
            completeness_score += 0.2

        # Final confidence calculation
        confidence = (
            llm_confidence * 0.5 +
            completeness_score * 0.5 -
            warning_penalty -
            assumption_penalty
        )

        return max(0.0, min(1.0, confidence))

    def _determine_quality(
        self,
        confidence: float,
        validation_result: Dict[str, Any]
    ) -> str:
        """Determine extraction quality level."""
        if confidence >= 0.85 and len(validation_result["warnings"]) == 0:
            return "high"
        elif confidence >= 0.65:
            return "medium"
        else:
            return "low"

    def _generate_extraction_id(self) -> str:
        """Generate unique extraction ID for tracking."""
        import uuid
        return f"ext_{uuid.uuid4().hex[:12]}"
```

#### Content Fetcher

**File: `src/extraction/content_fetcher.py`**

```python
"""Content fetching for strategy extraction."""

import requests
from typing import Tuple, Dict, Any
import base64
import PyPDF2
from io import BytesIO

class ContentFetcher:
    """Fetches content from various sources for extraction."""

    def fetch_github(self, url: str) -> Tuple[str, Dict[str, Any]]:
        """Fetch content from GitHub repository.

        Strategies:
        1. If URL points to specific file: fetch file content
        2. If URL points to repo: fetch README + main strategy files
        3. Parse file tree to find relevant files (*.py with "strategy" in name)
        """
        # Parse GitHub URL
        parts = url.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid GitHub URL")

        owner, repo = parts[0], parts[1]

        # Check if URL points to specific file
        if "blob" in parts:
            # https://github.com/owner/repo/blob/main/strategy.py
            branch = parts[3]
            file_path = "/".join(parts[4:])
            content = self._fetch_github_file(owner, repo, file_path, branch)
            info = {
                "type": "github_file",
                "url": url,
                "owner": owner,
                "repo": repo,
                "file": file_path
            }
            return content, info
        else:
            # Fetch README and strategy files
            content = self._fetch_github_repo(owner, repo)
            info = {
                "type": "github_repo",
                "url": url,
                "owner": owner,
                "repo": repo
            }
            return content, info

    def _fetch_github_file(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str = "main"
    ) -> str:
        """Fetch single file from GitHub."""
        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
        response = requests.get(api_url)

        if response.status_code != 200:
            raise ValueError(f"Failed to fetch GitHub file: {response.status_code}")

        data = response.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content

    def _fetch_github_repo(self, owner: str, repo: str) -> str:
        """Fetch README and strategy files from repo."""
        combined_content = []

        # Fetch README
        try:
            readme = self._fetch_github_file(owner, repo, "README.md")
            combined_content.append("=== README.md ===\n" + readme)
        except:
            pass

        # Fetch file tree and find strategy files
        tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        response = requests.get(tree_url)

        if response.status_code == 200:
            tree = response.json()
            strategy_files = [
                item["path"]
                for item in tree.get("tree", [])
                if item["type"] == "blob"
                and ("strategy" in item["path"].lower() or "backtest" in item["path"].lower())
                and item["path"].endswith(".py")
            ]

            # Fetch up to 3 strategy files
            for file_path in strategy_files[:3]:
                try:
                    content = self._fetch_github_file(owner, repo, file_path)
                    combined_content.append(f"\n=== {file_path} ===\n{content}")
                except:
                    pass

        return "\n\n".join(combined_content)

    def parse_pdf(self, base64_content: str) -> Tuple[str, Dict[str, Any]]:
        """Parse PDF and extract text content."""
        pdf_bytes = base64.b64decode(base64_content)
        pdf_file = BytesIO(pdf_bytes)

        reader = PyPDF2.PdfReader(pdf_file)
        text_content = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            text_content.append(f"=== Page {page_num + 1} ===\n{text}")

        combined_text = "\n\n".join(text_content)

        info = {
            "type": "pdf",
            "pages": len(reader.pages),
            "length": len(combined_text)
        }

        return combined_text, info
```

#### LLM Prompts

**File: `src/extraction/prompts.py`**

```python
"""LLM prompts for strategy extraction."""

SYSTEM_PROMPT = """You are a trading strategy analysis expert. Your task is to extract trading strategy parameters from provided content (code, papers, or descriptions) and convert them into a structured configuration format.

You must extract:
1. Strategy type (ma_crossover, rsi, multi_strategy, or custom)
2. Strategy parameters (periods, thresholds, etc.)
3. Position sizing method and parameters
4. Risk management rules
5. Transaction cost assumptions

Output Format (JSON):
{
  "config": {
    "mode": "portfolio",
    "strategy": {
      "type": "rsi",
      "params": {
        "rsi_period": 14,
        "oversold_threshold": 30,
        ...
      }
    },
    "position_sizing": {
      "method": "atr",
      "base_risk_per_trade": 0.05,
      ...
    },
    "risk_management": {
      "market_regime_filter": {...},
      "sector_limits": {...},
      ...
    }
  },
  "assumptions": [
    "Assumed RSI period of 14 (not explicitly stated)",
    "Inferred oversold threshold of 30 from typical RSI mean reversion"
  ],
  "llm_confidence": 0.85
}

Rules:
1. Only extract what is explicitly stated or strongly implied
2. List all assumptions you make
3. If critical parameters are missing, set llm_confidence < 0.7
4. For multi-strategy systems, use "multi_strategy" type
5. Map custom indicators to nearest supported strategy type if possible
"""

EXTRACTION_PROMPTS = {
    "github_url": SYSTEM_PROMPT + """

Content from GitHub repository:
{content}

Optional hints:
{hints}

Extract the trading strategy configuration following the JSON format specified above.
""",

    "pdf": SYSTEM_PROMPT + """

Content from research paper (PDF):
{content}

Optional hints:
{hints}

Extract the trading strategy configuration following the JSON format specified above.
Focus on the methodology and parameters sections.
""",

    "text": SYSTEM_PROMPT + """

Strategy description:
{content}

Optional hints:
{hints}

Extract the trading strategy configuration following the JSON format specified above.
""",

    "code_snippet": SYSTEM_PROMPT + """

Code snippet:
{content}

Optional hints:
{hints}

Extract the trading strategy configuration following the JSON format specified above.
Analyze the code logic to determine strategy type and parameters.
"""
}
```

#### API Router

**File: `src/api_extraction.py`**

```python
"""Strategy extraction API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
import os

from .models import StrategyImportRequest, StrategyImportResponse
from .extraction.extractor import StrategyExtractor

router = APIRouter(prefix="/api/v1/strategy", tags=["extraction"])

def get_extractor():
    """Dependency to get extractor instance."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Strategy extraction service not configured (missing ANTHROPIC_API_KEY)"
        )
    return StrategyExtractor(api_key=api_key)

@router.post("/import", response_model=StrategyImportResponse)
async def import_strategy(
    request: StrategyImportRequest,
    extractor: StrategyExtractor = Depends(get_extractor)
):
    """Extract strategy configuration from external source.

    Supported source types:
    - github_url: GitHub repository or file URL
    - pdf: Research paper (base64 encoded)
    - text: Plain text strategy description
    - code_snippet: Python code snippet

    Request Body:
    - source_type: Type of source content
    - content: URL, base64 PDF, or text content
    - hints: Optional hints to guide extraction (expected_strategy_type, language, etc.)
    - save_as_preset: Whether to save as custom preset
    - preset_name: Name for custom preset (if save_as_preset=true)

    Returns:
    - Extracted configuration with confidence score
    - Warnings and assumptions
    - Matched preset (if similar to existing preset)

    Note: Extraction may take 10-30 seconds depending on content size.
    User MUST review extracted parameters before running backtest.
    """
    try:
        result = extractor.extract_from_source(
            source_type=request.source_type,
            content=request.content,
            hints=request.hints
        )

        # TODO: If save_as_preset=True, save to database
        if request.save_as_preset and request.preset_name:
            # Future: Save to user_presets table
            pass

        return StrategyImportResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")
```

### Frontend Implementation

#### Import Wizard Component

**File: `frontend/src/components/StrategyImportWizard.js`**

```javascript
/**
 * Strategy import wizard with LLM-assisted parameter extraction.
 *
 * Flow:
 * 1. Select input type (GitHub URL, PDF, Text)
 * 2. Enter/upload content
 * 3. View extraction progress
 * 4. Review extracted parameters
 * 5. Edit if needed
 * 6. Confirm and load into backtest form
 */

export class StrategyImportWizard {
  constructor(container, appState) {
    this.container = container;
    this.appState = appState;
    this.currentStep = 1;
    this.extractionResult = null;
  }

  render() {
    this.container.innerHTML = `
      <div class="import-wizard">
        <div class="import-wizard__header">
          <h3>Import Strategy</h3>
          <div class="import-wizard__steps">
            <div class="step ${this.currentStep >= 1 ? 'active' : ''}">1. Input</div>
            <div class="step ${this.currentStep >= 2 ? 'active' : ''}">2. Extract</div>
            <div class="step ${this.currentStep >= 3 ? 'active' : ''}">3. Review</div>
            <div class="step ${this.currentStep >= 4 ? 'active' : ''}">4. Confirm</div>
          </div>
        </div>

        <div class="import-wizard__body">
          ${this.renderCurrentStep()}
        </div>
      </div>
    `;

    this.attachEventListeners();
  }

  renderCurrentStep() {
    switch (this.currentStep) {
      case 1:
        return this.renderInputStep();
      case 2:
        return this.renderExtractionStep();
      case 3:
        return this.renderReviewStep();
      case 4:
        return this.renderConfirmStep();
      default:
        return '';
    }
  }

  renderInputStep() {
    return `
      <div class="import-step import-step--input">
        <h4>Select Input Type</h4>

        <div class="input-type-selector">
          <label class="input-type-card">
            <input type="radio" name="input-type" value="github_url" checked>
            <div class="card-content">
              <div class="icon">📦</div>
              <h5>GitHub Repository</h5>
              <p>Import from GitHub repo or file URL</p>
            </div>
          </label>

          <label class="input-type-card">
            <input type="radio" name="input-type" value="text">
            <div class="card-content">
              <div class="icon">📝</div>
              <h5>Text Description</h5>
              <p>Paste strategy description or logic</p>
            </div>
          </label>

          <label class="input-type-card">
            <input type="radio" name="input-type" value="code_snippet">
            <div class="card-content">
              <div class="icon">💻</div>
              <h5>Code Snippet</h5>
              <p>Paste Python code with strategy logic</p>
            </div>
          </label>

          <label class="input-type-card">
            <input type="radio" name="input-type" value="pdf">
            <div class="card-content">
              <div class="icon">📄</div>
              <h5>Research Paper (PDF)</h5>
              <p>Upload PDF with strategy details</p>
            </div>
          </label>
        </div>

        <div class="input-content-area">
          <div class="input-field" data-type="github_url">
            <label>GitHub URL</label>
            <input type="text" id="github-url" placeholder="https://github.com/user/repo">
            <small>Examples: repo URL, file URL, or specific commit</small>
          </div>

          <div class="input-field hidden" data-type="text">
            <label>Strategy Description</label>
            <textarea id="text-input" rows="8" placeholder="Describe the trading strategy..."></textarea>
          </div>

          <div class="input-field hidden" data-type="code_snippet">
            <label>Python Code</label>
            <textarea id="code-input" rows="12" placeholder="# Paste your strategy code here..."></textarea>
          </div>

          <div class="input-field hidden" data-type="pdf">
            <label>Upload PDF</label>
            <input type="file" id="pdf-upload" accept=".pdf">
          </div>
        </div>

        <div class="import-wizard__actions">
          <button class="btn btn--secondary" onclick="this.closest('.import-wizard').remove()">
            Cancel
          </button>
          <button class="btn btn--primary" id="btn-extract">
            Extract Parameters →
          </button>
        </div>
      </div>
    `;
  }

  renderExtractionStep() {
    return `
      <div class="import-step import-step--extraction">
        <div class="extraction-progress">
          <div class="spinner"></div>
          <h4>Extracting Strategy Parameters...</h4>
          <p>This may take 10-30 seconds</p>

          <div class="extraction-log">
            <div class="log-entry">✓ Fetching content...</div>
            <div class="log-entry active">⏳ Analyzing strategy logic...</div>
            <div class="log-entry">Validating parameters...</div>
            <div class="log-entry">Matching to presets...</div>
          </div>
        </div>
      </div>
    `;
  }

  renderReviewStep() {
    const result = this.extractionResult;
    const quality = result.extraction_quality;
    const qualityColor = quality === 'high' ? 'success' : quality === 'medium' ? 'warning' : 'error';

    return `
      <div class="import-step import-step--review">
        <div class="extraction-summary">
          <div class="summary-header">
            <h4>Extraction Complete</h4>
            <div class="confidence-badge confidence-badge--${qualityColor}">
              ${Math.round(result.confidence * 100)}% Confidence
              <span class="quality-label">${quality.toUpperCase()}</span>
            </div>
          </div>

          ${result.matched_preset_id ? `
            <div class="matched-preset">
              <div class="icon">🎯</div>
              <div>
                <strong>Matched Existing Preset</strong>
                <p>${Math.round(result.match_similarity * 100)}% similar to "${result.matched_preset_id}"</p>
              </div>
              <button class="btn btn--small" id="btn-load-matched">
                Load Preset Instead
              </button>
            </div>
          ` : ''}

          ${result.warnings.length > 0 ? `
            <div class="warnings-box">
              <h5>⚠️ Warnings</h5>
              <ul>
                ${result.warnings.map(w => `<li>${w}</li>`).join('')}
              </ul>
            </div>
          ` : ''}

          ${result.assumptions.length > 0 ? `
            <div class="assumptions-box">
              <h5>📋 Assumptions Made</h5>
              <ul>
                ${result.assumptions.map(a => `<li>${a}</li>`).join('')}
              </ul>
            </div>
          ` : ''}
        </div>

        <div class="extracted-config">
          <h5>Extracted Configuration</h5>
          <div class="config-editor">
            <pre><code>${JSON.stringify(result.config, null, 2)}</code></pre>
          </div>
          <button class="btn btn--small btn--secondary" id="btn-edit-config">
            Edit JSON
          </button>
        </div>

        <div class="import-wizard__actions">
          <button class="btn btn--secondary" id="btn-back-to-input">
            ← Back
          </button>
          <button class="btn btn--primary" id="btn-confirm-import">
            Load Configuration →
          </button>
        </div>
      </div>
    `;
  }

  async extractStrategy(sourceType, content) {
    this.currentStep = 2;
    this.render();

    try {
      const response = await fetch('/api/v1/strategy/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_type: sourceType,
          content: content,
          hints: {}
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Extraction failed');
      }

      this.extractionResult = await response.json();
      this.currentStep = 3;
      this.render();

    } catch (error) {
      alert(`Extraction failed: ${error.message}`);
      this.currentStep = 1;
      this.render();
    }
  }

  loadExtractedConfig() {
    const config = this.extractionResult.config;

    this.appState.setState({
      mode: config.mode,
      strategy: config.strategy.type,
      strategyParams: config.strategy.params,
      positionSizing: config.position_sizing,
      transactionCosts: config.transaction_costs,
      riskManagement: config.risk_management,
      importedStrategy: true,
      extractionId: this.extractionResult.extraction_id
    });

    // Close wizard
    this.container.remove();

    // Show success message
    alert(`Strategy imported successfully!\n\nConfidence: ${Math.round(this.extractionResult.confidence * 100)}%\n\nPlease review parameters before running backtest.`);
  }

  attachEventListeners() {
    // Input type selector
    const inputTypeRadios = this.container.querySelectorAll('input[name="input-type"]');
    inputTypeRadios.forEach(radio => {
      radio.addEventListener('change', (e) => {
        // Show/hide input fields
        const fields = this.container.querySelectorAll('.input-field');
        fields.forEach(field => field.classList.add('hidden'));

        const activeField = this.container.querySelector(`.input-field[data-type="${e.target.value}"]`);
        if (activeField) activeField.classList.remove('hidden');
      });
    });

    // Extract button
    const btnExtract = this.container.querySelector('#btn-extract');
    if (btnExtract) {
      btnExtract.addEventListener('click', async () => {
        const selectedType = this.container.querySelector('input[name="input-type"]:checked').value;
        let content;

        if (selectedType === 'github_url') {
          content = this.container.querySelector('#github-url').value;
        } else if (selectedType === 'text') {
          content = this.container.querySelector('#text-input').value;
        } else if (selectedType === 'code_snippet') {
          content = this.container.querySelector('#code-input').value;
        } else if (selectedType === 'pdf') {
          const file = this.container.querySelector('#pdf-upload').files[0];
          if (file) {
            content = await this.fileToBase64(file);
          }
        }

        if (!content) {
          alert('Please provide content to extract');
          return;
        }

        await this.extractStrategy(selectedType, content);
      });
    }

    // Confirm import button
    const btnConfirm = this.container.querySelector('#btn-confirm-import');
    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => {
        this.loadExtractedConfig();
      });
    }

    // Back button
    const btnBack = this.container.querySelector('#btn-back-to-input');
    if (btnBack) {
      btnBack.addEventListener('click', () => {
        this.currentStep = 1;
        this.render();
      });
    }
  }

  async fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }
}
```

### Testing Strategy

#### Backend Tests

```python
# tests/test_extraction.py

class TestStrategyExtractor:
    def test_extract_from_github_url(self):
        """Test extraction from GitHub URL."""
        extractor = StrategyExtractor()
        result = extractor.extract_from_source(
            source_type="github_url",
            content="https://github.com/Thinh-nguyen-03/rapid-trader"
        )

        assert result["confidence"] > 0.7
        assert result["config"]["strategy"]["type"] in ["rsi", "multi_strategy"]
        assert len(result["assumptions"]) >= 0

    def test_extract_from_text(self):
        """Test extraction from text description."""
        extractor = StrategyExtractor()
        text = """
        Our strategy uses RSI(14) with oversold threshold at 30 and overbought at 70.
        We use 2-of-3 confirmation window. Position sizing is 5% of account with ATR-based
        adjustment. Stop loss is 2x ATR.
        """
        result = extractor.extract_from_source(
            source_type="text",
            content=text
        )

        assert result["confidence"] > 0.8
        assert result["config"]["strategy"]["params"]["rsi_period"] == 14
        assert result["config"]["strategy"]["params"]["oversold_threshold"] == 30

class TestExtractionAPI:
    def test_import_strategy_endpoint(self, client):
        """Test POST /api/v1/strategy/import."""
        response = client.post("/api/v1/strategy/import", json={
            "source_type": "text",
            "content": "RSI mean reversion with period 14, oversold at 25"
        })

        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        assert "confidence" in data
        assert data["config"]["strategy"]["type"] == "rsi"
```

### Performance & Cost Considerations

**API Costs (Anthropic):**
- Claude 3.7 Sonnet: ~$3 per million input tokens, ~$15 per million output tokens
- Average extraction: ~2000 input tokens + 1000 output tokens
- Cost per extraction: ~$0.03
- Monthly budget for 1000 extractions: ~$30

**Rate Limiting:**
- 10 extractions per hour per user
- Prevents API abuse
- Monthly limit: ~300 extractions per user

**Caching Strategy:**
- Cache extractions by content hash for 24 hours
- Avoid re-extracting same content
- ~70% cache hit rate expected

### Migration Path

**Week 1: Backend Extraction Service**
- Day 1-2: Implement StrategyExtractor class
- Day 3: Content fetchers (GitHub, PDF)
- Day 4: LLM prompts and validation
- Day 5: API endpoints + tests

**Week 2: Frontend Wizard**
- Day 1-2: StrategyImportWizard component
- Day 3: Progress UI and review flow
- Day 4: Integration with main app
- Day 5: CSS styling

**Week 3: Testing & Refinement**
- Day 1-2: End-to-end testing with real repos
- Day 3: Prompt engineering refinement
- Day 4: Documentation
- Day 5: Deploy to staging

---

## Integration with Immediate Recommendations

### Can Phase A+B Run in Parallel with Frontend Tests / Monitoring?

**Answer: YES - Full parallelization possible**

#### Resource Independence Matrix

| Task | Backend Dev | Frontend Dev | DevOps | Testing |
|------|-------------|--------------|--------|---------|
| **Phase A: Presets** | ✅ 20% | ✅ 30% | - | ✅ 20% |
| **Phase B: Extraction** | ✅ 60% | ✅ 40% | - | ✅ 30% |
| **Frontend Tests** | - | ✅ 60% | - | ✅ 100% |
| **Monitoring** | ✅ 30% | - | ✅ 80% | ✅ 20% |
| **CI/CD** | - | - | ✅ 100% | ✅ 40% |

#### Recommended Parallel Track Plan

**Track 1: Backend Engineer**
- Week 1: Phase A backend (PresetLibrary, API)
- Week 2: Phase B extraction service
- Week 3: Monitoring (Prometheus endpoint, health checks)

**Track 2: Frontend Engineer**
- Week 1: Phase A frontend (PresetSelector component)
- Week 2: Jest setup + component tests (50% coverage)
- Week 3: Phase B frontend (ImportWizard component)

**Track 3: DevOps Engineer** (can be part-time)
- Week 1: CI/CD pipeline (GitHub Actions)
- Week 2: Grafana dashboard setup
- Week 3: Production deployment docs

**Track 4: QA / Test Engineer** (can be part-time)
- Week 1-2: Write tests for Phase A
- Week 2-3: Write tests for Phase B
- Week 3: Load testing and monitoring validation

#### No Blocking Dependencies

**Phase A+B DO NOT block:**
- Frontend testing (different files, no conflicts)
- Monitoring setup (different endpoints)
- CI/CD (runs all tests regardless of features)

**Potential Conflicts (Minimal):**
- Merge conflicts in `api.py` if adding routers simultaneously
  - **Mitigation**: Phase A router first, then Phase B (sequential router addition)
- Test suite runtime increases
  - **Mitigation**: Parallel test execution in CI

#### Combined Timeline (3 Weeks)

**Week 1 Deliverables:**
- ✅ Phase A backend + frontend
- ✅ CI/CD pipeline operational
- ✅ Jest test framework setup

**Week 2 Deliverables:**
- ✅ Phase B extraction service
- ✅ Frontend tests (50% coverage)
- ✅ Prometheus metrics endpoint
- ✅ Grafana dashboard

**Week 3 Deliverables:**
- ✅ Phase B frontend wizard
- ✅ End-to-end tests for import flow
- ✅ Monitoring in production
- ✅ Documentation complete

---

## Success Metrics

### Phase A Success Criteria

**Functional:**
- [ ] 10+ strategy presets available
- [ ] Preset load time <100ms
- [ ] 100% of presets pass validation
- [ ] UI dropdown renders all presets with categorization

**Quality:**
- [ ] 30+ backend tests passing
- [ ] 20+ frontend tests passing
- [ ] Zero validation errors in preset JSON

**User Experience:**
- [ ] Strategy setup time reduced from 5 min → <1 min
- [ ] 80%+ user preference for presets over manual entry

### Phase B Success Criteria

**Functional:**
- [ ] Support GitHub URL, PDF, text, code snippet sources
- [ ] Extraction completes in <30 seconds
- [ ] Confidence score calculated accurately
- [ ] User review step prevents all misconfigurations

**Quality:**
- [ ] Extraction accuracy >85% for supported strategy types
- [ ] 40+ backend tests passing
- [ ] 25+ frontend tests passing

**User Experience:**
- [ ] 90%+ of users trust high-confidence extractions
- [ ] <5% false positives (incorrect extractions with high confidence)

**Cost:**
- [ ] Monthly API cost <$50 for expected usage
- [ ] Cache hit rate >60%

---

## Future Enhancements (Phase 3+)

1. **User Custom Presets**
   - Save extracted configs as personal presets
   - Share community presets
   - Preset versioning

2. **Batch Extraction**
   - Import multiple strategies from single paper
   - Compare extracted configs side-by-side

3. **Strategy Code Generation**
   - Generate complete BaseStrategy implementation
   - Export to Python file for customization

4. **Learning & Feedback Loop**
   - Track extraction accuracy
   - User feedback on extractions
   - Improve prompts based on feedback

5. **Multi-Language Support**
   - Extract from R, Julia, C++ strategy code
   - Cross-language parameter mapping

---

## Appendix: Example Presets

### A1: RapidTrader RSI Mean Reversion

(Full JSON shown in Data Model section)

### A2: Turtle Trader Breakout

```json
{
  "id": "turtle-trader-breakout",
  "name": "Turtle Trader 20-Day Breakout",
  "description": "Classic Turtle Trader strategy with 20-day breakout entries and ATR-based position sizing",
  "category": "trend_following",
  "tags": ["breakout", "trend", "turtle"],
  "source": {
    "type": "book",
    "author": "Curtis Faith",
    "date": "1983-01-01"
  },
  "config": {
    "mode": "portfolio",
    "strategy": {
      "type": "breakout",
      "params": {
        "entry_period": 20,
        "exit_period": 10
      }
    },
    "position_sizing": {
      "method": "atr",
      "base_risk_per_trade": 0.02,
      "atr_period": 20,
      "unit_limit": 4
    },
    "risk_management": {
      "stop_loss": {
        "enabled": true,
        "method": "atr",
        "atr_multiplier": 2.0
      }
    }
  }
}
```

### A3: Simple MA Golden Cross

```json
{
  "id": "ma-golden-cross-simple",
  "name": "Simple MA Golden Cross (50/200)",
  "description": "Basic trend following with 50/200 day moving average crossover",
  "category": "trend_following",
  "tags": ["ma", "simple", "beginner"],
  "config": {
    "mode": "single",
    "strategy": {
      "type": "ma_crossover",
      "params": {
        "fast_period": 50,
        "slow_period": 200
      }
    },
    "position_sizing": {
      "method": "fixed_fractional",
      "position_size": 0.10
    }
  }
}
```

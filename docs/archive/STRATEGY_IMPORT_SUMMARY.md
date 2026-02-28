# Strategy Import System - Quick Summary

**Status**: Design Complete (2026-02-21)
**Full Design**: See [STRATEGY_IMPORT_DESIGN.md](STRATEGY_IMPORT_DESIGN.md)

## Overview

Two-phase system to dramatically reduce time required to test external strategies (papers, GitHub repos):

**Current State**: 5-10 minutes of manual parameter extraction
**Target State**: <1 minute with presets, <2 minutes with LLM extraction

---

## Phase A: Strategy Preset Library

### What It Is
- JSON-based strategy templates with complete configurations
- One-click load into backtest form
- 10+ initial presets covering common strategies

### Key Features
- Categorized presets (mean reversion, trend following, momentum, etc.)
- Metadata with source URLs, authors, descriptions
- Complete config including strategy params, position sizing, risk management
- No code execution (pure configuration)

### Implementation Effort
- **Time**: 1-2 weeks
- **Complexity**: Low
- **Backend**: 2 days (PresetLibrary class, API endpoints)
- **Frontend**: 3 days (PresetSelector component, UI)
- **Testing**: 2 days (50+ tests)

### Example Use Case
```
Before: Read RapidTrader code → Extract 12+ params → Enter manually → Run
After:  Select "RapidTrader RSI" preset → Run
```

---

## Phase B: LLM-Assisted Parameter Extraction

### What It Is
- Import wizard accepting GitHub URLs, PDFs, text, code snippets
- Claude API extracts strategy parameters automatically
- User reviews extracted config before running

### Key Features
- Multi-source support (GitHub, PDF, text, code)
- Confidence scoring (0-1) with quality levels
- Lists assumptions and warnings
- Matches to existing presets (prevents duplication)
- Rate limiting (10/hour) to prevent API abuse
- Cost: ~$0.03 per extraction

### Implementation Effort
- **Time**: 1-2 weeks
- **Complexity**: Medium
- **Backend**: 3 days (StrategyExtractor, content fetchers, LLM prompts)
- **Frontend**: 3 days (ImportWizard component, multi-step flow)
- **Testing**: 2 days (40+ tests)

### Example Use Case
```
1. Paste GitHub URL: https://github.com/user/strategy-repo
2. Click "Extract Parameters"
3. Review extracted config (confidence: 87%)
4. Edit if needed
5. Load into backtest form
```

---

## Technology Stack

**Phase A:**
- Pydantic models for schema validation
- JSON file storage (`src/strategies/preset_data.json`)
- FastAPI router (`/api/v1/presets`)
- Vanilla JS component (`PresetSelector.js`)

**Phase B:**
- Claude 3.7 Sonnet API
- PyPDF2 for PDF parsing
- GitHub API for repo content
- FastAPI router (`/api/v1/strategy/import`)
- Multi-step wizard component (`StrategyImportWizard.js`)

---

## Security Considerations

**What This Does:**
- ✅ Extracts configuration parameters only
- ✅ Requires user review before execution
- ✅ No arbitrary code execution
- ✅ Rate limiting prevents abuse

**What This Does NOT Do:**
- ❌ Execute arbitrary code
- ❌ Auto-run backtests without review
- ❌ Store API keys in database
- ❌ Allow dynamic code loading

---

## Success Metrics

### Phase A
- [ ] 10+ presets available covering common strategies
- [ ] Preset load time <100ms
- [ ] 80%+ user preference for presets over manual entry
- [ ] Strategy setup time: 5-10 min → <1 min

### Phase B
- [ ] Extraction accuracy >85% for supported strategy types
- [ ] User review catches 100% of misconfigurations
- [ ] Extraction completes in <30 seconds
- [ ] Monthly API cost <$50
- [ ] Cache hit rate >60%

---

## Parallelization with Other Work

**Can run fully in parallel with:**
- ✅ Frontend testing (Jest + Testing Library setup)
- ✅ Production monitoring (Prometheus + Grafana)
- ✅ CI/CD pipeline (GitHub Actions)

**No blocking dependencies** - separate code paths, minimal merge conflicts

---

## Implementation Checklist

### Phase A: Presets (Weeks 1-2)

**Week 1: Backend**
- [ ] Create `src/strategies/presets.py` with PresetLibrary class
- [ ] Define Pydantic models (StrategyPreset, PresetConfig, PresetSource)
- [ ] Create initial 10 presets in `src/strategies/preset_data.json`
  - [ ] RapidTrader RSI Mean Reversion
  - [ ] RapidTrader Combined (RSI + MA)
  - [ ] Turtle Trader Breakout
  - [ ] Simple MA Golden Cross
  - [ ] RSI Basic (no risk management)
  - [ ] Momentum Rotation
  - [ ] Conservative Mean Reversion
  - [ ] Aggressive Trend Following
  - [ ] Value Averaging
  - [ ] Swing Trading
- [ ] Implement validation logic
- [ ] Create API router `src/api_presets.py`
  - [ ] `GET /api/v1/presets` - List all presets
  - [ ] `GET /api/v1/presets/{id}` - Get specific preset
- [ ] Write 30+ backend tests in `tests/test_presets.py`

**Week 2: Frontend**
- [ ] Create `frontend/src/components/PresetSelector.js`
- [ ] Add category filtering
- [ ] Implement preset card UI
- [ ] Add preview modal
- [ ] Create CSS styles in `frontend/src/styles/preset-selector.css`
- [ ] Integrate with main app (update `main.js`)
- [ ] Add notification system
- [ ] Write 20+ frontend tests
- [ ] Update `docs/API.md` with preset endpoints
- [ ] User testing and refinement

### Phase B: LLM Extraction (Weeks 3-4)

**Week 3: Backend**
- [ ] Create `src/extraction/` module
- [ ] Implement `StrategyExtractor` class
- [ ] Create content fetchers
  - [ ] GitHub URL fetcher (API client)
  - [ ] PDF parser (PyPDF2)
  - [ ] Text/code snippet handler
- [ ] Write LLM prompts in `src/extraction/prompts.py`
- [ ] Implement confidence scoring algorithm
- [ ] Create similarity matching (find matching presets)
- [ ] Add API router `src/api_extraction.py`
  - [ ] `POST /api/v1/strategy/import` - Extract from source
- [ ] Add rate limiting
- [ ] Write 40+ backend tests in `tests/test_extraction.py`
- [ ] Set up ANTHROPIC_API_KEY environment variable

**Week 4: Frontend**
- [ ] Create `frontend/src/components/StrategyImportWizard.js`
- [ ] Implement 4-step wizard flow
  - [ ] Step 1: Input type selection
  - [ ] Step 2: Extraction progress
  - [ ] Step 3: Review results
  - [ ] Step 4: Confirm and load
- [ ] Add source type selector UI
- [ ] Implement extraction progress animation
- [ ] Add review/edit interface
- [ ] Create CSS styles in `frontend/src/styles/import-wizard.css`
- [ ] Add file upload handling (PDF)
- [ ] Write 25+ frontend tests
- [ ] Update documentation
- [ ] User testing and refinement

---

## File Structure

```
src/
├── strategies/
│   ├── presets.py              # NEW: PresetLibrary class
│   └── preset_data.json        # NEW: Preset definitions
├── extraction/                 # NEW: LLM extraction module
│   ├── __init__.py
│   ├── extractor.py            # StrategyExtractor class
│   ├── content_fetcher.py      # GitHub, PDF fetching
│   ├── prompts.py              # LLM prompts
│   ├── validator.py            # Config validation
│   └── similarity.py           # Preset matching
├── api_presets.py              # NEW: Preset API router
└── api_extraction.py           # NEW: Extraction API router

frontend/src/
├── components/
│   ├── PresetSelector.js       # NEW: Preset selector
│   └── StrategyImportWizard.js # NEW: Import wizard
└── styles/
    ├── preset-selector.css     # NEW: Preset styles
    └── import-wizard.css       # NEW: Wizard styles

tests/
├── test_presets.py             # NEW: Preset tests (30+)
└── test_extraction.py          # NEW: Extraction tests (40+)

docs/
├── STRATEGY_IMPORT_DESIGN.md   # NEW: Full design spec
└── STRATEGY_IMPORT_SUMMARY.md  # NEW: This file
```

---

## API Endpoints

### Phase A: Presets

```
GET /api/v1/presets
  Query params:
    - category (optional): Filter by category
    - tag (optional): Filter by tag
  Response:
    - presets: List of presets
    - total: Count
    - categories: Available categories

GET /api/v1/presets/{preset_id}
  Response:
    - preset: Full preset config
    - warnings: Validation warnings
    - compatible: Boolean
```

### Phase B: Extraction

```
POST /api/v1/strategy/import
  Body:
    - source_type: "github_url" | "pdf" | "text" | "code_snippet"
    - content: URL or text content
    - hints: Optional extraction hints
    - save_as_preset: Boolean
    - preset_name: Optional name
  Response:
    - config: Extracted configuration
    - confidence: 0-1 score
    - extraction_quality: "high" | "medium" | "low"
    - warnings: List of issues
    - assumptions: List of assumptions
    - matched_preset_id: Similar preset (if any)
    - match_similarity: Similarity score
```

---

## Cost Analysis

### Phase B API Costs (Anthropic)

**Per Extraction:**
- Input tokens: ~2,000 (~$0.006)
- Output tokens: ~1,000 (~$0.015)
- Total: ~$0.021 per extraction

**Monthly Budget:**
- 1,000 extractions: ~$21
- 2,000 extractions: ~$42
- 5,000 extractions: ~$105

**Rate Limiting:**
- 10 extractions/hour per user
- ~300 extractions/month per user max
- Cost per user: ~$6.30/month

**Caching:**
- 24-hour cache on content hash
- Expected 60-70% cache hit rate
- Reduces costs by ~65%

---

## Next Steps

1. **Review design document** ([STRATEGY_IMPORT_DESIGN.md](STRATEGY_IMPORT_DESIGN.md))
2. **Prioritize Phase A vs Phase B** (recommend Phase A first)
3. **Set up development environment**
   - Install additional dependencies (anthropic, PyPDF2, requests)
   - Get ANTHROPIC_API_KEY for Phase B
4. **Create feature branch** (`git checkout -b feature/strategy-import`)
5. **Follow implementation checklist** above
6. **Run tests continuously** during development
7. **Deploy to staging** for user testing
8. **Measure success metrics** after deployment

---

## Questions for Discussion

1. **Priority**: Should Phase A and B be implemented sequentially or in parallel?
2. **Initial presets**: Which 10 strategies should be included in Phase A?
3. **LLM model**: Claude 3.7 Sonnet vs. other models (Haiku for cost, Opus for accuracy)?
4. **Rate limits**: Is 10/hour appropriate, or should it be higher/lower?
5. **User custom presets**: Save to database immediately or defer to Phase 3?
6. **GitHub authentication**: Anonymous API (60 req/hour) or authenticated (5000 req/hour)?

---

## References

- **Full Design**: [STRATEGY_IMPORT_DESIGN.md](STRATEGY_IMPORT_DESIGN.md)
- **Decision Log Entry**: [DECISION_LOG.md](DECISION_LOG.md#phase-25---strategy-import-system-design-2026-02-21)
- **Strategy SDK**: [STRATEGY_SDK.md](STRATEGY_SDK.md)
- **API Documentation**: [API.md](API.md)

import { BacktestAPI } from '../services/api.js';

export class UniverseValidator {
  constructor(container) {
    this.container = container;
    this.result = null;
    this.detailsOpen = false;
    this.onAdjustDate = null; // callback: (dateStr) => void
    this._debounceTimer = null;
  }

  scheduleValidation(symbols, startDate, endDate) {
    clearTimeout(this._debounceTimer);
    this._debounceTimer = setTimeout(() => {
      this.validate(symbols, startDate, endDate);
    }, 500);
  }

  async validate(symbols, startDate, endDate) {
    if (!symbols || symbols.length === 0 || !startDate || !endDate) {
      this.clear();
      return;
    }

    try {
      const payload = { symbols, start: startDate, end: endDate };
      console.log('[UniverseValidator] request:', payload);
      this.result = await BacktestAPI.validateSP500Symbols(payload);
      console.log('[UniverseValidator] response:', this.result);
      this.detailsOpen = false;
      this.render();
    } catch (err) {
      console.error('[UniverseValidator] error:', err);
      this.clear();
    }
  }

  clear() {
    this.result = null;
    this.container.innerHTML = '';
  }

  render() {
    if (!this.result) {
      this.container.innerHTML = '';
      return;
    }

    const r = this.result;
    const risk = r.survivorship_bias_risk || 'unknown';
    const riskClass = `validation-panel__risk--${risk}`;
    const totalSymbols = (r.full_members?.length || 0)
      + (r.partial_members?.length || 0)
      + (r.non_members?.length || 0)
      + (r.not_found?.length || 0);

    const riskTitle = this.getRiskTitle(risk);
    const toggleLabel = this.detailsOpen ? '\u25B2' : '\u25BC';

    let html = `
      <div class="validation-panel">
        <div class="validation-panel__header" id="validationToggle">
          <div class="validation-panel__risk ${riskClass}">
            <span class="validation-panel__risk-dot"></span>
            ${riskTitle}
          </div>
          <span class="validation-panel__summary">${r.bias_summary || ''}</span>
          <button type="button" class="validation-panel__toggle">${toggleLabel}</button>
        </div>
        <div class="validation-panel__details ${this.detailsOpen ? 'validation-panel__details--open' : ''}">
          ${this.renderDetails(r, totalSymbols)}
        </div>
        ${this.renderActions(r)}
      </div>
    `;

    this.container.innerHTML = html;
    this.attachEvents();
  }

  getRiskTitle(risk) {
    const titles = {
      none: 'BIAS: NONE',
      low: 'BIAS: LOW',
      medium: 'BIAS: MED',
      high: 'BIAS: HIGH',
      unknown: 'BIAS: N/A',
    };
    return titles[risk] || 'BIAS CHECK';
  }

  renderDetails(r, totalSymbols) {
    let rows = '';

    // Large portfolio: summary counts first
    if (totalSymbols > 50) {
      rows += `<div class="validation-panel__symbol" style="font-style:italic;">
        ${r.full_members?.length || 0} full, ${r.partial_members?.length || 0} partial,
        ${r.non_members?.length || 0} not in S&P 500, ${r.not_found?.length || 0} unknown
      </div>`;
    }

    // Full members
    if (r.full_members) {
      for (const sym of r.full_members) {
        rows += this.renderSymbolRow(sym, 'Full member', 100);
      }
    }

    // Partial members
    if (r.partial_members) {
      for (const m of r.partial_members) {
        const pct = Math.round((m.coverage_pct || 0) * 100);
        let status = 'Partial';
        if (m.periods && m.periods.length > 0) {
          const lastPeriod = m.periods[m.periods.length - 1];
          if (lastPeriod[1]) {
            status = `Removed: ${this.formatDate(lastPeriod[1])}`;
          }
        }
        rows += this.renderSymbolRow(m.symbol, status, pct);
      }
    }

    // Non-members
    if (r.non_members) {
      for (const m of r.non_members) {
        let status = 'Not in S&P 500';
        if (m.first_join_date) {
          status = `Joined: ${this.formatDate(m.first_join_date)}`;
        }
        rows += this.renderSymbolRow(m.symbol, status, 0);
      }
    }

    // Not found
    if (r.not_found) {
      for (const sym of r.not_found) {
        rows += this.renderSymbolRow(sym, 'No data', 0);
      }
    }

    return rows;
  }

  renderActions(r) {
    if (!r.earliest_overlap_date || !this.onAdjustDate) return '';
    return `
      <div class="validation-panel__actions">
        <button type="button" class="validation-panel__adjust-btn" id="adjustDateBtn">
          ADJUST START DATE TO ${this.formatDate(r.earliest_overlap_date)}
        </button>
      </div>
    `;
  }

  renderSymbolRow(symbol, status, pct) {
    const fillColor = pct === 100 ? '#22c55e' : pct === 0 ? '#ef4444' : '#eab308';
    return `
      <div class="validation-panel__symbol">
        <span class="validation-panel__symbol-name">${symbol}</span>
        <span class="validation-panel__symbol-status">${status}</span>
        <span class="validation-panel__symbol-pct">${pct}%</span>
        <div class="validation-panel__coverage-bar">
          <div class="validation-panel__coverage-fill" style="width:${pct}%;background:${fillColor};"></div>
        </div>
      </div>
    `;
  }

  attachEvents() {
    const toggle = this.container.querySelector('#validationToggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        this.detailsOpen = !this.detailsOpen;
        this.render();
      });
    }

    const adjustBtn = this.container.querySelector('#adjustDateBtn');
    if (adjustBtn && this.onAdjustDate) {
      adjustBtn.addEventListener('click', () => {
        this.onAdjustDate(this.result.earliest_overlap_date);
      });
    }
  }

  formatDate(dateStr) {
    try {
      const d = new Date(dateStr + 'T00:00:00');
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  }
}

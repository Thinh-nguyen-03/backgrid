import { BacktestAPI } from '../services/api.js';
import { getHistory } from '../services/storage.js';

const METRIC_LABELS = {
  average_return:      'Avg Return',
  average_sharpe:      'Avg Sharpe',
  average_max_drawdown:'Avg Drawdown',
  total_trades:        'Total Trades',
  symbols_completed:   'Symbols OK',
  symbols_failed:      'Symbols Failed',
  runtime_seconds:     'Runtime',
};

const HIGHER_IS_BETTER = new Set(['average_return', 'average_sharpe', 'symbols_completed']);
const LOWER_IS_BETTER  = new Set(['average_max_drawdown', 'symbols_failed', 'runtime_seconds']);

function fmtMetric(key, v) {
  if (v == null) return '—';
  if (key.includes('return') || key.includes('drawdown')) return (v * 100).toFixed(2) + '%';
  if (key.includes('sharpe'))  return v.toFixed(3);
  if (key.includes('runtime')) return v.toFixed(2) + 's';
  return String(v);
}

function fmtDelta(key, delta) {
  if (delta == null) return { text: '—', cls: '' };
  const sign = delta >= 0 ? '+' : '';
  let text;
  if (key.includes('return') || key.includes('drawdown')) text = sign + (delta * 100).toFixed(2) + '%';
  else if (key.includes('sharpe'))  text = sign + delta.toFixed(3);
  else if (key.includes('runtime')) text = sign + delta.toFixed(2) + 's';
  else text = sign + delta;

  let cls = '';
  if (HIGHER_IS_BETTER.has(key)) cls = delta > 0 ? 'diff-delta--pos' : delta < 0 ? 'diff-delta--neg' : '';
  if (LOWER_IS_BETTER.has(key))  cls = delta < 0 ? 'diff-delta--pos' : delta > 0 ? 'diff-delta--neg' : '';
  return { text, cls };
}

export class DiffModal {
  constructor() {
    this.overlay = null;
  }

  open(currentBatchId = null) {
    const history = getHistory().filter(e => e.mode === 'portfolio');
    this.overlay = document.createElement('div');
    this.overlay.className = 'modal-overlay';

    if (history.length < 2) {
      this.overlay.innerHTML = `
        <div class="modal" style="max-width:460px;">
          <div class="modal__header">
            COMPARE BACKTEST RUNS
            <button class="modal__close" id="diffClose">×</button>
          </div>
          <div class="modal__body">
            <p class="diff-note">At least 2 portfolio runs are needed. Run more portfolio backtests to enable comparison.</p>
          </div>
        </div>
      `;
    } else {
      const options = history.map(e => {
        const d = new Date(e.timestamp);
        const label = `${(e.strategy || 'unknown').toUpperCase()}  ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
        return `<option value="${e.id}">${label}</option>`;
      }).join('');

      this.overlay.innerHTML = `
        <div class="modal" style="max-width:720px;">
          <div class="modal__header">
            COMPARE BACKTEST RUNS
            <button class="modal__close" id="diffClose">×</button>
          </div>
          <div class="modal__body">
            <div class="diff-selectors">
              <div class="diff-selector">
                <label class="diff-selector__label">RUN A</label>
                <select class="diff-selector__select" id="diffRunA">${options}</select>
              </div>
              <div class="diff-vs">VS</div>
              <div class="diff-selector">
                <label class="diff-selector__label">RUN B</label>
                <select class="diff-selector__select" id="diffRunB">${options}</select>
              </div>
              <button type="button" id="diffCompareBtn" class="diff-compare-btn">COMPARE</button>
            </div>
            <div id="diffResults"></div>
          </div>
        </div>
      `;

      if (currentBatchId) {
        const selA = this.overlay.querySelector('#diffRunA');
        const opt = [...selA.options].find(o => o.value === currentBatchId);
        if (opt) selA.value = currentBatchId;
        const selB = this.overlay.querySelector('#diffRunB');
        if (selB.options.length > 1) {
          selB.selectedIndex = selA.selectedIndex === 0 ? 1 : 0;
        }
      }

      this.overlay.querySelector('#diffCompareBtn').addEventListener('click', () => this._compare());
    }

    document.body.appendChild(this.overlay);
    this.overlay.querySelector('#diffClose').addEventListener('click', () => this.close());
    this.overlay.addEventListener('click', e => { if (e.target === this.overlay) this.close(); });
  }

  async _compare() {
    const a = this.overlay.querySelector('#diffRunA')?.value;
    const b = this.overlay.querySelector('#diffRunB')?.value;
    const el = this.overlay.querySelector('#diffResults');

    if (!a || !b) return;
    if (a === b) {
      el.innerHTML = '<div class="diff-error">Select two different runs to compare.</div>';
      return;
    }

    el.innerHTML = '<div class="diff-loading">Loading...</div>';
    try {
      const diff = await BacktestAPI.diffBacktests(a, b);
      this._renderDiff(diff, el);
    } catch (err) {
      el.innerHTML = `<div class="diff-error">${err.message}</div>`;
    }
  }

  _renderDiff(diff, el) {
    const params    = diff.strategy_diff?.params ?? {};
    const dateRange = diff.date_range_diff ?? {};

    let paramRows = '';
    if (diff.strategy_diff?.strategy) {
      const s = diff.strategy_diff.strategy;
      paramRows += `<tr>
        <td class="diff-table__key">strategy</td>
        <td>${s.a ?? '—'}</td>
        <td class="diff-table__arrow">→</td>
        <td>${s.b ?? '—'}</td>
        <td class="diff-delta">—</td>
      </tr>`;
    }
    for (const [key, val] of Object.entries(params)) {
      const d    = val.b != null && val.a != null ? val.b - val.a : null;
      const dStr = d != null ? (d >= 0 ? `+${d}` : `${d}`) : '—';
      paramRows += `<tr>
        <td class="diff-table__key">${key}</td>
        <td>${val.a ?? '—'}</td>
        <td class="diff-table__arrow">→</td>
        <td>${val.b ?? '—'}</td>
        <td class="diff-delta">${dStr}</td>
      </tr>`;
    }
    for (const [key, val] of Object.entries(dateRange)) {
      paramRows += `<tr>
        <td class="diff-table__key">${key}</td>
        <td>${val.a ?? '—'}</td>
        <td class="diff-table__arrow">→</td>
        <td>${val.b ?? '—'}</td>
        <td class="diff-delta">—</td>
      </tr>`;
    }

    let metricRows = '';
    for (const [key, val] of Object.entries(diff.metric_diff ?? {})) {
      const label  = METRIC_LABELS[key] ?? key;
      const { text, cls } = fmtDelta(key, val.delta);
      metricRows += `<tr>
        <td class="diff-table__key">${label}</td>
        <td>${fmtMetric(key, val.a)}</td>
        <td>${fmtMetric(key, val.b)}</td>
        <td class="diff-delta ${cls}">${text}</td>
      </tr>`;
    }

    const symbolsA = (diff.symbols_a || []).join(', ') || 'N/A';
    const symbolsB = (diff.symbols_b || []).join(', ') || 'N/A';

    el.innerHTML = `
      <div class="diff-section">
        <div class="diff-section__title">PARAMETERS</div>
        ${paramRows
          ? `<table class="diff-table">
               <thead><tr><th>Parameter</th><th>Run A</th><th></th><th>Run B</th><th>Delta</th></tr></thead>
               <tbody>${paramRows}</tbody>
             </table>`
          : '<div class="diff-note">No parameter differences.</div>'}
      </div>
      <div class="diff-section">
        <div class="diff-section__title">METRICS</div>
        ${metricRows
          ? `<table class="diff-table diff-table--metrics">
               <thead><tr><th>Metric</th><th>Run A</th><th>Run B</th><th>Delta</th></tr></thead>
               <tbody>${metricRows}</tbody>
             </table>`
          : '<div class="diff-note">No metric data.</div>'}
      </div>
      <div class="diff-symbols">
        <span class="diff-symbols__label">Symbols A:</span> ${symbolsA}
        <span class="diff-symbols__label" style="margin-left:1.5rem;">Symbols B:</span> ${symbolsB}
      </div>
    `;
  }

  close() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
  }
}

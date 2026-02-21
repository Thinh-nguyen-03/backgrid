import { getHistory, addHistoryEntry, clearHistory } from '../services/storage.js';
import { fmtNum, fmtPct } from '../services/utils.js';

export class JobHistory {
  constructor(container) {
    this.container = container;
    this.onLoad = null; // callback for loading a result
  }

  render() {
    const entries = getHistory();

    if (entries.length === 0) {
      this.container.innerHTML = '';
      return;
    }

    const rows = entries.map((e, i) => `
      <div class="history-item">
        <div class="history-item__header">
          <span class="history-item__symbol">${e.symbols.join(', ')}</span>
          <span class="history-item__sharpe ${e.sharpe >= 0 ? 'text-green' : 'text-red'}">${fmtNum(e.sharpe, 2)}</span>
        </div>
        <div class="history-item__details">
          <span class="history-item__strategy">${e.strategy}</span>
          <span class="history-item__divider">|</span>
          <span class="history-item__mode">${e.mode}</span>
        </div>
        <div class="history-item__timestamp">${new Date(e.timestamp).toLocaleDateString()} ${new Date(e.timestamp).toLocaleTimeString()}</div>
      </div>
    `).join('');

    this.container.innerHTML = `
      <details class="config-section config-section--history" open>
        <summary class="section-badge section-badge--muted">
          Recent Backtests (${entries.length})
        </summary>
        <div class="history-list">
          ${rows}
        </div>
        <button type="button" id="clearHistoryBtn" class="btn-sm btn-sm--danger" style="margin-top:1rem; width:100%;">CLEAR HISTORY</button>
      </details>
    `;

    this.container.querySelector('#clearHistoryBtn')?.addEventListener('click', () => {
      clearHistory();
      this.render();
    });
  }

  saveEntry(data) {
    addHistoryEntry(data);
    this.render();
  }
}

import { BacktestAPI } from '../services/api.js';
import { fmtNum, fmtPct, escapeHtml } from '../services/utils.js';

export class TradeLedgerModal {
  constructor() {
    this.overlay = null;
    this.batchId = null;
    this.offset = 0;
    this.limit = 50;
    this.totalTrades = 0;
  }

  async open(batchId) {
    this.batchId = batchId;
    this.offset = 0;

    this.overlay = document.createElement('div');
    this.overlay.className = 'modal-overlay';
    this.overlay.innerHTML = `
      <div class="modal">
        <div class="modal__header">
          <span>Trade Ledger</span>
          <button class="modal__close" id="closeLedger">X</button>
        </div>
        <div class="modal__body">
          <div class="modal__filters">
            <div class="input-group">
              <label>Symbol</label>
              <input type="text" id="filterSymbol" placeholder="All">
            </div>
            <div class="input-group">
              <label>Strategy</label>
              <input type="text" id="filterStrategy" placeholder="All">
            </div>
            <button type="button" class="btn-sm" id="applyFilters" style="align-self:flex-end;">Filter</button>
            <button type="button" class="btn-sm" id="exportCsv" style="align-self:flex-end;">Export CSV</button>
          </div>
          <div id="tradesContainer">Loading...</div>
          <div class="pagination" id="tradesPagination"></div>
        </div>
      </div>
    `;

    document.body.appendChild(this.overlay);

    this.overlay.querySelector('#closeLedger').addEventListener('click', () => this.close());
    this.overlay.addEventListener('click', (e) => { if (e.target === this.overlay) this.close(); });
    this.overlay.querySelector('#applyFilters').addEventListener('click', () => { this.offset = 0; this.loadTrades(); });
    this.overlay.querySelector('#exportCsv').addEventListener('click', () => this.exportCsv());

    await this.loadTrades();
  }

  close() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
  }

  async loadTrades() {
    const container = this.overlay.querySelector('#tradesContainer');
    container.innerHTML = '<div class="loading-pulse" style="padding:1rem;">Loading trades...</div>';

    const params = {
      limit: this.limit,
      offset: this.offset,
    };

    const symbolFilter = this.overlay.querySelector('#filterSymbol').value.trim();
    const strategyFilter = this.overlay.querySelector('#filterStrategy').value.trim();
    if (symbolFilter) params.symbol = symbolFilter.toUpperCase();
    if (strategyFilter) params.strategy = strategyFilter;

    try {
      const data = await BacktestAPI.getPortfolioTrades(this.batchId, params);
      this.totalTrades = data.total_trades;
      this.renderTrades(data.trades);
      this.renderPagination();
    } catch (err) {
      container.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
    }
  }

  renderTrades(trades) {
    const container = this.overlay.querySelector('#tradesContainer');

    if (trades.length === 0) {
      container.innerHTML = '<div style="padding:1rem; font-family:var(--font-mono);">No trades found.</div>';
      return;
    }

    const rows = trades.map(t => `
      <tr>
        <td>${t.entry_date ? new Date(t.entry_date).toLocaleDateString() : 'N/A'}</td>
        <td>${t.exit_date ? new Date(t.exit_date).toLocaleDateString() : 'Open'}</td>
        <td style="font-weight:700;">${escapeHtml(t.symbol)}</td>
        <td>${t.side}</td>
        <td class="text-right">${t.shares}</td>
        <td class="text-right">${fmtNum(t.entry_price, 2)}</td>
        <td class="text-right">${fmtNum(t.exit_price, 2)}</td>
        <td class="text-right ${t.pnl >= 0 ? 'text-green' : 'text-red'}">${fmtNum(t.pnl, 2)}</td>
        <td class="text-right">${fmtPct(t.pnl_pct)}</td>
        <td>${escapeHtml(t.strategy || 'N/A')}</td>
        <td class="text-right">${fmtNum(t.transaction_costs, 2)}</td>
      </tr>
    `).join('');

    container.innerHTML = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Entry</th><th>Exit</th><th>Symbol</th><th>Side</th>
            <th>Shares</th><th>Entry $</th><th>Exit $</th><th>P&L</th>
            <th>P&L %</th><th>Strategy</th><th>Tx Costs</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  renderPagination() {
    const pag = this.overlay.querySelector('#tradesPagination');
    const page = Math.floor(this.offset / this.limit) + 1;
    const totalPages = Math.ceil(this.totalTrades / this.limit);

    pag.innerHTML = `
      <button id="prevPage" ${this.offset === 0 ? 'disabled' : ''}>Prev</button>
      <span>Page ${page} of ${totalPages} (${this.totalTrades} trades)</span>
      <button id="nextPage" ${this.offset + this.limit >= this.totalTrades ? 'disabled' : ''}>Next</button>
    `;

    pag.querySelector('#prevPage').addEventListener('click', () => {
      this.offset = Math.max(0, this.offset - this.limit);
      this.loadTrades();
    });
    pag.querySelector('#nextPage').addEventListener('click', () => {
      this.offset += this.limit;
      this.loadTrades();
    });
  }

  async exportCsv() {
    try {
      const data = await BacktestAPI.getPortfolioTrades(this.batchId, { limit: 10000, offset: 0 });
      const headers = ['Entry Date', 'Exit Date', 'Symbol', 'Side', 'Shares', 'Entry Price', 'Exit Price', 'P&L', 'P&L %', 'Strategy', 'Tx Costs'];
      const rows = data.trades.map(t => [
        t.entry_date, t.exit_date, t.symbol, t.side, t.shares,
        t.entry_price, t.exit_price, t.pnl, t.pnl_pct, t.strategy, t.transaction_costs,
      ]);

      const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trades_${this.batchId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Export failed: ' + err.message);
    }
  }
}

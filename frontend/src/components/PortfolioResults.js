import { fmtNum, fmtPct, colorClass } from '../services/utils.js';
import { EquityCurveChart } from './EquityCurveChart.js';

export class PortfolioResults {
  constructor(container) {
    this.container = container;
    this.onViewTrades = null; // callback
    this.equityCurveChart = null;
  }

  formatPortfolioLog(data) {
    const sections = [
      {
        title: 'Portfolio Overview',
        items: [
          { key: 'batch_id', label: 'Batch ID', value: data.batch_id },
          { key: 'symbols_requested', label: 'Symbols Requested', value: data.symbols_requested },
          { key: 'symbols_completed', label: 'Symbols Completed', value: data.symbols_completed },
          { key: 'symbols_failed', label: 'Symbols Failed', value: data.symbols_failed },
          { key: 'status', label: 'Status', value: data.status },
        ]
      },
      {
        title: 'Aggregate Performance',
        items: [
          { key: 'average_sharpe', label: 'Average Sharpe', value: fmtNum(data.average_sharpe, 3) },
          { key: 'average_return', label: 'Average Return', value: fmtPct(data.average_return) },
          { key: 'average_max_drawdown', label: 'Average Drawdown', value: fmtPct(data.average_max_drawdown) },
          { key: 'total_trades', label: 'Total Trades', value: data.total_trades || 0 },
        ]
      },
      {
        title: 'Top & Bottom',
        items: [
          { key: 'best_symbol', label: 'Best Symbol', value: data.best_symbol || 'N/A' },
          { key: 'worst_symbol', label: 'Worst Symbol', value: data.worst_symbol || 'N/A' },
        ]
      }
    ];

    return sections.map(section => `
      <div class="log-section">
        <div class="log-section__header">${section.title}</div>
        <div class="log-section__grid">
          ${section.items.filter(item => data[item.key] != null).map(item => `
            <div class="log-item">
              <span class="log-item__label">${item.label}</span>
              <span class="log-item__value">${item.value}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }

  render(data) {
    const summary = `
      <div class="portfolio-summary">
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Symbols</div>
          <div class="portfolio-summary__value">${data.symbols_completed || 0} / ${data.symbols_requested}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Avg Sharpe</div>
          <div class="portfolio-summary__value">${fmtNum(data.average_sharpe, 3)}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Avg Return</div>
          <div class="portfolio-summary__value ${colorClass(data.average_return)}">${fmtPct(data.average_return)}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Avg Drawdown</div>
          <div class="portfolio-summary__value text-red">${fmtPct(data.average_max_drawdown)}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Best</div>
          <div class="portfolio-summary__value">${data.best_symbol || 'N/A'}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Worst</div>
          <div class="portfolio-summary__value">${data.worst_symbol || 'N/A'}</div>
        </div>
        <div class="portfolio-summary__item">
          <div class="portfolio-summary__label">Total Trades</div>
          <div class="portfolio-summary__value">${data.total_trades || 0}</div>
        </div>
      </div>
    `;

    let failedHtml = '';
    if (data.failed_symbols && data.failed_symbols.length > 0) {
      failedHtml = `
        <div class="failed-symbols">
          <div class="failed-symbols__title">Failed Symbols (${data.symbols_failed})</div>
          <div class="failed-symbols__list">${data.failed_symbols.join(', ')}</div>
        </div>
      `;
    }

    const results = data.results_by_symbol || {};
    const symbols = Object.keys(results);
    let tableHtml = '';

    if (symbols.length > 0) {
      const rows = symbols.map(sym => {
        const r = results[sym];
        return `
          <tr>
            <td style="font-weight:700;">${sym}</td>
            <td>${r.status}</td>
            <td class="text-right">${fmtNum(r.sharpe, 3)}</td>
            <td class="text-right ${colorClass(r.total_return)}">${fmtPct(r.total_return)}</td>
            <td class="text-right text-red">${fmtPct(r.max_drawdown)}</td>
            <td class="text-right">${r.total_trades ?? 'N/A'}</td>
            <td class="text-right">${r.win_rate != null ? fmtPct(r.win_rate) : 'N/A'}</td>
            <td class="text-right">${r.total_transaction_costs != null ? '$' + fmtNum(r.total_transaction_costs, 2) : 'N/A'}</td>
          </tr>
        `;
      }).join('');

      tableHtml = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Symbol</th><th>Status</th><th>Sharpe</th><th>Return</th>
              <th>Drawdown</th><th>Trades</th><th>Win Rate</th><th>Tx Costs</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    const logData = this.formatPortfolioLog(data);

    this.container.innerHTML = `
      ${summary}
      ${failedHtml}
      <div id="portfolioChartContainer"></div>
      ${tableHtml}
      <button type="button" id="viewTradesBtn" class="btn-sm" style="margin-top:1rem;">View Trade Ledger</button>
      <details class="console-output" style="margin-top:1rem;">
        <summary>
          <span class="console-output__icon">▸</span>
          <span class="console-output__title">SYSTEM LOG</span>
        </summary>
        <div class="console-output__content">
          ${logData}
        </div>
      </details>
    `;

    if (data.portfolio_equity_curve && data.portfolio_equity_curve.length > 0) {
      const chartEl = this.container.querySelector('#portfolioChartContainer');
      if (this.equityCurveChart) this.equityCurveChart.destroy();
      this.equityCurveChart = new EquityCurveChart(chartEl);
      this.equityCurveChart.render(data.portfolio_equity_curve, 'Portfolio Equity');
    }

    this.container.querySelector('#viewTradesBtn').addEventListener('click', () => {
      if (this.onViewTrades) this.onViewTrades(data.batch_id);
    });
  }
}

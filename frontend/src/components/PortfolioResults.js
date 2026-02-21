import { fmtNum, fmtPct, colorClass } from '../services/utils.js';
import { EquityCurveChart } from './EquityCurveChart.js';
import { formatSystemLog } from '../services/logFormatter.js';

export class PortfolioResults {
  constructor(container) {
    this.container = container;
    this.onViewTrades = null;
    this.equityCurveChart = null;
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

    const logText = formatSystemLog(data);

    this.container.innerHTML = `
      ${summary}
      ${failedHtml}
      <div id="portfolioChartContainer"></div>
      ${tableHtml}
      <button type="button" id="viewTradesBtn" class="btn-sm" style="margin-top:1rem;">View Trade Ledger</button>
      <div class="console-output console-output--collapsed" id="systemLog" style="margin-top:1rem;">
        <div class="console-output__header" id="systemLogHeader">
          <span class="console-output__icon">▸</span>
          <span class="console-output__title">SYSTEM LOG</span>
        </div>
        <div class="console-output__content">
          <pre class="console-output__json">${logText}</pre>
        </div>
      </div>
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

    const logHeader = this.container.querySelector('#systemLogHeader');
    const logContainer = this.container.querySelector('#systemLog');
    logHeader.addEventListener('click', () => {
      logContainer.classList.toggle('console-output--collapsed');
    });
  }
}

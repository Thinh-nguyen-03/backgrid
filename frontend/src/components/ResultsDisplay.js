import { fmtNum, fmtPct, colorClass } from '../services/utils.js';
import { formatSystemLog } from '../services/logFormatter.js';

export class ResultsDisplay {
  constructor(container) {
    this.container = container;
  }

  showEmpty() {
    this.container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__icon">///</div>
        <div class="empty-state__text">Awaiting Input Parameters</div>
      </div>
    `;
  }

  showLoading(message = 'Running backtest...') {
    this.container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__text loading-pulse">${message}</div>
        <div class="loading-bar" style="width: 200px; margin-top: 1.5rem;"></div>
      </div>
    `;
  }

  showError(message) {
    this.container.innerHTML = `<div class="error-box">ERROR: ${message}</div>`;
  }

  showSingleResult(data) {
    const cards = [
      { label: 'Sharpe Ratio', value: fmtNum(data.sharpe, 3), primary: true, cardClass: 'kpi-card--sharpe' },
      { label: 'Total Return', value: fmtPct(data.total_return), cls: colorClass(data.total_return), cardClass: 'kpi-card--return' },
      { label: 'Max Drawdown', value: fmtPct(data.max_drawdown), cls: 'text-red', cardClass: 'kpi-card--drawdown' },
      { label: 'Runtime', value: fmtNum(data.runtime_seconds, 2) + 's', cardClass: 'kpi-card--neutral' },
    ];

    if (data.total_trades != null && data.total_trades > 0) {
      cards.push({ label: 'Total Trades', value: data.total_trades.toString(), cardClass: 'kpi-card--neutral' });
    }
    if (data.win_rate != null && data.win_rate > 0) {
      cards.push({ label: 'Win Rate', value: fmtPct(data.win_rate), cardClass: 'kpi-card--neutral' });
    }
    if (data.total_transaction_costs != null) {
      cards.push({ label: 'Tx Costs', value: '$' + fmtNum(data.total_transaction_costs, 2), cardClass: 'kpi-card--neutral' });
    }

    let extra = '';
    if (data.strategies_used) {
      extra = `<div class="result-meta">
        Strategies: ${data.strategies_used.join(', ')} | Method: ${data.combination_method || 'N/A'}
      </div>`;
    }

    const logText = formatSystemLog(data);

    this.container.innerHTML = `
      ${extra}
      <div class="kpi-grid">
        ${cards.map(c => `
          <div class="kpi-card ${c.primary ? 'kpi-card--primary' : ''} ${c.cardClass || ''}">
            <div class="kpi-card__label">${c.label}</div>
            <div class="kpi-card__value ${c.cls || ''}">${c.value}</div>
          </div>
        `).join('')}
      </div>
      <div id="chartContainer"></div>
      <div class="console-output console-output--collapsed" id="systemLog">
        <div class="console-output__header" id="systemLogHeader">
          <span class="console-output__icon">▸</span>
          <span class="console-output__title">SYSTEM LOG</span>
        </div>
        <div class="console-output__content">
          <pre class="console-output__json">${logText}</pre>
        </div>
      </div>
    `;

    const logHeader = this.container.querySelector('#systemLogHeader');
    const logContainer = this.container.querySelector('#systemLog');
    logHeader.addEventListener('click', () => {
      logContainer.classList.toggle('console-output--collapsed');
    });
  }
}

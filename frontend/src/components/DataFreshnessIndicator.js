import { BacktestAPI } from '../services/api.js';

export class DataFreshnessIndicator {
  constructor(container) {
    this.container = container;
    this.status = null;
    this.updating = false;
  }

  async init() {
    try {
      this.status = await BacktestAPI.getSP500Status();
      this.render();
    } catch {
      // Graceful degradation: no badge if API unavailable
      this.container.innerHTML = '';
    }
  }

  render() {
    if (!this.status) {
      this.container.innerHTML = '';
      return;
    }

    const { freshness, last_updated } = this.status;
    const freshnessClass = `freshness-badge--${freshness}`;
    const dateLabel = last_updated === 'none' || last_updated === 'unknown'
      ? 'NO DATA'
      : this.formatDate(last_updated);

    const showUpdate = freshness === 'stale' || freshness === 'outdated';
    const updateLabel = this.updating ? 'UPDATING...' : 'UPDATE';

    this.container.innerHTML = `
      <div class="freshness-badge ${freshnessClass}">
        <div class="freshness-badge__status">
          <span class="freshness-badge__dot"></span>
          S&P 500
        </div>
        <span class="freshness-badge__date">${dateLabel}</span>
        ${showUpdate ? `<button class="freshness-badge__update-btn" id="sp500UpdateBtn">${updateLabel}</button>` : ''}
      </div>
    `;

    if (showUpdate) {
      const btn = this.container.querySelector('#sp500UpdateBtn');
      btn.addEventListener('click', () => this.handleUpdate());
      if (this.updating) btn.disabled = true;
    }
  }

  async handleUpdate() {
    if (this.updating) return;
    this.updating = true;
    this.render();

    try {
      await BacktestAPI.updateSP500Data();
      this.status = await BacktestAPI.getSP500Status();
    } catch {
      // Badge stays as-is on failure
    } finally {
      this.updating = false;
      this.render();
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

import { BacktestAPI } from '../services/api.js';

export class HealthIndicator {
  constructor(container) {
    this.container = container;
    this.status = null;
    this._pollInterval = null;
  }

  async init() {
    await this._check();
    this._pollInterval = setInterval(() => this._check(), 30000);
  }

  async _check() {
    try {
      this.status = await BacktestAPI.getHealth();
    } catch {
      this.status = { status: 'unavailable', dependencies: {} };
    }
    this.render();
  }

  render() {
    const s = this.status?.status ?? 'unknown';
    const labels = { ok: 'SYSTEM OK', degraded: 'DEGRADED', unavailable: 'UNAVAILABLE' };
    const label = labels[s] ?? s.toUpperCase();

    const deps = this.status?.dependencies ?? {};
    const depHtml = Object.entries(deps).map(([name, info]) => {
      const ok = info.status === 'ok';
      const latency = info.latency_ms != null ? `${info.latency_ms}ms` : '';
      return `
        <div class="health-popover__dep">
          <span class="health-popover__dot health-popover__dot--${ok ? 'ok' : 'err'}"></span>
          <span class="health-popover__name">${name}</span>
          ${latency ? `<span class="health-popover__latency">${latency}</span>` : ''}
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="health-badge health-badge--${s}">
        <div class="health-badge__pill">
          <span class="health-badge__dot"></span>
          <span class="health-badge__label">${label}</span>
        </div>
        ${depHtml ? `<div class="health-popover">${depHtml}</div>` : ''}
      </div>
    `;
  }
}

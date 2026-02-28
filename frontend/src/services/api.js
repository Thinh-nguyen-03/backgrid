import { API_BASE } from '../config/constants.js';

async function handleResponse(res) {
  const body = await res.json();
  if (!res.ok) {
    if (res.status === 422 && body.detail) {
      const msg = Array.isArray(body.detail)
        ? body.detail.map(e => e.msg).join('; ')
        : body.detail;
      throw new Error(`Validation error: ${msg}`);
    }
    throw new Error(body.error || body.detail || 'Unknown error');
  }
  return body;
}

export class BacktestAPI {
  static async submitSingleBacktest(payload) {
    const res = await fetch(`${API_BASE}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  }

  static async submitMultiStrategy(payload) {
    const res = await fetch(`${API_BASE}/backtest/multi-strategy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  }

  static async submitPortfolioBacktest(payload) {
    const res = await fetch(`${API_BASE}/backtest/portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  }

  static async getPortfolioTrades(batchId, params = {}) {
    const query = new URLSearchParams();
    if (params.symbol) query.set('symbol', params.symbol);
    if (params.strategy) query.set('strategy', params.strategy);
    if (params.limit) query.set('limit', params.limit);
    if (params.offset) query.set('offset', params.offset);
    const res = await fetch(`${API_BASE}/backtest/portfolio/${batchId}/trades?${query}`);
    return handleResponse(res);
  }

  static async getSymbols(params = {}) {
    const query = new URLSearchParams();
    query.set('source', params.source || 'yahoo');
    query.set('limit', params.limit || 1000);
    if (params.offset) query.set('offset', params.offset);
    if (params.sector) query.set('sector', params.sector);
    const res = await fetch(`${API_BASE}/symbols?${query}`);
    return handleResponse(res);
  }

  static async getSectors() {
    const res = await fetch(`${API_BASE}/sectors`);
    return handleResponse(res);
  }

  static async getPresets(params = {}) {
    const query = new URLSearchParams();
    if (params.category) query.set('category', params.category);
    if (params.strategy) query.set('strategy', params.strategy);
    if (params.q) query.set('q', params.q);
    const qs = query.toString();
    const res = await fetch(`${API_BASE}/presets${qs ? '?' + qs : ''}`);
    return handleResponse(res);
  }

  static async getPreset(id) {
    const res = await fetch(`${API_BASE}/presets/${id}`);
    return handleResponse(res);
  }

  static async importStrategy(payload) {
    const res = await fetch(`${API_BASE}/strategy/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  }

  static async importStrategyPdf(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/strategy/import/pdf`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  }

  static async getSP500Status() {
    const res = await fetch(`${API_BASE}/sp500-history/status`);
    return handleResponse(res);
  }

  static async validateSP500Symbols(payload) {
    const res = await fetch(`${API_BASE}/sp500-history/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  }

  static async getSP500Universe(date) {
    const res = await fetch(`${API_BASE}/sp500-history/universe?date=${date}`);
    return handleResponse(res);
  }

  static async updateSP500Data() {
    const res = await fetch(`${API_BASE}/sp500-history/update`, {
      method: 'POST',
    });
    return handleResponse(res);
  }
}

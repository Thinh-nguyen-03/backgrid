import { STRATEGIES, MODES, DEFAULTS } from '../config/constants.js';

export class AppState {
  constructor() {
    this.state = {
      mode: MODES.SINGLE,
      strategy: STRATEGIES.MA_CROSSOVER,
      loading: false,
      results: null,
      resultType: null, // 'single' | 'multi-strategy' | 'portfolio'
      error: null,
    };
    this.listeners = new Map();
  }

  get(key) {
    return this.state[key];
  }

  setState(updates) {
    const prev = { ...this.state };
    this.state = { ...this.state, ...updates };
    this.notify(prev);
  }

  subscribe(key, listener) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, []);
    }
    this.listeners.get(key).push(listener);
  }

  notify(prev) {
    for (const [key, fns] of this.listeners) {
      if (key === '*' || this.state[key] !== prev[key]) {
        fns.forEach(fn => fn(this.state));
      }
    }
  }
}

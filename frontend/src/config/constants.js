export const API_BASE = '/api/v1';

export const STRATEGIES = {
  MA_CROSSOVER: 'ma_crossover',
  RSI: 'rsi',
  COMBINED: 'combined',
};

export const STRATEGY_LABELS = {
  [STRATEGIES.MA_CROSSOVER]: 'Moving Average Crossover',
  [STRATEGIES.RSI]: 'RSI Mean Reversion',
  [STRATEGIES.COMBINED]: 'Combined Strategies',
};

export const COMBINATION_METHODS = {
  OR: 'or',
  AND: 'and',
  PRIORITY: 'priority',
  WEIGHTED: 'weighted',
};

export const MODES = {
  SINGLE: 'single',
  PORTFOLIO: 'portfolio',
};

export const DEFAULTS = {
  symbol: 'AAPL',
  start: '2020-01-01',
  end: '2023-12-31',
  fast: 10,
  slow: 30,
  rsi_period: 14,
  oversold_threshold: 30,
  overbought_threshold: 55,
  confirmation_window: 3,
  min_confirmations: 2,
  initial_capital: 10000,
  position_sizing: 'fixed',
  risk_per_trade: 0.05,
  atr_period: 14,
  atr_multiplier: 3.0,
  commission_per_share: 0.005,
  spread_bps: 5.0,
  slippage_bps: 2.0,
  fill_at: 'next_open',
  enable_transaction_costs: true,
};

export const JOB_HISTORY_KEY = 'backgrid_job_history';
export const JOB_HISTORY_MAX = 10;
export const JOB_HISTORY_VERSION = 1;

const SKIP_KEYS = new Set(['equity_curve', 'portfolio_equity_curve']);

const PCT_KEYS = new Set([
  'total_return', 'max_drawdown', 'average_return',
  'average_max_drawdown', 'win_rate',
]);

const CURRENCY_KEYS = new Set([
  'total_transaction_costs', 'initial_capital',
]);

const RATIO_KEYS = new Set([
  'sharpe', 'average_sharpe', 'calmar_ratio', 'sortino_ratio',
]);

const LABEL_MAP = {
  batch_id: 'Batch ID',
  status: 'Status',
  symbols_requested: 'Symbols Requested',
  symbols_completed: 'Symbols Completed',
  symbols_failed: 'Symbols Failed',
  failed_symbols: 'Failed Symbols',
  symbol_count: 'Symbol Count',
  total_trades: 'Total Trades',
  average_sharpe: 'Average Sharpe',
  average_return: 'Average Return',
  average_max_drawdown: 'Average Drawdown',
  best_symbol: 'Best Symbol',
  worst_symbol: 'Worst Symbol',
  runtime_seconds: 'Runtime',
  results_by_symbol: 'Results by Symbol',
  created_at: 'Created',
  error: 'Error',
  symbol: 'Symbol',
  sharpe: 'Sharpe Ratio',
  max_drawdown: 'Max Drawdown',
  total_return: 'Total Return',
  win_rate: 'Win Rate',
  total_transaction_costs: 'Tx Costs',
  initial_capital: 'Initial Capital',
  calmar_ratio: 'Calmar Ratio',
  sortino_ratio: 'Sortino Ratio',
  strategy: 'Strategy',
  combination_method: 'Combination',
  strategies_used: 'Strategies',
};

function getLabel(key) {
  if (LABEL_MAP[key]) return LABEL_MAP[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatVal(key, value) {
  if (value === null || value === undefined) return null;

  if (key === 'runtime_seconds') {
    return Number(value).toFixed(2) + 's';
  }
  if (key === 'created_at') {
    return new Date(value).toLocaleString();
  }
  if (PCT_KEYS.has(key)) {
    return (value * 100).toFixed(2) + '%';
  }
  if (CURRENCY_KEYS.has(key)) {
    return '$' + Number(value).toFixed(2);
  }
  if (RATIO_KEYS.has(key)) {
    return Number(value).toFixed(3);
  }
  if (Array.isArray(value)) {
    return value.length === 0 ? null : value.join(', ');
  }
  return String(value);
}

function formatObject(obj, indent = 0) {
  const prefix = '  '.repeat(indent);
  const pad = Math.max(24 - indent * 2, 14);
  let out = '';

  for (const [key, value] of Object.entries(obj)) {
    if (SKIP_KEYS.has(key)) continue;

    const label = getLabel(key);

    if (value && typeof value === 'object' && !Array.isArray(value)) {
      if (indent === 0) {
        out += `\n${label.toUpperCase()}\n\n`;
      } else {
        out += `${prefix}${label}\n`;
      }
      out += formatObject(value, indent + 1);
    } else {
      const display = formatVal(key, value);
      if (display === null) continue;
      out += `${prefix}${label.padEnd(pad)}${display}\n`;
    }
  }

  return out;
}

export function formatSystemLog(data) {
  return formatObject(data).trim();
}

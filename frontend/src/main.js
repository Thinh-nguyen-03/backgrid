import './styles/main.css';
import './styles/components/header.css';
import './styles/components/sidebar.css';
import './styles/components/forms.css';
import './styles/components/cards.css';
import './styles/components/tables.css';
import './styles/components/modals.css';
import './styles/components/flatpickr.css';
import './styles/utilities.css';

import flatpickr from 'flatpickr';
import 'flatpickr/dist/flatpickr.min.css';

import { AppState } from './state/AppState.js';
import { BacktestAPI } from './services/api.js';
import { MODES, STRATEGIES } from './config/constants.js';

import { Header } from './components/Header.js';
import { PortfolioMode } from './components/PortfolioMode.js';
import { StrategySelector } from './components/StrategySelector.js';
import { ExecutionConfig } from './components/ExecutionConfig.js';
import { ResultsDisplay } from './components/ResultsDisplay.js';
import { EquityCurveChart } from './components/EquityCurveChart.js';
import { PortfolioResults } from './components/PortfolioResults.js';
import { TradeLedgerModal } from './components/TradeLedgerModal.js';
import { SymbolSelector } from './components/SymbolSelector.js';
import { JobHistory } from './components/JobHistory.js';
import { HelpModal } from './components/HelpModal.js';

const appState = new AppState();

// Components
const header = new Header(document.querySelector('.app-header'));
const portfolioMode = new PortfolioMode(document.getElementById('universeSetup'), appState);
const strategySelector = new StrategySelector(document.getElementById('strategySection'), appState);
const executionConfig = new ExecutionConfig(document.getElementById('executionSection'));
const resultsDisplay = new ResultsDisplay(document.getElementById('results'));
const equityCurveChart = new EquityCurveChart(null); // container set dynamically
const portfolioResults = new PortfolioResults(document.getElementById('results'));
const tradeLedgerModal = new TradeLedgerModal();
const symbolSelector = new SymbolSelector();
const jobHistory = new JobHistory(document.getElementById('historySection'));
const helpModal = new HelpModal();

// Init components
header.init();
portfolioMode.init();
strategySelector.init();
executionConfig.init();
resultsDisplay.showEmpty();
jobHistory.render();
helpModal.init();

// Theme toggle handler
const themeToggle = document.getElementById('themeToggle');
const savedTheme = localStorage.getItem('theme') || 'light';
if (savedTheme === 'dark') {
  document.body.classList.add('dark-mode');
  themeToggle.textContent = '☾';
}

themeToggle?.addEventListener('click', () => {
  document.body.classList.toggle('dark-mode');
  const isDark = document.body.classList.contains('dark-mode');
  themeToggle.textContent = isDark ? '☾' : '☀';
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
});

// Help button handler
document.getElementById('helpBtn')?.addEventListener('click', () => {
  helpModal.show();
});

// Date pickers
portfolioMode.initDatePickers(flatpickr);

// Wire up symbol browser
portfolioMode.onBrowseSymbols = () => {
  symbolSelector.open((symbols) => {
    portfolioMode.addSymbols(symbols);
  });
};

// Wire up trade ledger from portfolio results
portfolioResults.onViewTrades = (batchId) => {
  tradeLedgerModal.open(batchId);
};

// Form submit
const form = document.getElementById('form');
const submitBtn = document.getElementById('submitBtn');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = 'PROCESSING...';

  const mode = appState.get('mode');
  const strategy = appState.get('strategy');
  const dates = portfolioMode.getDateRange();
  const config = executionConfig.getConfig();

  try {
    let data;

    if (mode === MODES.PORTFOLIO) {
      // Portfolio batch
      const symbols = portfolioMode.getSymbols();
      if (symbols.length === 0) throw new Error('Enter at least one symbol');

      const stratParams = strategySelector.getParams();
      resultsDisplay.showLoading(`Processing ${symbols.length} symbols...`);

      data = await BacktestAPI.submitPortfolioBacktest({
        symbols,
        strategy: stratParams.strategy,
        params: stratParams.params,
        start: dates.start,
        end: dates.end,
        config,
      });

      appState.setState({ results: data, resultType: 'portfolio' });
      portfolioResults.container = document.getElementById('results');
      portfolioResults.render(data);

      jobHistory.saveEntry({
        id: data.batch_id,
        timestamp: new Date().toISOString(),
        mode: 'portfolio',
        strategy: stratParams.strategy,
        symbols,
        sharpe: data.average_sharpe,
        total_return: data.average_return,
        max_drawdown: data.average_max_drawdown,
      });

    } else if (strategy === STRATEGIES.COMBINED) {
      // Multi-strategy single symbol
      const symbol = portfolioMode.getSymbol();
      const stratParams = strategySelector.getParams();
      resultsDisplay.showLoading('Running multi-strategy backtest...');

      data = await BacktestAPI.submitMultiStrategy({
        symbol,
        strategies: stratParams.strategies,
        combination_method: stratParams.combination_method,
        start: dates.start,
        end: dates.end,
        config,
      });

      appState.setState({ results: data, resultType: 'multi-strategy' });
      resultsDisplay.showSingleResult(data);

      if (data.equity_curve) {
        const chartEl = document.getElementById('chartContainer');
        if (chartEl) {
          equityCurveChart.container = chartEl;
          equityCurveChart.render(data.equity_curve, `${symbol} Multi-Strategy`);
        }
      }

      jobHistory.saveEntry({
        id: data.job_id,
        timestamp: new Date().toISOString(),
        mode: 'multi-strategy',
        strategy: 'combined',
        symbols: [symbol],
        sharpe: data.sharpe,
        total_return: data.total_return,
        max_drawdown: data.max_drawdown,
      });

    } else {
      // Single symbol, single strategy
      const symbol = portfolioMode.getSymbol();
      const stratParams = strategySelector.getParams();
      resultsDisplay.showLoading('Running backtest...');

      data = await BacktestAPI.submitSingleBacktest({
        symbol,
        strategy: stratParams.strategy,
        params: stratParams.params,
        start: dates.start,
        end: dates.end,
        config,
      });

      appState.setState({ results: data, resultType: 'single' });
      resultsDisplay.showSingleResult(data);

      if (data.equity_curve) {
        const chartEl = document.getElementById('chartContainer');
        if (chartEl) {
          equityCurveChart.container = chartEl;
          equityCurveChart.render(data.equity_curve, `${symbol} Equity`);
        }
      }

      jobHistory.saveEntry({
        id: data.job_id,
        timestamp: new Date().toISOString(),
        mode: 'single',
        strategy: stratParams.strategy,
        symbols: [symbol],
        sharpe: data.sharpe,
        total_return: data.total_return,
        max_drawdown: data.max_drawdown,
      });
    }

  } catch (err) {
    resultsDisplay.showError(err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'INITIALIZE BACKTEST';
  }
});

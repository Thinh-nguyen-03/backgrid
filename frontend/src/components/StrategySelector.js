import { STRATEGIES, STRATEGY_LABELS, COMBINATION_METHODS, DEFAULTS } from '../config/constants.js';

export class StrategySelector {
  constructor(container, appState) {
    this.container = container;
    this.appState = appState;
    this.multiStrategies = [];
  }

  init() {
    this.render();
    this.attachEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="config-section">
        <div class="section-badge">Strategy Logic</div>
        <div class="input-group">
          <label>Strategy Model</label>
          <select id="strategySelect">
            <option value="${STRATEGIES.MA_CROSSOVER}">${STRATEGY_LABELS[STRATEGIES.MA_CROSSOVER]}</option>
            <option value="${STRATEGIES.RSI}">${STRATEGY_LABELS[STRATEGIES.RSI]}</option>
            <option value="${STRATEGIES.COMBINED}">${STRATEGY_LABELS[STRATEGIES.COMBINED]}</option>
          </select>
        </div>

        <div id="maParams">
          <div class="row">
            <div class="input-group">
              <label>Fast Period</label>
              <input type="number" id="maFast" value="${DEFAULTS.fast}" min="2">
            </div>
            <div class="input-group">
              <label>Slow Period</label>
              <input type="number" id="maSlow" value="${DEFAULTS.slow}" min="5">
            </div>
          </div>
        </div>

        <div id="rsiParams" class="hidden">
          <div class="row">
            <div class="input-group">
              <label>RSI Period</label>
              <input type="number" id="rsiPeriod" value="${DEFAULTS.rsi_period}" min="2">
            </div>
            <div class="input-group">
              <label>Oversold</label>
              <input type="number" id="rsiOversold" value="${DEFAULTS.oversold_threshold}" min="0" max="100">
            </div>
          </div>
          <div class="row">
            <div class="input-group">
              <label>Overbought</label>
              <input type="number" id="rsiOverbought" value="${DEFAULTS.overbought_threshold}" min="0" max="100">
            </div>
            <div class="input-group">
              <label>Confirm Window</label>
              <input type="number" id="rsiConfirmWindow" value="${DEFAULTS.confirmation_window}" min="1">
            </div>
          </div>
          <div class="input-group">
            <label>Min Confirmations</label>
            <input type="number" id="rsiMinConfirm" value="${DEFAULTS.min_confirmations}" min="1">
          </div>
        </div>

        <div id="combinedParams" class="hidden">
          <div class="input-group">
            <label>Combination Method</label>
            <select id="combinationMethod">
              <option value="${COMBINATION_METHODS.OR}">OR (any signal)</option>
              <option value="${COMBINATION_METHODS.AND}">AND (all agree)</option>
              <option value="${COMBINATION_METHODS.PRIORITY}" selected>PRIORITY (first wins)</option>
              <option value="${COMBINATION_METHODS.WEIGHTED}">WEIGHTED</option>
            </select>
          </div>
          <div id="multiStrategyList"></div>
          <button type="button" id="addStrategyBtn" class="btn-sm" style="margin-top: 0.5rem;">+ Add Strategy</button>
        </div>
      </div>
    `;
  }

  attachEvents() {
    const select = this.container.querySelector('#strategySelect');
    select.addEventListener('change', () => this.onStrategyChange(select.value));

    const addBtn = this.container.querySelector('#addStrategyBtn');
    addBtn.addEventListener('click', () => this.addMultiStrategy());
  }

  onStrategyChange(value) {
    this.appState.setState({ strategy: value });
    this.container.querySelector('#maParams').classList.toggle('hidden', value !== STRATEGIES.MA_CROSSOVER);
    this.container.querySelector('#rsiParams').classList.toggle('hidden', value !== STRATEGIES.RSI);
    this.container.querySelector('#combinedParams').classList.toggle('hidden', value !== STRATEGIES.COMBINED);

    if (value === STRATEGIES.COMBINED && this.multiStrategies.length === 0) {
      this.addMultiStrategy('ma_crossover');
      this.addMultiStrategy('rsi');
    }
  }

  addMultiStrategy(type = 'ma_crossover') {
    const id = Date.now();
    this.multiStrategies.push({ id, type });
    this.renderMultiStrategies();
  }

  removeMultiStrategy(id) {
    this.multiStrategies = this.multiStrategies.filter(s => s.id !== id);
    this.renderMultiStrategies();
  }

  renderMultiStrategies() {
    const list = this.container.querySelector('#multiStrategyList');
    const method = this.container.querySelector('#combinationMethod')?.value;

    list.innerHTML = this.multiStrategies.map(s => `
      <div class="config-section" style="margin-top: 1rem; padding: 1rem; background: #fff;" data-strat-id="${s.id}">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
          <select class="multi-strat-type" data-id="${s.id}" style="flex:1; padding:0.4rem; border:var(--border-thick); font-family:var(--font-mono); font-size:0.8rem;">
            <option value="ma_crossover" ${s.type === 'ma_crossover' ? 'selected' : ''}>MA Crossover</option>
            <option value="rsi" ${s.type === 'rsi' ? 'selected' : ''}>RSI</option>
          </select>
          <button type="button" class="btn-sm btn-sm--danger remove-strat-btn" data-id="${s.id}" style="margin-left:0.5rem;">X</button>
        </div>
        ${s.type === 'ma_crossover' ? `
          <div class="row">
            <div class="input-group"><label>Fast</label><input type="number" class="ms-fast" value="${DEFAULTS.fast}" min="2"></div>
            <div class="input-group"><label>Slow</label><input type="number" class="ms-slow" value="${DEFAULTS.slow}" min="5"></div>
          </div>
        ` : `
          <div class="row">
            <div class="input-group"><label>RSI Period</label><input type="number" class="ms-rsi-period" value="${DEFAULTS.rsi_period}" min="2"></div>
            <div class="input-group"><label>Oversold</label><input type="number" class="ms-rsi-oversold" value="${DEFAULTS.oversold_threshold}" min="0" max="100"></div>
          </div>
          <div class="input-group"><label>Overbought</label><input type="number" class="ms-rsi-overbought" value="${DEFAULTS.overbought_threshold}" min="0" max="100"></div>
        `}
        ${method === 'weighted' ? `
          <div class="input-group"><label>Weight</label><input type="number" class="ms-weight" value="1.0" min="0" step="0.1"></div>
        ` : ''}
      </div>
    `).join('');

    list.querySelectorAll('.remove-strat-btn').forEach(btn => {
      btn.addEventListener('click', () => this.removeMultiStrategy(Number(btn.dataset.id)));
    });

    list.querySelectorAll('.multi-strat-type').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const strat = this.multiStrategies.find(s => s.id === Number(e.target.dataset.id));
        if (strat) { strat.type = e.target.value; this.renderMultiStrategies(); }
      });
    });
  }

  getParams() {
    const strategy = this.appState.get('strategy');

    if (strategy === STRATEGIES.MA_CROSSOVER) {
      return {
        strategy: 'ma_crossover',
        params: {
          fast: parseInt(this.container.querySelector('#maFast').value),
          slow: parseInt(this.container.querySelector('#maSlow').value),
        },
      };
    }

    if (strategy === STRATEGIES.RSI) {
      return {
        strategy: 'rsi',
        params: {
          rsi_period: parseInt(this.container.querySelector('#rsiPeriod').value),
          oversold_threshold: parseInt(this.container.querySelector('#rsiOversold').value),
          overbought_threshold: parseInt(this.container.querySelector('#rsiOverbought').value),
          confirmation_window: parseInt(this.container.querySelector('#rsiConfirmWindow').value),
          min_confirmations: parseInt(this.container.querySelector('#rsiMinConfirm').value),
        },
      };
    }

    if (strategy === STRATEGIES.COMBINED) {
      const method = this.container.querySelector('#combinationMethod').value;
      const strategies = [];
      const items = this.container.querySelectorAll('[data-strat-id]');

      items.forEach((el, i) => {
        const type = el.querySelector('.multi-strat-type').value;
        const weight = el.querySelector('.ms-weight')?.value || 1.0;
        let params;

        if (type === 'ma_crossover') {
          params = {
            fast: parseInt(el.querySelector('.ms-fast').value),
            slow: parseInt(el.querySelector('.ms-slow').value),
          };
        } else {
          params = {
            rsi_period: parseInt(el.querySelector('.ms-rsi-period').value),
            oversold_threshold: parseInt(el.querySelector('.ms-rsi-oversold').value),
            overbought_threshold: parseInt(el.querySelector('.ms-rsi-overbought').value),
          };
        }

        strategies.push({
          type,
          params,
          weight: parseFloat(weight),
          name: `${type}_${i}`,
        });
      });

      return { strategy: 'combined', combination_method: method, strategies };
    }
  }
}

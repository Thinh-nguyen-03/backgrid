import { DEFAULTS } from '../config/constants.js';

export class ExecutionConfig {
  constructor(container) {
    this.container = container;
  }

  init() {
    this.render();
    this.attachEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="config-section">
        <div class="section-badge">Execution Setup</div>

        <div class="row">
          <div class="input-group">
            <label>Initial Capital</label>
            <input type="number" id="initialCapital" value="${DEFAULTS.initial_capital}" min="100" step="any">
          </div>
          <div class="input-group">
            <label>Position Sizing</label>
            <select id="positionSizing">
              <option value="fixed">Fixed Fractional</option>
              <option value="atr">ATR-based</option>
            </select>
          </div>
        </div>

        <div id="atrParams" class="hidden">
          <div class="row-3">
            <div class="input-group">
              <label>Risk/Trade %</label>
              <input type="number" id="riskPerTrade" value="${(DEFAULTS.risk_per_trade * 100)}" min="0.1" max="100" step="any">
            </div>
            <div class="input-group">
              <label>ATR Period</label>
              <input type="number" id="atrPeriod" value="${DEFAULTS.atr_period}" min="2" step="1">
            </div>
            <div class="input-group">
              <label>ATR Mult</label>
              <input type="number" id="atrMultiplier" value="${DEFAULTS.atr_multiplier}" min="0.1" step="any">
            </div>
          </div>
        </div>

        <div class="checkbox-row" style="margin-top: 1rem; margin-bottom: 1rem;">
          <input type="checkbox" id="enableTxCosts" checked>
          <label for="enableTxCosts" style="font-size:0.8rem;">Enable Transaction Costs</label>
        </div>

        <div id="txCostParams">
          <div class="row-3">
            <div class="input-group">
              <label>Comm/Share</label>
              <input type="number" id="commissionPerShare" value="${DEFAULTS.commission_per_share}" min="0" step="any">
            </div>
            <div class="input-group">
              <label>Spread (bps)</label>
              <input type="number" id="spreadBps" value="${DEFAULTS.spread_bps}" min="0" step="any">
            </div>
            <div class="input-group">
              <label>Slippage (bps)</label>
              <input type="number" id="slippageBps" value="${DEFAULTS.slippage_bps}" min="0" step="any">
            </div>
          </div>
        </div>
      </div>
    `;
  }

  attachEvents() {
    const sizingSelect = this.container.querySelector('#positionSizing');
    sizingSelect.addEventListener('change', () => {
      const isAtr = sizingSelect.value === 'atr';
      const atrParams = this.container.querySelector('#atrParams');
      atrParams.classList.toggle('hidden', !isAtr);

      // Disable hidden inputs to prevent validation errors
      atrParams.querySelectorAll('input').forEach(input => {
        input.disabled = !isAtr;
      });
    });

    const txCheck = this.container.querySelector('#enableTxCosts');
    txCheck.addEventListener('change', () => {
      const isEnabled = txCheck.checked;
      const txParams = this.container.querySelector('#txCostParams');
      txParams.classList.toggle('hidden', !isEnabled);

      // Disable hidden inputs to prevent validation errors
      txParams.querySelectorAll('input').forEach(input => {
        input.disabled = !isEnabled;
      });
    });

    // Initialize disabled state for hidden sections
    this.container.querySelector('#atrParams').querySelectorAll('input').forEach(input => {
      input.disabled = true;
    });
  }

  getConfig() {
    const sizing = this.container.querySelector('#positionSizing').value;
    const config = {
      initial_capital: parseFloat(this.container.querySelector('#initialCapital').value),
      position_sizing: sizing,
      risk_per_trade: parseFloat(this.container.querySelector('#riskPerTrade').value) / 100,
      enable_transaction_costs: this.container.querySelector('#enableTxCosts').checked,
    };

    if (sizing === 'atr') {
      config.atr_period = parseInt(this.container.querySelector('#atrPeriod').value);
      config.atr_multiplier = parseFloat(this.container.querySelector('#atrMultiplier').value);
    }

    if (config.enable_transaction_costs) {
      config.commission_per_share = parseFloat(this.container.querySelector('#commissionPerShare').value);
      config.spread_bps = parseFloat(this.container.querySelector('#spreadBps').value);
      config.slippage_bps = parseFloat(this.container.querySelector('#slippageBps').value);
    }

    config.fill_at = 'next_open';
    return config;
  }
}

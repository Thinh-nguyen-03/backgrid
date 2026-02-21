export class HelpModal {
  constructor() {
    this.modalId = 'helpModal';
  }

  init() {
    this.render();
    this.attachEvents();
  }

  render() {
    const existingModal = document.getElementById(this.modalId);
    if (existingModal) return;

    const modal = document.createElement('div');
    modal.id = this.modalId;
    modal.className = 'modal hidden';
    modal.innerHTML = `
      <div class="modal__overlay"></div>
      <div class="modal__content modal__content--large">
        <div class="modal__header">
          <h2 class="modal__title">PARAMETER REFERENCE</h2>
          <button class="modal__close" data-close-help>&times;</button>
        </div>
        <div class="modal__body">

          <div class="help-category">
            <div class="help-category__header">STRATEGY PARAMETERS</div>
            <div class="help-grid">
              <div class="help-card">
                <div class="help-card__title">MA FAST PERIOD</div>
                <div class="help-card__value">5-50 days</div>
                <div class="help-card__desc">Short-term moving average. Common: 10, 20</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">MA SLOW PERIOD</div>
                <div class="help-card__value">20-200 days</div>
                <div class="help-card__desc">Long-term moving average. Common: 50, 100, 200</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">RSI PERIOD</div>
                <div class="help-card__value">2-50 days</div>
                <div class="help-card__desc">Standard: 14 days</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">OVERSOLD</div>
                <div class="help-card__value">10-50</div>
                <div class="help-card__desc">RSI buy trigger. Standard: 30</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">OVERBOUGHT</div>
                <div class="help-card__value">50-90</div>
                <div class="help-card__desc">RSI sell trigger. Standard: 70</div>
              </div>
            </div>
          </div>

          <div class="help-category">
            <div class="help-category__header">EXECUTION & RISK</div>
            <div class="help-grid">
              <div class="help-card">
                <div class="help-card__title">INITIAL CAPITAL</div>
                <div class="help-card__value">$100+</div>
                <div class="help-card__desc">Starting cash. Typical: $10k-$100k</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">POSITION SIZING</div>
                <div class="help-card__value">Fixed / ATR</div>
                <div class="help-card__desc">Fixed: % of capital. ATR: volatility-based</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">RISK/TRADE %</div>
                <div class="help-card__value">1-10%</div>
                <div class="help-card__desc">Conservative: 1-2%. Aggressive: 5-10%</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">ATR PERIOD</div>
                <div class="help-card__value">7-30 days</div>
                <div class="help-card__desc">Volatility window. Standard: 14</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">ATR MULTIPLIER</div>
                <div class="help-card__value">1.5-5x</div>
                <div class="help-card__desc">Stop distance. Tight: 2x, Wide: 4x</div>
              </div>
            </div>
          </div>

          <div class="help-category">
            <div class="help-category__header">TRANSACTION COSTS</div>
            <div class="help-grid">
              <div class="help-card">
                <div class="help-card__title">COMMISSION</div>
                <div class="help-card__value">$0-$0.01</div>
                <div class="help-card__desc">Per share. Zero-fee brokers: $0</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">SPREAD (BPS)</div>
                <div class="help-card__value">2-50 bps</div>
                <div class="help-card__desc">Liquid: 2-10. Illiquid: 20-50</div>
              </div>

              <div class="help-card">
                <div class="help-card__title">SLIPPAGE (BPS)</div>
                <div class="help-card__value">1-20 bps</div>
                <div class="help-card__desc">Market impact. Small: 1-5. Large: 5-20</div>
              </div>
            </div>
          </div>

          <div class="help-tips">
            <div class="help-tips__header">BEST PRACTICES</div>
            <div class="help-tips__list">
              <div class="help-tip">Start with defaults, then optimize</div>
              <div class="help-tip">Use 2+ years of data</div>
              <div class="help-tip">Always include transaction costs</div>
              <div class="help-tip">Lower risk% for portfolios</div>
              <div class="help-tip">Avoid overfitting to one period</div>
            </div>
          </div>

        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  attachEvents() {
    const modal = document.getElementById(this.modalId);
    if (!modal) return;

    const closeBtn = modal.querySelector('[data-close-help]');
    const overlay = modal.querySelector('.modal__overlay');

    const closeModal = () => modal.classList.add('hidden');

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (overlay) overlay.addEventListener('click', closeModal);
  }

  show() {
    const modal = document.getElementById(this.modalId);
    if (modal) modal.classList.remove('hidden');
  }
}

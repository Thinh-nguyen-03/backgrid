import { MODES, DEFAULTS } from '../config/constants.js';

export class PortfolioMode {
  constructor(container, appState) {
    this.container = container;
    this.appState = appState;
    this.onBrowseSymbols = null; // callback set by parent
  }

  init() {
    this.render();
    this.attachEvents();
  }

  render() {
    this.container.innerHTML = `
      <div class="config-section">
        <div class="section-badge">Universe Setup</div>

        <div class="mode-toggle" style="margin-bottom: 1.5rem;">
          <button type="button" class="mode-toggle__btn mode-toggle__btn--active" data-mode="${MODES.SINGLE}">Single Symbol</button>
          <button type="button" class="mode-toggle__btn" data-mode="${MODES.PORTFOLIO}">Portfolio Batch</button>
        </div>

        <div id="singleMode">
          <div class="input-group">
            <label>Ticker Symbol</label>
            <div class="input-wrapper">
              <input type="text" id="symbolInput" value="${DEFAULTS.symbol}" style="text-transform: uppercase;">
              <button type="button" class="input-clear-btn" id="clearSymbolBtn" style="display:none;">×</button>
            </div>
          </div>
        </div>

        <div id="portfolioMode" class="hidden">
          <div class="input-group">
            <label>Symbols (one per line or comma-separated)</label>
            <div class="input-wrapper">
              <textarea id="symbolsTextarea" placeholder="AAPL&#10;MSFT&#10;GOOGL"></textarea>
              <button type="button" class="input-clear-btn input-clear-btn--textarea" id="clearSymbolsBtn" style="display:none;">×</button>
            </div>
            <div class="symbol-count" id="symbolCount">0 symbols entered</div>
          </div>
          <button type="button" id="browseSymbolsBtn" class="btn-sm" style="margin-top: 0.5rem;">Browse Symbols</button>
        </div>

        <div class="row" style="margin-top: 1.5rem;">
          <div class="input-group">
            <label>Start Date</label>
            <input type="text" id="startDate" value="${DEFAULTS.start}">
          </div>
          <div class="input-group">
            <label>End Date</label>
            <input type="text" id="endDate" value="${DEFAULTS.end}">
          </div>
        </div>
      </div>
    `;
  }

  attachEvents() {
    const toggleBtns = this.container.querySelectorAll('.mode-toggle__btn');
    toggleBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        toggleBtns.forEach(b => b.classList.remove('mode-toggle__btn--active'));
        btn.classList.add('mode-toggle__btn--active');
        const mode = btn.dataset.mode;
        this.appState.setState({ mode });
        this.container.querySelector('#singleMode').classList.toggle('hidden', mode !== MODES.SINGLE);
        this.container.querySelector('#portfolioMode').classList.toggle('hidden', mode !== MODES.PORTFOLIO);
      });
    });

    // Single symbol input clear button
    const symbolInput = this.container.querySelector('#symbolInput');
    const clearSymbolBtn = this.container.querySelector('#clearSymbolBtn');
    symbolInput.addEventListener('input', () => {
      clearSymbolBtn.style.display = symbolInput.value ? 'flex' : 'none';
    });
    clearSymbolBtn.addEventListener('click', () => {
      symbolInput.value = '';
      clearSymbolBtn.style.display = 'none';
      symbolInput.focus();
    });

    // Symbols textarea clear button
    const textarea = this.container.querySelector('#symbolsTextarea');
    const clearSymbolsBtn = this.container.querySelector('#clearSymbolsBtn');
    textarea.addEventListener('input', () => {
      this.updateSymbolCount();
      clearSymbolsBtn.style.display = textarea.value ? 'flex' : 'none';
    });
    clearSymbolsBtn.addEventListener('click', () => {
      textarea.value = '';
      clearSymbolsBtn.style.display = 'none';
      this.updateSymbolCount();
      textarea.focus();
    });

    const browseBtn = this.container.querySelector('#browseSymbolsBtn');
    browseBtn.addEventListener('click', () => {
      if (this.onBrowseSymbols) this.onBrowseSymbols();
    });
  }

  updateSymbolCount() {
    const symbols = this.getSymbols();
    const countEl = this.container.querySelector('#symbolCount');
    countEl.textContent = `${symbols.length} symbol${symbols.length !== 1 ? 's' : ''} entered`;
  }

  addSymbols(symbols) {
    const textarea = this.container.querySelector('#symbolsTextarea');
    const existing = this.getSymbols();
    const merged = [...new Set([...existing, ...symbols])];
    textarea.value = merged.join('\n');
    this.updateSymbolCount();
  }

  getSymbols() {
    const textarea = this.container.querySelector('#symbolsTextarea');
    if (!textarea) return [];
    return textarea.value
      .split(/[,\n]+/)
      .map(s => s.trim().toUpperCase())
      .filter(s => s.length > 0);
  }

  getSymbol() {
    const input = this.container.querySelector('#symbolInput');
    return input ? input.value.trim().toUpperCase() : DEFAULTS.symbol;
  }

  getDateRange() {
    return {
      start: this.container.querySelector('#startDate').value,
      end: this.container.querySelector('#endDate').value,
    };
  }

  initDatePickers(flatpickr) {
    const commonConfig = {
      dateFormat: "Y-m-d",
      allowInput: true,
      altInput: true,
      altFormat: "M j, Y",
      disableMobile: true,
      locale: {
        months: {
          shorthand: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
          longhand: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        }
      },
      onReady(selectedDates, dateStr, instance) {
        const yearInput = instance.calendarContainer.querySelector('.cur-year');
        if (yearInput && yearInput.tagName === 'INPUT') {
          const currentYear = yearInput.value || new Date().getFullYear();
          const yearSelect = document.createElement('select');
          yearSelect.className = 'cur-year';
          for (let year = 1990; year <= new Date().getFullYear() + 10; year++) {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            if (year == currentYear) option.selected = true;
            yearSelect.appendChild(option);
          }
          yearSelect.addEventListener('change', function() {
            instance.changeYear(parseInt(this.value));
            instance.changeMonth(instance.currentMonth, false);
          });
          yearInput.parentNode.replaceChild(yearSelect, yearInput);
        }
      }
    };

    flatpickr('#startDate', { ...commonConfig, defaultDate: DEFAULTS.start });
    flatpickr('#endDate', { ...commonConfig, defaultDate: DEFAULTS.end });
  }
}

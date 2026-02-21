import { BacktestAPI } from '../services/api.js';

export class SymbolSelector {
  constructor() {
    this.overlay = null;
    this.selected = new Set();
    this.symbols = [];
    this.onConfirm = null;
  }

  async open(onConfirm) {
    this.onConfirm = onConfirm;
    this.selected = new Set();

    this.overlay = document.createElement('div');
    this.overlay.className = 'modal-overlay';
    this.overlay.innerHTML = `
      <div class="modal" style="max-width:900px;">
        <div class="modal__header">
          <span class="modal__title">Browse Symbols</span>
          <button class="modal__close" id="closeSymbols">X</button>
        </div>
        <div class="modal__body">
          <div class="symbol-selector-toolbar">
            <div class="search-input-wrapper">
              <input type="text" id="symbolSearch" class="symbol-search" placeholder="Search symbol or company name...">
              <button type="button" class="search-clear-btn" id="clearSearchBtn" style="display:none;">×</button>
            </div>
            <span id="selectedCount" class="symbol-selected-count">0 selected</span>
            <button type="button" class="btn-sm" id="clearAllBtn">Clear All</button>
            <button type="button" class="btn-sm btn-primary" id="addSelectedBtn">Add Selected</button>
          </div>
          <div id="symbolGroups" class="symbol-groups">Loading...</div>
        </div>
      </div>
    `;

    document.body.appendChild(this.overlay);

    this.overlay.querySelector('#closeSymbols').addEventListener('click', () => this.close());
    this.overlay.addEventListener('click', (e) => { if (e.target === this.overlay) this.close(); });

    const searchInput = this.overlay.querySelector('#symbolSearch');
    const clearSearchBtn = this.overlay.querySelector('#clearSearchBtn');

    searchInput.addEventListener('input', (e) => {
      this.filterSymbols(e.target.value);
      clearSearchBtn.style.display = e.target.value ? 'flex' : 'none';
    });

    clearSearchBtn.addEventListener('click', () => {
      searchInput.value = '';
      clearSearchBtn.style.display = 'none';
      this.filterSymbols('');
    });

    this.overlay.querySelector('#clearAllBtn').addEventListener('click', () => this.clearAll());
    this.overlay.querySelector('#addSelectedBtn').addEventListener('click', () => this.confirm());

    await this.loadSymbols();
  }

  close() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
  }

  async loadSymbols() {
    const container = this.overlay.querySelector('#symbolGroups');
    try {
      const data = await BacktestAPI.getSymbols({ limit: 1000 });
      this.symbols = data.symbols.sort((a, b) => a.symbol.localeCompare(b.symbol));
      this.renderGroups(this.symbols);
    } catch (err) {
      container.innerHTML = `<div class="error-box">${err.message}</div>`;
    }
  }

  groupBySector(symbols) {
    const groups = {};
    for (const s of symbols) {
      const sector = s.sector || 'Other';
      if (!groups[sector]) groups[sector] = [];
      groups[sector].push(s);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }

  renderGroups(symbols) {
    const container = this.overlay.querySelector('#symbolGroups');
    const groups = this.groupBySector(symbols);

    if (groups.length === 0) {
      container.innerHTML = '<div style="padding:1rem;font-family:var(--font-mono);color:var(--color-text-sub);">No symbols found.</div>';
      return;
    }

    container.innerHTML = groups.map(([sector, syms]) => `
      <details class="sector-group">
        <summary class="sector-group__header">
          <span class="sector-group__name">${sector}</span>
          <span class="sector-group__count">${syms.length}</span>
          <button type="button" class="btn-sm sector-select-btn" data-sector="${sector}">Select All</button>
        </summary>
        <div class="sector-group__symbols">
          ${syms.map(s => `
            <label class="symbol-row ${this.selected.has(s.symbol) ? 'symbol-row--checked' : ''}">
              <input type="checkbox" class="sym-check" value="${s.symbol}" ${this.selected.has(s.symbol) ? 'checked' : ''}>
              <span class="symbol-row__ticker">${s.symbol}</span>
              <span class="symbol-row__name">${s.name || ''}</span>
            </label>
          `).join('')}
        </div>
      </details>
    `).join('');

    container.querySelectorAll('.sym-check').forEach(cb => {
      cb.addEventListener('change', () => {
        const row = cb.closest('.symbol-row');
        if (cb.checked) {
          this.selected.add(cb.value);
          row.classList.add('symbol-row--checked');
        } else {
          this.selected.delete(cb.value);
          row.classList.remove('symbol-row--checked');
        }
        this.updateCount();
      });
    });

    container.querySelectorAll('.sector-select-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const group = btn.closest('.sector-group');
        const checkboxes = group.querySelectorAll('.sym-check');
        const allChecked = [...checkboxes].every(cb => cb.checked);
        checkboxes.forEach(cb => {
          const row = cb.closest('.symbol-row');
          if (allChecked) {
            cb.checked = false;
            this.selected.delete(cb.value);
            row.classList.remove('symbol-row--checked');
          } else {
            cb.checked = true;
            this.selected.add(cb.value);
            row.classList.add('symbol-row--checked');
          }
        });
        btn.textContent = allChecked ? 'Select All' : 'Deselect All';
        this.updateCount();
      });
    });
  }

  filterSymbols(query) {
    const q = query.trim().toLowerCase();
    if (!q) {
      this.renderGroups(this.symbols);
      return;
    }
    const filtered = this.symbols.filter(s =>
      s.symbol.toLowerCase().includes(q) ||
      (s.name || '').toLowerCase().includes(q)
    );
    this.renderGroups(filtered);
  }

  clearAll() {
    this.overlay.querySelectorAll('.sym-check').forEach(cb => {
      cb.checked = false;
      cb.closest('.symbol-row')?.classList.remove('symbol-row--checked');
    });
    this.selected.clear();
    this.updateCount();
  }

  updateCount() {
    const el = this.overlay.querySelector('#selectedCount');
    el.textContent = `${this.selected.size} selected`;
  }

  confirm() {
    if (this.onConfirm && this.selected.size > 0) {
      this.onConfirm([...this.selected]);
    }
    this.close();
  }
}

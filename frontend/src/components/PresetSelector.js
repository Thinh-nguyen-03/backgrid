import { BacktestAPI } from '../services/api.js';

export class PresetSelector {
  constructor(container, appState) {
    this.container = container;
    this.appState = appState;
    this.presets = [];
    this.onPresetSelected = null;
  }

  init() {
    this.render();
    this.loadPresets();
  }

  render() {
    this.container.innerHTML = `
      <div class="config-section">
        <div class="section-badge section-badge--muted">Preset Library</div>
        <div class="preset-selector">
          <div class="preset-selector__toolbar">
            <select id="presetCategoryFilter" class="preset-selector__filter">
              <option value="">ALL CATEGORIES</option>
            </select>
          </div>
          <div id="presetList" class="preset-selector__list">
            <div class="preset-selector__empty">Loading presets...</div>
          </div>
        </div>
      </div>
    `;
  }

  async loadPresets() {
    try {
      this.presets = await BacktestAPI.getPresets();
      this.renderPresets(this.presets);
      this.populateCategories();
      this.attachEvents();
    } catch (err) {
      this.container.querySelector('#presetList').innerHTML =
        '<div class="preset-selector__empty">Failed to load presets</div>';
    }
  }

  populateCategories() {
    const select = this.container.querySelector('#presetCategoryFilter');
    const categories = [...new Set(this.presets.map(p => p.category))].sort();
    categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat.replace(/_/g, ' ').toUpperCase();
      select.appendChild(opt);
    });
  }

  attachEvents() {
    this.container.querySelector('#presetCategoryFilter')
      .addEventListener('change', (e) => this.filterByCategory(e.target.value));
  }

  filterByCategory(category) {
    const filtered = category
      ? this.presets.filter(p => p.category === category)
      : this.presets;
    this.renderPresets(filtered);
  }

  renderPresets(presets) {
    const list = this.container.querySelector('#presetList');
    if (presets.length === 0) {
      list.innerHTML = '<div class="preset-selector__empty">No presets found</div>';
      return;
    }
    list.innerHTML = presets.map(p => `
      <div class="preset-card" data-preset-id="${p.id}">
        <div class="preset-card__header">
          <span class="preset-card__name">${p.name}</span>
          <span class="preset-card__risk preset-card__risk--${p.risk_level}">${p.risk_level}</span>
        </div>
        <div class="preset-card__desc">${p.description}</div>
        <div class="preset-card__meta">
          <span class="preset-card__strategy">${p.strategy.replace('_', ' ')}</span>
          <span>${p.recommended_timeframe}</span>
        </div>
        <button type="button" class="btn-sm preset-card__apply" data-preset-id="${p.id}">APPLY</button>
      </div>
    `).join('');

    list.querySelectorAll('.preset-card__apply').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const id = btn.dataset.presetId;
        const preset = this.presets.find(p => p.id === id);
        if (preset && this.onPresetSelected) {
          this.onPresetSelected(preset);
        }
      });
    });
  }
}

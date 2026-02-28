import { BacktestAPI } from '../services/api.js';

const STEPS = ['Source', 'Processing', 'Review', 'Applied'];

export class StrategyImportWizard {
  constructor() {
    this.overlay = null;
    this.currentStep = 0;
    this.activeTab = 'text';
    this.result = null;
    this.onApply = null;
  }

  open(onApply) {
    this.onApply = onApply;
    this.currentStep = 0;
    this.result = null;
    this.activeTab = 'text';
    this._createOverlay();
    this._renderStep();
  }

  close() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
  }

  _createOverlay() {
    this.close();
    this.overlay = document.createElement('div');
    this.overlay.className = 'wizard-overlay';
    this.overlay.innerHTML = `
      <div class="wizard-modal">
        <div class="wizard-header">
          <span class="wizard-header__title">Import Strategy</span>
          <button class="wizard-header__close" id="wizardClose">&times;</button>
        </div>
        <div class="wizard-steps" id="wizardSteps"></div>
        <div class="wizard-body" id="wizardBody"></div>
      </div>
    `;
    document.body.appendChild(this.overlay);

    this.overlay.querySelector('#wizardClose').addEventListener('click', () => this.close());
    this.overlay.addEventListener('click', (e) => {
      if (e.target === this.overlay) this.close();
    });
  }

  _renderStepIndicators() {
    const container = this.overlay.querySelector('#wizardSteps');
    container.innerHTML = STEPS.map((label, i) => {
      let cls = 'wizard-step';
      if (i === this.currentStep) cls += ' wizard-step--active';
      else if (i < this.currentStep) cls += ' wizard-step--done';
      return `<div class="${cls}">${label}</div>`;
    }).join('');
  }

  _renderStep() {
    this._renderStepIndicators();
    const body = this.overlay.querySelector('#wizardBody');

    switch (this.currentStep) {
      case 0: this._renderSourceStep(body); break;
      case 1: this._renderProcessingStep(body); break;
      case 2: this._renderReviewStep(body); break;
      case 3: this._renderAppliedStep(body); break;
    }
  }

  _renderSourceStep(body) {
    body.innerHTML = `
      <div class="wizard-body__tabs">
        <div class="wizard-body__tab ${this.activeTab === 'text' ? 'wizard-body__tab--active' : ''}" data-tab="text">Text</div>
        <div class="wizard-body__tab ${this.activeTab === 'url' ? 'wizard-body__tab--active' : ''}" data-tab="url">URL</div>
        <div class="wizard-body__tab ${this.activeTab === 'pdf' ? 'wizard-body__tab--active' : ''}" data-tab="pdf">PDF</div>
      </div>

      <div class="wizard-body__tab-content ${this.activeTab === 'text' ? 'wizard-body__tab-content--active' : ''}" data-content="text">
        <div class="wizard-body__label">Paste strategy description</div>
        <textarea class="wizard-body__textarea" id="wizardText" placeholder="e.g. Use a 20/50 MA crossover with RSI confirmation..."></textarea>
      </div>

      <div class="wizard-body__tab-content ${this.activeTab === 'url' ? 'wizard-body__tab-content--active' : ''}" data-content="url">
        <div class="wizard-body__label">Strategy article URL</div>
        <input class="wizard-body__input" id="wizardUrl" type="url" placeholder="https://example.com/strategy-article">
      </div>

      <div class="wizard-body__tab-content ${this.activeTab === 'pdf' ? 'wizard-body__tab-content--active' : ''}" data-content="pdf">
        <div class="wizard-body__label">Upload PDF</div>
        <input class="wizard-body__file-input" id="wizardPdf" type="file" accept=".pdf">
      </div>

      <button class="wizard-body__submit-btn" id="wizardExtract">EXTRACT PARAMETERS</button>
    `;

    body.querySelectorAll('.wizard-body__tab').forEach(tab => {
      tab.addEventListener('click', () => {
        this.activeTab = tab.dataset.tab;
        this._renderStep();
      });
    });

    body.querySelector('#wizardExtract').addEventListener('click', () => this._startExtraction());
  }

  async _startExtraction() {
    const text = this.overlay.querySelector('#wizardText')?.value?.trim();
    const url = this.overlay.querySelector('#wizardUrl')?.value?.trim();
    const pdfInput = this.overlay.querySelector('#wizardPdf');
    const pdfFile = pdfInput?.files?.[0];

    let hasInput = false;
    if (this.activeTab === 'text' && text) hasInput = true;
    if (this.activeTab === 'url' && url) hasInput = true;
    if (this.activeTab === 'pdf' && pdfFile) hasInput = true;

    if (!hasInput) return;

    this.currentStep = 1;
    this._renderStep();

    try {
      let result;
      if (this.activeTab === 'pdf' && pdfFile) {
        result = await BacktestAPI.importStrategyPdf(pdfFile);
      } else {
        const payload = {};
        if (this.activeTab === 'text') payload.text = text;
        if (this.activeTab === 'url') payload.url = url;
        result = await BacktestAPI.importStrategy(payload);
      }

      this.result = result;
      if (result.success) {
        this.currentStep = 2;
      } else {
        this._renderError(result.errors?.join('; ') || 'Extraction failed');
        return;
      }
    } catch (err) {
      this._renderError(err.message);
      return;
    }

    this._renderStep();
  }

  _renderProcessingStep(body) {
    body.innerHTML = `
      <div class="wizard-processing">
        <div class="wizard-spinner"></div>
        <div class="wizard-processing__text">Analyzing strategy content...</div>
      </div>
    `;
  }

  _renderReviewStep(body) {
    if (!this.result) return;

    const { strategy, params, config, confidence, reasoning } = this.result;
    const confidencePct = Math.round(confidence * 100);
    const lowConfidence = confidence < 0.5;

    const paramRows = params ? Object.entries(params).map(([k, v]) => `
      <div class="wizard-review__param-row">
        <span class="wizard-review__param-key">${k.replace(/_/g, ' ')}</span>
        <span class="wizard-review__param-value">${v}</span>
      </div>
    `).join('') : '<div class="wizard-review__param-row">No parameters extracted</div>';

    const configRows = config ? Object.entries(config).map(([k, v]) => `
      <div class="wizard-review__param-row">
        <span class="wizard-review__param-key">${k.replace(/_/g, ' ')}</span>
        <span class="wizard-review__param-value">${v}</span>
      </div>
    `).join('') : '';

    body.innerHTML = `
      <div>
        <div class="wizard-confidence ${lowConfidence ? 'wizard-confidence--low' : ''}">${confidencePct}%</div>
        <div class="wizard-review__strategy">Strategy: ${(strategy || 'unknown').replace(/_/g, ' ')}</div>

        <div class="wizard-body__label">Parameters</div>
        <div class="wizard-review__params">${paramRows}</div>

        ${configRows ? `
          <div class="wizard-body__label">Configuration</div>
          <div class="wizard-review__params">${configRows}</div>
        ` : ''}

        ${reasoning ? `<div class="wizard-review__reasoning">${reasoning}</div>` : ''}

        <div class="wizard-review__actions">
          <button class="wizard-body__submit-btn" id="wizardApply">APPLY TO FORM</button>
          <button class="wizard-error__retry" id="wizardCancel">CANCEL</button>
        </div>
      </div>
    `;

    body.querySelector('#wizardApply').addEventListener('click', () => {
      if (this.result && this.onApply) {
        this.onApply({
          strategy: this.result.strategy,
          params: this.result.params,
          config: this.result.config,
        });
        this.currentStep = 3;
        this._renderStep();
      }
    });

    body.querySelector('#wizardCancel').addEventListener('click', () => this.close());
  }

  _renderAppliedStep(body) {
    body.innerHTML = `
      <div class="wizard-processing">
        <div class="wizard-body__label" style="font-size: 0.9rem; margin-bottom: 0.5rem;">Parameters Applied</div>
        <div class="wizard-processing__text">Strategy configuration has been loaded into the form.</div>
        <button class="wizard-error__retry" id="wizardDone" style="margin-top: 1rem;">CLOSE</button>
      </div>
    `;
    body.querySelector('#wizardDone').addEventListener('click', () => this.close());
  }

  _renderError(message) {
    const body = this.overlay.querySelector('#wizardBody');
    body.innerHTML = `
      <div class="wizard-error">
        <div class="wizard-body__label">Extraction Failed</div>
        <div class="wizard-error__message">${message}</div>
        <button class="wizard-error__retry" id="wizardRetry">TRY AGAIN</button>
      </div>
    `;
    body.querySelector('#wizardRetry').addEventListener('click', () => {
      this.currentStep = 0;
      this._renderStep();
    });
  }
}

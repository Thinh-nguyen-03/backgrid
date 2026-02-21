import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);

export class EquityCurveChart {
  constructor(container) {
    this.container = container;
    this.chart = null;
  }

  render(equityCurve, label = 'Equity Curve') {
    if (!equityCurve || equityCurve.length === 0) return;

    this.container.innerHTML = `
      <div class="chart-wrapper">
        <div class="chart-header">
          <span class="chart-title">Equity Curve</span>
          <button type="button" id="scaleToggle" class="btn-sm">Log Scale</button>
        </div>
        <div class="chart-canvas-container">
          <canvas id="equityChart"></canvas>
        </div>
      </div>
    `;

    this.drawChart(equityCurve, label, false);

    this.container.querySelector('#scaleToggle').addEventListener('click', (e) => {
      const isLog = e.target.textContent === 'Log Scale';
      e.target.textContent = isLog ? 'Linear Scale' : 'Log Scale';
      this.drawChart(equityCurve, label, isLog);
    });
  }

  drawChart(data, label, logScale) {
    if (this.chart) this.chart.destroy();

    const canvas = this.container.querySelector('#equityChart');
    if (!canvas) return;

    const labels = data.map((_, i) => i);

    const isDarkMode = document.body.classList.contains('dark-mode');
    const gridColor = isDarkMode ? '#3f3f3f' : '#CBD5E1';
    const textColor = isDarkMode ? '#ffffff' : '#020617';

    this.chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label,
          data,
          borderColor: '#10B981',
          backgroundColor: 'rgba(16, 185, 129, 0.08)',
          borderWidth: 3,
          pointRadius: 0,
          fill: true,
          tension: 0.1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: {
            display: true,
            title: {
              display: true,
              text: 'Trading Days',
              font: { family: 'Space Grotesk', size: 12, weight: '800' },
              color: textColor
            },
            ticks: {
              font: { family: 'JetBrains Mono', size: 10, weight: '700' },
              maxTicksLimit: 10,
              color: textColor
            },
            grid: { color: gridColor, lineWidth: 1 },
            border: { color: textColor, width: 2 },
          },
          y: {
            type: logScale ? 'logarithmic' : 'linear',
            title: {
              display: true,
              text: 'Equity ($)',
              font: { family: 'Space Grotesk', size: 12, weight: '800' },
              color: textColor,
              padding: { bottom: 10 }
            },
            ticks: {
              font: { family: 'JetBrains Mono', size: 10, weight: '700' },
              callback: v => '$' + v.toLocaleString(),
              color: textColor,
              padding: 8
            },
            grid: { color: gridColor, lineWidth: 1 },
            border: { color: textColor, width: 2 },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#020617',
            titleFont: { family: 'JetBrains Mono', size: 12, weight: '700' },
            bodyFont: { family: 'JetBrains Mono', size: 12, weight: '700' },
            titleColor: '#FDE047',
            bodyColor: '#10B981',
            padding: 12,
            borderColor: '#10B981',
            borderWidth: 2,
            callbacks: {
              label: ctx => `$${ctx.parsed.y.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
            },
          },
        },
      },
    });
  }

  destroy() {
    if (this.chart) {
      this.chart.destroy();
      this.chart = null;
    }
  }
}

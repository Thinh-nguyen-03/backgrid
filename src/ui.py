"""Simple HTML UI for Phase 1"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def home():
    return """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Backgrid - Backtesting Engine</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
        }
        header { margin-bottom: 2rem; }
        h1 { font-size: 1.8rem; font-weight: 600; margin-bottom: 0.5rem; }
        .subtitle { color: #666; font-size: 0.9rem; }
        .container { display: grid; grid-template-columns: 400px 1fr; gap: 2rem; }
        .form-section { background: #f9f9f9; padding: 1.5rem; border-radius: 4px; }
        .form-group { margin-bottom: 1rem; }
        label { display: block; margin-bottom: 0.3rem; font-weight: 500; font-size: 0.9rem; }
        input {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 3px;
            font-size: 0.9rem;
        }
        input:focus { outline: none; border-color: #4CAF50; }
        button {
            width: 100%;
            padding: 0.7rem;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 3px;
            font-size: 1rem;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        button:hover { background: #45a049; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        .results-section { min-height: 400px; }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .metric {
            background: #f9f9f9;
            padding: 1rem;
            border-radius: 4px;
            border-left: 3px solid #4CAF50;
        }
        .metric-label { font-size: 0.75rem; color: #666; text-transform: uppercase; }
        .metric-value { font-size: 1.5rem; font-weight: 600; margin-top: 0.3rem; }
        .metric-value.positive { color: #4CAF50; }
        .metric-value.negative { color: #f44336; }
        .raw-json {
            background: #f9f9f9;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.85rem;
        }
        .raw-json summary { cursor: pointer; font-weight: 500; margin-bottom: 0.5rem; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
        .loading { color: #666; font-style: italic; }
        .error { color: #f44336; padding: 1rem; background: #ffebee; border-radius: 4px; }
        @media (max-width: 768px) {
            .container { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header>
        <h1>Backgrid</h1>
        <div class="subtitle">MA Crossover Backtesting Engine - Phase 1 MVP</div>
    </header>

    <div class="container">
        <div class="form-section">
            <form id="form">
                <div class="form-group">
                    <label for="symbol">Stock Symbol</label>
                    <input type="text" id="symbol" name="symbol" value="AAPL" required>
                </div>
                <div class="form-group">
                    <label for="start">Start Date</label>
                    <input type="date" id="start" name="start" value="2020-01-01" required>
                </div>
                <div class="form-group">
                    <label for="end">End Date</label>
                    <input type="date" id="end" name="end" value="2023-12-31" required>
                </div>
                <div class="form-group">
                    <label for="fast">Fast MA Period</label>
                    <input type="number" id="fast" name="fast" value="10" min="1" required>
                </div>
                <div class="form-group">
                    <label for="slow">Slow MA Period</label>
                    <input type="number" id="slow" name="slow" value="30" min="1" required>
                </div>
                <button type="submit" id="submitBtn">Run Backtest</button>
            </form>
        </div>

        <div class="results-section">
            <div id="results"></div>
        </div>
    </div>

    <script>
        const form = document.getElementById('form');
        const submitBtn = document.getElementById('submitBtn');
        const results = document.getElementById('results');

        form.onsubmit = async (e) => {
            e.preventDefault();

            submitBtn.disabled = true;
            submitBtn.textContent = 'Running...';
            results.innerHTML = '<div class="loading">Running backtest...</div>';

            const formData = new FormData(form);
            const body = {
                symbol: formData.get('symbol').trim().toUpperCase(),
                strategy: 'ma_crossover',
                start: formData.get('start'),
                end: formData.get('end'),
                params: {
                    fast: parseInt(formData.get('fast')),
                    slow: parseInt(formData.get('slow'))
                }
            };

            try {
                const res = await fetch("/api/v1/jobs", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(body)
                });

                const data = await res.json();

                if (!res.ok) {
                    results.innerHTML = `<div class="error">Error: ${data.error || data.detail || 'Unknown error'}</div>`;
                    return;
                }

                const sharpe = data.sharpe?.toFixed(4) || 'N/A';
                const maxDD = data.max_drawdown ? (data.max_drawdown * 100).toFixed(2) : 'N/A';
                const totalReturn = data.total_return ? (data.total_return * 100).toFixed(2) : 'N/A';
                const runtime = data.runtime_seconds?.toFixed(2) || 'N/A';

                const returnClass = data.total_return >= 0 ? 'positive' : 'negative';
                const sharpeClass = data.sharpe >= 0 ? 'positive' : 'negative';

                results.innerHTML = `
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-label">Sharpe Ratio</div>
                            <div class="metric-value ${sharpeClass}">${sharpe}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Total Return</div>
                            <div class="metric-value ${returnClass}">${totalReturn}%</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Max Drawdown</div>
                            <div class="metric-value negative">${maxDD}%</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Runtime</div>
                            <div class="metric-value">${runtime}s</div>
                        </div>
                    </div>
                    <details class="raw-json">
                        <summary>Full JSON Response</summary>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </details>
                `;
            } catch (err) {
                results.innerHTML = `<div class="error">Network error: ${err.message}</div>`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Run Backtest';
            }
        };
    </script>
</body>
</html>
    """

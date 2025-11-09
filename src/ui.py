"""Simple HTML UI for Phase 1"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def home():
    return """
    <!doctype html>
    <title>Backgrid - Phase 1</title>
    <h2>Run Backtest</h2>
    <form id="form">
        Symbol: <input name="symbol" value="AAPL"><br>
        Start: <input name="start" type="date" value="2020-01-01"><br>
        End: <input name="end" type="date" value="2023-12-31"><br>
        Fast MA: <input name="fast" type="number" value="10"><br>
        Slow MA: <input name="slow" type="number" value="30"><br>
        <button type="submit">Submit</button>
    </form>
    <pre id="result"></pre>

    <script>
      form.onsubmit = async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const body = {
          symbol: formData.get('symbol'),
          strategy: 'ma_crossover',
          start: formData.get('start'),
          end: formData.get('end'),
          params: {
            fast: parseInt(formData.get('fast')),
            slow: parseInt(formData.get('slow'))
          }
        };
        const res = await fetch("/api/v1/jobs", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(body)
        });
        result.textContent = JSON.stringify(await res.json(), null, 2);
      };
    </script>
    """

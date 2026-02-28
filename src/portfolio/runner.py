"""Portfolio backtest execution logic, used by both the API and Celery worker."""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_portfolio_backtest_sync(
    batch_id: str,
    symbols: List[str],
    strategy: str,
    params: Optional[Dict[str, Any]],
    start_date: str,
    end_date: Optional[str],
    config_dict: Optional[Dict[str, Any]],
    db: Session,
) -> Dict[str, Any]:
    """Run a portfolio backtest synchronously and persist all results to the DB.

    Updates PortfolioResult status from pending → running → completed/failed.
    Creates SymbolResult and TradeLedgerEntry records for each symbol processed.

    Returns a summary dict with successful and failed symbol lists.
    """
    from ..backtest import run_backtest_enhanced, BacktestConfig
    from ..data import YahooDataLoader
    from ..db import (
        update_portfolio_result,
        create_symbol_result,
        create_trade_entry,
    )
    from ..portfolio.metrics import aggregate_equity_curves

    def _result_id(symbol: str) -> str:
        return f"{batch_id}-{symbol}"

    def _trade_id(symbol: str, index: int) -> str:
        return f"{batch_id}-{symbol}-{index}"

    update_portfolio_result(db, batch_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc),
    })

    loader = YahooDataLoader()
    config = BacktestConfig(**(config_dict or {}))

    results = []
    failed_symbols = []
    symbol_curves = {}
    start_time = time.monotonic()

    for symbol in symbols:
        result_id = _result_id(symbol)
        try:
            df = loader.load(symbol, start_date, end_date)

            if df.empty:
                create_symbol_result(db, result_id, batch_id, symbol, {
                    "status": "error",
                    "error": "No data available",
                })
                failed_symbols.append(symbol)
                continue

            backtest_result = run_backtest_enhanced(df, strategy, params or {}, config, symbol)

            curve = backtest_result.equity_curve
            symbol_curves[symbol] = curve

            symbol_data = {
                "status": "completed",
                "job_id": backtest_result.job_id,
                "sharpe": backtest_result.sharpe,
                "max_drawdown": backtest_result.max_drawdown,
                "total_return": backtest_result.total_return,
                "total_trades": backtest_result.total_trades,
                "win_rate": backtest_result.win_rate,
                "total_transaction_costs": backtest_result.total_transaction_costs,
                "runtime_seconds": backtest_result.runtime_seconds,
                "equity_curve": curve,
            }
            create_symbol_result(db, result_id, batch_id, symbol, symbol_data)

            results.append({"symbol": symbol, **symbol_data})

            for i, trade in enumerate(backtest_result.trades):
                trade_id = _trade_id(symbol, i)
                create_trade_entry(db, trade_id, batch_id, trade.to_dict())

        except Exception as e:
            logger.error(f"Backtest failed for {symbol}: {e}")
            create_symbol_result(db, result_id, batch_id, symbol, {
                "status": "error",
                "error": str(e),
            })
            failed_symbols.append(symbol)

    successful = [r for r in results if r.get("status") == "completed"]
    sharpes = [r.get("sharpe", 0) for r in successful]
    returns = [r.get("total_return", 0) for r in successful]
    drawdowns = [r.get("max_drawdown", 0) for r in successful]

    avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0.0
    avg_return = sum(returns) / len(returns) if returns else 0.0
    avg_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else 0.0

    best_symbol = max(successful, key=lambda x: x.get("total_return", 0)).get("symbol") if successful else None
    worst_symbol = min(successful, key=lambda x: x.get("total_return", 0)).get("symbol") if successful else None

    total_trades = sum(r.get("total_trades", 0) for r in successful)
    runtime = round(time.monotonic() - start_time, 2)

    initial_capital = (config_dict or {}).get("initial_capital", 10000.0)
    portfolio_curve = aggregate_equity_curves(symbol_curves, initial_capital)

    update_portfolio_result(db, batch_id, {
        "status": "completed",
        "finished_at": datetime.now(timezone.utc),
        "symbols_completed": len(successful),
        "symbols_failed": len(failed_symbols),
        "failed_symbols": failed_symbols if failed_symbols else None,
        "symbol_count": len(successful),
        "total_trades": total_trades,
        "average_sharpe": round(avg_sharpe, 4),
        "average_return": round(avg_return, 4),
        "average_max_drawdown": round(avg_drawdown, 4),
        "best_symbol": best_symbol,
        "worst_symbol": worst_symbol,
        "runtime_seconds": runtime,
        "portfolio_equity_curve": portfolio_curve if portfolio_curve else None,
    })

    return {
        "successful": successful,
        "failed_symbols": failed_symbols,
    }

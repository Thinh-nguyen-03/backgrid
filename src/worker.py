"""Celery worker tasks for parallel backtesting."""

import logging
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from celery import Celery, group

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "backgrid",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Use threads pool on Windows - prefork has Python 3.13 compatibility issues
if sys.platform == "win32":
    app.conf.worker_pool = "threads"

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)


@app.task(bind=True, max_retries=3, default_retry_delay=5)
def run_single_backtest(
    self,
    symbol: str,
    strategy: str,
    params: Dict[str, Any],
    start_date: str,
    end_date: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a single-symbol backtest.

    This task is designed to be run in parallel across multiple symbols
    using Celery's group primitive.

    Args:
        symbol: Stock symbol to backtest
        strategy: Strategy name (ma_crossover, rsi, combined)
        params: Strategy parameters
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        config: Optional BacktestConfig as dict

    Returns:
        Backtest result dict with metrics and trade records
    """
    try:
        from .backtest import run_backtest_enhanced, BacktestConfig
        from .data import YahooDataLoader

        loader = YahooDataLoader()
        df = loader.load(symbol, start_date, end_date)

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return {
                "symbol": symbol,
                "status": "error",
                "error": "No data available",
            }

        backtest_config = BacktestConfig(**(config or {}))
        result = run_backtest_enhanced(df, strategy, params, backtest_config, symbol)

        return {
            "symbol": symbol,
            "status": "completed",
            "job_id": result.job_id,
            "sharpe": result.sharpe,
            "max_drawdown": result.max_drawdown,
            "total_return": result.total_return,
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_transaction_costs": result.total_transaction_costs,
            "runtime_seconds": result.runtime_seconds,
            "trades": [t.to_dict() for t in result.trades],
        }

    except Exception as exc:
        logger.error(f"Backtest failed for {symbol}: {exc}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(exc),
        }


@app.task(bind=True)
def run_portfolio_backtest(
    self,
    symbols: List[str],
    strategy: str,
    params: Dict[str, Any],
    start_date: str,
    end_date: str,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run parallel backtests across multiple symbols and aggregate results.

    This is the main entry point for portfolio backtesting. It dispatches
    individual symbol backtests in parallel using Celery group, waits for
    completion, and aggregates results.

    Args:
        symbols: List of stock symbols to backtest
        strategy: Strategy name
        params: Strategy parameters
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        config: Optional BacktestConfig as dict

    Returns:
        Aggregated portfolio results
    """
    from .portfolio.metrics import aggregate_symbol_results

    logger.info(f"Starting portfolio backtest: {len(symbols)} symbols")
    start_time = datetime.utcnow()

    job = group(
        run_single_backtest.s(
            symbol=symbol,
            strategy=strategy,
            params=params,
            start_date=start_date,
            end_date=end_date,
            config=config,
        )
        for symbol in symbols
    )

    result = job.apply_async()
    results = result.get(timeout=600)

    successful = [r for r in results if r.get("status") == "completed"]
    failed = [r for r in results if r.get("status") == "error"]

    aggregated = aggregate_symbol_results(successful)

    end_time = datetime.utcnow()
    runtime = (end_time - start_time).total_seconds()

    return {
        "batch_id": self.request.id,
        "status": "completed",
        "symbols_requested": len(symbols),
        "symbols_completed": len(successful),
        "symbols_failed": len(failed),
        "failed_symbols": [r.get("symbol") for r in failed],
        "runtime_seconds": round(runtime, 2),
        **aggregated,
    }


@app.task
def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results from multiple backtest tasks.

    This is a utility task that can be chained after a group of backtests.

    Args:
        results: List of backtest result dicts

    Returns:
        Aggregated statistics
    """
    from .portfolio.metrics import aggregate_symbol_results
    return aggregate_symbol_results(results)


@app.task(bind=True, name="backgrid.run_portfolio_backtest_task")
def run_portfolio_backtest_task(
    self,
    batch_id: str,
    symbols: List[str],
    strategy: str,
    params: Optional[Dict[str, Any]],
    start_date: str,
    end_date: Optional[str],
    config_dict: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Run portfolio backtest as an async task, persisting results to the DB.

    Status lifecycle: pending → running → completed / failed
    """
    from .db import SessionLocal, update_portfolio_result
    from .portfolio.runner import run_portfolio_backtest_sync

    db = SessionLocal()
    try:
        result = run_portfolio_backtest_sync(
            batch_id=batch_id,
            symbols=symbols,
            strategy=strategy,
            params=params,
            start_date=start_date,
            end_date=end_date,
            config_dict=config_dict,
            db=db,
        )
        return {"batch_id": batch_id, "status": "completed", **result}
    except Exception as exc:
        logger.error(f"Portfolio backtest task failed for {batch_id}: {exc}")
        update_portfolio_result(db, batch_id, {
            "status": "failed",
            "error": str(exc),
            "finished_at": datetime.now(timezone.utc),
        })
        raise
    finally:
        db.close()


@app.task
def health_check() -> Dict[str, Any]:
    """Health check task for worker monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": app.conf.broker_url,
    }

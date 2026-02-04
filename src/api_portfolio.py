"""Portfolio API endpoints (Week 6)

Provides endpoints for portfolio backtesting, multi-strategy backtests,
and symbol listing.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session

from .models import (
    PortfolioBacktestRequest,
    PortfolioBacktestResponse,
    TradeLedgerResponse,
    TradeRecordModel,
    MultiStrategyRequest,
    MultiStrategyResponse,
    SymbolListResponse,
    SymbolInfo,
    SymbolResultModel,
    JobStatus,
)
from .db import (
    get_db,
    PortfolioResult,
    SymbolResult,
    TradeLedgerEntry,
    create_portfolio_result,
    update_portfolio_result,
    get_portfolio_result,
    create_symbol_result,
    create_trade_entry,
    get_trades_for_batch,
)
from .backtest import run_backtest_enhanced, BacktestConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtest", tags=["portfolio"])


def _generate_batch_id() -> str:
    """Generate a unique batch ID."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_uuid = str(uuid.uuid4())[:8]
    return f"portfolio-{timestamp}-{short_uuid}"


def _generate_result_id(batch_id: str, symbol: str) -> str:
    """Generate a unique result ID for a symbol."""
    return f"{batch_id}-{symbol}"


def _generate_trade_id(batch_id: str, symbol: str, index: int) -> str:
    """Generate a unique trade ID."""
    return f"{batch_id}-{symbol}-{index}"


def _run_portfolio_backtest_sync(
    batch_id: str,
    symbols: List[str],
    strategy: str,
    params: Optional[Dict[str, Any]],
    start_date: str,
    end_date: Optional[str],
    config_dict: Optional[Dict[str, Any]],
    db: Session,
) -> Dict[str, Any]:
    """Run portfolio backtest synchronously and store results."""
    from .data import YahooDataLoader

    update_portfolio_result(db, batch_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc),
    })

    loader = YahooDataLoader()
    config = BacktestConfig(**(config_dict or {}))

    results = []
    all_trades = []
    failed_symbols = []

    for symbol in symbols:
        result_id = _generate_result_id(batch_id, symbol)
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
            }
            create_symbol_result(db, result_id, batch_id, symbol, symbol_data)

            results.append({
                "symbol": symbol,
                **symbol_data,
            })

            for i, trade in enumerate(backtest_result.trades):
                trade_id = _generate_trade_id(batch_id, symbol, i)
                create_trade_entry(db, trade_id, batch_id, trade.to_dict())
                all_trades.append(trade.to_dict())

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
    })

    return {
        "successful": successful,
        "failed_symbols": failed_symbols,
    }


@router.post("/portfolio", response_model=PortfolioBacktestResponse)
async def submit_portfolio_backtest(
    request: PortfolioBacktestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit a portfolio backtest job.

    Runs backtest across multiple symbols with the same strategy and
    aggregates results. For large portfolios (>10 symbols), consider
    using async execution with Celery workers.

    Args:
        request: Portfolio backtest request with symbols and strategy

    Returns:
        Portfolio backtest results with aggregated metrics
    """
    batch_id = _generate_batch_id()

    logger.info(
        f"Received portfolio backtest: batch_id={batch_id}, "
        f"symbols={len(request.symbols)}, strategy={request.strategy}"
    )

    config_dict = request.config.model_dump() if request.config else None

    portfolio = create_portfolio_result(
        db=db,
        batch_id=batch_id,
        symbols=request.symbols,
        strategy=request.strategy.value,
        params=request.params,
        start_date=request.start,
        end_date=request.end,
        config=config_dict,
    )

    try:
        result = _run_portfolio_backtest_sync(
            batch_id=batch_id,
            symbols=request.symbols,
            strategy=request.strategy.value,
            params=request.params,
            start_date=request.start,
            end_date=request.end,
            config_dict=config_dict,
            db=db,
        )

        db.refresh(portfolio)

        results_by_symbol = {}
        for r in result["successful"]:
            results_by_symbol[r["symbol"]] = SymbolResultModel(
                symbol=r["symbol"],
                status=r["status"],
                sharpe=r.get("sharpe"),
                max_drawdown=r.get("max_drawdown"),
                total_return=r.get("total_return"),
                total_trades=r.get("total_trades"),
                win_rate=r.get("win_rate"),
                total_transaction_costs=r.get("total_transaction_costs"),
            )

        return PortfolioBacktestResponse(
            batch_id=batch_id,
            status=JobStatus.COMPLETED,
            symbols_requested=portfolio.symbols_requested,
            symbols_completed=portfolio.symbols_completed,
            symbols_failed=portfolio.symbols_failed,
            failed_symbols=portfolio.failed_symbols,
            symbol_count=portfolio.symbol_count,
            total_trades=portfolio.total_trades,
            average_sharpe=portfolio.average_sharpe,
            average_return=portfolio.average_return,
            average_max_drawdown=portfolio.average_max_drawdown,
            best_symbol=portfolio.best_symbol,
            worst_symbol=portfolio.worst_symbol,
            runtime_seconds=portfolio.runtime_seconds,
            results_by_symbol=results_by_symbol,
            created_at=portfolio.created_at,
        )

    except Exception as e:
        logger.error(f"Portfolio backtest failed: {e}")
        update_portfolio_result(db, batch_id, {
            "status": "failed",
            "error": str(e),
            "finished_at": datetime.now(timezone.utc),
        })
        raise HTTPException(
            status_code=500,
            detail=f"Portfolio backtest failed: {str(e)}"
        )


@router.get("/portfolio/{batch_id}", response_model=PortfolioBacktestResponse)
async def get_portfolio_backtest(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """
    Get portfolio backtest results by batch ID.

    Args:
        batch_id: Unique batch identifier

    Returns:
        Portfolio backtest results

    Raises:
        HTTPException: If batch not found
    """
    portfolio = get_portfolio_result(db, batch_id)

    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail=f"Portfolio batch not found: {batch_id}"
        )

    symbol_results = db.query(SymbolResult).filter(
        SymbolResult.batch_id == batch_id
    ).all()

    results_by_symbol = {}
    for sr in symbol_results:
        results_by_symbol[sr.symbol] = SymbolResultModel(
            symbol=sr.symbol,
            status=sr.status,
            sharpe=sr.sharpe,
            max_drawdown=sr.max_drawdown,
            total_return=sr.total_return,
            total_trades=sr.total_trades,
            win_rate=sr.win_rate,
            total_transaction_costs=sr.total_transaction_costs,
            error=sr.error,
        )

    return PortfolioBacktestResponse(
        batch_id=portfolio.batch_id,
        status=JobStatus(portfolio.status),
        symbols_requested=portfolio.symbols_requested,
        symbols_completed=portfolio.symbols_completed,
        symbols_failed=portfolio.symbols_failed,
        failed_symbols=portfolio.failed_symbols,
        symbol_count=portfolio.symbol_count,
        total_trades=portfolio.total_trades,
        average_sharpe=portfolio.average_sharpe,
        average_return=portfolio.average_return,
        average_max_drawdown=portfolio.average_max_drawdown,
        best_symbol=portfolio.best_symbol,
        worst_symbol=portfolio.worst_symbol,
        runtime_seconds=portfolio.runtime_seconds,
        results_by_symbol=results_by_symbol,
        error=portfolio.error,
        created_at=portfolio.created_at,
    )


@router.get("/portfolio/{batch_id}/trades", response_model=TradeLedgerResponse)
async def get_portfolio_trades(
    batch_id: str,
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    limit: int = Query(1000, ge=1, le=10000, description="Max trades to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
):
    """
    Get trade ledger for a portfolio backtest.

    Args:
        batch_id: Unique batch identifier
        symbol: Optional filter by symbol
        strategy: Optional filter by strategy
        limit: Maximum number of trades to return
        offset: Pagination offset

    Returns:
        Trade ledger with list of trades
    """
    portfolio = get_portfolio_result(db, batch_id)

    if not portfolio:
        raise HTTPException(
            status_code=404,
            detail=f"Portfolio batch not found: {batch_id}"
        )

    trades = get_trades_for_batch(db, batch_id, symbol, strategy, limit, offset)

    trade_models = []
    for trade in trades:
        trade_models.append(TradeRecordModel(
            id=trade.id,
            symbol=trade.symbol,
            entry_date=trade.entry_date,
            exit_date=trade.exit_date,
            side=trade.side,
            shares=trade.shares,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            strategy=trade.strategy,
            transaction_costs=trade.transaction_costs,
        ))

    total_count = db.query(TradeLedgerEntry).filter(
        TradeLedgerEntry.batch_id == batch_id
    ).count()

    return TradeLedgerResponse(
        batch_id=batch_id,
        total_trades=total_count,
        trades=trade_models,
        offset=offset,
        limit=limit,
    )


@router.post("/multi-strategy", response_model=MultiStrategyResponse)
async def submit_multi_strategy_backtest(
    request: MultiStrategyRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a multi-strategy backtest for a single symbol.

    Combines signals from multiple strategies using the specified
    combination method.

    Args:
        request: Multi-strategy backtest request

    Returns:
        Backtest results with combined strategy metrics
    """
    from .strategies import StrategyManager, MAStrategy, RSIStrategy, CombinationMethod
    from .data import YahooDataLoader

    logger.info(
        f"Received multi-strategy backtest: symbol={request.symbol}, "
        f"strategies={len(request.strategies)}, method={request.combination_method}"
    )

    try:
        loader = YahooDataLoader()
        df = loader.load(request.symbol, request.start, request.end)

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail=f"No data available for {request.symbol}"
            )

        method_map = {
            "or": CombinationMethod.OR,
            "and": CombinationMethod.AND,
            "priority": CombinationMethod.PRIORITY,
            "weighted": CombinationMethod.WEIGHTED,
        }
        method = method_map.get(request.combination_method.value, CombinationMethod.PRIORITY)

        manager = StrategyManager(method=method)
        strategies_used = []

        for i, strat_config in enumerate(request.strategies):
            strat_type = strat_config.get("type")
            strat_params = strat_config.get("params", {})
            strat_name = strat_config.get("name", f"{strat_type}_{i}")
            weight = strat_config.get("weight", 1.0)

            if strat_type == "ma_crossover":
                strategy = MAStrategy(strat_params)
            elif strat_type == "rsi":
                strategy = RSIStrategy(strat_params)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown strategy type: {strat_type}"
                )

            manager.add_strategy(strat_name, strategy, weight)
            strategies_used.append(strat_name)

        signals = manager.calculate_signals(df)

        config = BacktestConfig(**(request.config.model_dump() if request.config else {}))

        from .backtest import (
            calculate_returns,
            calculate_sharpe_ratio,
            calculate_max_drawdown,
            calculate_total_return,
            _signals_to_positions,
        )

        positions = _signals_to_positions(signals)
        equity_curve = calculate_returns(df, positions, config.initial_capital)

        sharpe = calculate_sharpe_ratio(equity_curve)
        max_dd = calculate_max_drawdown(equity_curve)
        total_ret = calculate_total_return(equity_curve)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        job_id = f"multistrat-{timestamp}"

        return MultiStrategyResponse(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            symbol=request.symbol,
            strategies_used=strategies_used,
            combination_method=request.combination_method.value,
            sharpe=round(sharpe, 4),
            max_drawdown=round(max_dd, 4),
            total_return=round(total_ret, 4),
            total_trades=0,
            win_rate=0.0,
            equity_curve=equity_curve.tolist(),
            created_at=datetime.now(timezone.utc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-strategy backtest failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Multi-strategy backtest failed: {str(e)}"
        )


symbols_router = APIRouter(prefix="/api/v1", tags=["symbols"])


@symbols_router.get("/symbols", response_model=SymbolListResponse)
async def list_symbols(
    source: str = Query("yahoo", description="Data source: yahoo or postgres"),
    active_only: bool = Query(True, description="Only return active symbols"),
    limit: int = Query(100, ge=1, le=1000, description="Max symbols to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
):
    """
    List available symbols.

    For Yahoo Finance source, returns a default list of popular symbols.
    For PostgreSQL source, queries the symbols table from RapidTrader DB.

    Args:
        source: Data source (yahoo or postgres)
        active_only: Filter to active symbols only
        limit: Maximum symbols to return
        offset: Pagination offset
        sector: Optional sector filter

    Returns:
        List of available symbols with metadata
    """
    if source == "yahoo":
        default_symbols = [
            SymbolInfo(symbol="AAPL", name="Apple Inc.", sector="Technology", is_active=True),
            SymbolInfo(symbol="MSFT", name="Microsoft Corporation", sector="Technology", is_active=True),
            SymbolInfo(symbol="GOOGL", name="Alphabet Inc.", sector="Technology", is_active=True),
            SymbolInfo(symbol="AMZN", name="Amazon.com Inc.", sector="Consumer Cyclical", is_active=True),
            SymbolInfo(symbol="NVDA", name="NVIDIA Corporation", sector="Technology", is_active=True),
            SymbolInfo(symbol="META", name="Meta Platforms Inc.", sector="Technology", is_active=True),
            SymbolInfo(symbol="TSLA", name="Tesla Inc.", sector="Consumer Cyclical", is_active=True),
            SymbolInfo(symbol="BRK.B", name="Berkshire Hathaway", sector="Financial Services", is_active=True),
            SymbolInfo(symbol="JPM", name="JPMorgan Chase & Co.", sector="Financial Services", is_active=True),
            SymbolInfo(symbol="V", name="Visa Inc.", sector="Financial Services", is_active=True),
            SymbolInfo(symbol="JNJ", name="Johnson & Johnson", sector="Healthcare", is_active=True),
            SymbolInfo(symbol="UNH", name="UnitedHealth Group", sector="Healthcare", is_active=True),
            SymbolInfo(symbol="HD", name="The Home Depot", sector="Consumer Cyclical", is_active=True),
            SymbolInfo(symbol="PG", name="Procter & Gamble", sector="Consumer Defensive", is_active=True),
            SymbolInfo(symbol="MA", name="Mastercard Inc.", sector="Financial Services", is_active=True),
            SymbolInfo(symbol="DIS", name="Walt Disney Co.", sector="Communication Services", is_active=True),
            SymbolInfo(symbol="PYPL", name="PayPal Holdings", sector="Financial Services", is_active=True),
            SymbolInfo(symbol="NFLX", name="Netflix Inc.", sector="Communication Services", is_active=True),
            SymbolInfo(symbol="ADBE", name="Adobe Inc.", sector="Technology", is_active=True),
            SymbolInfo(symbol="CRM", name="Salesforce Inc.", sector="Technology", is_active=True),
            SymbolInfo(symbol="XOM", name="Exxon Mobil", sector="Energy", is_active=True),
            SymbolInfo(symbol="CVX", name="Chevron Corporation", sector="Energy", is_active=True),
            SymbolInfo(symbol="INTC", name="Intel Corporation", sector="Technology", is_active=True),
            SymbolInfo(symbol="CSCO", name="Cisco Systems", sector="Technology", is_active=True),
            SymbolInfo(symbol="VZ", name="Verizon Communications", sector="Communication Services", is_active=True),
        ]

        if sector:
            default_symbols = [s for s in default_symbols if s.sector == sector]

        symbols = default_symbols[offset:offset + limit]

        return SymbolListResponse(
            total=len(default_symbols),
            symbols=symbols,
            source="yahoo",
        )

    elif source == "postgres":
        try:
            from .data import PostgresDataLoader
            import os

            connection_string = os.getenv(
                "RT_DB_URL",
                "postgresql://user:pass@localhost:5432/rapidtrader"
            )
            loader = PostgresDataLoader(connection_string)
            all_symbols = loader.get_available_symbols(active_only=active_only)
            loader.close()

            symbols = []
            for sym in all_symbols[offset:offset + limit]:
                symbols.append(SymbolInfo(symbol=sym, is_active=True))

            return SymbolListResponse(
                total=len(all_symbols),
                symbols=symbols,
                source="postgres",
            )

        except Exception as e:
            logger.warning(f"Failed to load symbols from PostgreSQL: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"PostgreSQL data source unavailable: {str(e)}"
            )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown data source: {source}. Use 'yahoo' or 'postgres'"
        )

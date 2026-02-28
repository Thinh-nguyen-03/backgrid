"""Portfolio API endpoints."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, Query, Response
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
    SurvivorshipContext,
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
    get_trades_for_batch,
)
from .backtest import (
    run_backtest_enhanced,
    BacktestConfig,
    calculate_returns,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_total_return,
    _signals_to_positions,
)

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


@router.post("/portfolio", response_model=PortfolioBacktestResponse, status_code=202)
async def submit_portfolio_backtest(
    request: PortfolioBacktestRequest,
    db: Session = Depends(get_db),
):
    """Submit a portfolio backtest job for async execution.

    Returns 202 Accepted immediately. Poll GET /portfolio/{batch_id} for status.
    """
    from .worker import run_portfolio_backtest_task

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

    run_portfolio_backtest_task.delay(
        batch_id=batch_id,
        symbols=request.symbols,
        strategy=request.strategy.value,
        params=request.params,
        start_date=request.start,
        end_date=request.end,
        config_dict=config_dict,
    )

    return PortfolioBacktestResponse(
        batch_id=batch_id,
        status=JobStatus.PENDING,
        symbols_requested=portfolio.symbols_requested,
        created_at=portfolio.created_at,
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
            equity_curve=sr.equity_curve,
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
        portfolio_equity_curve=portfolio.portfolio_equity_curve,
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

        result = run_backtest_enhanced(
            df=df,
            strategy="combined",
            params={},
            config=config,
            symbol=request.symbol,
        )
        # Override equity curve with combined signals if strategy manager was used
        positions = _signals_to_positions(signals)
        equity_curve = calculate_returns(df, positions, config.initial_capital)
        sharpe = calculate_sharpe_ratio(equity_curve)
        max_dd = calculate_max_drawdown(equity_curve)
        total_ret = calculate_total_return(equity_curve)

        # Use trade metrics from enhanced backtest
        total_trades = result.total_trades
        win_rate = result.win_rate

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
            total_trades=total_trades,
            win_rate=round(win_rate, 4),
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
        from .sp500 import get_sp500_symbols
        all_raw = get_sp500_symbols()
        all_symbols = [
            SymbolInfo(symbol=s["symbol"], name=s["name"], sector=s["sector"], is_active=True)
            for s in all_raw
        ]

        if sector:
            all_symbols = [s for s in all_symbols if s.sector == sector]

        symbols = all_symbols[offset:offset + limit]

        return SymbolListResponse(
            total=len(all_symbols),
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


@symbols_router.get("/sectors", response_model=List[str])
async def list_sectors():
    """Return distinct sector names from the S&P 500 symbol list."""
    from .sp500 import get_sp500_symbols
    sectors = sorted({s["sector"] for s in get_sp500_symbols()})
    return sectors

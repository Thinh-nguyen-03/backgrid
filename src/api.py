"""FastAPI application"""

import time
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from .config import settings
    from .logging_config import configure_logging, set_request_id
    from .models import (
        BacktestRequest,
        BacktestResponse,
        HealthResponse,
        ErrorResponse,
        JobStatus
    )
    from .data import fetch_ohlcv, DataFetchError
    from .backtest import run_backtest, run_backtest_enhanced, BacktestConfig, BacktestResult
    from .db import get_db, init_db, Job, Result, create_job, create_result, get_job, get_result
    from .ui import router as ui_router, mount_static_files
    from .api_portfolio import router as portfolio_router
    from .api_portfolio import symbols_router
    from .api_presets import router as presets_router
    from .api_extraction import router as extraction_router
    from .api_sp500_history import router as sp500_history_router, run_auto_update_loop
except ImportError:
    import os

    class _FallbackSettings:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    settings = _FallbackSettings()

    def configure_logging(level: int = logging.INFO) -> None:
        logging.basicConfig(level=level)

    def set_request_id(value: str) -> None:
        pass

    from models import (
        BacktestRequest,
        BacktestResponse,
        HealthResponse,
        ErrorResponse,
        JobStatus
    )
    from data import fetch_ohlcv, DataFetchError
    from backtest import run_backtest, run_backtest_enhanced, BacktestConfig, BacktestResult
    from db import get_db, init_db, Job, Result, create_job, create_result, get_job, get_result
    from ui import router as ui_router, mount_static_files
    from api_portfolio import router as portfolio_router
    from api_portfolio import symbols_router
    from api_presets import router as presets_router
    from api_extraction import router as extraction_router
    from api_sp500_history import router as sp500_history_router, run_auto_update_loop

configure_logging()
logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a UUID to each request and expose it as X-Request-ID."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        set_request_id(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    init_db()
    logger.info("Starting Backgrid API")
    update_task = asyncio.create_task(run_auto_update_loop())
    yield
    update_task.cancel()
    logger.info("Shutting down Backgrid API")


app = FastAPI(
    title="Backgrid API",
    description="Backtesting engine for trading strategies",
    version="0.3.0",
    lifespan=lifespan
)

app.add_middleware(RequestIdMiddleware)

app.include_router(ui_router)
app.include_router(portfolio_router)
app.include_router(symbols_router)
app.include_router(presets_router)
app.include_router(extraction_router)
app.include_router(sp500_history_router)
mount_static_files(app)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check(response: Response, db: Session = Depends(get_db)):
    """Return service health with dependency probe results."""
    deps: dict = {}
    overall = "ok"

    # Probe database (critical)
    try:
        t0 = time.monotonic()
        db.execute(text("SELECT 1"))
        deps["database"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception as e:
        deps["database"] = {"status": "unavailable", "error": str(e)}
        overall = "degraded"

    # Probe Redis (non-critical)
    try:
        import redis as redis_lib
        t0 = time.monotonic()
        r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1)
        r.ping()
        deps["redis"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 2)}
    except Exception:
        deps["redis"] = {"status": "unavailable"}

    # Report yfinance circuit breaker state (non-critical)
    try:
        from .data.yahoo_loader import _yfinance_circuit
        circuit = _yfinance_circuit.status()
        deps["yfinance"] = {
            "status": circuit["state"],
            "failure_count": circuit["failure_count"],
            "last_success_seconds_ago": circuit["last_success_seconds_ago"],
        }
    except Exception:
        deps["yfinance"] = {"status": "unknown"}

    if overall == "degraded":
        response.status_code = 503

    return HealthResponse(
        status=overall,
        phase=2,
        timestamp=datetime.now(timezone.utc),
        dependencies=deps,
    )


@app.post("/api/v1/jobs", response_model=BacktestResponse)
async def submit_job(request: BacktestRequest, db: Session = Depends(get_db)):
    """Submit a backtest job and persist the result to the database."""
    try:
        logger.info(
            f"Received backtest job: symbol={request.symbol}, "
            f"strategy={request.strategy}, params={request.params}"
        )

        try:
            df = fetch_ohlcv(
                symbol=request.symbol,
                start=request.start,
                end=request.end
            )
            logger.info(f"Fetched {len(df)} data points for {request.symbol}")
        except DataFetchError as e:
            logger.error(f"Data fetch error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch data: {str(e)}"
            )
        except ValueError as e:
            logger.error(f"Invalid parameters: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters: {str(e)}"
            )

        try:
            if request.config:
                config = BacktestConfig(**request.config.model_dump())
                enhanced_result = run_backtest_enhanced(
                    df=df,
                    strategy=request.strategy.value,
                    params=request.params,
                    config=config,
                    symbol=request.symbol
                )
                result = enhanced_result.to_dict()
            else:
                result = run_backtest(
                    df=df,
                    strategy=request.strategy.value,
                    params=request.params
                )
            logger.info(f"Backtest completed: job_id={result['job_id']}, sharpe={result['sharpe']}")
        except ValueError as e:
            logger.error(f"Backtest error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Backtest execution failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during backtest: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal error during backtest: {str(e)}"
            )

        create_job(
            db=db,
            job_id=result["job_id"],
            symbol=request.symbol,
            strategy=request.strategy.value,
            params=request.params,
            start_date=request.start,
            end_date=request.end,
            created_at=result.get("created_at"),
        )
        create_result(
            db=db,
            job_id=result["job_id"],
            sharpe=result["sharpe"],
            max_drawdown=result["max_drawdown"],
            total_return=result["total_return"],
            runtime_seconds=result["runtime_seconds"],
            equity_curve=result["equity_curve"],
        )

        return BacktestResponse(
            job_id=result["job_id"],
            status=JobStatus.COMPLETED,
            sharpe=result["sharpe"],
            max_drawdown=result["max_drawdown"],
            total_return=result["total_return"],
            equity_curve=result["equity_curve"],
            runtime_seconds=result["runtime_seconds"],
            created_at=result["created_at"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in submit_job: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/v1/jobs/{job_id}", response_model=BacktestResponse)
async def get_job_endpoint(job_id: str, db: Session = Depends(get_db)):
    """Retrieve a backtest job and its result from the database."""
    logger.info(f"Retrieving job: {job_id}")

    job = get_job(db, job_id)
    if not job:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    result = get_result(db, job_id)

    return BacktestResponse(
        job_id=job.job_id,
        status=JobStatus(job.status),
        sharpe=result.sharpe if result else None,
        max_drawdown=result.max_drawdown if result else None,
        total_return=result.total_return if result else None,
        equity_curve=result.equity_curve if result else None,
        runtime_seconds=result.runtime_seconds if result else None,
        error=result.error if result else None,
        created_at=job.created_at,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

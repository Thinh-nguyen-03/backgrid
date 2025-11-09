"""FastAPI application (Phase 1 - MVP)"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict
import logging

from src.models import (
    BacktestRequest,
    BacktestResponse,
    HealthResponse,
    ErrorResponse,
    JobStatus
)
from src.data import fetch_ohlcv, DataFetchError
from src.backtest import run_backtest


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for Phase 1 (will be replaced with SQLite in next step)
job_results: Dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    logger.info("Starting Backgrid API (Phase 1 - MVP)")
    yield
    logger.info("Shutting down Backgrid API")


app = FastAPI(
    title="Backgrid API",
    description="Backtesting engine for trading strategies (Phase 1 - MVP)",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status with current phase information
    """
    return HealthResponse(
        status="ok",
        phase=1,
        timestamp=datetime.utcnow()
    )


@app.post("/api/v1/jobs", response_model=BacktestResponse)
async def submit_job(request: BacktestRequest):
    """
    Submit a backtest job (synchronous execution in Phase 1).

    Args:
        request: Backtest request parameters

    Returns:
        Backtest results including metrics and equity curve

    Raises:
        HTTPException: If data fetch fails or backtest execution fails
    """
    try:
        logger.info(
            f"Received backtest job: symbol={request.symbol}, "
            f"strategy={request.strategy}, params={request.params}"
        )

        # Fetch market data
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

        # Run backtest
        try:
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

        # Store result in memory (Phase 1)
        job_results[result["job_id"]] = result

        # Return response
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
async def get_job(job_id: str):
    """
    Retrieve backtest job results by ID.

    Args:
        job_id: Unique job identifier

    Returns:
        Backtest results

    Raises:
        HTTPException: If job not found
    """
    logger.info(f"Retrieving job: {job_id}")

    if job_id not in job_results:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    result = job_results[job_id]

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


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom exception handler for HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

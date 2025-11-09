"""Pydantic models for API request/response validation (Phase 1)"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum

class StrategyType(str, Enum):
    """Available trading strategies"""
    MA_CROSSOVER = "ma_crossover"

class JobStatus(str, Enum):
    """Job execution status"""
    QUEUED = "queued"  # Phase 2
    RUNNING = "running"  # Phase 2
    COMPLETED = "completed"
    FAILED = "failed"

class BacktestRequest(BaseModel):
    """Request model for submitting a backtest job"""
    symbol: str = Field(
        ...,
        description="Stock ticker symbol (e.g., AAPL, MSFT)",
        min_length=1,
        max_length=10
    )
    strategy: StrategyType = Field(
        ...,
        description="Strategy to backtest"
    )
    params: Optional[Dict[str, Any]] = Field(
        default={"fast": 10, "slow": 30},
        description="Strategy parameters (defaults to fast=10, slow=30 for MA crossover)"
    )
    start: str = Field(
        ...,
        description="Start date (YYYY-MM-DD format)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD format, defaults to today)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is uppercase and alphanumeric"""
        v = v.upper().strip()
        if not v.replace('.', '').replace('-', '').isalnum():
            raise ValueError("Symbol must be alphanumeric (dots and hyphens allowed)")
        return v

    @field_validator('params')
    @classmethod
    def validate_params(cls, v: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate strategy parameters"""
        if v is None:
            return {"fast": 10, "slow": 30}

        # Validate MA crossover params
        if 'fast' in v and 'slow' in v:
            fast = v['fast']
            slow = v['slow']
            if not isinstance(fast, int) or not isinstance(slow, int):
                raise ValueError("fast and slow must be integers")
            if fast <= 0 or slow <= 0:
                raise ValueError("fast and slow must be positive")
            if fast >= slow:
                raise ValueError("fast period must be less than slow period")

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "strategy": "ma_crossover",
                    "params": {"fast": 10, "slow": 30},
                    "start": "2020-01-01",
                    "end": "2023-12-31"
                }
            ]
        }
    }

class BacktestResponse(BaseModel):
    """Response model for backtest results"""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Job execution status")
    sharpe: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown (negative value)")
    total_return: Optional[float] = Field(None, description="Total return (percentage)")
    equity_curve: Optional[List[float]] = Field(None, description="Equity curve values")
    runtime_seconds: Optional[float] = Field(None, description="Execution time in seconds")
    error: Optional[str] = Field(None, description="Error message if job failed")
    created_at: Optional[datetime] = Field(None, description="Job creation timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_id": "manual-2025-01-15-123456",
                    "status": "completed",
                    "sharpe": 1.23,
                    "max_drawdown": -0.18,
                    "total_return": 0.45,
                    "equity_curve": [10000, 10200, 10500],
                    "runtime_seconds": 2.3,
                    "created_at": "2025-01-15T12:34:56"
                }
            ]
        }
    }

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(default="ok")
    phase: int = Field(default=1, description="Current implementation phase")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")

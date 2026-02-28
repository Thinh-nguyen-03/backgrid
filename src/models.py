"""Pydantic models for API request/response validation (Phase 1 + Week 6 Extensions)"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class StrategyType(str, Enum):
    """Available trading strategies"""
    MA_CROSSOVER = "ma_crossover"
    RSI = "rsi"
    COMBINED = "combined"


class JobStatus(str, Enum):
    """Job execution status"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CombinationMethodType(str, Enum):
    """Signal combination methods for multi-strategy"""
    OR = "or"
    AND = "and"
    PRIORITY = "priority"
    WEIGHTED = "weighted"


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

        if 'fast' in v and 'slow' in v:
            fast = v['fast']
            slow = v['slow']
            if not isinstance(fast, int) or not isinstance(slow, int):
                raise ValueError("fast and slow must be integers")
            if fast <= 0 or slow <= 0:
                raise ValueError("fast and slow must be positive")
            if fast >= slow:
                raise ValueError("fast period must be less than slow period")

        if 'rsi_period' in v:
            rsi_period = v['rsi_period']
            if not isinstance(rsi_period, int) or rsi_period < 2:
                raise ValueError("rsi_period must be an integer >= 2")

        if 'oversold_threshold' in v:
            oversold = v['oversold_threshold']
            if not isinstance(oversold, (int, float)) or not (0 <= oversold <= 100):
                raise ValueError("oversold_threshold must be between 0 and 100")

        if 'overbought_threshold' in v:
            overbought = v['overbought_threshold']
            if not isinstance(overbought, (int, float)) or not (0 <= overbought <= 100):
                raise ValueError("overbought_threshold must be between 0 and 100")

        if 'oversold_threshold' in v and 'overbought_threshold' in v:
            if v['oversold_threshold'] >= v['overbought_threshold']:
                raise ValueError("oversold_threshold must be less than overbought_threshold")

        return v

    config: Optional["BacktestConfigModel"] = Field(
        default=None,
        description="Backtest configuration (position sizing, transaction costs, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "strategy": "ma_crossover",
                    "params": {"fast": 10, "slow": 30},
                    "start": "2020-01-01",
                    "end": "2023-12-31",
                    "config": {
                        "initial_capital": 10000,
                        "enable_transaction_costs": True
                    }
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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


class BacktestConfigModel(BaseModel):
    """Configuration for enhanced backtest execution."""
    initial_capital: float = Field(default=10000.0, description="Starting capital", gt=0)
    position_sizing: str = Field(default="fixed", description="Position sizing method: fixed or atr")
    risk_per_trade: float = Field(default=0.05, description="Risk per trade as fraction", gt=0, le=1)
    atr_period: int = Field(default=14, description="ATR calculation period", ge=2)
    atr_multiplier: float = Field(default=3.0, description="ATR multiplier for stops", gt=0)
    enable_transaction_costs: bool = Field(default=True, description="Enable transaction cost modeling")
    commission_per_share: float = Field(default=0.005, description="Commission per share", ge=0)
    spread_bps: float = Field(default=5.0, description="Spread in basis points", ge=0)
    slippage_bps: float = Field(default=2.0, description="Slippage in basis points", ge=0)
    fill_at: str = Field(default="next_open", description="Fill timing: next_open, close, or vwap")

    @field_validator('position_sizing')
    @classmethod
    def validate_position_sizing(cls, v: str) -> str:
        valid = ["fixed", "atr"]
        if v not in valid:
            raise ValueError(f"position_sizing must be one of {valid}")
        return v

    @field_validator('fill_at')
    @classmethod
    def validate_fill_at(cls, v: str) -> str:
        valid = ["next_open", "close", "vwap"]
        if v not in valid:
            raise ValueError(f"fill_at must be one of {valid}")
        return v


class PortfolioBacktestRequest(BaseModel):
    """Request model for portfolio backtest submission."""
    symbols: List[str] = Field(
        ...,
        description="List of stock symbols to backtest",
        min_length=1,
        max_length=500
    )
    strategy: StrategyType = Field(
        ...,
        description="Strategy to apply to all symbols"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Strategy parameters"
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
    config: Optional[BacktestConfigModel] = Field(
        default=None,
        description="Backtest configuration"
    )

    @field_validator('symbols')
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        """Validate and normalize symbol list"""
        validated = []
        for symbol in v:
            symbol = symbol.upper().strip()
            if not symbol.replace('.', '').replace('-', '').isalnum():
                raise ValueError(f"Invalid symbol format: {symbol}")
            if symbol not in validated:
                validated.append(symbol)
        return validated

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbols": ["AAPL", "MSFT", "GOOGL"],
                    "strategy": "ma_crossover",
                    "params": {"fast": 20, "slow": 100},
                    "start": "2023-01-01",
                    "end": "2023-12-31",
                    "config": {
                        "initial_capital": 100000,
                        "position_sizing": "atr",
                        "risk_per_trade": 0.05
                    }
                }
            ]
        }
    }


class SymbolResultModel(BaseModel):
    """Per-symbol backtest result within a portfolio."""
    symbol: str = Field(..., description="Stock symbol")
    status: str = Field(..., description="Result status")
    sharpe: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown")
    total_return: Optional[float] = Field(None, description="Total return")
    total_trades: Optional[int] = Field(None, description="Number of trades")
    win_rate: Optional[float] = Field(None, description="Win rate")
    total_transaction_costs: Optional[float] = Field(None, description="Total transaction costs")
    equity_curve: Optional[List[float]] = Field(None, description="Equity curve values")
    error: Optional[str] = Field(None, description="Error message if failed")


class SurvivorshipContext(BaseModel):
    """Survivorship bias analysis attached to portfolio backtest results."""
    validation_performed: bool = False
    bias_risk: Optional[str] = Field(None, description="none, low, medium, high, or unknown")
    full_members: Optional[List[str]] = Field(None, description="Symbols with full S&P 500 coverage")
    partial_members_count: Optional[int] = None
    non_members_count: Optional[int] = None
    bias_summary: Optional[str] = None


class PortfolioBacktestResponse(BaseModel):
    """Response model for portfolio backtest results."""
    batch_id: str = Field(..., description="Unique batch identifier")
    status: JobStatus = Field(..., description="Overall job status")
    symbols_requested: int = Field(..., description="Number of symbols requested")
    symbols_completed: Optional[int] = Field(None, description="Number completed successfully")
    symbols_failed: Optional[int] = Field(None, description="Number that failed")
    failed_symbols: Optional[List[str]] = Field(None, description="List of failed symbols")
    symbol_count: Optional[int] = Field(None, description="Total symbols processed")
    total_trades: Optional[int] = Field(None, description="Total trades across all symbols")
    average_sharpe: Optional[float] = Field(None, description="Average Sharpe ratio")
    average_return: Optional[float] = Field(None, description="Average return")
    average_max_drawdown: Optional[float] = Field(None, description="Average max drawdown")
    best_symbol: Optional[str] = Field(None, description="Best performing symbol")
    worst_symbol: Optional[str] = Field(None, description="Worst performing symbol")
    runtime_seconds: Optional[float] = Field(None, description="Total runtime")
    portfolio_equity_curve: Optional[List[float]] = Field(
        None, description="Aggregated portfolio equity curve"
    )
    results_by_symbol: Optional[Dict[str, SymbolResultModel]] = Field(
        None, description="Per-symbol results"
    )
    survivorship_context: Optional[SurvivorshipContext] = Field(
        None, description="Survivorship bias analysis for the portfolio"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "batch_id": "portfolio-20260203-120000",
                    "status": "completed",
                    "symbols_requested": 3,
                    "symbols_completed": 3,
                    "symbols_failed": 0,
                    "symbol_count": 3,
                    "total_trades": 45,
                    "average_sharpe": 1.15,
                    "average_return": 0.12,
                    "average_max_drawdown": -0.08,
                    "best_symbol": "AAPL",
                    "worst_symbol": "MSFT",
                    "runtime_seconds": 5.2
                }
            ]
        }
    }


class TradeRecordModel(BaseModel):
    """Individual trade record."""
    id: Optional[str] = Field(None, description="Trade ID")
    symbol: str = Field(..., description="Stock symbol")
    entry_date: Optional[datetime] = Field(None, description="Entry date")
    exit_date: Optional[datetime] = Field(None, description="Exit date")
    side: str = Field(..., description="Trade side (long/short)")
    shares: int = Field(..., description="Number of shares")
    entry_price: Optional[float] = Field(None, description="Entry price")
    exit_price: Optional[float] = Field(None, description="Exit price")
    pnl: Optional[float] = Field(None, description="Profit/loss")
    pnl_pct: Optional[float] = Field(None, description="P&L percentage")
    strategy: Optional[str] = Field(None, description="Strategy name")
    transaction_costs: Optional[float] = Field(None, description="Transaction costs")


class TradeLedgerResponse(BaseModel):
    """Response model for trade ledger query."""
    batch_id: str = Field(..., description="Batch identifier")
    total_trades: int = Field(..., description="Total number of trades")
    trades: List[TradeRecordModel] = Field(..., description="List of trades")
    offset: int = Field(default=0, description="Pagination offset")
    limit: int = Field(default=1000, description="Pagination limit")


class MultiStrategyRequest(BaseModel):
    """Request model for multi-strategy single-symbol backtest."""
    symbol: str = Field(
        ...,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10
    )
    strategies: List[Dict[str, Any]] = Field(
        ...,
        description="List of strategy configurations",
        min_length=1,
        max_length=10
    )
    combination_method: CombinationMethodType = Field(
        default=CombinationMethodType.PRIORITY,
        description="How to combine signals from multiple strategies"
    )
    start: str = Field(
        ...,
        description="Start date (YYYY-MM-DD format)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    end: Optional[str] = Field(
        default=None,
        description="End date (YYYY-MM-DD format)",
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    config: Optional[BacktestConfigModel] = Field(
        default=None,
        description="Backtest configuration"
    )

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.upper().strip()
        if not v.replace('.', '').replace('-', '').isalnum():
            raise ValueError("Symbol must be alphanumeric (dots and hyphens allowed)")
        return v

    @field_validator('strategies')
    @classmethod
    def validate_strategies(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        valid_types = ["ma_crossover", "rsi"]
        for strat in v:
            if "type" not in strat:
                raise ValueError("Each strategy must have a 'type' field")
            if strat["type"] not in valid_types:
                raise ValueError(f"Strategy type must be one of {valid_types}")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "symbol": "AAPL",
                    "strategies": [
                        {"type": "ma_crossover", "params": {"fast": 20, "slow": 100}, "weight": 1.0},
                        {"type": "rsi", "params": {"rsi_period": 14, "oversold_threshold": 30}, "weight": 1.0}
                    ],
                    "combination_method": "priority",
                    "start": "2023-01-01",
                    "end": "2023-12-31"
                }
            ]
        }
    }


class MultiStrategyResponse(BaseModel):
    """Response model for multi-strategy backtest."""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Job status")
    symbol: str = Field(..., description="Stock symbol")
    strategies_used: List[str] = Field(..., description="Strategies that were applied")
    combination_method: str = Field(..., description="Signal combination method")
    sharpe: Optional[float] = Field(None, description="Sharpe ratio")
    max_drawdown: Optional[float] = Field(None, description="Maximum drawdown")
    total_return: Optional[float] = Field(None, description="Total return")
    total_trades: Optional[int] = Field(None, description="Number of trades")
    win_rate: Optional[float] = Field(None, description="Win rate")
    equity_curve: Optional[List[float]] = Field(None, description="Equity curve")
    runtime_seconds: Optional[float] = Field(None, description="Runtime")
    error: Optional[str] = Field(None, description="Error message")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class SymbolInfo(BaseModel):
    """Symbol information model."""
    symbol: str = Field(..., description="Stock symbol")
    name: Optional[str] = Field(None, description="Company name")
    sector: Optional[str] = Field(None, description="Sector")
    industry: Optional[str] = Field(None, description="Industry")
    is_active: bool = Field(default=True, description="Whether symbol is active")


class SymbolListResponse(BaseModel):
    """Response model for symbol list."""
    total: int = Field(..., description="Total number of symbols")
    symbols: List[SymbolInfo] = Field(..., description="List of symbols")
    source: str = Field(..., description="Data source")


# Resolve forward reference for BacktestRequest.config
BacktestRequest.model_rebuild()

"""Database models and configuration using SQLAlchemy (Phase 2)"""

import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, Column, String, DateTime, Float, Text, JSON, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship


def _utcnow():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://backgrid:backgrid_dev_password@localhost:5432/backgrid"
)

# Create SQLAlchemy engine with appropriate options for database type
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


class Job(Base):
    """Job model - stores backtest job metadata"""
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    strategy = Column(String, nullable=False)
    params = Column(JSON, nullable=True)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=True)

    status = Column(String, nullable=False, index=True, default="queued")

    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Job(job_id='{self.job_id}', symbol='{self.symbol}', status='{self.status}')>"


class Result(Base):
    """Result model - stores backtest results"""
    __tablename__ = "results"

    job_id = Column(String, primary_key=True, index=True)

    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    runtime_seconds = Column(Float, nullable=True)

    equity_curve = Column(JSON, nullable=True)

    error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)

    def __repr__(self):
        return f"<Result(job_id='{self.job_id}', sharpe={self.sharpe})>"


class PortfolioResult(Base):
    """Portfolio backtest result - stores batch backtest metadata and aggregated metrics."""
    __tablename__ = "portfolio_results"

    batch_id = Column(String(64), primary_key=True, index=True)
    symbols = Column(JSON, nullable=False)
    strategy = Column(String(64), nullable=False)
    params = Column(JSON, nullable=True)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=True)
    config = Column(JSON, nullable=True)

    status = Column(String(32), nullable=False, default="pending", index=True)

    symbols_requested = Column(Integer, nullable=True)
    symbols_completed = Column(Integer, nullable=True)
    symbols_failed = Column(Integer, nullable=True)
    failed_symbols = Column(JSON, nullable=True)

    symbol_count = Column(Integer, nullable=True)
    total_trades = Column(Integer, nullable=True)
    average_sharpe = Column(Float, nullable=True)
    average_return = Column(Float, nullable=True)
    average_max_drawdown = Column(Float, nullable=True)
    best_symbol = Column(String(16), nullable=True)
    worst_symbol = Column(String(16), nullable=True)

    runtime_seconds = Column(Float, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    symbol_results = relationship("SymbolResult", back_populates="portfolio", cascade="all, delete-orphan")
    trades = relationship("TradeLedgerEntry", back_populates="portfolio", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PortfolioResult(batch_id='{self.batch_id}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "symbols": self.symbols,
            "strategy": self.strategy,
            "params": self.params,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "config": self.config,
            "status": self.status,
            "symbols_requested": self.symbols_requested,
            "symbols_completed": self.symbols_completed,
            "symbols_failed": self.symbols_failed,
            "failed_symbols": self.failed_symbols,
            "symbol_count": self.symbol_count,
            "total_trades": self.total_trades,
            "average_sharpe": self.average_sharpe,
            "average_return": self.average_return,
            "average_max_drawdown": self.average_max_drawdown,
            "best_symbol": self.best_symbol,
            "worst_symbol": self.worst_symbol,
            "runtime_seconds": self.runtime_seconds,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class SymbolResult(Base):
    """Per-symbol result within a portfolio backtest."""
    __tablename__ = "symbol_results"

    id = Column(String(64), primary_key=True, index=True)
    batch_id = Column(String(64), ForeignKey("portfolio_results.batch_id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="pending")
    job_id = Column(String(64), nullable=True)

    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)
    total_transaction_costs = Column(Float, nullable=True)
    runtime_seconds = Column(Float, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)

    portfolio = relationship("PortfolioResult", back_populates="symbol_results")

    def __repr__(self):
        return f"<SymbolResult(id='{self.id}', symbol='{self.symbol}', sharpe={self.sharpe})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "symbol": self.symbol,
            "status": self.status,
            "job_id": self.job_id,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "total_transaction_costs": self.total_transaction_costs,
            "runtime_seconds": self.runtime_seconds,
            "error": self.error,
            "created_at": self.created_at,
        }


class TradeLedgerEntry(Base):
    """Individual trade record within a portfolio backtest."""
    __tablename__ = "trade_ledger"

    id = Column(String(64), primary_key=True, index=True)
    batch_id = Column(String(64), ForeignKey("portfolio_results.batch_id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)

    entry_date = Column(DateTime, nullable=True, index=True)
    exit_date = Column(DateTime, nullable=True)
    side = Column(String(8), nullable=False)
    shares = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    strategy = Column(String(64), nullable=True, index=True)
    transaction_costs = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=_utcnow)

    portfolio = relationship("PortfolioResult", back_populates="trades")

    def __repr__(self):
        return f"<TradeLedgerEntry(id='{self.id}', symbol='{self.symbol}', pnl={self.pnl})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "symbol": self.symbol,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "side": self.side,
            "shares": self.shares,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "strategy": self.strategy,
            "transaction_costs": self.transaction_costs,
            "created_at": self.created_at,
        }


def get_db() -> Session:
    """
    Dependency function for FastAPI to get database session.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session
            pass

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.

    This should be called once during application startup or migration.
    """
    Base.metadata.create_all(bind=engine)


def drop_db():
    """
    Drop all tables - USE WITH CAUTION!

    This is primarily for testing purposes.
    """
    Base.metadata.drop_all(bind=engine)


def create_portfolio_result(
    db: Session,
    batch_id: str,
    symbols: List[str],
    strategy: str,
    params: Optional[Dict[str, Any]],
    start_date: str,
    end_date: Optional[str],
    config: Optional[Dict[str, Any]] = None,
) -> PortfolioResult:
    """Create a new portfolio result entry."""
    portfolio = PortfolioResult(
        batch_id=batch_id,
        symbols=symbols,
        strategy=strategy,
        params=params,
        start_date=start_date,
        end_date=end_date,
        config=config,
        status="pending",
        symbols_requested=len(symbols),
        created_at=_utcnow(),
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def update_portfolio_result(
    db: Session,
    batch_id: str,
    updates: Dict[str, Any],
) -> Optional[PortfolioResult]:
    """Update a portfolio result with new data."""
    portfolio = db.query(PortfolioResult).filter(PortfolioResult.batch_id == batch_id).first()
    if not portfolio:
        return None

    for key, value in updates.items():
        if hasattr(portfolio, key):
            setattr(portfolio, key, value)

    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_portfolio_result(db: Session, batch_id: str) -> Optional[PortfolioResult]:
    """Get a portfolio result by batch_id."""
    return db.query(PortfolioResult).filter(PortfolioResult.batch_id == batch_id).first()


def create_symbol_result(
    db: Session,
    result_id: str,
    batch_id: str,
    symbol: str,
    result_data: Optional[Dict[str, Any]] = None,
) -> SymbolResult:
    """Create a symbol result entry."""
    symbol_result = SymbolResult(
        id=result_id,
        batch_id=batch_id,
        symbol=symbol,
        status="pending",
        created_at=_utcnow(),
    )
    if result_data:
        for key, value in result_data.items():
            if hasattr(symbol_result, key):
                setattr(symbol_result, key, value)

    db.add(symbol_result)
    db.commit()
    db.refresh(symbol_result)
    return symbol_result


def create_trade_entry(
    db: Session,
    trade_id: str,
    batch_id: str,
    trade_data: Dict[str, Any],
) -> TradeLedgerEntry:
    """Create a trade ledger entry."""
    trade = TradeLedgerEntry(
        id=trade_id,
        batch_id=batch_id,
        symbol=trade_data.get("symbol", "UNKNOWN"),
        entry_date=trade_data.get("entry_date"),
        exit_date=trade_data.get("exit_date"),
        side=trade_data.get("side", "long"),
        shares=trade_data.get("shares", 0),
        entry_price=trade_data.get("entry_price"),
        exit_price=trade_data.get("exit_price"),
        pnl=trade_data.get("pnl"),
        pnl_pct=trade_data.get("pnl_pct"),
        strategy=trade_data.get("strategy"),
        transaction_costs=trade_data.get("transaction_costs"),
        created_at=_utcnow(),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def get_trades_for_batch(
    db: Session,
    batch_id: str,
    symbol: Optional[str] = None,
    strategy: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[TradeLedgerEntry]:
    """Get trades for a batch with optional filtering."""
    query = db.query(TradeLedgerEntry).filter(TradeLedgerEntry.batch_id == batch_id)

    if symbol:
        query = query.filter(TradeLedgerEntry.symbol == symbol)
    if strategy:
        query = query.filter(TradeLedgerEntry.strategy == strategy)

    return query.order_by(TradeLedgerEntry.entry_date).offset(offset).limit(limit).all()


if __name__ == "__main__":
    print(f"Creating tables in database: {DATABASE_URL}")
    init_db()
    print("Tables created successfully!")

    print("\nTables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
        for column in table.columns:
            print(f"      {column.name}: {column.type}")

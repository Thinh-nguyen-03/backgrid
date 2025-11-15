"""Database models and configuration using SQLAlchemy (Phase 2)"""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, String, DateTime, Float, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://backgrid:backgrid_dev_password@localhost:5432/backgrid"
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,         # Number of permanent connections
    max_overflow=10,     # Max additional connections
    echo=False           # Set to True for SQL logging
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
    params = Column(JSON, nullable=True)  # Store as JSON
    start_date = Column(String, nullable=False)  # YYYY-MM-DD
    end_date = Column(String, nullable=True)     # YYYY-MM-DD

    status = Column(String, nullable=False, index=True, default="queued")

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Job(job_id='{self.job_id}', symbol='{self.symbol}', status='{self.status}')>"


class Result(Base):
    """Result model - stores backtest results"""
    __tablename__ = "results"

    job_id = Column(String, primary_key=True, index=True)

    # Backtest metrics
    sharpe = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    runtime_seconds = Column(Float, nullable=True)

    # Equity curve stored as JSON array
    equity_curve = Column(JSON, nullable=True)

    # Error information
    error = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Result(job_id='{self.job_id}', sharpe={self.sharpe})>"


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


if __name__ == "__main__":
    # For testing: create tables directly
    print(f"Creating tables in database: {DATABASE_URL}")
    init_db()
    print("Tables created successfully!")

    # Print table info
    print("\nTables created:")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")
        for column in table.columns:
            print(f"      {column.name}: {column.type}")

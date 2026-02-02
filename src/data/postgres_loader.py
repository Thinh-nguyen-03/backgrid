"""PostgreSQL data loader for RapidTrader database."""

import os
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from .base_loader import BaseDataLoader, DataLoaderConfig, DataLoadError

logger = logging.getLogger(__name__)


@dataclass
class PostgresLoaderConfig(DataLoaderConfig):
    """Configuration for PostgreSQL data loader.

    Attributes:
        database_url: PostgreSQL connection string
        pool_size: Number of connections in the pool
        max_overflow: Maximum overflow connections
        bars_table: Name of the daily bars table
        symbols_table: Name of the symbols metadata table
    """
    database_url: Optional[str] = None
    pool_size: int = 5
    max_overflow: int = 10
    bars_table: str = "bars_daily"
    symbols_table: str = "symbols"


class PostgresDataLoader(BaseDataLoader):
    """Data loader for RapidTrader PostgreSQL database.

    Connects to a PostgreSQL database containing market data in the
    RapidTrader schema format. Supports connection pooling and batch
    loading for efficient retrieval of multi-symbol data.

    RapidTrader Schema:
        bars_daily: symbol, d (date), open, high, low, close, volume
        symbols: symbol, name, sector, sub_sector, is_active, date_added

    Example:
        config = PostgresLoaderConfig(
            database_url="postgresql://user:pass@localhost:5432/rapidtrader"
        )
        loader = PostgresDataLoader(config)
        df = loader.load("AAPL", "2023-01-01", "2023-12-31")
    """

    def __init__(self, config: Optional[PostgresLoaderConfig] = None):
        """Initialize PostgreSQL loader with connection pooling.

        Args:
            config: PostgreSQL configuration. If database_url is not provided,
                   uses RT_DB_URL or DATABASE_URL environment variable.
        """
        self.pg_config = config or PostgresLoaderConfig()
        super().__init__(self.pg_config)

        db_url = (
            self.pg_config.database_url
            or os.getenv("RT_DB_URL")
            or os.getenv("DATABASE_URL")
        )

        if not db_url:
            raise DataLoadError(
                "Database URL not configured. Set RT_DB_URL environment variable "
                "or provide database_url in config."
            )

        self._engine: Engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=self.pg_config.pool_size,
            max_overflow=self.pg_config.max_overflow,
            pool_pre_ping=True,
            echo=False
        )

        logger.info(f"PostgreSQL loader initialized with pool_size={self.pg_config.pool_size}")

    def load(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None
    ) -> pd.DataFrame:
        """Load OHLCV data for a single symbol from PostgreSQL.

        Args:
            symbol: Stock ticker symbol
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format (defaults to today)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns

        Raises:
            DataLoadError: If data cannot be loaded
            ValueError: If parameters are invalid
        """
        self.validate_dates(start, end)
        symbol = symbol.upper().strip()

        cached = self._get_cached(symbol, start, end)
        if cached is not None:
            logger.debug(f"Cache hit for {symbol}")
            return cached

        logger.info(f"Loading {symbol} from PostgreSQL: {start} to {end or 'today'}")

        query = text(f"""
            SELECT d as date, open, high, low, close, volume
            FROM {self.pg_config.bars_table}
            WHERE symbol = :symbol
            AND d >= :start_date
            {"AND d <= :end_date" if end else ""}
            ORDER BY d
        """)

        params = {"symbol": symbol, "start_date": start}
        if end:
            params["end_date"] = end

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params=params, parse_dates=['date'])
        except Exception as e:
            raise DataLoadError(f"Failed to load data for {symbol}: {str(e)}") from e

        if df.empty:
            raise DataLoadError(
                f"No data found for {symbol} from {start} to {end or 'today'}"
            )

        df = df.set_index('date')
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df.index.name = None

        self.validate_dataframe(df, symbol)
        self._set_cached(symbol, start, end, df)

        logger.info(f"Loaded {len(df)} data points for {symbol}")
        return df

    def load_batch(
        self,
        symbols: List[str],
        start: str,
        end: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Load OHLCV data for multiple symbols efficiently.

        Uses a single SQL query to fetch all symbols, which is significantly
        faster than individual queries for large symbol lists.

        Args:
            symbols: List of stock ticker symbols
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format

        Returns:
            Dictionary mapping symbol to DataFrame
        """
        self.validate_dates(start, end)
        symbols = [s.upper().strip() for s in symbols]

        result: Dict[str, pd.DataFrame] = {}
        to_fetch: List[str] = []

        for symbol in symbols:
            cached = self._get_cached(symbol, start, end)
            if cached is not None:
                result[symbol] = cached
            else:
                to_fetch.append(symbol)

        if not to_fetch:
            return result

        logger.info(f"Batch loading {len(to_fetch)} symbols from PostgreSQL")

        query = text(f"""
            SELECT symbol, d as date, open, high, low, close, volume
            FROM {self.pg_config.bars_table}
            WHERE symbol = ANY(:symbols)
            AND d >= :start_date
            {"AND d <= :end_date" if end else ""}
            ORDER BY symbol, d
        """)

        params = {"symbols": to_fetch, "start_date": start}
        if end:
            params["end_date"] = end

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(query, conn, params=params, parse_dates=['date'])
        except Exception as e:
            raise DataLoadError(f"Batch load failed: {str(e)}") from e

        for symbol in to_fetch:
            symbol_df = df[df['symbol'] == symbol].copy()
            if len(symbol_df) >= 2:
                symbol_df = symbol_df.set_index('date')
                symbol_df = symbol_df[['open', 'high', 'low', 'close', 'volume']]
                symbol_df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                symbol_df.index.name = None
                self._set_cached(symbol, start, end, symbol_df)
                result[symbol] = symbol_df
            else:
                logger.warning(f"Insufficient data for {symbol}: {len(symbol_df)} rows")

        logger.info(f"Successfully loaded {len(result)} of {len(symbols)} symbols")
        return result

    def get_available_symbols(self) -> List[str]:
        """Get list of all active symbols from the symbols table.

        Returns:
            List of active ticker symbols
        """
        query = text(f"""
            SELECT symbol
            FROM {self.pg_config.symbols_table}
            WHERE is_active = true
            ORDER BY symbol
        """)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(query)
                return [row[0] for row in result]
        except Exception as e:
            logger.warning(f"Failed to get symbols list: {str(e)}")
            return []

    def get_symbol_metadata(self, symbol: str) -> Optional[Dict]:
        """Get metadata for a specific symbol.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with symbol metadata or None if not found
        """
        query = text(f"""
            SELECT symbol, name, sector, sub_sector, is_active, date_added
            FROM {self.pg_config.symbols_table}
            WHERE symbol = :symbol
        """)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(query, {"symbol": symbol.upper()})
                row = result.fetchone()
                if row:
                    return {
                        "symbol": row[0],
                        "name": row[1],
                        "sector": row[2],
                        "sub_sector": row[3],
                        "is_active": row[4],
                        "date_added": row[5]
                    }
        except Exception as e:
            logger.warning(f"Failed to get metadata for {symbol}: {str(e)}")

        return None

    def get_symbols_by_sector(self, sector: str) -> List[str]:
        """Get all active symbols in a specific sector.

        Args:
            sector: Sector name to filter by

        Returns:
            List of symbols in the sector
        """
        query = text(f"""
            SELECT symbol
            FROM {self.pg_config.symbols_table}
            WHERE sector = :sector
            AND is_active = true
            ORDER BY symbol
        """)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(query, {"sector": sector})
                return [row[0] for row in result]
        except Exception as e:
            logger.warning(f"Failed to get symbols for sector {sector}: {str(e)}")
            return []

    def close(self) -> None:
        """Close the database connection pool."""
        self._engine.dispose()
        logger.info("PostgreSQL connection pool closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

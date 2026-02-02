"""Abstract base class for data loaders."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import pandas as pd


@dataclass
class DataLoaderConfig:
    """Configuration for data loaders.

    Attributes:
        cache_ttl_seconds: Time-to-live for cached data in seconds
        batch_size: Number of symbols to fetch in a single batch
        max_retries: Maximum number of retry attempts for failed requests
        timeout_seconds: Request timeout in seconds
    """
    cache_ttl_seconds: int = 3600
    batch_size: int = 50
    max_retries: int = 3
    timeout_seconds: int = 30


class DataLoadError(Exception):
    """Raised when data loading fails."""
    pass


class BaseDataLoader(ABC):
    """Abstract base class for all data loaders.

    Data loaders are responsible for fetching OHLCV data from various sources
    including Yahoo Finance, PostgreSQL databases, and other providers.

    Subclasses must implement:
        - load(): Fetch data for a single symbol
        - load_batch(): Fetch data for multiple symbols
        - get_available_symbols(): List available symbols
    """

    def __init__(self, config: Optional[DataLoaderConfig] = None):
        """Initialize the data loader.

        Args:
            config: Loader configuration. Uses defaults if not provided.
        """
        self.config = config or DataLoaderConfig()
        self._cache: Dict[str, tuple[pd.DataFrame, datetime]] = {}

    @abstractmethod
    def load(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None
    ) -> pd.DataFrame:
        """Load OHLCV data for a single symbol.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format (defaults to today)

        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume
            Index is DatetimeIndex

        Raises:
            DataLoadError: If data cannot be loaded
            ValueError: If parameters are invalid
        """
        pass

    @abstractmethod
    def load_batch(
        self,
        symbols: List[str],
        start: str,
        end: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Load OHLCV data for multiple symbols.

        Args:
            symbols: List of stock ticker symbols
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format (defaults to today)

        Returns:
            Dictionary mapping symbol to DataFrame

        Raises:
            DataLoadError: If batch loading fails
        """
        pass

    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols.

        Returns:
            List of available ticker symbols
        """
        pass

    def validate_dates(self, start: str, end: Optional[str] = None) -> None:
        """Validate date parameters.

        Args:
            start: Start date string
            end: End date string (optional)

        Raises:
            ValueError: If dates are invalid
        """
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid start date format: {start}. Expected YYYY-MM-DD") from e

        if end:
            try:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError as e:
                raise ValueError(f"Invalid end date format: {end}. Expected YYYY-MM-DD") from e

            if end_dt <= start_dt:
                raise ValueError(f"End date ({end}) must be after start date ({start})")

    def validate_dataframe(self, df: pd.DataFrame, symbol: str) -> None:
        """Validate loaded DataFrame has required structure.

        Args:
            df: DataFrame to validate
            symbol: Symbol for error messages

        Raises:
            DataLoadError: If DataFrame is invalid
        """
        if df is None or df.empty:
            raise DataLoadError(f"No data returned for {symbol}")

        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise DataLoadError(f"Missing required columns for {symbol}: {missing}")

        if len(df) < 2:
            raise DataLoadError(
                f"Insufficient data for {symbol}: only {len(df)} data point(s). "
                f"Need at least 2 for backtesting."
            )

        if df['Close'].isna().any():
            nan_count = df['Close'].isna().sum()
            raise DataLoadError(
                f"Data contains {nan_count} missing Close price(s) for {symbol}"
            )

    def _get_cache_key(self, symbol: str, start: str, end: Optional[str]) -> str:
        """Generate cache key for a data request."""
        return f"{symbol}:{start}:{end or 'today'}"

    def _get_cached(self, symbol: str, start: str, end: Optional[str]) -> Optional[pd.DataFrame]:
        """Get cached data if available and not expired.

        Args:
            symbol: Stock ticker symbol
            start: Start date
            end: End date

        Returns:
            Cached DataFrame or None if not available/expired
        """
        key = self._get_cache_key(symbol, start, end)
        if key not in self._cache:
            return None

        df, cached_at = self._cache[key]
        age_seconds = (datetime.now() - cached_at).total_seconds()

        if age_seconds > self.config.cache_ttl_seconds:
            del self._cache[key]
            return None

        return df.copy()

    def _set_cached(
        self,
        symbol: str,
        start: str,
        end: Optional[str],
        df: pd.DataFrame
    ) -> None:
        """Cache loaded data.

        Args:
            symbol: Stock ticker symbol
            start: Start date
            end: End date
            df: DataFrame to cache
        """
        key = self._get_cache_key(symbol, start, end)
        self._cache[key] = (df.copy(), datetime.now())

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(config={self.config})"

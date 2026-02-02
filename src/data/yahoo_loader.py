"""Yahoo Finance data loader implementation."""

import logging
from typing import Optional, List, Dict
import pandas as pd
import yfinance as yf

from .base_loader import BaseDataLoader, DataLoaderConfig, DataLoadError

logger = logging.getLogger(__name__)


class YahooDataLoader(BaseDataLoader):
    """Data loader for Yahoo Finance via yfinance.

    Fetches OHLCV data from Yahoo Finance with caching support.
    This loader is suitable for development and testing but may have
    rate limits for production use.

    Example:
        loader = YahooDataLoader()
        df = loader.load("AAPL", "2023-01-01", "2023-12-31")
    """

    def __init__(self, config: Optional[DataLoaderConfig] = None):
        """Initialize Yahoo Finance loader.

        Args:
            config: Loader configuration
        """
        super().__init__(config)

    def load(
        self,
        symbol: str,
        start: str,
        end: Optional[str] = None
    ) -> pd.DataFrame:
        """Load OHLCV data for a single symbol from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            start: Start date in YYYY-MM-DD format
            end: End date in YYYY-MM-DD format (defaults to today)

        Returns:
            DataFrame with Open, High, Low, Close, Volume columns

        Raises:
            DataLoadError: If data cannot be fetched
            ValueError: If parameters are invalid
        """
        self.validate_dates(start, end)
        symbol = symbol.upper().strip()

        cached = self._get_cached(symbol, start, end)
        if cached is not None:
            logger.debug(f"Cache hit for {symbol}")
            return cached

        logger.info(f"Fetching data for {symbol} from {start} to {end or 'today'}")

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, auto_adjust=False)
        except Exception as e:
            raise DataLoadError(f"Failed to fetch data for {symbol}: {str(e)}") from e

        if df is None or df.empty:
            raise DataLoadError(
                f"No data returned for {symbol} from {start} to {end or 'today'}. "
                f"Symbol may be invalid or no trading data available."
            )

        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise DataLoadError(f"Missing columns in Yahoo data: {missing}")

        df = df[required_columns].copy()

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
        """Load OHLCV data for multiple symbols.

        Uses yfinance's batch download capability for efficiency.

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

        logger.info(f"Batch fetching {len(to_fetch)} symbols")

        try:
            batch_data = yf.download(
                to_fetch,
                start=start,
                end=end,
                auto_adjust=False,
                group_by='ticker',
                progress=False
            )
        except Exception as e:
            raise DataLoadError(f"Batch download failed: {str(e)}") from e

        for symbol in to_fetch:
            try:
                if len(to_fetch) == 1:
                    df = batch_data
                else:
                    if symbol not in batch_data.columns.get_level_values(0):
                        logger.warning(f"No data returned for {symbol}")
                        continue
                    df = batch_data[symbol]

                required = ['Open', 'High', 'Low', 'Close', 'Volume']
                if all(col in df.columns for col in required):
                    df = df[required].copy()
                    df = df.dropna()
                    if len(df) >= 2:
                        self._set_cached(symbol, start, end, df)
                        result[symbol] = df
                    else:
                        logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
                else:
                    logger.warning(f"Missing columns for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to process {symbol}: {str(e)}")
                continue

        logger.info(f"Successfully loaded {len(result)} of {len(symbols)} symbols")
        return result

    def get_available_symbols(self) -> List[str]:
        """Get list of available symbols.

        Yahoo Finance doesn't provide a symbol list API,
        so this returns an empty list.
        Use validate by attempting to fetch data.

        Returns:
            Empty list (Yahoo doesn't provide symbol enumeration)
        """
        return []

    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if a symbol is valid by attempting a minimal fetch.

        Args:
            symbol: Stock ticker symbol to validate

        Returns:
            True if symbol exists and has data
        """
        try:
            ticker = yf.Ticker(symbol.upper())
            info = ticker.info
            return info is not None and 'symbol' in info
        except Exception:
            return False

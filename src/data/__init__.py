"""Data loader module for Backgrid backtesting engine.

This module provides data loaders for fetching OHLCV data from various sources
including Yahoo Finance and PostgreSQL databases.

For backward compatibility, this module also exports legacy functions:
- fetch_ohlcv: Original Yahoo Finance fetcher
- DataFetchError: Legacy exception class
- validate_data: Data validation helper
- get_latest_close: Price extraction helper
"""

from .base_loader import BaseDataLoader, DataLoaderConfig, DataLoadError
from .yahoo_loader import YahooDataLoader
from .postgres_loader import PostgresDataLoader, PostgresLoaderConfig

from .legacy import (
    fetch_ohlcv,
    DataFetchError,
    validate_data,
    get_latest_close,
)

__all__ = [
    "BaseDataLoader",
    "DataLoaderConfig",
    "DataLoadError",
    "YahooDataLoader",
    "PostgresDataLoader",
    "PostgresLoaderConfig",
    "fetch_ohlcv",
    "DataFetchError",
    "validate_data",
    "get_latest_close",
]

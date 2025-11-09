"""Data fetcher module for downloading market data (Phase 1)"""

import yfinance as yf
import pandas as pd
from datetime import datetime
from typing import Optional

class DataFetchError(Exception):
    """Custom exception for data fetching errors"""
    pass

def fetch_ohlcv(
    symbol: str,
    start: str,
    end: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch OHLCV (Open, High, Low, Close, Volume) data from Yahoo Finance.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'MSFT')
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format (defaults to today)

    Returns:
        pandas DataFrame with columns: Open, High, Low, Close, Volume, Date (as index)

    Raises:
        DataFetchError: If data cannot be fetched or is invalid
        ValueError: If date format is invalid
    """
    # Validate date format
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid start date format: {start}. Expected YYYY-MM-DD") from e

    if end:
        try:
            end_date = datetime.strptime(end, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid end date format: {end}. Expected YYYY-MM-DD") from e

        if end_date <= start_date:
            raise ValueError(f"End date ({end}) must be after start date ({start})")

    # Fetch data from Yahoo Finance
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, auto_adjust=False)
    except Exception as e:
        raise DataFetchError(f"Failed to fetch data for {symbol}: {str(e)}") from e

    # Validate that we got data
    if df is None or df.empty:
        raise DataFetchError(
            f"No data returned for {symbol} from {start} to {end or 'today'}. "
            f"Symbol may be invalid or no trading data available for this period."
        )

    # Check for minimum data points (need at least 2 for any meaningful analysis)
    if len(df) < 2:
        raise DataFetchError(
            f"Insufficient data for {symbol}: only {len(df)} data point(s). "
            f"Need at least 2 data points for backtesting."
        )

    # Keep only the columns we need and ensure they exist
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise DataFetchError(
            f"Missing required columns in data: {missing_columns}. "
            f"Available columns: {list(df.columns)}"
        )

    # Select and return only required columns
    df = df[required_columns].copy()

    # Check for NaN values in critical columns (Close is most important)
    if df['Close'].isna().any():
        nan_count = df['Close'].isna().sum()
        raise DataFetchError(
            f"Data contains {nan_count} missing Close price(s) for {symbol}. "
            f"Cannot proceed with incomplete data."
        )

    return df

def validate_data(df: pd.DataFrame) -> bool:
    """
    Validate that the DataFrame contains valid OHLCV data.

    Args:
        df: DataFrame to validate

    Returns:
        True if valid, False otherwise
    """
    if df is None or df.empty:
        return False

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if not all(col in df.columns for col in required_columns):
        return False

    # Check that we have at least 2 rows
    if len(df) < 2:
        return False

    # Check for NaN in Close prices
    if df['Close'].isna().any():
        return False

    # Check that prices are positive
    if (df['Close'] <= 0).any():
        return False

    return True

def get_latest_close(df: pd.DataFrame) -> float:
    """
    Get the most recent closing price from the DataFrame.

    Args:
        df: OHLCV DataFrame

    Returns:
        Latest closing price

    Raises:
        ValueError: If DataFrame is empty or invalid
    """
    if df is None or df.empty:
        raise ValueError("DataFrame is empty")

    if 'Close' not in df.columns:
        raise ValueError("DataFrame missing 'Close' column")

    return float(df['Close'].iloc[-1])

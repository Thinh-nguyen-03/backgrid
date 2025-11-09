"""Unit tests for data fetcher module"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch
from src.data import (
    fetch_ohlcv,
    validate_data,
    get_latest_close,
    DataFetchError
)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing"""
    dates = pd.date_range(start='2020-01-01', periods=10, freq='D')
    data = {
        'Open': [100 + i for i in range(10)],
        'High': [105 + i for i in range(10)],
        'Low': [95 + i for i in range(10)],
        'Close': [102 + i for i in range(10)],
        'Volume': [1000000 + i * 10000 for i in range(10)]
    }
    df = pd.DataFrame(data, index=dates)
    return df


@pytest.fixture
def minimal_ohlcv_data():
    """Create minimal valid OHLCV data (2 rows)"""
    dates = pd.date_range(start='2020-01-01', periods=2, freq='D')
    data = {
        'Open': [100, 101],
        'High': [105, 106],
        'Low': [95, 96],
        'Close': [102, 103],
        'Volume': [1000000, 1010000]
    }
    df = pd.DataFrame(data, index=dates)
    return df


class TestFetchOHLCV:
    """Test fetch_ohlcv function"""

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_success(self, mock_ticker, sample_ohlcv_data):
        """Test successful data fetch"""
        # Mock the yfinance Ticker
        mock_instance = Mock()
        mock_instance.history.return_value = sample_ohlcv_data
        mock_ticker.return_value = mock_instance

        # Fetch data
        result = fetch_ohlcv('AAPL', '2020-01-01', '2020-01-10')

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        assert all(col in result.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
        mock_instance.history.assert_called_once_with(start='2020-01-01', end='2020-01-10', auto_adjust=False)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_without_end_date(self, mock_ticker, sample_ohlcv_data):
        """Test fetch without specifying end date"""
        mock_instance = Mock()
        mock_instance.history.return_value = sample_ohlcv_data
        mock_ticker.return_value = mock_instance

        result = fetch_ohlcv('AAPL', '2020-01-01')

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        mock_instance.history.assert_called_once_with(start='2020-01-01', end=None, auto_adjust=False)

    def test_fetch_ohlcv_invalid_start_date_format(self):
        """Test that invalid start date format raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            fetch_ohlcv('AAPL', '01/01/2020')
        assert "Invalid start date format" in str(exc_info.value)

    def test_fetch_ohlcv_invalid_end_date_format(self):
        """Test that invalid end date format raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '01/10/2020')
        assert "Invalid end date format" in str(exc_info.value)

    def test_fetch_ohlcv_end_before_start(self):
        """Test that end date before start date raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-10', '2020-01-01')
        assert "End date" in str(exc_info.value)
        assert "must be after start date" in str(exc_info.value)

    def test_fetch_ohlcv_end_equals_start(self):
        """Test that end date equal to start date raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '2020-01-01')
        assert "must be after start date" in str(exc_info.value)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_empty_data(self, mock_ticker):
        """Test that empty data raises DataFetchError"""
        mock_instance = Mock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        with pytest.raises(DataFetchError) as exc_info:
            fetch_ohlcv('INVALID', '2020-01-01', '2020-01-10')
        assert "No data returned" in str(exc_info.value)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_insufficient_data(self, mock_ticker):
        """Test that insufficient data (1 row) raises DataFetchError"""
        dates = pd.date_range(start='2020-01-01', periods=1, freq='D')
        data = {
            'Open': [100],
            'High': [105],
            'Low': [95],
            'Close': [102],
            'Volume': [1000000]
        }
        df = pd.DataFrame(data, index=dates)

        mock_instance = Mock()
        mock_instance.history.return_value = df
        mock_ticker.return_value = mock_instance

        with pytest.raises(DataFetchError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '2020-01-02')
        assert "Insufficient data" in str(exc_info.value)
        assert "only 1 data point" in str(exc_info.value)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_missing_columns(self, mock_ticker):
        """Test that missing required columns raises DataFetchError"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'Close': [102, 103, 104, 105, 106]
            # Missing High, Low, Volume
        }
        df = pd.DataFrame(data, index=dates)

        mock_instance = Mock()
        mock_instance.history.return_value = df
        mock_ticker.return_value = mock_instance

        with pytest.raises(DataFetchError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '2020-01-10')
        assert "Missing required columns" in str(exc_info.value)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_nan_in_close(self, mock_ticker):
        """Test that NaN values in Close column raises DataFetchError"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, np.nan, 104, 105, 106],
            'Volume': [1000000, 1010000, 1020000, 1030000, 1040000]
        }
        df = pd.DataFrame(data, index=dates)

        mock_instance = Mock()
        mock_instance.history.return_value = df
        mock_ticker.return_value = mock_instance

        with pytest.raises(DataFetchError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '2020-01-10')
        assert "missing Close price" in str(exc_info.value)

    @patch('src.data.yf.Ticker')
    def test_fetch_ohlcv_network_error(self, mock_ticker):
        """Test that network errors are handled gracefully"""
        mock_instance = Mock()
        mock_instance.history.side_effect = Exception("Network timeout")
        mock_ticker.return_value = mock_instance

        with pytest.raises(DataFetchError) as exc_info:
            fetch_ohlcv('AAPL', '2020-01-01', '2020-01-10')
        assert "Failed to fetch data" in str(exc_info.value)


class TestValidateData:
    """Test validate_data function"""

    def test_validate_data_valid(self, sample_ohlcv_data):
        """Test validation of valid data"""
        assert validate_data(sample_ohlcv_data) is True

    def test_validate_data_minimal_valid(self, minimal_ohlcv_data):
        """Test validation of minimal valid data (2 rows)"""
        assert validate_data(minimal_ohlcv_data) is True

    def test_validate_data_none(self):
        """Test validation of None"""
        assert validate_data(None) is False

    def test_validate_data_empty(self):
        """Test validation of empty DataFrame"""
        df = pd.DataFrame()
        assert validate_data(df) is False

    def test_validate_data_missing_columns(self):
        """Test validation with missing columns"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'Close': [102, 103, 104, 105, 106]
        }
        df = pd.DataFrame(data, index=dates)
        assert validate_data(df) is False

    def test_validate_data_single_row(self):
        """Test validation with single row (insufficient)"""
        dates = pd.date_range(start='2020-01-01', periods=1, freq='D')
        data = {
            'Open': [100],
            'High': [105],
            'Low': [95],
            'Close': [102],
            'Volume': [1000000]
        }
        df = pd.DataFrame(data, index=dates)
        assert validate_data(df) is False

    def test_validate_data_nan_in_close(self):
        """Test validation with NaN in Close column"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, np.nan, 104, 105, 106],
            'Volume': [1000000, 1010000, 1020000, 1030000, 1040000]
        }
        df = pd.DataFrame(data, index=dates)
        assert validate_data(df) is False

    def test_validate_data_negative_prices(self):
        """Test validation with negative prices"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, -103, 104, 105, 106],
            'Volume': [1000000, 1010000, 1020000, 1030000, 1040000]
        }
        df = pd.DataFrame(data, index=dates)
        assert validate_data(df) is False

    def test_validate_data_zero_prices(self):
        """Test validation with zero prices"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109],
            'Low': [95, 96, 97, 98, 99],
            'Close': [102, 0, 104, 105, 106],
            'Volume': [1000000, 1010000, 1020000, 1030000, 1040000]
        }
        df = pd.DataFrame(data, index=dates)
        assert validate_data(df) is False


class TestGetLatestClose:
    """Test get_latest_close function"""

    def test_get_latest_close_valid(self, sample_ohlcv_data):
        """Test getting latest close price from valid data"""
        result = get_latest_close(sample_ohlcv_data)
        assert result == 111.0  # Last close price in sample data

    def test_get_latest_close_minimal(self, minimal_ohlcv_data):
        """Test getting latest close from minimal data"""
        result = get_latest_close(minimal_ohlcv_data)
        assert result == 103.0

    def test_get_latest_close_empty_dataframe(self):
        """Test that empty DataFrame raises ValueError"""
        df = pd.DataFrame()
        with pytest.raises(ValueError) as exc_info:
            get_latest_close(df)
        assert "empty" in str(exc_info.value).lower()

    def test_get_latest_close_none(self):
        """Test that None raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            get_latest_close(None)
        assert "empty" in str(exc_info.value).lower()

    def test_get_latest_close_missing_column(self):
        """Test that missing Close column raises ValueError"""
        dates = pd.date_range(start='2020-01-01', periods=5, freq='D')
        data = {
            'Open': [100, 101, 102, 103, 104],
            'High': [105, 106, 107, 108, 109]
        }
        df = pd.DataFrame(data, index=dates)

        with pytest.raises(ValueError) as exc_info:
            get_latest_close(df)
        assert "Close" in str(exc_info.value)

    def test_get_latest_close_returns_float(self, sample_ohlcv_data):
        """Test that return type is float"""
        result = get_latest_close(sample_ohlcv_data)
        assert isinstance(result, float)

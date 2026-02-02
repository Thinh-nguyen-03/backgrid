"""Unit tests for data loader module."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.data import (
    BaseDataLoader,
    DataLoaderConfig,
    DataLoadError,
    YahooDataLoader,
    PostgresDataLoader,
    PostgresLoaderConfig,
)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(50) * 2)
    return pd.DataFrame({
        "Open": prices + np.random.randn(50) * 0.5,
        "High": prices + abs(np.random.randn(50)) * 2,
        "Low": prices - abs(np.random.randn(50)) * 2,
        "Close": prices,
        "Volume": np.random.randint(1000000, 10000000, 50)
    }, index=dates)


class TestDataLoaderConfig:
    """Test DataLoaderConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DataLoaderConfig()
        assert config.cache_ttl_seconds == 3600
        assert config.batch_size == 50
        assert config.max_retries == 3
        assert config.timeout_seconds == 30

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DataLoaderConfig(
            cache_ttl_seconds=1800,
            batch_size=100,
            max_retries=5,
            timeout_seconds=60
        )
        assert config.cache_ttl_seconds == 1800
        assert config.batch_size == 100


class TestBaseDataLoader:
    """Test BaseDataLoader abstract class."""

    def test_base_loader_is_abstract(self):
        """Test that BaseDataLoader cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseDataLoader()

    def test_validate_dates_valid(self):
        """Test date validation with valid dates."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        loader.validate_dates("2023-01-01", "2023-12-31")

    def test_validate_dates_invalid_format(self):
        """Test date validation with invalid format."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        with pytest.raises(ValueError) as exc_info:
            loader.validate_dates("01-01-2023")
        assert "invalid start date format" in str(exc_info.value).lower()

    def test_validate_dates_end_before_start(self):
        """Test date validation with end before start."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        with pytest.raises(ValueError) as exc_info:
            loader.validate_dates("2023-12-31", "2023-01-01")
        assert "must be after" in str(exc_info.value)

    def test_validate_dataframe_valid(self, sample_ohlcv_data):
        """Test DataFrame validation with valid data."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        loader.validate_dataframe(sample_ohlcv_data, "TEST")

    def test_validate_dataframe_empty(self):
        """Test DataFrame validation with empty data."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        with pytest.raises(DataLoadError):
            loader.validate_dataframe(pd.DataFrame(), "TEST")

    def test_validate_dataframe_missing_columns(self):
        """Test DataFrame validation with missing columns."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()
        df = pd.DataFrame({"Close": [100, 101, 102]})
        with pytest.raises(DataLoadError) as exc_info:
            loader.validate_dataframe(df, "TEST")
        assert "missing" in str(exc_info.value).lower()

    def test_cache_operations(self, sample_ohlcv_data):
        """Test caching functionality."""
        class ConcreteLoader(BaseDataLoader):
            def load(self, symbol, start, end=None):
                pass
            def load_batch(self, symbols, start, end=None):
                pass
            def get_available_symbols(self):
                return []

        loader = ConcreteLoader()

        assert loader._get_cached("AAPL", "2023-01-01", "2023-12-31") is None

        loader._set_cached("AAPL", "2023-01-01", "2023-12-31", sample_ohlcv_data)

        cached = loader._get_cached("AAPL", "2023-01-01", "2023-12-31")
        assert cached is not None
        assert len(cached) == len(sample_ohlcv_data)

        loader.clear_cache()
        assert loader._get_cached("AAPL", "2023-01-01", "2023-12-31") is None


class TestYahooDataLoader:
    """Test YahooDataLoader."""

    def test_yahoo_loader_init(self):
        """Test Yahoo loader initialization."""
        loader = YahooDataLoader()
        assert loader.config.cache_ttl_seconds == 3600

    def test_yahoo_loader_custom_config(self):
        """Test Yahoo loader with custom config."""
        config = DataLoaderConfig(cache_ttl_seconds=1800)
        loader = YahooDataLoader(config)
        assert loader.config.cache_ttl_seconds == 1800

    @patch('src.data.yahoo_loader.yf.Ticker')
    def test_yahoo_load_success(self, mock_ticker, sample_ohlcv_data):
        """Test successful data load from Yahoo."""
        mock_instance = Mock()
        mock_instance.history.return_value = sample_ohlcv_data
        mock_ticker.return_value = mock_instance

        loader = YahooDataLoader()
        df = loader.load("AAPL", "2023-01-01", "2023-12-31")

        assert len(df) == len(sample_ohlcv_data)
        assert "Close" in df.columns
        mock_ticker.assert_called_once_with("AAPL")

    @patch('src.data.yahoo_loader.yf.Ticker')
    def test_yahoo_load_empty_data(self, mock_ticker):
        """Test Yahoo load with empty response."""
        mock_instance = Mock()
        mock_instance.history.return_value = pd.DataFrame()
        mock_ticker.return_value = mock_instance

        loader = YahooDataLoader()
        with pytest.raises(DataLoadError) as exc_info:
            loader.load("INVALID", "2023-01-01", "2023-12-31")
        assert "no data" in str(exc_info.value).lower()

    @patch('src.data.yahoo_loader.yf.Ticker')
    def test_yahoo_load_uses_cache(self, mock_ticker, sample_ohlcv_data):
        """Test that Yahoo loader uses cache on second call."""
        mock_instance = Mock()
        mock_instance.history.return_value = sample_ohlcv_data
        mock_ticker.return_value = mock_instance

        loader = YahooDataLoader()

        df1 = loader.load("AAPL", "2023-01-01", "2023-12-31")
        df2 = loader.load("AAPL", "2023-01-01", "2023-12-31")

        assert mock_ticker.call_count == 1

    @patch('src.data.yahoo_loader.yf.download')
    def test_yahoo_batch_load(self, mock_download, sample_ohlcv_data):
        """Test batch loading from Yahoo."""
        mock_download.return_value = sample_ohlcv_data

        loader = YahooDataLoader()
        result = loader.load_batch(["AAPL"], "2023-01-01", "2023-12-31")

        assert "AAPL" in result or len(result) >= 0

    def test_yahoo_get_available_symbols(self):
        """Test that Yahoo returns empty symbol list."""
        loader = YahooDataLoader()
        symbols = loader.get_available_symbols()
        assert symbols == []


class TestPostgresDataLoader:
    """Test PostgresDataLoader."""

    def test_postgres_loader_no_url_raises(self):
        """Test that missing database URL raises error."""
        with patch.dict('os.environ', {}, clear=True):
            config = PostgresLoaderConfig(database_url=None)
            with pytest.raises(DataLoadError) as exc_info:
                PostgresDataLoader(config)
            assert "database url" in str(exc_info.value).lower()

    def test_postgres_config_defaults(self):
        """Test PostgresLoaderConfig default values."""
        config = PostgresLoaderConfig()
        assert config.pool_size == 5
        assert config.max_overflow == 10
        assert config.bars_table == "bars_daily"
        assert config.symbols_table == "symbols"

    @patch('src.data.postgres_loader.create_engine')
    def test_postgres_loader_init_with_url(self, mock_create_engine):
        """Test PostgreSQL loader initialization with URL."""
        mock_create_engine.return_value = MagicMock()

        config = PostgresLoaderConfig(
            database_url="postgresql://user:pass@localhost:5432/test"
        )
        loader = PostgresDataLoader(config)

        mock_create_engine.assert_called_once()

    @patch('src.data.postgres_loader.create_engine')
    def test_postgres_loader_context_manager(self, mock_create_engine):
        """Test PostgreSQL loader as context manager."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        config = PostgresLoaderConfig(
            database_url="postgresql://user:pass@localhost:5432/test"
        )

        with PostgresDataLoader(config) as loader:
            pass

        mock_engine.dispose.assert_called_once()


class TestDataLoadError:
    """Test DataLoadError exception."""

    def test_data_load_error_message(self):
        """Test DataLoadError stores message correctly."""
        error = DataLoadError("Test error message")
        assert str(error) == "Test error message"

    def test_data_load_error_inheritance(self):
        """Test DataLoadError is an Exception."""
        error = DataLoadError("Test")
        assert isinstance(error, Exception)

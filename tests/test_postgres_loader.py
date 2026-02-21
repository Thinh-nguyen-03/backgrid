"""Unit tests for PostgreSQL data loader.

Week 7: Tests connection setup, parameter validation, query construction,
batch loading, caching, and error handling. Uses mocks to avoid requiring
a live PostgreSQL connection.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.data.postgres_loader import PostgresDataLoader, PostgresLoaderConfig
from src.data.base_loader import DataLoadError


class TestPostgresLoaderConfig:

    def test_default_config(self):
        cfg = PostgresLoaderConfig()
        assert cfg.pool_size == 5
        assert cfg.max_overflow == 10
        assert cfg.bars_table == "bars_daily"
        assert cfg.symbols_table == "symbols"
        assert cfg.database_url is None

    def test_custom_config(self):
        cfg = PostgresLoaderConfig(
            database_url="postgresql://user:pass@host/db",
            pool_size=10,
            bars_table="custom_bars",
        )
        assert cfg.database_url == "postgresql://user:pass@host/db"
        assert cfg.pool_size == 10
        assert cfg.bars_table == "custom_bars"


class TestPostgresLoaderInit:

    @patch("src.data.postgres_loader.create_engine")
    def test_init_with_config_url(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)
        mock_engine.assert_called_once()
        assert loader.pg_config.database_url == "postgresql://u:p@h/d"

    @patch.dict("os.environ", {"RT_DB_URL": "postgresql://env:test@h/db"})
    @patch("src.data.postgres_loader.create_engine")
    def test_init_uses_rt_db_url_env(self, mock_engine):
        loader = PostgresDataLoader()
        mock_engine.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_init_no_url_raises(self):
        # Clear both env vars
        import os
        os.environ.pop("RT_DB_URL", None)
        os.environ.pop("DATABASE_URL", None)
        with pytest.raises(DataLoadError, match="Database URL not configured"):
            PostgresDataLoader()

    @patch("src.data.postgres_loader.create_engine")
    def test_pool_size_passed_to_engine(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d", pool_size=8)
        PostgresDataLoader(cfg)
        call_kwargs = mock_engine.call_args[1]
        assert call_kwargs["pool_size"] == 8


class TestPostgresLoaderLoad:

    @patch("src.data.postgres_loader.create_engine")
    def test_load_returns_dataframe(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        mock_df = pd.DataFrame({
            "date": dates,
            "open": np.random.rand(10) * 100 + 100,
            "high": np.random.rand(10) * 100 + 110,
            "low": np.random.rand(10) * 100 + 90,
            "close": np.random.rand(10) * 100 + 100,
            "volume": np.random.randint(100_000, 1_000_000, 10),
        })

        with patch("pandas.read_sql", return_value=mock_df):
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            result = loader.load("AAPL", "2023-01-01", "2023-01-10")
            assert "Open" in result.columns
            assert "Close" in result.columns
            assert len(result) == 10

    @patch("src.data.postgres_loader.create_engine")
    def test_load_empty_raises(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        empty_df = pd.DataFrame()

        with patch("pandas.read_sql", return_value=empty_df):
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            with pytest.raises(DataLoadError, match="No data found"):
                loader.load("FAKE", "2023-01-01", "2023-12-31")

    @patch("src.data.postgres_loader.create_engine")
    def test_load_caches_result(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        mock_df = pd.DataFrame({
            "date": dates,
            "open": [100] * 10,
            "high": [110] * 10,
            "low": [90] * 10,
            "close": [100] * 10,
            "volume": [1_000_000] * 10,
        })

        with patch("pandas.read_sql", return_value=mock_df) as mock_read:
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            loader.load("AAPL", "2023-01-01", "2023-01-10")
            loader.load("AAPL", "2023-01-01", "2023-01-10")
            assert mock_read.call_count == 1

    @patch("src.data.postgres_loader.create_engine")
    def test_load_validates_dates(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)
        with pytest.raises(ValueError):
            loader.load("AAPL", "not-a-date")

    @patch("src.data.postgres_loader.create_engine")
    def test_load_normalizes_symbol(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        mock_df = pd.DataFrame({
            "date": dates,
            "open": [100] * 10,
            "high": [110] * 10,
            "low": [90] * 10,
            "close": [100] * 10,
            "volume": [1_000_000] * 10,
        })

        with patch("pandas.read_sql", return_value=mock_df):
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            result = loader.load(" aapl ", "2023-01-01", "2023-01-10")
            assert len(result) == 10


class TestPostgresLoaderBatch:

    @patch("src.data.postgres_loader.create_engine")
    def test_batch_load_multiple_symbols(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        rows = []
        for sym in ["AAPL", "MSFT"]:
            for i, d in enumerate(dates):
                rows.append({
                    "symbol": sym,
                    "date": d,
                    "open": 100 + i,
                    "high": 110 + i,
                    "low": 90 + i,
                    "close": 100 + i,
                    "volume": 1_000_000,
                })
        mock_df = pd.DataFrame(rows)

        with patch("pandas.read_sql", return_value=mock_df):
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            result = loader.load_batch(["AAPL", "MSFT"], "2023-01-01", "2023-01-10")
            assert "AAPL" in result
            assert "MSFT" in result
            assert len(result["AAPL"]) == 10

    @patch("src.data.postgres_loader.create_engine")
    def test_batch_skips_insufficient_data(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        # Only one row for FAKE (insufficient), 10 for AAPL
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        rows = [{"symbol": "FAKE", "date": dates[0], "open": 100, "high": 110,
                 "low": 90, "close": 100, "volume": 1_000_000}]
        for d in dates:
            rows.append({"symbol": "AAPL", "date": d, "open": 100, "high": 110,
                         "low": 90, "close": 100, "volume": 1_000_000})
        mock_df = pd.DataFrame(rows)

        with patch("pandas.read_sql", return_value=mock_df):
            mock_conn = MagicMock()
            mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
            mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

            result = loader.load_batch(["AAPL", "FAKE"], "2023-01-01", "2023-01-10")
            assert "AAPL" in result
            assert "FAKE" not in result


class TestPostgresLoaderMetadata:

    @patch("src.data.postgres_loader.create_engine")
    def test_get_available_symbols(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([("AAPL",), ("MSFT",)]))
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        symbols = loader.get_available_symbols()
        assert symbols == ["AAPL", "MSFT"]

    @patch("src.data.postgres_loader.create_engine")
    def test_get_symbol_metadata(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        mock_row = ("AAPL", "Apple Inc.", "Technology", "Consumer Electronics", True, "2020-01-01")
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        meta = loader.get_symbol_metadata("AAPL")
        assert meta["symbol"] == "AAPL"
        assert meta["sector"] == "Technology"

    @patch("src.data.postgres_loader.create_engine")
    def test_get_symbol_metadata_not_found(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(return_value=False)

        meta = loader.get_symbol_metadata("FAKE")
        assert meta is None

    @patch("src.data.postgres_loader.create_engine")
    def test_context_manager(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        with PostgresDataLoader(cfg) as loader:
            assert loader is not None
        mock_engine.return_value.dispose.assert_called_once()

    @patch("src.data.postgres_loader.create_engine")
    def test_close_disposes_engine(self, mock_engine):
        cfg = PostgresLoaderConfig(database_url="postgresql://u:p@h/d")
        loader = PostgresDataLoader(cfg)
        loader.close()
        mock_engine.return_value.dispose.assert_called_once()

"""Unit tests for position sizing module."""

import pytest
import pandas as pd
import numpy as np

from src.position_sizing import (
    BasePositionSizer,
    PositionSizeResult,
    ATRPositionSizer,
    FixedFractionalSizer,
)


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=50, freq="D")
    np.random.seed(42)
    base_price = 100
    prices = []
    for i in range(50):
        base_price += np.random.randn() * 2
        prices.append(base_price)

    prices = np.array(prices)
    return pd.DataFrame({
        "Open": prices + np.random.randn(50) * 0.5,
        "High": prices + abs(np.random.randn(50)) * 2,
        "Low": prices - abs(np.random.randn(50)) * 2,
        "Close": prices,
        "Volume": np.random.randint(1000000, 10000000, 50)
    }, index=dates)


@pytest.fixture
def volatile_data():
    """Create volatile price data for ATR testing."""
    dates = pd.date_range(start="2023-01-01", periods=30, freq="D")
    np.random.seed(123)
    prices = 100 + np.cumsum(np.random.randn(30) * 5)
    return pd.DataFrame({
        "Open": prices + np.random.randn(30) * 2,
        "High": prices + abs(np.random.randn(30)) * 5,
        "Low": prices - abs(np.random.randn(30)) * 5,
        "Close": prices,
        "Volume": np.random.randint(1000000, 10000000, 30)
    }, index=dates)


class TestPositionSizeResult:
    """Test PositionSizeResult dataclass."""

    def test_position_size_result_creation(self):
        """Test creating a PositionSizeResult."""
        result = PositionSizeResult(
            shares=100,
            position_value=15000.0,
            risk_amount=750.0,
            stop_price=142.50,
            risk_per_share=7.50
        )
        assert result.shares == 100
        assert result.position_value == 15000.0
        assert result.risk_amount == 750.0
        assert result.stop_price == 142.50

    def test_position_size_result_to_dict(self):
        """Test converting result to dictionary."""
        result = PositionSizeResult(
            shares=100,
            position_value=15000.0,
            risk_amount=750.0
        )
        d = result.to_dict()
        assert d["shares"] == 100
        assert d["position_value"] == 15000.0
        assert d["risk_amount"] == 750.0


class TestBasePositionSizer:
    """Test BasePositionSizer abstract class."""

    def test_base_sizer_is_abstract(self):
        """Test that BasePositionSizer cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BasePositionSizer()

    def test_calculate_max_shares(self):
        """Test max shares calculation."""
        class ConcreteSizer(BasePositionSizer):
            def calculate_position_size(self, equity, price, df=None, **kwargs):
                return PositionSizeResult(0, 0, 0)

        sizer = ConcreteSizer()
        assert sizer.calculate_max_shares(10000, 100) == 100
        assert sizer.calculate_max_shares(10000, 150) == 66
        assert sizer.calculate_max_shares(10000, 0) == 0


class TestATRPositionSizer:
    """Test ATR position sizing."""

    def test_atr_sizer_default_params(self):
        """Test ATR sizer with default parameters."""
        sizer = ATRPositionSizer()
        assert sizer.params["atr_period"] == 14
        assert sizer.params["risk_per_trade"] == 0.05
        assert sizer.params["atr_multiplier"] == 3.0
        assert sizer.params["max_position_pct"] == 0.25

    def test_atr_sizer_custom_params(self):
        """Test ATR sizer with custom parameters."""
        sizer = ATRPositionSizer({
            "atr_period": 20,
            "risk_per_trade": 0.02,
            "atr_multiplier": 2.0
        })
        assert sizer.params["atr_period"] == 20
        assert sizer.params["risk_per_trade"] == 0.02
        assert sizer.params["atr_multiplier"] == 2.0

    def test_atr_sizer_invalid_period(self):
        """Test ATR sizer with invalid period."""
        with pytest.raises(ValueError) as exc_info:
            ATRPositionSizer({"atr_period": 0})
        assert "positive integer" in str(exc_info.value)

    def test_atr_sizer_invalid_risk(self):
        """Test ATR sizer with invalid risk parameter."""
        with pytest.raises(ValueError) as exc_info:
            ATRPositionSizer({"risk_per_trade": 1.5})
        assert "between 0 and 1" in str(exc_info.value)

    def test_atr_sizer_invalid_multiplier(self):
        """Test ATR sizer with invalid multiplier."""
        with pytest.raises(ValueError) as exc_info:
            ATRPositionSizer({"atr_multiplier": -1.0})
        assert "positive" in str(exc_info.value)

    def test_atr_sizer_calculate_basic(self, sample_ohlcv_data):
        """Test basic ATR position sizing calculation."""
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.05
        })

        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            df=sample_ohlcv_data
        )

        assert isinstance(result, PositionSizeResult)
        assert result.shares > 0
        assert result.position_value > 0
        assert result.stop_price is not None
        assert result.stop_price < 100.0

    def test_atr_sizer_respects_max_position(self, sample_ohlcv_data):
        """Test that ATR sizer respects maximum position size."""
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.50,
            "max_position_pct": 0.10
        })

        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            df=sample_ohlcv_data
        )

        assert result.position_value <= 100000 * 0.10

    def test_atr_sizer_insufficient_data(self):
        """Test ATR sizer with insufficient data."""
        sizer = ATRPositionSizer({"atr_period": 14})

        dates = pd.date_range(start="2023-01-01", periods=5, freq="D")
        df = pd.DataFrame({
            "Open": [100, 101, 102, 103, 104],
            "High": [102, 103, 104, 105, 106],
            "Low": [98, 99, 100, 101, 102],
            "Close": [101, 102, 103, 104, 105],
            "Volume": [1000000] * 5
        }, index=dates)

        with pytest.raises(ValueError) as exc_info:
            sizer.calculate_position_size(100000, 100.0, df)
        assert "insufficient" in str(exc_info.value).lower()

    def test_atr_sizer_no_dataframe(self):
        """Test ATR sizer requires DataFrame."""
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError) as exc_info:
            sizer.calculate_position_size(100000, 100.0, df=None)
        assert "dataframe required" in str(exc_info.value).lower()

    def test_atr_sizer_zero_equity(self, sample_ohlcv_data):
        """Test ATR sizer with zero equity."""
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError):
            sizer.calculate_position_size(0, 100.0, sample_ohlcv_data)

    def test_atr_sizer_zero_price(self, sample_ohlcv_data):
        """Test ATR sizer with zero price."""
        sizer = ATRPositionSizer()
        with pytest.raises(ValueError):
            sizer.calculate_position_size(100000, 0, sample_ohlcv_data)

    def test_atr_calculation(self, sample_ohlcv_data):
        """Test ATR calculation produces valid values."""
        atr = ATRPositionSizer.calculate_atr(sample_ohlcv_data, 14)

        assert isinstance(atr, pd.Series)
        assert len(atr) == len(sample_ohlcv_data)
        valid_atr = atr.dropna()
        assert (valid_atr > 0).all()

    def test_atr_volatile_vs_stable(self, sample_ohlcv_data, volatile_data):
        """Test that volatile data produces higher ATR."""
        stable_atr = ATRPositionSizer.calculate_atr(sample_ohlcv_data, 14).iloc[-1]
        volatile_atr = ATRPositionSizer.calculate_atr(volatile_data, 14).iloc[-1]

        assert volatile_atr > stable_atr

    def test_get_atr_values(self, sample_ohlcv_data):
        """Test getting full ATR series."""
        sizer = ATRPositionSizer({"atr_period": 14})
        atr = sizer.get_atr_values(sample_ohlcv_data)

        assert isinstance(atr, pd.Series)
        assert len(atr) == len(sample_ohlcv_data)


class TestFixedFractionalSizer:
    """Test fixed fractional position sizing."""

    def test_fixed_sizer_default_params(self):
        """Test fixed sizer with default parameters."""
        sizer = FixedFractionalSizer()
        assert sizer.params["fraction"] == 0.10
        assert sizer.params["max_position_pct"] == 0.25

    def test_fixed_sizer_custom_params(self):
        """Test fixed sizer with custom parameters."""
        sizer = FixedFractionalSizer({"fraction": 0.05})
        assert sizer.params["fraction"] == 0.05

    def test_fixed_sizer_invalid_fraction(self):
        """Test fixed sizer with invalid fraction."""
        with pytest.raises(ValueError) as exc_info:
            FixedFractionalSizer({"fraction": 1.5})
        assert "between 0 and 1" in str(exc_info.value)

    def test_fixed_sizer_zero_fraction(self):
        """Test fixed sizer with zero fraction."""
        with pytest.raises(ValueError):
            FixedFractionalSizer({"fraction": 0})

    def test_fixed_sizer_calculate_basic(self):
        """Test basic fixed fractional calculation."""
        sizer = FixedFractionalSizer({"fraction": 0.10})

        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0
        )

        assert result.shares == 100
        assert result.position_value == 10000.0

    def test_fixed_sizer_respects_max_position(self):
        """Test that fixed sizer respects max position."""
        sizer = FixedFractionalSizer({
            "fraction": 0.50,
            "max_position_pct": 0.20
        })

        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0
        )

        assert result.position_value <= 100000 * 0.20

    def test_fixed_sizer_with_stop_price(self):
        """Test fixed sizer with stop price calculates risk."""
        sizer = FixedFractionalSizer({"fraction": 0.10})

        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            stop_price=95.0
        )

        assert result.stop_price == 95.0
        assert result.risk_per_share == 5.0
        assert result.risk_amount == result.shares * 5.0

    def test_fixed_sizer_zero_equity(self):
        """Test fixed sizer with zero equity."""
        sizer = FixedFractionalSizer()
        with pytest.raises(ValueError):
            sizer.calculate_position_size(0, 100.0)

    def test_fixed_sizer_zero_price(self):
        """Test fixed sizer with zero price."""
        sizer = FixedFractionalSizer()
        with pytest.raises(ValueError):
            sizer.calculate_position_size(100000, 0)

    def test_fixed_sizer_df_not_required(self, sample_ohlcv_data):
        """Test that fixed sizer doesn't require DataFrame."""
        sizer = FixedFractionalSizer()
        result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            df=sample_ohlcv_data
        )
        assert result.shares > 0

    def test_calculate_shares_for_target(self):
        """Test calculating shares for target weight."""
        sizer = FixedFractionalSizer()

        shares = sizer.calculate_shares_for_target(
            equity=100000,
            price=100.0,
            target_weight=0.15
        )

        assert shares == 150

    def test_calculate_shares_invalid_target(self):
        """Test invalid target weight raises error."""
        sizer = FixedFractionalSizer()
        with pytest.raises(ValueError):
            sizer.calculate_shares_for_target(100000, 100.0, 1.5)


class TestPositionSizingIntegration:
    """Integration tests for position sizing."""

    def test_atr_sizes_smaller_for_volatile(self, sample_ohlcv_data, volatile_data):
        """Test that ATR sizer sizes smaller for volatile stocks."""
        sizer = ATRPositionSizer({
            "atr_period": 14,
            "risk_per_trade": 0.05
        })

        stable_result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            df=sample_ohlcv_data
        )

        volatile_result = sizer.calculate_position_size(
            equity=100000,
            price=100.0,
            df=volatile_data
        )

        assert volatile_result.shares <= stable_result.shares

    def test_sizer_repr(self):
        """Test sizer repr string."""
        sizer = ATRPositionSizer({"atr_period": 20})
        repr_str = repr(sizer)

        assert "ATRPositionSizer" in repr_str
        assert "params" in repr_str

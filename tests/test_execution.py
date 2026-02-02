"""Unit tests for execution module."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.execution import (
    TransactionCostModel,
    TransactionCost,
    OrderSimulator,
    Order,
    Fill,
    OrderSide,
)
from src.execution.order_simulator import OrderStatus


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


class TestTransactionCost:
    """Test TransactionCost dataclass."""

    def test_transaction_cost_creation(self):
        """Test creating a TransactionCost."""
        cost = TransactionCost(
            commission=1.50,
            spread_cost=0.75,
            slippage=0.30,
            total=2.55
        )
        assert cost.commission == 1.50
        assert cost.spread_cost == 0.75
        assert cost.slippage == 0.30
        assert cost.total == 2.55

    def test_transaction_cost_to_dict(self):
        """Test converting cost to dictionary."""
        cost = TransactionCost(
            commission=1.50,
            spread_cost=0.75,
            slippage=0.30,
            total=2.55
        )
        d = cost.to_dict()
        assert d["commission"] == 1.50
        assert d["total"] == 2.55


class TestTransactionCostModel:
    """Test TransactionCostModel."""

    def test_cost_model_default_params(self):
        """Test cost model with default parameters."""
        model = TransactionCostModel()
        assert model.params["commission_per_share"] == 0.005
        assert model.params["min_commission"] == 1.0
        assert model.params["spread_bps"] == 5.0
        assert model.params["slippage_bps"] == 2.0

    def test_cost_model_custom_params(self):
        """Test cost model with custom parameters."""
        model = TransactionCostModel({
            "commission_per_share": 0.01,
            "spread_bps": 10.0
        })
        assert model.params["commission_per_share"] == 0.01
        assert model.params["spread_bps"] == 10.0

    def test_cost_model_invalid_params(self):
        """Test cost model with invalid parameters."""
        with pytest.raises(ValueError):
            TransactionCostModel({"commission_per_share": -0.01})

    def test_calculate_cost_basic(self):
        """Test basic cost calculation."""
        model = TransactionCostModel({
            "commission_per_share": 0.005,
            "min_commission": 1.0,
            "spread_bps": 5.0,
            "slippage_bps": 2.0
        })

        cost = model.calculate_cost(
            price=100.0,
            shares=100,
            volume=1000000
        )

        assert cost.commission >= 1.0
        assert cost.spread_cost > 0
        assert cost.slippage > 0
        assert cost.total == cost.commission + cost.spread_cost + cost.slippage

    def test_calculate_cost_min_commission(self):
        """Test minimum commission is applied."""
        model = TransactionCostModel({
            "commission_per_share": 0.005,
            "min_commission": 5.0
        })

        cost = model.calculate_cost(price=100.0, shares=10)

        assert cost.commission >= 5.0

    def test_calculate_cost_zero_shares(self):
        """Test cost with zero shares."""
        model = TransactionCostModel()
        cost = model.calculate_cost(price=100.0, shares=0)

        assert cost.total == 0.0

    def test_calculate_cost_zero_price(self):
        """Test cost with zero price."""
        model = TransactionCostModel()
        cost = model.calculate_cost(price=0, shares=100)

        assert cost.total == 0.0

    def test_calculate_cost_with_volume_impact(self):
        """Test that large orders have higher volume impact."""
        model = TransactionCostModel({
            "volume_impact_factor": 0.1
        })

        small_order = model.calculate_cost(price=100.0, shares=100, volume=10000000)
        large_order = model.calculate_cost(price=100.0, shares=100000, volume=10000000)

        assert large_order.slippage > small_order.slippage

    def test_calculate_effective_price_buy(self):
        """Test effective price for buy orders."""
        model = TransactionCostModel()

        effective = model.calculate_effective_price(
            price=100.0,
            shares=100,
            is_buy=True
        )

        assert effective > 100.0

    def test_calculate_effective_price_sell(self):
        """Test effective price for sell orders."""
        model = TransactionCostModel()

        effective = model.calculate_effective_price(
            price=100.0,
            shares=100,
            is_buy=False
        )

        assert effective < 100.0

    def test_calculate_round_trip_cost(self):
        """Test round-trip cost calculation."""
        model = TransactionCostModel()

        cost = model.calculate_round_trip_cost(
            entry_price=100.0,
            exit_price=110.0,
            shares=100
        )

        assert cost > 0

    def test_cost_as_percentage(self):
        """Test cost as percentage of trade value."""
        model = TransactionCostModel()

        pct = model.cost_as_percentage(
            price=100.0,
            shares=100
        )

        assert 0 < pct < 0.01

    def test_zero_cost_model(self):
        """Test zero cost model for testing."""
        model = TransactionCostModel.zero_cost()

        cost = model.calculate_cost(price=100.0, shares=100)

        assert cost.total == 0.0

    def test_cost_model_repr(self):
        """Test cost model repr string."""
        model = TransactionCostModel()
        repr_str = repr(model)

        assert "TransactionCostModel" in repr_str


class TestOrder:
    """Test Order dataclass."""

    def test_order_creation(self):
        """Test creating an Order."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.shares == 100
        assert order.order_type == "market"

    def test_order_to_dict(self):
        """Test converting order to dictionary."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15),
            strategy="ma_crossover"
        )

        d = order.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["side"] == "buy"
        assert d["strategy"] == "ma_crossover"


class TestFill:
    """Test Fill dataclass."""

    def test_fill_creation(self):
        """Test creating a Fill."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        fill = Fill(
            order=order,
            fill_price=150.50,
            fill_date=datetime(2023, 6, 16),
            shares_filled=100,
            transaction_cost=TransactionCost(1.0, 0.5, 0.3, 1.8)
        )

        assert fill.fill_price == 150.50
        assert fill.shares_filled == 100
        assert fill.status == OrderStatus.FILLED

    def test_fill_effective_price_buy(self):
        """Test effective price for buy fill."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        fill = Fill(
            order=order,
            fill_price=150.0,
            fill_date=datetime(2023, 6, 16),
            shares_filled=100,
            transaction_cost=TransactionCost(1.0, 0.5, 0.3, 1.8)
        )

        assert fill.effective_price > 150.0

    def test_fill_effective_price_sell(self):
        """Test effective price for sell fill."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.SELL,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        fill = Fill(
            order=order,
            fill_price=150.0,
            fill_date=datetime(2023, 6, 16),
            shares_filled=100,
            transaction_cost=TransactionCost(1.0, 0.5, 0.3, 1.8)
        )

        assert fill.effective_price < 150.0

    def test_fill_total_value(self):
        """Test fill total value."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        fill = Fill(
            order=order,
            fill_price=150.0,
            fill_date=datetime(2023, 6, 16),
            shares_filled=100,
            transaction_cost=TransactionCost(1.0, 0.5, 0.3, 1.8)
        )

        assert fill.total_value == 15000.0

    def test_fill_to_dict(self):
        """Test converting fill to dictionary."""
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            shares=100,
            signal_price=150.0,
            signal_date=datetime(2023, 6, 15)
        )

        fill = Fill(
            order=order,
            fill_price=150.50,
            fill_date=datetime(2023, 6, 16),
            shares_filled=100,
            transaction_cost=TransactionCost(1.0, 0.5, 0.3, 1.8)
        )

        d = fill.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["fill_price"] == 150.50


class TestOrderSimulator:
    """Test OrderSimulator."""

    def test_simulator_default_init(self):
        """Test simulator with default initialization."""
        simulator = OrderSimulator()
        assert simulator.fill_at == "next_open"
        assert simulator.cost_model is not None

    def test_simulator_custom_init(self):
        """Test simulator with custom parameters."""
        cost_model = TransactionCostModel.zero_cost()
        simulator = OrderSimulator(
            cost_model=cost_model,
            fill_at="close"
        )

        assert simulator.fill_at == "close"

    def test_execute_order_next_open(self, sample_ohlcv_data):
        """Test order execution at next open."""
        simulator = OrderSimulator(fill_at="next_open")

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[10],
            signal_date=sample_ohlcv_data.index[10].to_pydatetime()
        )

        fill = simulator.execute_order(order, sample_ohlcv_data, signal_idx=10)

        assert fill is not None
        assert fill.status == OrderStatus.FILLED
        assert fill.fill_price == sample_ohlcv_data['Open'].iloc[11]

    def test_execute_order_at_close(self, sample_ohlcv_data):
        """Test order execution at close."""
        simulator = OrderSimulator(fill_at="close")

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[10],
            signal_date=sample_ohlcv_data.index[10].to_pydatetime()
        )

        fill = simulator.execute_order(order, sample_ohlcv_data, signal_idx=10)

        assert fill.fill_price == sample_ohlcv_data['Close'].iloc[10]

    def test_execute_order_at_vwap(self, sample_ohlcv_data):
        """Test order execution at VWAP approximation."""
        simulator = OrderSimulator(fill_at="vwap")

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[10],
            signal_date=sample_ohlcv_data.index[10].to_pydatetime()
        )

        fill = simulator.execute_order(order, sample_ohlcv_data, signal_idx=10)

        bar = sample_ohlcv_data.iloc[11]
        expected_vwap = (bar['Open'] + bar['High'] + bar['Low'] + bar['Close']) / 4
        assert abs(fill.fill_price - expected_vwap) < 0.01

    def test_execute_order_last_bar(self, sample_ohlcv_data):
        """Test order execution on last bar returns None."""
        simulator = OrderSimulator(fill_at="next_open")

        last_idx = len(sample_ohlcv_data) - 1
        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[last_idx],
            signal_date=sample_ohlcv_data.index[last_idx].to_pydatetime()
        )

        fill = simulator.execute_order(order, sample_ohlcv_data, signal_idx=last_idx)

        assert fill is None or fill.status == OrderStatus.REJECTED

    def test_execute_order_invalid_index(self, sample_ohlcv_data):
        """Test order execution with invalid index."""
        simulator = OrderSimulator()

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=100.0,
            signal_date=datetime(2023, 1, 1)
        )

        fill = simulator.execute_order(order, sample_ohlcv_data, signal_idx=-1)
        assert fill is None

    def test_get_fills(self, sample_ohlcv_data):
        """Test getting all fills."""
        simulator = OrderSimulator()

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[10],
            signal_date=sample_ohlcv_data.index[10].to_pydatetime()
        )

        simulator.execute_order(order, sample_ohlcv_data, signal_idx=10)

        fills = simulator.get_fills()
        assert len(fills) == 1

    def test_clear_fills(self, sample_ohlcv_data):
        """Test clearing fills."""
        simulator = OrderSimulator()

        order = Order(
            symbol="TEST",
            side=OrderSide.BUY,
            shares=100,
            signal_price=sample_ohlcv_data['Close'].iloc[10],
            signal_date=sample_ohlcv_data.index[10].to_pydatetime()
        )

        simulator.execute_order(order, sample_ohlcv_data, signal_idx=10)
        simulator.clear_fills()

        assert len(simulator.get_fills()) == 0

    def test_get_fill_summary(self, sample_ohlcv_data):
        """Test getting fill summary."""
        simulator = OrderSimulator()

        for i in range(10, 15):
            order = Order(
                symbol="TEST",
                side=OrderSide.BUY,
                shares=100,
                signal_price=sample_ohlcv_data['Close'].iloc[i],
                signal_date=sample_ohlcv_data.index[i].to_pydatetime()
            )
            simulator.execute_order(order, sample_ohlcv_data, signal_idx=i)

        summary = simulator.get_fill_summary()

        assert summary["total_fills"] == 5
        assert summary["total_volume"] == 500
        assert summary["total_costs"] > 0

    def test_get_fill_summary_empty(self):
        """Test fill summary with no fills."""
        simulator = OrderSimulator()
        summary = simulator.get_fill_summary()

        assert summary["total_fills"] == 0
        assert summary["total_costs"] == 0.0

    def test_simulator_repr(self):
        """Test simulator repr string."""
        simulator = OrderSimulator()
        repr_str = repr(simulator)

        assert "OrderSimulator" in repr_str
        assert "next_open" in repr_str


class TestOrderSide:
    """Test OrderSide enum."""

    def test_order_side_values(self):
        """Test order side enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_side_is_string(self):
        """Test order side can be compared to string."""
        assert OrderSide.BUY == "buy"
        assert OrderSide.SELL == "sell"

"""Unit tests for transaction cost modeling.

Week 7: Tests cost calculation accuracy, commission minimums,
spread/slippage modeling, round-trip costs, and parameter validation.
"""

import pytest

from src.execution.transaction_costs import TransactionCostModel, TransactionCost, CostModel


class TestTransactionCostDataclass:

    def test_creation(self):
        cost = TransactionCost(commission=0.50, spread_cost=0.75, slippage=0.30, total=1.55)
        assert cost.total == 1.55

    def test_to_dict(self):
        cost = TransactionCost(commission=0.50, spread_cost=0.75, slippage=0.30, total=1.55)
        d = cost.to_dict()
        assert d["commission"] == 0.50
        assert d["spread_cost"] == 0.75
        assert d["slippage"] == 0.30
        assert d["total"] == 1.55


class TestCostModelEnum:

    def test_enum_values(self):
        assert CostModel.ZERO.value == "zero"
        assert CostModel.FIXED.value == "fixed"
        assert CostModel.PERCENTAGE.value == "percentage"
        assert CostModel.TIERED.value == "tiered"


class TestCostModelDefaults:

    def test_default_commission(self):
        model = TransactionCostModel()
        assert model.params["commission_per_share"] == 0.005

    def test_default_min_commission(self):
        model = TransactionCostModel()
        assert model.params["min_commission"] == 1.0

    def test_default_spread(self):
        model = TransactionCostModel()
        assert model.params["spread_bps"] == 5.0

    def test_default_slippage(self):
        model = TransactionCostModel()
        assert model.params["slippage_bps"] == 2.0

    def test_custom_params(self):
        model = TransactionCostModel({
            "commission_per_share": 0.01,
            "spread_bps": 10.0,
        })
        assert model.params["commission_per_share"] == 0.01
        assert model.params["spread_bps"] == 10.0


class TestCostModelValidation:

    def test_negative_commission_raises(self):
        with pytest.raises(ValueError, match="commission_per_share"):
            TransactionCostModel({"commission_per_share": -0.01})

    def test_negative_min_commission_raises(self):
        with pytest.raises(ValueError, match="min_commission"):
            TransactionCostModel({"min_commission": -1})

    def test_negative_spread_raises(self):
        with pytest.raises(ValueError, match="spread_bps"):
            TransactionCostModel({"spread_bps": -1})

    def test_negative_slippage_raises(self):
        with pytest.raises(ValueError, match="slippage_bps"):
            TransactionCostModel({"slippage_bps": -1})


class TestCostCalculation:

    def test_basic_cost(self):
        model = TransactionCostModel()
        cost = model.calculate_cost(100.0, 100)
        assert cost.total > 0
        assert cost.commission > 0
        assert cost.spread_cost > 0
        assert cost.slippage > 0

    def test_commission_per_share(self):
        model = TransactionCostModel({"commission_per_share": 0.01, "min_commission": 0.0})
        cost = model.calculate_cost(100.0, 200)
        assert cost.commission == 2.0

    def test_min_commission_applied(self):
        model = TransactionCostModel({"commission_per_share": 0.001, "min_commission": 1.0})
        cost = model.calculate_cost(100.0, 10)
        # 10 * 0.001 = 0.01, min_commission = 1.0
        assert cost.commission == 1.0

    def test_spread_calculation(self):
        model = TransactionCostModel({
            "commission_per_share": 0.0,
            "min_commission": 0.0,
            "spread_bps": 10.0,
            "slippage_bps": 0.0,
        })
        cost = model.calculate_cost(100.0, 100)
        # trade_value = 10000, spread = 10000 * (10/10000) / 2 = 5.0
        assert abs(cost.spread_cost - 5.0) < 0.01

    def test_slippage_without_volume(self):
        model = TransactionCostModel({
            "commission_per_share": 0.0,
            "min_commission": 0.0,
            "spread_bps": 0.0,
            "slippage_bps": 5.0,
        })
        cost = model.calculate_cost(100.0, 100)
        # trade_value = 10000, slippage = 10000 * (5/10000) = 5.0
        assert abs(cost.slippage - 5.0) < 0.01

    def test_volume_impact_increases_slippage(self):
        model = TransactionCostModel({"slippage_bps": 2.0, "volume_impact_factor": 0.1})
        cost_no_vol = model.calculate_cost(100.0, 100, volume=None)
        cost_low_vol = model.calculate_cost(100.0, 100, volume=100)
        # With 100 shares / 100 volume = 100% participation -> large volume impact
        assert cost_low_vol.slippage > cost_no_vol.slippage

    def test_zero_shares_returns_zero(self):
        model = TransactionCostModel()
        cost = model.calculate_cost(100.0, 0)
        assert cost.total == 0.0

    def test_zero_price_returns_zero(self):
        model = TransactionCostModel()
        cost = model.calculate_cost(0.0, 100)
        assert cost.total == 0.0

    def test_total_equals_sum_of_components(self):
        model = TransactionCostModel()
        cost = model.calculate_cost(150.0, 200, volume=1_000_000)
        expected = cost.commission + cost.spread_cost + cost.slippage
        assert abs(cost.total - expected) < 0.01


class TestEffectivePrice:

    def test_buy_effective_price_higher(self):
        model = TransactionCostModel()
        effective = model.calculate_effective_price(100.0, 100, is_buy=True)
        assert effective > 100.0

    def test_sell_effective_price_lower(self):
        model = TransactionCostModel()
        effective = model.calculate_effective_price(100.0, 100, is_buy=False)
        assert effective < 100.0

    def test_zero_shares_returns_market_price(self):
        model = TransactionCostModel()
        effective = model.calculate_effective_price(100.0, 0, is_buy=True)
        assert effective == 100.0


class TestRoundTripCost:

    def test_round_trip_cost_positive(self):
        model = TransactionCostModel()
        cost = model.calculate_round_trip_cost(100.0, 105.0, 100)
        assert cost > 0

    def test_round_trip_equals_entry_plus_exit(self):
        model = TransactionCostModel()
        entry = model.calculate_cost(100.0, 100, is_buy=True)
        exit_cost = model.calculate_cost(105.0, 100, is_buy=False)
        rt = model.calculate_round_trip_cost(100.0, 105.0, 100)
        assert abs(rt - (entry.total + exit_cost.total)) < 0.01


class TestCostAsPercentage:

    def test_cost_pct_positive(self):
        model = TransactionCostModel()
        pct = model.cost_as_percentage(150.0, 100)
        assert pct > 0

    def test_cost_pct_under_half_percent_for_liquid(self):
        """RapidTrader target: total costs < 0.5% for liquid stocks."""
        model = TransactionCostModel()
        pct = model.cost_as_percentage(150.0, 100, volume=10_000_000)
        assert pct < 0.005

    def test_zero_input_returns_zero(self):
        model = TransactionCostModel()
        assert model.cost_as_percentage(0.0, 100) == 0.0
        assert model.cost_as_percentage(100.0, 0) == 0.0


class TestZeroCostModel:

    def test_zero_cost_factory(self):
        model = TransactionCostModel.zero_cost()
        cost = model.calculate_cost(100.0, 1000, volume=1_000_000)
        assert cost.total == 0.0
        assert cost.commission == 0.0
        assert cost.spread_cost == 0.0
        assert cost.slippage == 0.0

    def test_repr(self):
        model = TransactionCostModel()
        assert "TransactionCostModel" in repr(model)

"""Comprehensive risk management tests.

Week 7: Tests market regime filter, stop loss manager, sector limits,
and portfolio heat tracker with integration scenarios.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.risk import (
    MarketRegimeFilter,
    MarketRegime,
    RegimeState,
    StopLossManager,
    StopLossResult,
    StopType,
    SectorLimitManager,
    SectorExposure,
    PortfolioHeatTracker,
    HeatStatus,
)


@pytest.fixture
def bull_data():
    """250-day uptrend data simulating a bull market."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    np.random.seed(42)
    prices = np.linspace(100, 160, 250) + np.random.randn(250) * 0.5
    return pd.DataFrame({
        "Open": prices * 0.999,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": [2_000_000] * 250,
    }, index=dates)


@pytest.fixture
def bear_data():
    """250-day downtrend data simulating a bear market."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    np.random.seed(42)
    prices = np.linspace(160, 100, 250) + np.random.randn(250) * 0.5
    return pd.DataFrame({
        "Open": prices * 1.001,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": [2_000_000] * 250,
    }, index=dates)


@pytest.fixture
def ohlcv_50():
    """50-day OHLCV data for stop loss / ATR tests."""
    dates = pd.date_range(start="2023-06-01", periods=50, freq="D")
    np.random.seed(99)
    base = 100 + np.cumsum(np.random.randn(50) * 0.5)
    return pd.DataFrame({
        "Open": base * 0.999,
        "High": base + np.abs(np.random.randn(50)) * 2,
        "Low": base - np.abs(np.random.randn(50)) * 2,
        "Close": base,
        "Volume": [1_000_000] * 50,
    }, index=dates)


# -- Market Regime Filter --

class TestMarketRegimeDefaults:

    def test_default_sma_period(self):
        f = MarketRegimeFilter()
        assert f.params["sma_period"] == 200

    def test_default_reference_symbol(self):
        f = MarketRegimeFilter()
        assert f.params["reference_symbol"] == "SPY"

    def test_default_buffer(self):
        f = MarketRegimeFilter()
        assert f.params["buffer_pct"] == 0.0


class TestMarketRegimeValidation:

    def test_invalid_sma_period(self):
        with pytest.raises(ValueError, match="sma_period"):
            MarketRegimeFilter({"sma_period": 0})

    def test_invalid_buffer(self):
        with pytest.raises(ValueError, match="buffer_pct"):
            MarketRegimeFilter({"buffer_pct": -0.1})

    def test_invalid_confirmation_days(self):
        with pytest.raises(ValueError, match="confirmation_days"):
            MarketRegimeFilter({"confirmation_days": 0})


class TestMarketRegimeDetection:

    def test_bull_market_detected(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        regime = f.get_regime(bull_data)
        assert regime.state == RegimeState.BULL
        assert regime.above_sma is True

    def test_bear_market_detected(self, bear_data):
        f = MarketRegimeFilter({"sma_period": 200})
        regime = f.get_regime(bear_data)
        assert regime.state == RegimeState.BEAR
        assert regime.above_sma is False

    def test_insufficient_data_raises(self):
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        df = pd.DataFrame({"Close": range(50)}, index=dates)
        f = MarketRegimeFilter({"sma_period": 200})
        with pytest.raises(ValueError, match="Insufficient"):
            f.get_regime(df)

    def test_sma_calculation(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        sma = f.calculate_sma(bull_data, 200)
        assert len(sma) == len(bull_data)
        assert pd.notna(sma.iloc[-1])

    def test_regime_to_dict(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        regime = f.get_regime(bull_data)
        d = regime.to_dict()
        assert "state" in d
        assert "reference_price" in d

    def test_allows_entry_bull(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        assert f.allows_entry(bull_data, side="long") is True

    def test_blocks_entry_bear(self, bear_data):
        f = MarketRegimeFilter({"sma_period": 200})
        assert f.allows_entry(bear_data, side="long") is False

    def test_regime_series(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        series = f.get_regime_series(bull_data)
        assert len(series) == len(bull_data)

    def test_bull_gate_series(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        gate = f.get_bull_gate_series(bull_data)
        # Bull market -> gate should be True
        assert gate.iloc[-1] is True or gate.iloc[-1] == True

    def test_buffer_zone_neutral(self):
        """Price near SMA with buffer should be NEUTRAL."""
        dates = pd.date_range("2023-01-01", periods=250, freq="D")
        prices = np.array([100.0] * 250)
        df = pd.DataFrame({"Close": prices}, index=dates)
        f = MarketRegimeFilter({"sma_period": 200, "buffer_pct": 0.05})
        regime = f.get_regime(df)
        assert regime.state == RegimeState.NEUTRAL

    def test_days_in_regime(self, bull_data):
        f = MarketRegimeFilter({"sma_period": 200})
        regime = f.get_regime(bull_data)
        assert regime.days_in_regime >= 0


# -- Stop Loss Manager --

class TestStopLossDefaults:

    def test_default_atr_multiplier(self):
        mgr = StopLossManager()
        assert mgr.params["atr_multiplier"] == 3.0

    def test_default_cooldown_days(self):
        mgr = StopLossManager()
        assert mgr.params["cooldown_days"] == 1


class TestStopLossValidation:

    def test_invalid_atr_multiplier(self):
        with pytest.raises(ValueError, match="atr_multiplier"):
            StopLossManager({"atr_multiplier": 0})

    def test_invalid_atr_period(self):
        with pytest.raises(ValueError, match="atr_period"):
            StopLossManager({"atr_period": -1})

    def test_invalid_cooldown(self):
        with pytest.raises(ValueError, match="cooldown_days"):
            StopLossManager({"cooldown_days": -1})

    def test_zero_entry_price_raises(self):
        mgr = StopLossManager()
        with pytest.raises(ValueError, match="entry_price"):
            mgr.calculate_stop_price(0, atr=2.0)


class TestStopPriceCalculation:

    def test_atr_stop_price(self):
        mgr = StopLossManager({"atr_multiplier": 3.0})
        stop = mgr.calculate_stop_price(100.0, atr=2.0)
        assert abs(stop - 94.0) < 0.01

    def test_atr_stop_from_dataframe(self, ohlcv_50):
        mgr = StopLossManager()
        stop = mgr.calculate_stop_price(100.0, df=ohlcv_50)
        assert 0 < stop < 100.0

    def test_stop_never_negative(self):
        mgr = StopLossManager({"atr_multiplier": 100.0})
        stop = mgr.calculate_stop_price(5.0, atr=2.0)
        assert stop >= 0.01


class TestStopLossTracking:

    def test_register_position(self, ohlcv_50):
        mgr = StopLossManager()
        now = datetime(2023, 7, 1)
        stop = mgr.register_position("AAPL", 150.0, now, atr=3.0)
        assert stop < 150.0

    def test_check_stop_not_triggered(self):
        mgr = StopLossManager()
        now = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, now, atr=2.0)
        result = mgr.check_stop("AAPL", 98.0, now)
        # stop = 100 - 3*2 = 94, price 98 > 94 -> not triggered
        assert result.triggered is False

    def test_check_stop_triggered(self):
        mgr = StopLossManager({"atr_multiplier": 3.0})
        now = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, now, atr=2.0)
        result = mgr.check_stop("AAPL", 93.0, now)
        assert result.triggered is True
        assert result.loss_amount > 0

    def test_stop_trigger_starts_cooldown(self):
        mgr = StopLossManager({"atr_multiplier": 3.0, "cooldown_days": 2})
        trigger_date = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, trigger_date, atr=2.0)
        mgr.check_stop("AAPL", 90.0, trigger_date)
        assert mgr.is_in_cooldown("AAPL", trigger_date)

    def test_cooldown_expires(self):
        mgr = StopLossManager({"atr_multiplier": 3.0, "cooldown_days": 1})
        trigger_date = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, trigger_date, atr=2.0)
        mgr.check_stop("AAPL", 90.0, trigger_date)
        after_cooldown = trigger_date + timedelta(days=2)
        assert mgr.is_in_cooldown("AAPL", after_cooldown) is False

    def test_in_cooldown_check_returns_not_triggered(self):
        mgr = StopLossManager({"atr_multiplier": 3.0, "cooldown_days": 5})
        trigger_date = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, trigger_date, atr=2.0)
        mgr.check_stop("AAPL", 90.0, trigger_date)
        next_day = trigger_date + timedelta(days=1)
        result = mgr.check_stop("AAPL", 85.0, next_day)
        assert result.triggered is False
        assert result.in_cooldown is True

    def test_stop_history_recorded(self):
        mgr = StopLossManager()
        now = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, now, atr=2.0)
        mgr.check_stop("AAPL", 90.0, now)
        history = mgr.get_stop_history()
        assert len(history) == 1
        assert history[0]["symbol"] == "AAPL"

    def test_clear_position(self):
        mgr = StopLossManager()
        now = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, now, atr=2.0)
        mgr.clear_position("AAPL")
        result = mgr.check_stop("AAPL", 50.0, now)
        assert result.triggered is False

    def test_clear_all_state(self):
        mgr = StopLossManager()
        now = datetime(2023, 7, 1)
        mgr.register_position("AAPL", 100.0, now, atr=2.0)
        mgr.clear_state()
        assert len(mgr.get_stop_history()) == 0

    def test_unregistered_symbol_not_triggered(self):
        mgr = StopLossManager()
        result = mgr.check_stop("FAKE", 50.0, datetime.now())
        assert result.triggered is False


# -- Sector Limits --

class TestSectorLimitDefaults:

    def test_default_max_exposure(self):
        mgr = SectorLimitManager()
        assert mgr.params["max_sector_exposure"] == 0.30

    def test_default_sector(self):
        mgr = SectorLimitManager()
        assert mgr.params["default_sector"] == "Unknown"


class TestSectorLimitValidation:

    def test_invalid_max_exposure(self):
        with pytest.raises(ValueError, match="max_sector_exposure"):
            SectorLimitManager({"max_sector_exposure": 0})

    def test_invalid_warn_threshold(self):
        with pytest.raises(ValueError, match="warn_threshold_pct"):
            SectorLimitManager({"warn_threshold_pct": 0})


class TestSectorExposureTracking:

    def test_add_position(self):
        mgr = SectorLimitManager()
        mgr.add_position("AAPL", "Technology", 100, 15_000)
        exposure = mgr.get_sector_exposure("Technology", 100_000)
        assert exposure.exposure_value == 15_000
        assert exposure.symbol_count == 1

    def test_multiple_positions_same_sector(self):
        mgr = SectorLimitManager()
        mgr.add_position("AAPL", "Technology", 100, 15_000)
        mgr.add_position("MSFT", "Technology", 50, 20_000)
        exposure = mgr.get_sector_exposure("Technology", 100_000)
        assert exposure.exposure_value == 35_000
        assert exposure.symbol_count == 2

    def test_remove_position(self):
        mgr = SectorLimitManager()
        mgr.add_position("AAPL", "Technology", 100, 15_000)
        mgr.remove_position("AAPL")
        assert mgr.get_position_count() == 0

    def test_allows_entry_within_limit(self):
        mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        mgr.add_position("AAPL", "Technology", 100, 10_000)
        assert mgr.allows_entry("MSFT", "Technology", 15_000, 100_000) is True

    def test_blocks_entry_over_limit(self):
        mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        mgr.add_position("AAPL", "Technology", 100, 25_000)
        assert mgr.allows_entry("MSFT", "Technology", 10_000, 100_000) is False

    def test_custom_sector_limit(self):
        mgr = SectorLimitManager()
        mgr.set_sector_limit("Energy", 0.15)
        assert mgr.get_sector_limit("Energy") == 0.15
        assert mgr.get_sector_limit("Technology") == 0.30

    def test_all_sector_exposures(self):
        mgr = SectorLimitManager()
        mgr.add_position("AAPL", "Technology", 100, 15_000)
        mgr.add_position("XOM", "Energy", 200, 10_000)
        exposures = mgr.get_all_sector_exposures(100_000)
        assert "Technology" in exposures
        assert "Energy" in exposures

    def test_compliance_check(self):
        mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        mgr.add_position("AAPL", "Technology", 100, 35_000)
        messages = mgr.check_compliance(100_000)
        assert any("VIOLATION" in m for m in messages)

    def test_available_capacity(self):
        mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        mgr.add_position("AAPL", "Technology", 100, 10_000)
        capacity = mgr.get_available_capacity("Technology", 100_000)
        assert abs(capacity - 20_000) < 1

    def test_zero_portfolio_blocks_entry(self):
        mgr = SectorLimitManager()
        assert mgr.allows_entry("AAPL", "Technology", 1_000, 0) is False


# -- Portfolio Heat Tracker --

class TestHeatTrackerDefaults:

    def test_default_max_heat(self):
        t = PortfolioHeatTracker()
        assert t.params["max_heat_pct"] == 0.06

    def test_default_max_positions(self):
        t = PortfolioHeatTracker()
        assert t.params["max_positions"] == 20


class TestHeatTrackerValidation:

    def test_invalid_max_heat(self):
        with pytest.raises(ValueError, match="max_heat_pct"):
            PortfolioHeatTracker({"max_heat_pct": 0})

    def test_invalid_max_positions(self):
        with pytest.raises(ValueError, match="max_positions"):
            PortfolioHeatTracker({"max_positions": 0})


class TestHeatTracking:

    def test_add_position_returns_risk(self):
        t = PortfolioHeatTracker()
        risk = t.add_position("AAPL", entry_price=150, shares=100, stop_price=145)
        assert risk == 500.0

    def test_total_heat_calculation(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", entry_price=150, shares=100, stop_price=145)
        t.add_position("MSFT", entry_price=300, shares=50, stop_price=290)
        assert t.get_total_heat() == 1000.0

    def test_heat_pct(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", entry_price=150, shares=100, stop_price=145)
        pct = t.get_heat_pct(100_000)
        assert abs(pct - 0.005) < 0.0001

    def test_cool_status(self):
        t = PortfolioHeatTracker({"max_heat_pct": 0.06})
        t.add_position("AAPL", entry_price=150, shares=10, stop_price=145)
        assert t.get_heat_status(100_000) == HeatStatus.COOL

    def test_critical_status(self):
        t = PortfolioHeatTracker({"max_heat_pct": 0.01})
        t.add_position("AAPL", entry_price=150, shares=100, stop_price=140)
        assert t.get_heat_status(100_000) == HeatStatus.CRITICAL

    def test_allows_new_risk(self):
        t = PortfolioHeatTracker({"max_heat_pct": 0.06})
        assert t.allows_new_risk(5_000, 100_000) is True

    def test_blocks_excessive_risk(self):
        t = PortfolioHeatTracker({"max_heat_pct": 0.06})
        assert t.allows_new_risk(7_000, 100_000) is False

    def test_max_positions_enforced(self):
        t = PortfolioHeatTracker({"max_positions": 2})
        t.add_position("A", 100, 10, 95)
        t.add_position("B", 100, 10, 95)
        assert t.allows_new_risk(50, 100_000) is False

    def test_remove_position(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", 150, 100, 145)
        t.remove_position("AAPL")
        assert t.get_total_heat() == 0.0

    def test_update_position_stop(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", 150, 100, 145)
        t.update_position("AAPL", stop_price=147)
        # risk = (150 - 147) * 100 = 300
        assert t.get_total_heat() == 300.0

    def test_heat_report(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", 150, 100, 145)
        report = t.get_heat_report(100_000)
        assert report.position_count == 1
        assert report.total_heat_value == 500.0
        assert len(report.positions) == 1

    def test_get_max_new_risk(self):
        t = PortfolioHeatTracker({"max_heat_pct": 0.06})
        max_risk = t.get_max_new_risk(100_000)
        assert abs(max_risk - 6_000) < 0.01

    def test_largest_risk_position(self):
        t = PortfolioHeatTracker()
        t.add_position("AAPL", 150, 100, 145)
        t.add_position("MSFT", 300, 50, 280)
        assert t.get_largest_risk_position() == "MSFT"

    def test_positions_available(self):
        t = PortfolioHeatTracker({"max_positions": 5})
        t.add_position("A", 100, 10, 95)
        assert t.get_positions_available() == 4

    def test_stop_above_entry_corrected(self):
        t = PortfolioHeatTracker()
        risk = t.add_position("AAPL", 100, 10, 110)
        # Should correct stop to 95% of entry
        assert risk > 0


# -- Risk Integration Tests --

class TestRiskIntegration:

    def test_bear_market_blocks_then_stops_manage(self, bear_data):
        regime_filter = MarketRegimeFilter({"sma_period": 200})
        stop_mgr = StopLossManager()

        if not regime_filter.allows_entry(bear_data, side="long"):
            pass  # correct: blocked
        else:
            pytest.fail("Bear market should block long entries")

    def test_combined_sector_and_heat_check(self):
        sector_mgr = SectorLimitManager({"max_sector_exposure": 0.30})
        heat_tracker = PortfolioHeatTracker({"max_heat_pct": 0.06})

        sector_mgr.add_position("AAPL", "Technology", 100, 25_000)
        heat_tracker.add_position("AAPL", 250, 100, 240)

        sector_ok = sector_mgr.allows_entry("MSFT", "Technology", 10_000, 100_000)
        heat_ok = heat_tracker.allows_new_risk(500, 100_000)

        # Sector should block (25k + 10k > 30k limit)
        assert sector_ok is False
        # Heat should allow (1000 + 500 < 6000)
        assert heat_ok is True

    def test_stop_trigger_cooldown_then_expire(self):
        mgr = StopLossManager({"atr_multiplier": 2.0, "cooldown_days": 3})
        trigger_date = datetime(2023, 7, 1)

        mgr.register_position("AAPL", 100.0, trigger_date, atr=2.5)
        result = mgr.check_stop("AAPL", 93.0, trigger_date)
        assert result.triggered is True

        day2 = trigger_date + timedelta(days=1)
        assert mgr.is_in_cooldown("AAPL", day2) is True

        day5 = trigger_date + timedelta(days=5)
        assert mgr.is_in_cooldown("AAPL", day5) is False

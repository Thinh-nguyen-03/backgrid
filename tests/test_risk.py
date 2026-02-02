"""Unit tests for risk management module."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.risk import (
    MarketRegime,
    MarketRegimeFilter,
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
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    np.random.seed(42)
    base_price = 100
    prices = []
    for i in range(250):
        base_price += np.random.randn() * 0.5
        prices.append(base_price)

    prices = np.array(prices)
    return pd.DataFrame({
        "Open": prices + np.random.randn(250) * 0.3,
        "High": prices + abs(np.random.randn(250)) * 1.0,
        "Low": prices - abs(np.random.randn(250)) * 1.0,
        "Close": prices,
        "Volume": np.random.randint(1000000, 10000000, 250)
    }, index=dates)


@pytest.fixture
def bull_market_data():
    """Create data with strong uptrend (bull market)."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    prices = np.linspace(100, 150, 250) + np.random.randn(250) * 1
    return pd.DataFrame({
        "Open": prices * 0.998,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": [1000000] * 250
    }, index=dates)


@pytest.fixture
def bear_market_data():
    """Create data with strong downtrend (bear market)."""
    dates = pd.date_range(start="2023-01-01", periods=250, freq="D")
    prices = np.linspace(150, 100, 250) + np.random.randn(250) * 1
    return pd.DataFrame({
        "Open": prices * 1.002,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": [1000000] * 250
    }, index=dates)


class TestMarketRegimeFilter:
    """Tests for market regime detection."""

    def test_default_params(self):
        """Test default parameters."""
        filter = MarketRegimeFilter()
        assert filter.params["sma_period"] == 200
        assert filter.params["reference_symbol"] == "SPY"
        assert filter.params["buffer_pct"] == 0.0

    def test_custom_params(self):
        """Test custom parameters."""
        filter = MarketRegimeFilter({
            "sma_period": 100,
            "buffer_pct": 0.02
        })
        assert filter.params["sma_period"] == 100
        assert filter.params["buffer_pct"] == 0.02

    def test_invalid_sma_period(self):
        """Test invalid SMA period raises error."""
        with pytest.raises(ValueError, match="positive integer"):
            MarketRegimeFilter({"sma_period": 0})

    def test_invalid_buffer_pct(self):
        """Test invalid buffer percentage raises error."""
        with pytest.raises(ValueError, match="buffer_pct"):
            MarketRegimeFilter({"buffer_pct": 0.6})

    def test_calculate_sma(self, sample_ohlcv_data):
        """Test SMA calculation."""
        filter = MarketRegimeFilter({"sma_period": 20})
        sma = filter.calculate_sma(sample_ohlcv_data)

        assert isinstance(sma, pd.Series)
        assert len(sma) == len(sample_ohlcv_data)
        assert sma.iloc[:19].isna().all()
        assert not sma.iloc[19:].isna().any()

    def test_get_regime_bull_market(self, bull_market_data):
        """Test regime detection in bull market."""
        filter = MarketRegimeFilter({"sma_period": 50})
        regime = filter.get_regime(bull_market_data)

        assert regime.state == RegimeState.BULL
        assert regime.above_sma is True
        assert regime.reference_price > regime.sma_value

    def test_get_regime_bear_market(self, bear_market_data):
        """Test regime detection in bear market."""
        filter = MarketRegimeFilter({"sma_period": 50})
        regime = filter.get_regime(bear_market_data)

        assert regime.state == RegimeState.BEAR
        assert regime.above_sma is False
        assert regime.reference_price < regime.sma_value

    def test_get_regime_insufficient_data(self, sample_ohlcv_data):
        """Test regime detection with insufficient data."""
        filter = MarketRegimeFilter({"sma_period": 200})
        short_data = sample_ohlcv_data.iloc[:50]

        with pytest.raises(ValueError, match="Insufficient data"):
            filter.get_regime(short_data)

    def test_allows_entry_bull(self, bull_market_data):
        """Test entry allowed in bull market for long positions."""
        filter = MarketRegimeFilter({"sma_period": 50})
        assert filter.allows_entry(bull_market_data, side="long") is True

    def test_allows_entry_bear_blocks_long(self, bear_market_data):
        """Test long entry blocked in bear market."""
        filter = MarketRegimeFilter({"sma_period": 50})
        assert filter.allows_entry(bear_market_data, side="long") is False

    def test_get_regime_series(self, sample_ohlcv_data):
        """Test regime series generation."""
        filter = MarketRegimeFilter({"sma_period": 50})
        regimes = filter.get_regime_series(sample_ohlcv_data)

        assert isinstance(regimes, pd.Series)
        assert len(regimes) == len(sample_ohlcv_data)
        assert all(r in [RegimeState.BULL, RegimeState.BEAR, RegimeState.NEUTRAL]
                   for r in regimes)

    def test_get_bull_gate_series(self, sample_ohlcv_data):
        """Test bull gate series generation."""
        filter = MarketRegimeFilter({"sma_period": 50})
        bull_gate = filter.get_bull_gate_series(sample_ohlcv_data)

        assert isinstance(bull_gate, pd.Series)
        assert bull_gate.dtype == bool

    def test_regime_with_buffer(self, sample_ohlcv_data):
        """Test regime detection with buffer zone."""
        filter = MarketRegimeFilter({
            "sma_period": 50,
            "buffer_pct": 0.02
        })
        regime = filter.get_regime(sample_ohlcv_data)

        assert regime.state in [RegimeState.BULL, RegimeState.BEAR, RegimeState.NEUTRAL]


class TestStopLossManager:
    """Tests for stop loss management."""

    def test_default_params(self):
        """Test default parameters."""
        manager = StopLossManager()
        assert manager.params["atr_multiplier"] == 3.0
        assert manager.params["cooldown_days"] == 1

    def test_custom_params(self):
        """Test custom parameters."""
        manager = StopLossManager({
            "atr_multiplier": 2.0,
            "cooldown_days": 5
        })
        assert manager.params["atr_multiplier"] == 2.0
        assert manager.params["cooldown_days"] == 5

    def test_invalid_atr_multiplier(self):
        """Test invalid ATR multiplier raises error."""
        with pytest.raises(ValueError, match="positive"):
            StopLossManager({"atr_multiplier": -1.0})

    def test_calculate_stop_price_atr(self, sample_ohlcv_data):
        """Test ATR-based stop price calculation."""
        manager = StopLossManager({"atr_multiplier": 3.0})
        stop = manager.calculate_stop_price(
            entry_price=100.0,
            df=sample_ohlcv_data,
            stop_type=StopType.ATR
        )

        assert stop < 100.0
        assert stop > 0

    def test_calculate_stop_price_with_atr_value(self):
        """Test stop price calculation with ATR value."""
        manager = StopLossManager({"atr_multiplier": 2.0})
        stop = manager.calculate_stop_price(
            entry_price=100.0,
            atr=2.5,
            stop_type=StopType.ATR
        )

        assert stop == 100.0 - (2.5 * 2.0)

    def test_register_position(self, sample_ohlcv_data):
        """Test position registration."""
        manager = StopLossManager()
        stop = manager.register_position(
            symbol="AAPL",
            entry_price=150.0,
            entry_date=datetime(2023, 6, 1),
            df=sample_ohlcv_data
        )

        assert stop > 0
        assert stop < 150.0

    def test_check_stop_not_triggered(self):
        """Test stop check when not triggered."""
        manager = StopLossManager()
        manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            entry_date=datetime(2023, 6, 1),
            atr=2.0
        )

        result = manager.check_stop("AAPL", current_price=98.0)
        assert result.triggered is False

    def test_check_stop_triggered(self):
        """Test stop check when triggered."""
        manager = StopLossManager({"atr_multiplier": 2.0})
        manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            entry_date=datetime(2023, 6, 1),
            atr=2.0
        )

        result = manager.check_stop("AAPL", current_price=95.0)
        assert result.triggered is True
        assert result.loss_amount > 0

    def test_cooldown_period(self):
        """Test cooldown period after stop triggered."""
        manager = StopLossManager({"atr_multiplier": 2.0, "cooldown_days": 3})
        manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            entry_date=datetime(2023, 6, 1),
            atr=2.0
        )

        trigger_date = datetime(2023, 6, 5)
        manager.check_stop("AAPL", current_price=90.0, current_date=trigger_date)

        assert manager.is_in_cooldown("AAPL", trigger_date + timedelta(days=1))
        assert not manager.is_in_cooldown("AAPL", trigger_date + timedelta(days=4))

    def test_cooldown_end_date(self):
        """Test cooldown end date tracking."""
        manager = StopLossManager({"atr_multiplier": 2.0, "cooldown_days": 2})
        manager.register_position("AAPL", 100.0, datetime(2023, 6, 1), atr=2.0)

        trigger_date = datetime(2023, 6, 5)
        manager.check_stop("AAPL", current_price=90.0, current_date=trigger_date)

        end_date = manager.get_cooldown_end("AAPL")
        assert end_date == trigger_date + timedelta(days=2)

    def test_stop_history(self):
        """Test stop trigger history tracking."""
        manager = StopLossManager({"atr_multiplier": 2.0})
        manager.register_position("AAPL", 100.0, datetime(2023, 6, 1), atr=2.0)
        manager.check_stop("AAPL", current_price=90.0, current_date=datetime(2023, 6, 5))

        history = manager.get_stop_history()
        assert len(history) == 1
        assert history[0]["symbol"] == "AAPL"

    def test_clear_position(self):
        """Test clearing position state."""
        manager = StopLossManager()
        manager.register_position("AAPL", 100.0, datetime(2023, 6, 1), atr=2.0)
        manager.clear_position("AAPL")

        result = manager.check_stop("AAPL", current_price=90.0)
        assert result.triggered is False


class TestSectorLimitManager:
    """Tests for sector concentration limits."""

    def test_default_params(self):
        """Test default parameters."""
        manager = SectorLimitManager()
        assert manager.params["max_sector_exposure"] == 0.30

    def test_custom_params(self):
        """Test custom parameters."""
        manager = SectorLimitManager({"max_sector_exposure": 0.25})
        assert manager.params["max_sector_exposure"] == 0.25

    def test_invalid_max_exposure(self):
        """Test invalid max exposure raises error."""
        with pytest.raises(ValueError):
            SectorLimitManager({"max_sector_exposure": 1.5})

    def test_add_position(self):
        """Test adding a position."""
        manager = SectorLimitManager()
        manager.add_position("AAPL", "Technology", 100, 15000.0)

        assert manager.get_position_count() == 1
        exposure = manager.get_sector_exposure("Technology", total_portfolio=100000)
        assert exposure.exposure_value == 15000.0

    def test_remove_position(self):
        """Test removing a position."""
        manager = SectorLimitManager()
        manager.add_position("AAPL", "Technology", 100, 15000.0)
        manager.remove_position("AAPL")

        assert manager.get_position_count() == 0

    def test_sector_exposure_calculation(self):
        """Test sector exposure calculation."""
        manager = SectorLimitManager()
        manager.add_position("AAPL", "Technology", 100, 15000.0)
        manager.add_position("MSFT", "Technology", 50, 10000.0)

        exposure = manager.get_sector_exposure("Technology", total_portfolio=100000)

        assert exposure.exposure_value == 25000.0
        assert exposure.exposure_pct == 0.25
        assert exposure.symbol_count == 2
        assert set(exposure.symbols) == {"AAPL", "MSFT"}

    def test_allows_entry_within_limit(self):
        """Test entry allowed when within limit."""
        manager = SectorLimitManager({"max_sector_exposure": 0.30})
        manager.add_position("AAPL", "Technology", 100, 15000.0)

        assert manager.allows_entry(
            "MSFT", "Technology", 10000.0, total_portfolio=100000
        )

    def test_allows_entry_exceeds_limit(self):
        """Test entry blocked when exceeding limit."""
        manager = SectorLimitManager({"max_sector_exposure": 0.30})
        manager.add_position("AAPL", "Technology", 100, 25000.0)

        assert not manager.allows_entry(
            "MSFT", "Technology", 10000.0, total_portfolio=100000
        )

    def test_set_sector_limit_override(self):
        """Test setting custom sector limit."""
        manager = SectorLimitManager()
        manager.set_sector_limit("Technology", 0.40)

        assert manager.get_sector_limit("Technology") == 0.40
        assert manager.get_sector_limit("Healthcare") == 0.30

    def test_available_capacity(self):
        """Test available capacity calculation."""
        manager = SectorLimitManager({"max_sector_exposure": 0.30})
        manager.add_position("AAPL", "Technology", 100, 15000.0)

        capacity = manager.get_available_capacity("Technology", 100000)
        assert capacity == 15000.0

    def test_compliance_check(self):
        """Test compliance checking."""
        manager = SectorLimitManager({"max_sector_exposure": 0.30})
        manager.add_position("AAPL", "Technology", 100, 35000.0)

        messages = manager.check_compliance(total_portfolio=100000)
        assert len(messages) > 0
        assert "VIOLATION" in messages[0]

    def test_multiple_sectors(self):
        """Test tracking multiple sectors."""
        manager = SectorLimitManager()
        manager.add_position("AAPL", "Technology", 100, 15000.0)
        manager.add_position("JNJ", "Healthcare", 50, 10000.0)

        exposures = manager.get_all_sector_exposures(total_portfolio=100000)

        assert "Technology" in exposures
        assert "Healthcare" in exposures
        assert exposures["Technology"].exposure_pct == 0.15
        assert exposures["Healthcare"].exposure_pct == 0.10


class TestPortfolioHeatTracker:
    """Tests for portfolio heat tracking."""

    def test_default_params(self):
        """Test default parameters."""
        tracker = PortfolioHeatTracker()
        assert tracker.params["max_heat_pct"] == 0.06
        assert tracker.params["max_positions"] == 20

    def test_custom_params(self):
        """Test custom parameters."""
        tracker = PortfolioHeatTracker({
            "max_heat_pct": 0.10,
            "max_positions": 15
        })
        assert tracker.params["max_heat_pct"] == 0.10
        assert tracker.params["max_positions"] == 15

    def test_invalid_max_heat(self):
        """Test invalid max heat raises error."""
        with pytest.raises(ValueError):
            PortfolioHeatTracker({"max_heat_pct": 1.5})

    def test_add_position(self):
        """Test adding a position for heat tracking."""
        tracker = PortfolioHeatTracker()
        risk = tracker.add_position(
            symbol="AAPL",
            entry_price=150.0,
            shares=100,
            stop_price=145.0
        )

        assert risk == 500.0
        assert tracker.get_position_count() == 1

    def test_get_total_heat(self):
        """Test total heat calculation."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 50, 290.0)

        total_heat = tracker.get_total_heat()
        assert total_heat == 1000.0

    def test_get_heat_pct(self):
        """Test heat percentage calculation."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)

        heat_pct = tracker.get_heat_pct(portfolio_value=100000)
        assert heat_pct == 0.005

    def test_heat_status_cool(self):
        """Test COOL heat status."""
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.10})
        tracker.add_position("AAPL", 150.0, 100, 145.0)

        status = tracker.get_heat_status(portfolio_value=100000)
        assert status == HeatStatus.COOL

    def test_heat_status_critical(self):
        """Test CRITICAL heat status."""
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.05})
        tracker.add_position("AAPL", 150.0, 1000, 145.0)
        tracker.add_position("MSFT", 300.0, 500, 290.0)

        status = tracker.get_heat_status(portfolio_value=100000)
        assert status == HeatStatus.CRITICAL

    def test_get_heat_report(self):
        """Test heat report generation."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 50, 290.0)

        report = tracker.get_heat_report(portfolio_value=100000)

        assert report.total_heat_value == 1000.0
        assert report.position_count == 2
        assert len(report.positions) == 2
        assert report.positions[0].total_risk >= report.positions[1].total_risk

    def test_allows_new_risk_within_limit(self):
        """Test allowing new risk within limit."""
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.06})
        tracker.add_position("AAPL", 150.0, 100, 145.0)

        assert tracker.allows_new_risk(
            proposed_risk=500.0,
            portfolio_value=100000
        )

    def test_allows_new_risk_exceeds_limit(self):
        """Test blocking new risk exceeding limit."""
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.05})
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 100, 290.0)
        tracker.add_position("GOOGL", 100.0, 100, 95.0)
        tracker.add_position("AMZN", 150.0, 100, 140.0)

        assert not tracker.allows_new_risk(
            proposed_risk=2500.0,
            portfolio_value=100000
        )

    def test_max_positions_limit(self):
        """Test max positions enforcement."""
        tracker = PortfolioHeatTracker({"max_positions": 2})
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 50, 290.0)

        assert not tracker.allows_new_risk(
            proposed_risk=100.0,
            portfolio_value=100000
        )

    def test_get_max_new_risk(self):
        """Test max new risk calculation."""
        tracker = PortfolioHeatTracker({"max_heat_pct": 0.06})
        tracker.add_position("AAPL", 150.0, 100, 145.0)

        max_risk = tracker.get_max_new_risk(portfolio_value=100000)
        assert max_risk == 5500.0

    def test_remove_position(self):
        """Test position removal."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.remove_position("AAPL")

        assert tracker.get_position_count() == 0
        assert tracker.get_total_heat() == 0

    def test_update_position(self):
        """Test position update."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.update_position("AAPL", stop_price=147.0)

        total_heat = tracker.get_total_heat()
        assert total_heat == 300.0

    def test_positions_available(self):
        """Test positions available calculation."""
        tracker = PortfolioHeatTracker({"max_positions": 5})
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 50, 290.0)

        assert tracker.get_positions_available() == 3

    def test_largest_risk_position(self):
        """Test finding largest risk position."""
        tracker = PortfolioHeatTracker()
        tracker.add_position("AAPL", 150.0, 100, 145.0)
        tracker.add_position("MSFT", 300.0, 100, 290.0)

        largest = tracker.get_largest_risk_position()
        assert largest == "MSFT"


class TestRiskIntegration:
    """Integration tests for risk management."""

    def test_market_regime_blocks_entry(self, bear_market_data):
        """Test that bear regime blocks entries."""
        regime_filter = MarketRegimeFilter({"sma_period": 50})
        sector_manager = SectorLimitManager()

        entry_allowed = regime_filter.allows_entry(bear_market_data, side="long")
        assert not entry_allowed

    def test_full_risk_check_workflow(self, sample_ohlcv_data):
        """Test complete risk check workflow."""
        regime_filter = MarketRegimeFilter({"sma_period": 50})
        sector_manager = SectorLimitManager({"max_sector_exposure": 0.30})
        stop_manager = StopLossManager({"atr_multiplier": 3.0})
        heat_tracker = PortfolioHeatTracker({"max_heat_pct": 0.06})

        portfolio_value = 100000
        proposed_position = 10000

        regime = regime_filter.get_regime(sample_ohlcv_data)
        regime_allows = regime.state != RegimeState.BEAR

        sector_allows = sector_manager.allows_entry(
            "AAPL", "Technology", proposed_position, portfolio_value
        )

        stop_price = stop_manager.calculate_stop_price(
            entry_price=150.0,
            df=sample_ohlcv_data,
            stop_type=StopType.ATR
        )
        proposed_risk = (150.0 - stop_price) * (proposed_position / 150.0)

        heat_allows = heat_tracker.allows_new_risk(proposed_risk, portfolio_value)

        all_checks_pass = regime_allows and sector_allows and heat_allows
        assert isinstance(all_checks_pass, bool)

    def test_stop_triggers_cooldown_blocks_reentry(self, sample_ohlcv_data):
        """Test that triggered stop creates cooldown."""
        stop_manager = StopLossManager({"atr_multiplier": 2.0, "cooldown_days": 3})

        entry_date = datetime(2023, 6, 1)
        stop_price = stop_manager.register_position(
            "AAPL", 100.0, entry_date, atr=2.0
        )

        trigger_date = datetime(2023, 6, 5)
        result = stop_manager.check_stop("AAPL", 90.0, trigger_date)
        assert result.triggered

        next_day = trigger_date + timedelta(days=1)
        reentry_check = stop_manager.check_stop("AAPL", 95.0, next_day)
        assert reentry_check.in_cooldown

    def test_sector_limit_with_multiple_entries(self):
        """Test sector limits across multiple entries."""
        manager = SectorLimitManager({"max_sector_exposure": 0.30})
        portfolio = 100000

        manager.add_position("AAPL", "Technology", 100, 15000)
        assert manager.allows_entry("MSFT", "Technology", 10000, portfolio)

        manager.add_position("MSFT", "Technology", 50, 10000)
        assert not manager.allows_entry("GOOGL", "Technology", 10000, portfolio)

        assert manager.allows_entry("JNJ", "Healthcare", 10000, portfolio)

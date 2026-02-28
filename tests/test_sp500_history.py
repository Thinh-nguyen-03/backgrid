"""Tests for SP500History lookup engine and interval conversion."""

import json
import os
import pytest

from src.sp500_history import (
    SP500History,
    ValidationResult,
    MembershipDetail,
    convert_snapshots_to_intervals,
    get_sp500_history,
    reset_sp500_history,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sp500_test_intervals.json"
)


@pytest.fixture
def history():
    return SP500History(data_path=FIXTURE_PATH)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset module singleton before each test."""
    reset_sp500_history()
    yield
    reset_sp500_history()


# --- SP500History: loading and metadata ---

class TestSP500HistoryLoad:
    def test_load_fixture(self, history):
        assert history._meta["total_symbols"] == 6

    def test_load_correct_symbol_count(self, history):
        assert len(history._intervals) == 6

    def test_load_missing_file(self, tmp_path):
        h = SP500History(data_path=str(tmp_path / "nonexistent.json"))
        assert h._intervals == {}
        assert h._meta == {}

    def test_reload(self, history, tmp_path):
        # Write a minimal file and reload
        data = {"meta": {"total_symbols": 1}, "intervals": {"TEST": [["2020-01-01", None]]}}
        p = tmp_path / "reload.json"
        p.write_text(json.dumps(data))
        history.reload(data_path=str(p))
        assert len(history._intervals) == 1
        assert history.is_member("TEST", "2020-06-01")

    def test_get_data_coverage(self, history):
        cov = history.get_data_coverage()
        assert cov["coverage_start"] == "1996-01-02"
        assert cov["coverage_end"] == "2026-01-17"
        assert cov["total_symbols"] == 6


# --- SP500History: is_member ---

class TestIsMember:
    def test_always_member(self, history):
        assert history.is_member("AAPL", "2000-01-01") is True
        assert history.is_member("AAPL", "2025-12-31") is True

    def test_removed_member_before_removal(self, history):
        assert history.is_member("ENRNQ", "2000-01-01") is True

    def test_removed_member_after_removal(self, history):
        assert history.is_member("ENRNQ", "2002-01-01") is False

    def test_removed_member_on_removal_date(self, history):
        # On the removal date itself, still considered a member
        assert history.is_member("ENRNQ", "2001-11-19") is True

    def test_added_later_before_join(self, history):
        assert history.is_member("META", "2010-01-01") is False

    def test_added_later_after_join(self, history):
        assert history.is_member("META", "2020-01-01") is True

    def test_temporary_member_during(self, history):
        assert history.is_member("SNDK", "2010-01-01") is True

    def test_temporary_member_before(self, history):
        assert history.is_member("SNDK", "2004-01-01") is False

    def test_temporary_member_after(self, history):
        assert history.is_member("SNDK", "2016-01-01") is False

    def test_never_member(self, history):
        assert history.is_member("PLTR", "2020-01-01") is False

    def test_unknown_symbol(self, history):
        assert history.is_member("ZZZZ", "2020-01-01") is False

    def test_case_insensitive(self, history):
        assert history.is_member("aapl", "2020-01-01") is True
        assert history.is_member("Msft", "2020-01-01") is True


# --- SP500History: get_members_on_date ---

class TestGetMembersOnDate:
    def test_early_date(self, history):
        members = history.get_members_on_date("1996-01-02")
        assert "AAPL" in members
        assert "MSFT" in members
        assert "ENRNQ" in members
        assert "META" not in members

    def test_recent_date(self, history):
        members = history.get_members_on_date("2025-01-01")
        assert "AAPL" in members
        assert "META" in members
        assert "ENRNQ" not in members
        assert "SNDK" not in members

    def test_members_sorted(self, history):
        members = history.get_members_on_date("2020-01-01")
        assert members == sorted(members)


# --- SP500History: get_membership_periods ---

class TestGetMembershipPeriods:
    def test_always_member(self, history):
        periods = history.get_membership_periods("AAPL")
        assert len(periods) == 1
        assert periods[0] == ("1996-01-02", None)

    def test_removed_member(self, history):
        periods = history.get_membership_periods("ENRNQ")
        assert len(periods) == 1
        assert periods[0] == ("1996-01-02", "2001-11-19")

    def test_never_member(self, history):
        periods = history.get_membership_periods("PLTR")
        assert periods == []

    def test_unknown_symbol(self, history):
        periods = history.get_membership_periods("ZZZZ")
        assert periods == []


# --- SP500History: get_first_join_date ---

class TestGetFirstJoinDate:
    def test_original_member(self, history):
        assert history.get_first_join_date("AAPL") == "1996-01-02"

    def test_later_member(self, history):
        assert history.get_first_join_date("META") == "2013-12-23"

    def test_temporary_member(self, history):
        assert history.get_first_join_date("SNDK") == "2005-07-01"

    def test_never_member(self, history):
        assert history.get_first_join_date("PLTR") is None

    def test_unknown_symbol(self, history):
        assert history.get_first_join_date("ZZZZ") is None


# --- SP500History: get_historical_universe ---

class TestGetHistoricalUniverse:
    def test_returns_same_as_get_members(self, history):
        u = history.get_historical_universe("2020-01-01")
        m = history.get_members_on_date("2020-01-01")
        assert u == m


# --- Validation ---

class TestValidation:
    def test_all_full_members(self, history):
        result = history.validate_symbols(["AAPL", "MSFT"], "2000-01-01", "2020-01-01")
        assert result.survivorship_bias_risk == "none"
        assert len(result.full_members) == 2
        assert len(result.partial_members) == 0
        assert len(result.non_members) == 0

    def test_partial_member(self, history):
        result = history.validate_symbols(["AAPL", "ENRNQ"], "1998-01-01", "2005-01-01")
        assert "AAPL" in result.full_members
        assert len(result.partial_members) == 1
        assert result.partial_members[0].symbol == "ENRNQ"
        assert 0 < result.partial_members[0].coverage_pct < 1.0

    def test_non_member(self, history):
        result = history.validate_symbols(["PLTR"], "2000-01-01", "2020-01-01")
        assert len(result.non_members) == 1
        assert result.non_members[0].symbol == "PLTR"
        assert result.non_members[0].coverage_pct == 0.0

    def test_not_found_symbol(self, history):
        result = history.validate_symbols(["ZZZZ"], "2000-01-01", "2020-01-01")
        assert "ZZZZ" in result.not_found

    def test_non_member_with_first_join_date(self, history):
        # META joined 2013, query range ends before that
        result = history.validate_symbols(["META"], "2000-01-01", "2010-01-01")
        assert len(result.non_members) == 1
        assert result.non_members[0].first_join_date == "2013-12-23"

    def test_risk_none(self, history):
        result = history.validate_symbols(["AAPL", "MSFT"], "2020-01-01", "2025-01-01")
        assert result.survivorship_bias_risk == "none"

    def test_risk_high(self, history):
        # All symbols have issues
        result = history.validate_symbols(
            ["PLTR", "ENRNQ", "META"], "2000-01-01", "2005-01-01"
        )
        assert result.survivorship_bias_risk == "high"

    def test_risk_low(self, history):
        # 1 issue out of 16 symbols -> 6.25% -> low
        # ENRNQ is partial for 1998-2005 range; AAPL and MSFT are full
        symbols = ["AAPL", "MSFT"] * 8 + ["ENRNQ"]
        result = history.validate_symbols(symbols, "1998-01-01", "2005-01-01")
        issues = len(result.partial_members) + len(result.non_members)
        total = len(symbols)
        assert issues / total < 0.10
        assert result.survivorship_bias_risk == "low"

    def test_earliest_overlap_date(self, history):
        result = history.validate_symbols(["AAPL", "META"], "2000-01-01", "2025-01-01")
        # META joined 2013-12-23, which is after start date
        assert result.earliest_overlap_date == "2013-12-23"

    def test_no_earliest_overlap_when_all_joined_before_start(self, history):
        result = history.validate_symbols(["AAPL", "MSFT"], "2020-01-01", "2025-01-01")
        assert result.earliest_overlap_date is None

    def test_coverage_pct_calculation(self, history):
        # SNDK: 2005-07-01 to 2015-10-21
        # Query: 2005-01-01 to 2016-01-01 (entire period ~4018 days)
        # Overlap: 2005-07-01 to 2015-10-21 (~3764 days)
        result = history.validate_symbols(["SNDK"], "2005-01-01", "2016-01-01")
        assert len(result.partial_members) == 1
        pct = result.partial_members[0].coverage_pct
        assert 0.9 < pct < 1.0  # ~93%

    def test_bias_summary_none(self, history):
        result = history.validate_symbols(["AAPL"], "2020-01-01", "2025-01-01")
        assert "full period" in result.bias_summary.lower()

    def test_bias_summary_has_issues(self, history):
        result = history.validate_symbols(["AAPL", "PLTR"], "2020-01-01", "2025-01-01")
        assert "survivorship" in result.bias_summary.lower() or "partial" in result.bias_summary.lower() or "not in" in result.bias_summary.lower()

    def test_date_range_before_coverage(self, history):
        result = history.validate_symbols(["AAPL"], "1990-01-01", "1995-01-01")
        assert result.survivorship_bias_risk == "unknown"
        assert "1996" in result.bias_summary

    def test_empty_intervals_loaded(self, history):
        result = history.validate_symbols(["AAPL"], "2020-01-01", "2025-01-01")
        assert result.survivorship_bias_risk != "unknown"

    def test_mixed_scenario(self, history):
        result = history.validate_symbols(
            ["AAPL", "MSFT", "ENRNQ", "META", "SNDK", "PLTR"],
            "2000-01-01", "2020-01-01"
        )
        assert "AAPL" in result.full_members
        assert "MSFT" in result.full_members
        assert any(m.symbol == "ENRNQ" for m in result.partial_members)
        # META joined 2013: partial for 2000-2020
        meta_in_partial = any(m.symbol == "META" for m in result.partial_members)
        meta_in_full = "META" in result.full_members
        assert meta_in_partial or meta_in_full  # joined in range -> partial
        # PLTR: never member
        assert any(m.symbol == "PLTR" for m in result.non_members)


# --- Interval conversion ---

class TestIntervalConversion:
    def test_simple_snapshots(self):
        rows = [
            ("2020-01-01", {"AAPL", "MSFT"}),
            ("2020-06-01", {"AAPL", "MSFT", "GOOGL"}),
        ]
        result = convert_snapshots_to_intervals(rows)
        assert "AAPL" in result["intervals"]
        assert "GOOGL" in result["intervals"]
        # AAPL: one interval, still member
        assert result["intervals"]["AAPL"] == [["2020-01-01", None]]
        # GOOGL: joined in second snapshot
        assert result["intervals"]["GOOGL"] == [["2020-06-01", None]]

    def test_add_remove_events(self):
        rows = [
            ("2020-01-01", {"A", "B"}),
            ("2020-06-01", {"A", "C"}),  # B removed, C added
        ]
        result = convert_snapshots_to_intervals(rows)
        assert result["intervals"]["B"] == [["2020-01-01", "2020-06-01"]]
        assert result["intervals"]["C"] == [["2020-06-01", None]]
        assert result["intervals"]["A"] == [["2020-01-01", None]]

    def test_symbol_rejoin(self):
        rows = [
            ("2020-01-01", {"A"}),
            ("2020-06-01", set()),  # A removed
            ("2020-12-01", {"A"}),  # A rejoins
        ]
        result = convert_snapshots_to_intervals(rows)
        intervals = result["intervals"]["A"]
        assert len(intervals) == 2
        assert intervals[0] == ["2020-01-01", "2020-06-01"]
        assert intervals[1] == ["2020-12-01", None]

    def test_metadata_populated(self):
        rows = [
            ("2020-01-01", {"A", "B"}),
            ("2020-06-01", {"A", "B", "C"}),
        ]
        result = convert_snapshots_to_intervals(rows)
        meta = result["meta"]
        assert meta["coverage_start"] == "2020-01-01"
        assert meta["coverage_end"] == "2020-06-01"
        assert meta["total_symbols"] == 3
        assert meta["total_changes"] == 1  # C added

    def test_empty_rows(self):
        result = convert_snapshots_to_intervals([])
        assert result == {"meta": {}, "intervals": {}}

    def test_single_snapshot(self):
        rows = [("2020-01-01", {"X", "Y"})]
        result = convert_snapshots_to_intervals(rows)
        assert result["intervals"]["X"] == [["2020-01-01", None]]
        assert result["intervals"]["Y"] == [["2020-01-01", None]]
        assert result["meta"]["total_changes"] == 0


# --- Singleton ---

class TestSingleton:
    def test_get_sp500_history_returns_instance(self):
        # This will try to load the default file; may or may not exist
        h = get_sp500_history()
        assert isinstance(h, SP500History)

    def test_singleton_returns_same_instance(self):
        h1 = get_sp500_history()
        h2 = get_sp500_history()
        assert h1 is h2

    def test_reset_clears_singleton(self):
        h1 = get_sp500_history()
        reset_sp500_history()
        h2 = get_sp500_history()
        assert h1 is not h2

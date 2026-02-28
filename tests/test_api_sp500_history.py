"""Tests for S&P 500 history API endpoints and updater."""

import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.sp500_history import SP500History, reset_sp500_history
from src.sp500_updater import SP500Updater, UpdateStatus, UpdateResult, ConstituentChange

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sp500_test_intervals.json"
)


@pytest.fixture(autouse=True)
def reset_singleton():
    reset_sp500_history()
    yield
    reset_sp500_history()


@pytest.fixture
def mock_history():
    """Patch get_sp500_history to use test fixture."""
    h = SP500History(data_path=FIXTURE_PATH)
    with patch("src.api_sp500_history.get_sp500_history", return_value=h):
        yield h


@pytest.fixture
def client(mock_history):
    from src.api import app
    return TestClient(app)


@pytest.fixture
def updater(tmp_path):
    """Updater with a writable copy of the fixture."""
    import shutil
    dest = tmp_path / "sp500_intervals.json"
    shutil.copy(FIXTURE_PATH, dest)
    return SP500Updater(data_path=str(dest))


# --- Status endpoint ---

class TestStatusEndpoint:
    def test_status_success(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.check_for_updates.return_value = UpdateStatus(
                last_updated="2026-01-17",
                days_since_update=5,
                freshness="fresh",
                coverage_start="1996-01-02",
                coverage_end="2026-01-17",
                total_symbols_tracked=503,
            )
            res = client.get("/api/v1/sp500-history/status")
            assert res.status_code == 200
            data = res.json()
            assert data["freshness"] == "fresh"
            assert data["total_symbols_tracked"] == 503

    def test_status_error(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.check_for_updates.side_effect = Exception("disk error")
            res = client.get("/api/v1/sp500-history/status")
            assert res.status_code == 503


# --- Validate endpoint ---

class TestValidateEndpoint:
    def test_validate_success(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["AAPL", "MSFT"],
            "start": "2020-01-01",
            "end": "2025-01-01",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["survivorship_bias_risk"] == "none"
        assert "AAPL" in data["full_members"]

    def test_validate_with_partial(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["AAPL", "ENRNQ"],
            "start": "1998-01-01",
            "end": "2005-01-01",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["partial_members"]) >= 1

    def test_validate_empty_symbols(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": [],
            "start": "2020-01-01",
            "end": "2025-01-01",
        })
        assert res.status_code == 422

    def test_validate_bad_date_format(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["AAPL"],
            "start": "01-01-2020",
            "end": "2025-01-01",
        })
        assert res.status_code == 422

    def test_validate_earliest_overlap(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["AAPL", "META"],
            "start": "2000-01-01",
            "end": "2025-01-01",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["earliest_overlap_date"] == "2013-12-23"

    def test_validate_non_member(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["PLTR"],
            "start": "2020-01-01",
            "end": "2025-01-01",
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["non_members"]) == 1

    def test_validate_unknown_symbol(self, client):
        res = client.post("/api/v1/sp500-history/validate", json={
            "symbols": ["ZZZZ"],
            "start": "2020-01-01",
            "end": "2025-01-01",
        })
        assert res.status_code == 200
        assert "ZZZZ" in res.json()["not_found"]


# --- Universe endpoint ---

class TestUniverseEndpoint:
    def test_universe_success(self, client):
        res = client.get("/api/v1/sp500-history/universe?date=2020-01-01")
        assert res.status_code == 200
        data = res.json()
        assert "AAPL" in data["symbols"]
        assert data["member_count"] == len(data["symbols"])

    def test_universe_no_date(self, client):
        res = client.get("/api/v1/sp500-history/universe")
        assert res.status_code == 422

    def test_universe_bad_format(self, client):
        res = client.get("/api/v1/sp500-history/universe?date=not-a-date")
        assert res.status_code == 422


# --- Symbol endpoint ---

class TestSymbolEndpoint:
    def test_known_symbol(self, client):
        res = client.get("/api/v1/sp500-history/symbol/AAPL")
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "AAPL"
        assert data["is_current_member"] is True
        assert len(data["periods"]) == 1

    def test_removed_symbol(self, client):
        res = client.get("/api/v1/sp500-history/symbol/ENRNQ")
        assert res.status_code == 200
        data = res.json()
        assert data["is_current_member"] is False

    def test_unknown_symbol(self, client):
        res = client.get("/api/v1/sp500-history/symbol/ZZZZ")
        assert res.status_code == 200
        data = res.json()
        assert data["periods"] == []
        assert data["is_current_member"] is False

    def test_case_insensitive(self, client):
        res = client.get("/api/v1/sp500-history/symbol/aapl")
        assert res.status_code == 200
        assert res.json()["symbol"] == "AAPL"


# --- Update endpoint ---

class TestUpdateEndpoint:
    def test_update_rate_limited(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.is_rate_limited.return_value = True
            res = client.post("/api/v1/sp500-history/update")
            assert res.status_code == 429

    def test_update_no_api_key(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.is_rate_limited.return_value = False
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            with patch("src.api_sp500_history._updater") as mock_updater:
                mock_updater.is_rate_limited.return_value = False
                # Remove the key entirely
                env = os.environ.copy()
                env.pop("ANTHROPIC_API_KEY", None)
                with patch.dict(os.environ, env, clear=True):
                    res = client.post("/api/v1/sp500-history/update")
                    assert res.status_code == 503

    def test_update_success(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.is_rate_limited.return_value = False
            mock_updater.update.return_value = UpdateResult(
                success=True,
                previous_date="2026-01-17",
                new_date="2026-02-01",
                announcements_found=1,
                changes_applied=2,
                symbols_added=["NEWCO"],
                symbols_removed=["OLDCO"],
            )
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                res = client.post("/api/v1/sp500-history/update")
                assert res.status_code == 200
                data = res.json()
                assert data["changes_applied"] == 2
                assert "NEWCO" in data["symbols_added"]

    def test_update_failure(self, client):
        with patch("src.api_sp500_history._updater") as mock_updater:
            mock_updater.is_rate_limited.return_value = False
            mock_updater.update.return_value = UpdateResult(
                success=False, error="Scrape failed"
            )
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
                res = client.post("/api/v1/sp500-history/update")
                assert res.status_code == 502


# --- SP500Updater unit tests ---

class TestUpdaterCheckForUpdates:
    def test_fresh_status(self, updater):
        status = updater.check_for_updates()
        assert status.freshness in ("fresh", "stale", "outdated")
        assert status.total_symbols_tracked == 6

    def test_missing_file(self, tmp_path):
        u = SP500Updater(data_path=str(tmp_path / "missing.json"))
        status = u.check_for_updates()
        assert status.freshness == "outdated"
        assert status.days_since_update == 999

    def test_freshness_thresholds(self, updater):
        # The fixture has last_updated=2026-01-17
        status = updater.check_for_updates()
        # As of 2026-02-21, that's ~35 days -> stale
        assert status.freshness in ("fresh", "stale")


class TestUpdaterRateLimit:
    def test_not_rate_limited_initially(self, updater):
        assert updater.is_rate_limited() is False

    def test_rate_limited_after_attempt(self, updater):
        updater._last_update_attempt = time.time()
        assert updater.is_rate_limited() is True

    def test_not_rate_limited_after_expiry(self, updater):
        updater._last_update_attempt = time.time() - 7200  # 2 hours ago
        assert updater.is_rate_limited() is False


class TestUpdaterScrapeCards:
    def test_scrape_parses_cards(self, updater):
        mock_html = """
        <html><body>
        <a gtm-content-type="IndexNews" data-gtm-label="S&P 500 Change" href="/doc.pdf">
            <h2>S&P 500 Change</h2>
            <li class="meta-data-date">Feb 01, 2026 - 5:15 PM</li>
        </a>
        </body></html>
        """
        with patch.object(updater, "_fetch_with_playwright", return_value=mock_html):
            cards = updater._scrape_news_cards()
            assert len(cards) == 1
            assert "S&P 500" in cards[0].title

    def test_scrape_no_cards(self, updater):
        with patch.object(updater, "_fetch_with_playwright", return_value="<html><body></body></html>"):
            cards = updater._scrape_news_cards()
            assert len(cards) == 0


class TestUpdaterClassifyRelevance:
    def test_classify_with_api(self, updater):
        from src.sp500_updater import NewsCard
        cards = [
            NewsCard(title="S&P 500 adds NEWCO", date="Feb 01, 2026", pdf_url="http://x.pdf"),
            NewsCard(title="Methodology update", date="Feb 01, 2026", pdf_url="http://y.pdf"),
        ]

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"relevant_indices": [0]}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            with patch("anthropic.Anthropic", return_value=mock_client):
                relevant = updater._classify_relevance(cards)
                assert len(relevant) == 1
                assert relevant[0].title == "S&P 500 adds NEWCO"

    def test_classify_no_api_key(self, updater):
        from src.sp500_updater import NewsCard
        cards = [NewsCard(title="Test", date="Feb 01, 2026", pdf_url="http://x.pdf")]

        with patch.dict(os.environ, {}, clear=True):
            relevant = updater._classify_relevance(cards)
            assert len(relevant) == 0


class TestUpdaterExtractChanges:
    def test_extract_from_pdf(self, updater):
        mock_pdf_response = MagicMock()
        mock_pdf_response.content = b"fake pdf bytes"
        mock_pdf_response.raise_for_status = MagicMock()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "NEWCO will be added to S&P 500 effective 2026-03-01"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        mock_ai_response = MagicMock()
        mock_ai_response.content = [MagicMock(
            text='{"changes": [{"action": "add", "symbol": "NEWCO", "effective_date": "2026-03-01"}]}'
        )]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_ai_response

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}):
            with patch("requests.get", return_value=mock_pdf_response):
                with patch("PyPDF2.PdfReader", return_value=mock_reader):
                    with patch("anthropic.Anthropic", return_value=mock_client):
                        changes = updater._extract_changes_from_pdf("http://test.pdf")
                        assert len(changes) == 1
                        assert changes[0].symbol == "NEWCO"
                        assert changes[0].action == "add"


class TestUpdaterApplyChanges:
    def test_apply_add(self, updater):
        data = {"intervals": {}, "meta": {}}
        changes = [ConstituentChange(action="add", symbol="NEWCO", effective_date="2026-03-01")]
        added, removed = updater._apply_changes(data, changes)
        assert "NEWCO" in added
        assert data["intervals"]["NEWCO"] == [["2026-03-01", None]]

    def test_apply_remove(self, updater):
        data = {
            "intervals": {"OLDCO": [["2020-01-01", None]]},
            "meta": {},
        }
        changes = [ConstituentChange(action="remove", symbol="OLDCO", effective_date="2026-03-01")]
        added, removed = updater._apply_changes(data, changes)
        assert "OLDCO" in removed
        assert data["intervals"]["OLDCO"] == [["2020-01-01", "2026-03-01"]]

    def test_apply_add_and_remove(self, updater):
        data = {
            "intervals": {"OLDCO": [["2020-01-01", None]]},
            "meta": {},
        }
        changes = [
            ConstituentChange(action="remove", symbol="OLDCO", effective_date="2026-03-01"),
            ConstituentChange(action="add", symbol="NEWCO", effective_date="2026-03-01"),
        ]
        added, removed = updater._apply_changes(data, changes)
        assert "NEWCO" in added
        assert "OLDCO" in removed


# --- Portfolio integration ---

class TestPortfolioIntegration:
    def test_response_includes_survivorship_context(self, client):
        """Portfolio response should include survivorship_context field."""
        # Just verify the model accepts the field
        from src.models import PortfolioBacktestResponse, SurvivorshipContext
        ctx = SurvivorshipContext(
            validation_performed=True,
            bias_risk="none",
            full_members=["AAPL", "MSFT"],
            partial_members_count=0,
            non_members_count=0,
            bias_summary="All symbols were full members.",
        )
        assert ctx.validation_performed is True
        assert ctx.bias_risk == "none"

    def test_survivorship_context_optional(self):
        """SurvivorshipContext should be optional on the response."""
        from src.models import PortfolioBacktestResponse, JobStatus
        response = PortfolioBacktestResponse(
            batch_id="test-batch",
            status=JobStatus.COMPLETED,
            symbols_requested=2,
        )
        assert response.survivorship_context is None

    def test_survivorship_context_with_data(self):
        """SurvivorshipContext should serialize correctly."""
        from src.models import SurvivorshipContext
        ctx = SurvivorshipContext(
            validation_performed=True,
            bias_risk="high",
            partial_members_count=3,
            non_members_count=2,
        )
        d = ctx.model_dump()
        assert d["bias_risk"] == "high"
        assert d["partial_members_count"] == 3

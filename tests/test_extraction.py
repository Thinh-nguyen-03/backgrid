"""Tests for LLM-assisted strategy extraction."""

import pytest
import json
import os
import time
from unittest.mock import patch, Mock, MagicMock
from fastapi.testclient import TestClient

from src.api import app
from src.extraction.extractor import StrategyExtractor, ExtractionResult
from src.extraction.content_fetcher import ContentFetcher
from src.extraction.validator import ExtractionValidator
from src.extraction.similarity import resolve_strategy_name


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def validator():
    return ExtractionValidator()


@pytest.fixture
def fetcher():
    return ContentFetcher()


@pytest.fixture
def mock_llm_ma_response():
    """Successful MA extraction response."""
    return {
        "strategy": "ma_crossover",
        "params": {"fast": 20, "slow": 50},
        "config": {"initial_capital": 10000},
        "confidence": 0.85,
        "reasoning": "Extracted MA crossover with 20/50 periods.",
    }


@pytest.fixture
def mock_llm_rsi_response():
    """Successful RSI extraction response."""
    return {
        "strategy": "rsi",
        "params": {
            "rsi_period": 14,
            "oversold_threshold": 30,
            "overbought_threshold": 70,
        },
        "config": None,
        "confidence": 0.90,
        "reasoning": "Extracted RSI with standard parameters.",
    }


@pytest.fixture
def mock_llm_low_confidence():
    """Low confidence extraction response."""
    return {
        "strategy": "ma_crossover",
        "params": {"fast": 10, "slow": 30},
        "confidence": 0.15,
        "reasoning": "Not enough information to confidently extract.",
    }


# --- ExtractionValidator tests ---


class TestExtractionValidator:
    """Tests for ExtractionValidator."""

    def test_valid_ma_params(self, validator):
        is_valid, cleaned, errors = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 20, "slow": 50}}
        )
        assert is_valid
        assert len(errors) == 0
        assert cleaned["params"]["fast"] == 20
        assert cleaned["params"]["slow"] == 50

    def test_valid_rsi_params(self, validator):
        is_valid, cleaned, errors = validator.validate({
            "strategy": "rsi",
            "params": {
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
            },
        })
        assert is_valid
        assert len(errors) == 0

    def test_unknown_strategy(self, validator):
        is_valid, _, errors = validator.validate({"strategy": "bollinger"})
        assert not is_valid
        assert any("Unknown strategy" in e for e in errors)

    def test_missing_strategy(self, validator):
        is_valid, _, errors = validator.validate({"params": {"fast": 10}})
        assert not is_valid

    def test_ma_fast_greater_than_slow(self, validator):
        is_valid, _, errors = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 50, "slow": 20}}
        )
        assert not is_valid
        assert any("fast" in e for e in errors)

    def test_ma_fast_equals_slow(self, validator):
        is_valid, _, errors = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 50, "slow": 50}}
        )
        assert not is_valid

    def test_ma_missing_params(self, validator):
        is_valid, _, errors = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 10}}
        )
        assert not is_valid
        assert any("require" in e.lower() for e in errors)

    def test_ma_clamp_fast_below_min(self, validator):
        is_valid, cleaned, _ = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 1, "slow": 100}}
        )
        assert cleaned["params"]["fast"] == 2

    def test_ma_clamp_slow_above_max(self, validator):
        is_valid, cleaned, _ = validator.validate(
            {"strategy": "ma_crossover", "params": {"fast": 10, "slow": 1000}}
        )
        assert cleaned["params"]["slow"] == 500

    def test_rsi_oversold_greater_than_overbought(self, validator):
        is_valid, _, errors = validator.validate({
            "strategy": "rsi",
            "params": {
                "rsi_period": 14,
                "oversold_threshold": 70,
                "overbought_threshold": 30,
            },
        })
        assert not is_valid
        assert any("oversold" in e for e in errors)

    def test_rsi_clamp_period(self, validator):
        is_valid, cleaned, _ = validator.validate({
            "strategy": "rsi",
            "params": {
                "rsi_period": 200,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
            },
        })
        assert cleaned["params"]["rsi_period"] == 100

    def test_rsi_optional_confirmation(self, validator):
        is_valid, cleaned, _ = validator.validate({
            "strategy": "rsi",
            "params": {
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "confirmation_window": 3,
                "min_confirmations": 2,
            },
        })
        assert is_valid
        assert cleaned["params"]["confirmation_window"] == 3
        assert cleaned["params"]["min_confirmations"] == 2

    def test_rsi_clamp_confirmation_window(self, validator):
        _, cleaned, _ = validator.validate({
            "strategy": "rsi",
            "params": {
                "rsi_period": 14,
                "oversold_threshold": 30,
                "overbought_threshold": 70,
                "confirmation_window": 50,
            },
        })
        assert cleaned["params"]["confirmation_window"] == 10

    def test_rsi_default_thresholds(self, validator):
        """When thresholds are missing, defaults are used."""
        is_valid, cleaned, _ = validator.validate({
            "strategy": "rsi",
            "params": {"rsi_period": 14},
        })
        assert is_valid
        assert cleaned["params"]["oversold_threshold"] == 30.0
        assert cleaned["params"]["overbought_threshold"] == 70.0


# --- ContentFetcher tests ---


class TestContentFetcher:

    @patch("requests.get")
    def test_fetch_url_extracts_text(self, mock_get, fetcher):
        mock_response = Mock()
        mock_response.text = (
            "<html><body><p>Buy when 20-day MA crosses above 50-day MA</p></body></html>"
        )
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        text = fetcher.fetch_url("https://example.com/strategy")
        assert "20-day" in text
        assert "50-day" in text

    @patch("requests.get")
    def test_fetch_url_strips_scripts(self, mock_get, fetcher):
        mock_response = Mock()
        mock_response.text = (
            "<html><body><script>evil();</script><p>Strategy info</p></body></html>"
        )
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        text = fetcher.fetch_url("https://example.com/strategy")
        assert "evil" not in text
        assert "Strategy info" in text

    @patch("requests.get")
    def test_fetch_url_timeout(self, mock_get, fetcher):
        import requests as real_requests
        mock_get.side_effect = real_requests.Timeout("timeout")

        with pytest.raises(Exception):
            fetcher.fetch_url("https://example.com/slow")

    def test_process_text_passthrough(self, fetcher):
        text = "Use RSI with period 14"
        assert fetcher.process_text(text) == text

    def test_process_text_truncation(self, fetcher):
        long_text = "x" * 100000
        result = fetcher.process_text(long_text)
        assert len(result) == 50000

    @patch("PyPDF2.PdfReader")
    def test_extract_pdf(self, mock_reader_cls, fetcher):
        mock_page = Mock()
        mock_page.extract_text.return_value = "RSI strategy with period 14"
        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        text = fetcher.extract_pdf(b"fake-pdf-bytes")
        assert "RSI strategy" in text


# --- Similarity tests ---


class TestSimilarity:

    def test_resolve_ma_crossover(self):
        assert resolve_strategy_name("ma_crossover") == "ma_crossover"

    def test_resolve_moving_average(self):
        assert resolve_strategy_name("moving_average") == "ma_crossover"

    def test_resolve_golden_cross(self):
        assert resolve_strategy_name("golden_cross") == "ma_crossover"

    def test_resolve_rsi(self):
        assert resolve_strategy_name("rsi") == "rsi"

    def test_resolve_relative_strength(self):
        assert resolve_strategy_name("relative_strength") == "rsi"

    def test_resolve_mean_reversion(self):
        assert resolve_strategy_name("mean_reversion") == "rsi"

    def test_resolve_unknown_passthrough(self):
        assert resolve_strategy_name("bollinger_bands") == "bollinger_bands"

    def test_resolve_case_insensitive(self):
        assert resolve_strategy_name("MA_CROSSOVER") == "ma_crossover"

    def test_resolve_with_hyphens(self):
        assert resolve_strategy_name("ma-crossover") == "ma_crossover"

    def test_resolve_with_spaces(self):
        assert resolve_strategy_name("moving average") == "ma_crossover"


# --- StrategyExtractor tests ---


class TestStrategyExtractor:

    def _mock_extractor(self, response_dict):
        """Create extractor with mocked _call_llm."""
        extractor = StrategyExtractor()
        extractor._call_llm = Mock(return_value=response_dict)
        return extractor

    def test_extract_from_text_success(self, mock_llm_ma_response):
        extractor = self._mock_extractor(mock_llm_ma_response)
        result = extractor.extract_from_text("Use a 20/50 MA crossover strategy")

        assert result.success
        assert result.strategy == "ma_crossover"
        assert result.params["fast"] == 20
        assert result.params["slow"] == 50
        assert result.confidence == 0.85
        assert result.source_type == "text"

    def test_extract_rsi_from_text(self, mock_llm_rsi_response):
        extractor = self._mock_extractor(mock_llm_rsi_response)
        result = extractor.extract_from_text("RSI strategy with period 14")

        assert result.success
        assert result.strategy == "rsi"
        assert result.params["rsi_period"] == 14

    def test_extract_low_confidence_fails(self, mock_llm_low_confidence):
        extractor = self._mock_extractor(mock_llm_low_confidence)
        result = extractor.extract_from_text("This is not about trading")

        assert not result.success
        assert result.confidence < 0.3

    def test_extract_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            extractor = StrategyExtractor()
            result = extractor.extract_from_text("test")
        assert not result.success
        assert any("ANTHROPIC_API_KEY" in e for e in result.errors)

    def test_extract_invalid_json_from_llm(self):
        extractor = StrategyExtractor()
        extractor._call_llm = Mock(side_effect=json.JSONDecodeError("err", "", 0))
        result = extractor.extract_from_text("test")

        assert not result.success
        assert len(result.errors) > 0

    def test_extract_from_url(self, mock_llm_ma_response):
        extractor = self._mock_extractor(mock_llm_ma_response)
        extractor.fetcher.fetch_url = Mock(return_value="MA 20/50 content")
        result = extractor.extract_from_url("https://example.com")

        assert result.success
        assert result.source_type == "url"

    def test_extract_from_pdf(self, mock_llm_rsi_response):
        extractor = self._mock_extractor(mock_llm_rsi_response)
        extractor.fetcher.extract_pdf = Mock(return_value="RSI 14")
        result = extractor.extract_from_pdf(b"fake-pdf")

        assert result.success
        assert result.source_type == "pdf"

    def test_rate_limit_enforcement(self):
        extractor = StrategyExtractor()
        extractor.MAX_REQUESTS_PER_HOUR = 2
        extractor._request_times = [time.time(), time.time()]

        with pytest.raises(RuntimeError, match="Rate limit"):
            extractor._check_rate_limit()

    def test_rate_limit_expired_entries_cleared(self):
        extractor = StrategyExtractor()
        extractor.MAX_REQUESTS_PER_HOUR = 2
        extractor._request_times = [time.time() - 7200, time.time() - 7200]

        # Should not raise because old entries are expired
        extractor._check_rate_limit()

    def test_strategy_alias_resolution(self):
        response = {
            "strategy": "moving_average",
            "params": {"fast": 10, "slow": 30},
            "confidence": 0.9,
            "reasoning": "MA strategy",
        }
        extractor = self._mock_extractor(response)
        result = extractor.extract_from_text("moving average 10/30")

        assert result.success
        assert result.strategy == "ma_crossover"


# --- API endpoint tests ---


class TestExtractionAPIEndpoints:

    @pytest.fixture(autouse=True)
    def reset_extractor(self):
        """Reset module-level extractor before each test."""
        import src.api_extraction as ext_mod
        ext_mod._extractor = None
        yield
        ext_mod._extractor = None

    def test_import_disabled_by_default(self, client):
        """Without ENABLE_LLM_EXTRACTION, returns 503."""
        with patch.dict(os.environ, {"ENABLE_LLM_EXTRACTION": ""}, clear=False):
            response = client.post(
                "/api/v1/strategy/import", json={"text": "test"}
            )
        assert response.status_code == 503

    def test_import_no_api_key(self, client):
        """With feature enabled but no API key, returns 503."""
        env = {"ENABLE_LLM_EXTRACTION": "true"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            response = client.post(
                "/api/v1/strategy/import", json={"text": "test"}
            )
        assert response.status_code == 503

    def test_import_no_input(self, client):
        """Without url or text, returns 400."""
        env = {"ENABLE_LLM_EXTRACTION": "true", "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            response = client.post("/api/v1/strategy/import", json={})
        assert response.status_code == 400

    def test_import_from_text(self, client, mock_llm_ma_response):
        env = {"ENABLE_LLM_EXTRACTION": "true", "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                StrategyExtractor, "_call_llm", return_value=mock_llm_ma_response
            ):
                response = client.post(
                    "/api/v1/strategy/import",
                    json={"text": "Use a 20/50 MA crossover"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"]
        assert data["strategy"] == "ma_crossover"

    def test_import_from_url(self, client, mock_llm_ma_response):
        env = {"ENABLE_LLM_EXTRACTION": "true", "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            with patch.object(
                StrategyExtractor, "_call_llm", return_value=mock_llm_ma_response
            ):
                with patch("requests.get") as mock_get:
                    mock_resp = Mock()
                    mock_resp.text = "<html><body>MA 20/50 strategy</body></html>"
                    mock_resp.raise_for_status = Mock()
                    mock_get.return_value = mock_resp

                    response = client.post(
                        "/api/v1/strategy/import",
                        json={"url": "https://example.com/strategy"},
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["success"]

    def test_pdf_import_wrong_extension(self, client):
        env = {"ENABLE_LLM_EXTRACTION": "true", "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict(os.environ, env, clear=False):
            response = client.post(
                "/api/v1/strategy/import/pdf",
                files={"file": ("test.txt", b"content", "text/plain")},
            )
        assert response.status_code == 400
        data = response.json()
        assert "PDF" in data.get("detail", data.get("error", ""))


# --- ExtractionResult model tests ---


class TestExtractionResult:

    def test_default_values(self):
        result = ExtractionResult(success=False)
        assert result.confidence == 0.0
        assert result.reasoning == ""
        assert result.errors == []
        assert result.source_type == ""

    def test_successful_result(self):
        result = ExtractionResult(
            success=True,
            strategy="ma_crossover",
            params={"fast": 10, "slow": 30},
            confidence=0.9,
        )
        assert result.success
        assert result.strategy == "ma_crossover"

    def test_result_serialization(self):
        result = ExtractionResult(
            success=True,
            strategy="rsi",
            params={"rsi_period": 14},
            confidence=0.8,
        )
        data = result.model_dump()
        assert data["success"]
        assert data["params"]["rsi_period"] == 14

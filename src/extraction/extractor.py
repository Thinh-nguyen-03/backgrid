"""Strategy parameter extraction via LLM."""

import json
import logging
import time
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

try:
    from ..config import settings
except ImportError:
    import os

    class _FallbackSettings:
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    settings = _FallbackSettings()

from .content_fetcher import ContentFetcher
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .validator import ExtractionValidator
from .similarity import resolve_strategy_name

logger = logging.getLogger(__name__)


class ExtractionResult(BaseModel):
    """Result of strategy extraction."""
    success: bool
    strategy: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    reasoning: str = ""
    errors: List[str] = Field(default_factory=list)
    source_type: str = ""


class StrategyExtractor:
    """Extracts strategy parameters from content using Claude API."""

    MAX_REQUESTS_PER_HOUR = 10

    def __init__(self):
        self.fetcher = ContentFetcher()
        self.validator = ExtractionValidator()
        self._request_times: List[float] = []

    def _check_rate_limit(self):
        """Enforce in-memory rate limiting."""
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 3600]
        if len(self._request_times) >= self.MAX_REQUESTS_PER_HOUR:
            raise RuntimeError("Rate limit exceeded: max 10 extractions per hour")
        self._request_times.append(now)

    def _call_llm(self, content: str) -> dict:
        """Call Anthropic Claude API for parameter extraction."""
        api_key = settings.anthropic_api_key
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")

        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        content=content[:10000]
                    ),
                }
            ],
        )

        text = message.content[0].text.strip()
        return json.loads(text)

    def _build_result(
        self, raw: dict, errors: List[str], source_type: str
    ) -> ExtractionResult:
        """Build ExtractionResult from LLM output and validation."""
        raw["strategy"] = resolve_strategy_name(raw.get("strategy", ""))
        is_valid, cleaned, validation_errors = self.validator.validate(raw)
        all_errors = errors + validation_errors
        confidence = raw.get("confidence", 0)

        return ExtractionResult(
            success=is_valid and confidence >= 0.3 and len(all_errors) == 0,
            strategy=cleaned.get("strategy"),
            params=cleaned.get("params"),
            config=cleaned.get("config"),
            confidence=confidence,
            reasoning=raw.get("reasoning", ""),
            errors=all_errors,
            source_type=source_type,
        )

    def extract_from_url(self, url: str) -> ExtractionResult:
        """Extract strategy from a URL."""
        self._check_rate_limit()
        try:
            content = self.fetcher.fetch_url(url)
            raw = self._call_llm(content)
            return self._build_result(raw, [], "url")
        except Exception as e:
            logger.error(f"Extraction from URL failed: {e}")
            return ExtractionResult(
                success=False, errors=[str(e)], source_type="url"
            )

    def extract_from_text(self, text: str) -> ExtractionResult:
        """Extract strategy from raw text."""
        self._check_rate_limit()
        try:
            content = self.fetcher.process_text(text)
            raw = self._call_llm(content)
            return self._build_result(raw, [], "text")
        except Exception as e:
            logger.error(f"Extraction from text failed: {e}")
            return ExtractionResult(
                success=False, errors=[str(e)], source_type="text"
            )

    def extract_from_pdf(self, pdf_bytes: bytes) -> ExtractionResult:
        """Extract strategy from PDF bytes."""
        self._check_rate_limit()
        try:
            content = self.fetcher.extract_pdf(pdf_bytes)
            raw = self._call_llm(content)
            return self._build_result(raw, [], "pdf")
        except Exception as e:
            logger.error(f"Extraction from PDF failed: {e}")
            return ExtractionResult(
                success=False, errors=[str(e)], source_type="pdf"
            )

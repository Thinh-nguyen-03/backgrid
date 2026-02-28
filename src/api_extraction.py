"""Strategy extraction API endpoints."""

import os
import logging
from typing import Optional

import redis as redis_lib
from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from pydantic import BaseModel

try:
    from .extraction import StrategyExtractor, ExtractionResult
except ImportError:
    from extraction import StrategyExtractor, ExtractionResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/strategy", tags=["extraction"])

_extractor = None
_redis_client = None

RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECS = 3600


def _get_redis() -> Optional[redis_lib.Redis]:
    """Return a shared Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            _redis_client = redis_lib.from_url(redis_url, socket_connect_timeout=1)
        except Exception as e:
            logger.warning(f"Redis unavailable, rate limiting disabled: {e}")
    return _redis_client


def _check_rate_limit(client_ip: str) -> None:
    """Enforce per-IP rate limit using Redis INCR + EXPIRE.

    Raises HTTPException(429) if the client has exceeded the limit.
    Fails open (allows the request) if Redis is unreachable.
    """
    r = _get_redis()
    if r is None:
        return

    key = f"rate_limit:extraction:{client_ip}"
    try:
        count = r.incr(key)
        if count == 1:
            r.expire(key, RATE_LIMIT_WINDOW_SECS)
        if count > RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per hour"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check failed, allowing request: {e}")


def _get_extractor() -> StrategyExtractor:
    """Get extractor instance, checking feature flag and API key."""
    global _extractor
    if os.getenv("ENABLE_LLM_EXTRACTION", "").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=503, detail="LLM extraction is not enabled"
        )
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503, detail="ANTHROPIC_API_KEY not configured"
        )
    if _extractor is None:
        _extractor = StrategyExtractor()
    return _extractor


class TextExtractionRequest(BaseModel):
    """Request for text or URL-based extraction."""
    text: Optional[str] = None
    url: Optional[str] = None


@router.post("/import", response_model=ExtractionResult)
async def import_strategy(request: Request, body: TextExtractionRequest):
    """Extract strategy parameters from URL or text."""
    _check_rate_limit(request.client.host)
    extractor = _get_extractor()

    if body.url:
        return extractor.extract_from_url(body.url)
    elif body.text:
        return extractor.extract_from_text(body.text)
    else:
        raise HTTPException(
            status_code=400, detail="Provide either 'url' or 'text'"
        )


@router.post("/import/pdf", response_model=ExtractionResult)
async def import_strategy_pdf(request: Request, file: UploadFile = File(...)):
    """Extract strategy parameters from uploaded PDF."""
    _check_rate_limit(request.client.host)
    extractor = _get_extractor()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF must be under 10MB")

    return extractor.extract_from_pdf(contents)

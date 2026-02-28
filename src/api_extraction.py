"""Strategy extraction API endpoints."""

import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

try:
    from .extraction import StrategyExtractor, ExtractionResult
except ImportError:
    from extraction import StrategyExtractor, ExtractionResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/strategy", tags=["extraction"])

_extractor = None


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
async def import_strategy(request: TextExtractionRequest):
    """Extract strategy parameters from URL or text."""
    extractor = _get_extractor()

    if request.url:
        return extractor.extract_from_url(request.url)
    elif request.text:
        return extractor.extract_from_text(request.text)
    else:
        raise HTTPException(
            status_code=400, detail="Provide either 'url' or 'text'"
        )


@router.post("/import/pdf", response_model=ExtractionResult)
async def import_strategy_pdf(file: UploadFile = File(...)):
    """Extract strategy parameters from uploaded PDF."""
    extractor = _get_extractor()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF must be under 10MB")

    return extractor.extract_from_pdf(contents)

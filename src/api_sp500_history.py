"""API endpoints for S&P 500 historical constituent data."""

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from .config import settings
    from .sp500_history import get_sp500_history, MembershipDetail, ValidationResult
    from .sp500_updater import SP500Updater, UpdateStatus, UpdateResult
except ImportError:
    import os

    class _FallbackSettings:
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    settings = _FallbackSettings()
    from sp500_history import get_sp500_history, MembershipDetail, ValidationResult
    from sp500_updater import SP500Updater, UpdateStatus, UpdateResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sp500-history", tags=["sp500-history"])

_updater = SP500Updater()


class ValidateRequest(BaseModel):
    """Request to validate symbols against a date range."""
    symbols: List[str] = Field(..., min_length=1)
    start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class UniverseResponse(BaseModel):
    """Historical S&P 500 universe on a specific date."""
    date: str
    member_count: int
    symbols: List[str]


class SymbolHistoryResponse(BaseModel):
    """Membership history for a single symbol."""
    symbol: str
    periods: List[List[Optional[str]]]
    first_join_date: Optional[str]
    is_current_member: bool


@router.get("/status", response_model=UpdateStatus)
async def get_status():
    """Get data freshness status."""
    try:
        status = _updater.check_for_updates()
        return status
    except Exception as e:
        logger.error(f"sp500_status_check_failed error={e}")
        raise HTTPException(status_code=503, detail="S&P 500 history data unavailable")


@router.post("/validate", response_model=ValidationResult)
async def validate_symbols(request: ValidateRequest):
    """Validate symbols against a date range for survivorship bias."""
    try:
        history = get_sp500_history()
        logger.info(
            f"sp500_validate_request symbols={request.symbols} "
            f"start={request.start} end={request.end} "
            f"intervals_loaded={len(history._intervals)}"
        )
        result = history.validate_symbols(request.symbols, request.start, request.end)
        logger.info(
            f"sp500_validate_result full={result.full_members} "
            f"partial={[m.symbol for m in result.partial_members]} "
            f"non_members={[m.symbol for m in result.non_members]} "
            f"not_found={result.not_found} risk={result.survivorship_bias_risk}"
        )
        return result
    except Exception as e:
        logger.error(f"sp500_validation_failed error={e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/universe", response_model=UniverseResponse)
async def get_universe(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format"),
):
    """Get historical S&P 500 members on a specific date."""
    try:
        history = get_sp500_history()
        members = history.get_historical_universe(date)
        return UniverseResponse(
            date=date,
            member_count=len(members),
            symbols=members,
        )
    except Exception as e:
        logger.error(f"sp500_universe_lookup_failed error={e}")
        raise HTTPException(status_code=500, detail=f"Universe lookup failed: {str(e)}")


@router.get("/symbol/{symbol}", response_model=SymbolHistoryResponse)
async def get_symbol_history(symbol: str):
    """Get membership history for a single symbol."""
    try:
        history = get_sp500_history()
        periods = history.get_membership_periods(symbol.upper())
        first_join = history.get_first_join_date(symbol.upper())
        is_current = bool(periods and periods[-1][1] is None)
        return SymbolHistoryResponse(
            symbol=symbol.upper(),
            periods=[[s, e] for s, e in periods],
            first_join_date=first_join,
            is_current_member=is_current,
        )
    except Exception as e:
        logger.error(f"sp500_symbol_lookup_failed error={e}")
        raise HTTPException(status_code=500, detail=f"Symbol lookup failed: {str(e)}")


class UpdateRequest(BaseModel):
    """Optional request body for update endpoint."""
    pass


@router.post("/update", response_model=UpdateResult)
async def trigger_update():
    """Fetch latest S&P 500 constituent changes from Wikipedia and apply them.

    Rate limited to 1 request per hour.
    """
    if _updater.is_rate_limited():
        raise HTTPException(
            status_code=429,
            detail="Update rate limited. Try again later (max 1 per hour).",
        )

    result = await asyncio.to_thread(_updater.update)

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "Update failed")

    return result


async def run_auto_update_loop() -> None:
    """Background task: check and update S&P 500 constituent data daily.

    Runs an initial check 60 seconds after startup, then every 24 hours.
    Only triggers a Wikipedia scrape if data is 7 or more days old.
    """
    await asyncio.sleep(60)
    while True:
        try:
            status = _updater.check_for_updates()
            if status.days_since_update >= 7:
                logger.info(
                    f"sp500_auto_update_triggered days_since={status.days_since_update}"
                )
                result = await asyncio.to_thread(_updater.update)
                if result.success:
                    logger.info(
                        f"sp500_auto_update_complete changes={result.changes_applied} "
                        f"new_date={result.new_date}"
                    )
                else:
                    logger.warning(f"sp500_auto_update_failed error={result.error}")
            else:
                logger.debug(
                    f"sp500_auto_update_skipped days_since={status.days_since_update}"
                )
        except Exception as e:
            logger.error(f"sp500_auto_update_error error={e}")
        await asyncio.sleep(24 * 3600)

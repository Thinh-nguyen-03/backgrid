"""Preset library API endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

try:
    from .strategies.presets import PresetLibrary, StrategyPreset
except ImportError:
    from strategies.presets import PresetLibrary, StrategyPreset

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/presets", tags=["presets"])

_library = PresetLibrary()


@router.get("", response_model=List[StrategyPreset])
async def list_presets(
    category: Optional[str] = Query(None, description="Filter by category"),
    strategy: Optional[str] = Query(None, description="Filter by strategy type"),
    q: Optional[str] = Query(None, description="Search query"),
):
    """List available strategy presets with optional filtering."""
    if q:
        return _library.search(q)
    if category:
        return _library.filter_by_category(category)
    if strategy:
        return _library.filter_by_strategy(strategy)
    return _library.list_all()


@router.get("/categories", response_model=List[str])
async def list_preset_categories():
    """List distinct preset categories."""
    return _library.get_categories()


@router.get("/{preset_id}", response_model=StrategyPreset)
async def get_preset(preset_id: str):
    """Get a specific preset by ID."""
    preset = _library.get_by_id(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_id}")
    return preset

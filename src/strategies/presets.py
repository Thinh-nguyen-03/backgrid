"""Strategy preset library for curated backtest configurations."""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class StrategyPreset(BaseModel):
    """A curated strategy configuration preset."""
    id: str
    name: str
    description: str
    category: str
    strategy: str
    params: Dict[str, Any]
    config: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)
    risk_level: str = "moderate"
    recommended_timeframe: str = ""


class PresetLibrary:
    """Loads and queries strategy presets from JSON."""

    def __init__(self, path: Optional[str] = None):
        if path is None:
            path = str(Path(__file__).parent / "preset_data.json")
        with open(path, "r") as f:
            raw = json.load(f)
        self._presets = [StrategyPreset(**item) for item in raw]
        self._by_id = {p.id: p for p in self._presets}

    def list_all(self) -> List[StrategyPreset]:
        """Return all presets."""
        return list(self._presets)

    def get_by_id(self, preset_id: str) -> Optional[StrategyPreset]:
        """Return a single preset by ID, or None."""
        return self._by_id.get(preset_id)

    def filter_by_category(self, category: str) -> List[StrategyPreset]:
        """Return presets matching a category."""
        return [p for p in self._presets if p.category == category]

    def filter_by_strategy(self, strategy: str) -> List[StrategyPreset]:
        """Return presets using a specific strategy type."""
        return [p for p in self._presets if p.strategy == strategy]

    def search(self, query: str) -> List[StrategyPreset]:
        """Search presets by name, description, or tags."""
        q = query.lower()
        return [
            p for p in self._presets
            if q in p.name.lower()
            or q in p.description.lower()
            or any(q in t for t in p.tags)
        ]

    def get_categories(self) -> List[str]:
        """Return sorted list of distinct categories."""
        return sorted(set(p.category for p in self._presets))

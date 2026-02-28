"""Tests for strategy preset library and API endpoints."""

import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.api import app
from src.strategies.presets import PresetLibrary, StrategyPreset


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def library():
    return PresetLibrary()


# --- PresetLibrary unit tests ---


class TestPresetLibrary:
    """Tests for PresetLibrary class."""

    def test_load_presets_returns_ten(self, library):
        assert len(library.list_all()) == 10

    def test_all_presets_have_required_fields(self, library):
        for p in library.list_all():
            assert p.id
            assert p.name
            assert p.description
            assert p.category
            assert p.strategy
            assert p.params

    def test_all_preset_ids_unique(self, library):
        ids = [p.id for p in library.list_all()]
        assert len(ids) == len(set(ids))

    def test_all_presets_have_valid_strategy(self, library):
        valid = {"ma_crossover", "rsi"}
        for p in library.list_all():
            assert p.strategy in valid, f"Preset {p.id} has invalid strategy: {p.strategy}"

    def test_ma_presets_have_fast_slow(self, library):
        for p in library.filter_by_strategy("ma_crossover"):
            assert "fast" in p.params, f"Preset {p.id} missing 'fast'"
            assert "slow" in p.params, f"Preset {p.id} missing 'slow'"
            assert p.params["fast"] < p.params["slow"], (
                f"Preset {p.id}: fast ({p.params['fast']}) >= slow ({p.params['slow']})"
            )

    def test_rsi_presets_have_required_params(self, library):
        for p in library.filter_by_strategy("rsi"):
            assert "rsi_period" in p.params, f"Preset {p.id} missing 'rsi_period'"
            assert "oversold_threshold" in p.params
            assert "overbought_threshold" in p.params
            assert p.params["oversold_threshold"] < p.params["overbought_threshold"]

    def test_ma_fast_period_positive(self, library):
        for p in library.filter_by_strategy("ma_crossover"):
            assert p.params["fast"] >= 2

    def test_rsi_period_minimum(self, library):
        for p in library.filter_by_strategy("rsi"):
            assert p.params["rsi_period"] >= 2

    def test_get_by_id_golden_cross(self, library):
        preset = library.get_by_id("golden-cross")
        assert preset is not None
        assert preset.strategy == "ma_crossover"
        assert preset.params["fast"] == 50
        assert preset.params["slow"] == 200

    def test_get_by_id_rapidtrader_rsi(self, library):
        preset = library.get_by_id("rapidtrader-rsi")
        assert preset is not None
        assert preset.strategy == "rsi"
        assert preset.params["rsi_period"] == 14
        assert preset.params["oversold_threshold"] == 30
        assert preset.params["overbought_threshold"] == 55

    def test_get_by_id_not_found(self, library):
        assert library.get_by_id("nonexistent") is None

    def test_get_by_id_empty_string(self, library):
        assert library.get_by_id("") is None

    def test_filter_by_category_trend_following(self, library):
        results = library.filter_by_category("trend_following")
        assert len(results) > 0
        assert all(p.category == "trend_following" for p in results)

    def test_filter_by_category_mean_reversion(self, library):
        results = library.filter_by_category("mean_reversion")
        assert len(results) > 0
        assert all(p.category == "mean_reversion" for p in results)

    def test_filter_by_category_momentum(self, library):
        results = library.filter_by_category("momentum")
        assert len(results) > 0

    def test_filter_by_category_nonexistent(self, library):
        results = library.filter_by_category("nonexistent_category")
        assert len(results) == 0

    def test_filter_by_strategy_ma(self, library):
        results = library.filter_by_strategy("ma_crossover")
        assert len(results) > 0
        assert all(p.strategy == "ma_crossover" for p in results)

    def test_filter_by_strategy_rsi(self, library):
        results = library.filter_by_strategy("rsi")
        assert len(results) > 0
        assert all(p.strategy == "rsi" for p in results)

    def test_filter_by_strategy_nonexistent(self, library):
        results = library.filter_by_strategy("bollinger")
        assert len(results) == 0

    def test_search_golden(self, library):
        results = library.search("golden")
        assert len(results) >= 1
        assert any("golden" in p.name.lower() for p in results)

    def test_search_rsi(self, library):
        results = library.search("rsi")
        assert len(results) >= 1

    def test_search_by_tag(self, library):
        results = library.search("rapidtrader")
        assert len(results) >= 1

    def test_search_case_insensitive(self, library):
        results1 = library.search("GOLDEN")
        results2 = library.search("golden")
        assert len(results1) == len(results2)

    def test_search_no_results(self, library):
        results = library.search("zzzznonexistent")
        assert len(results) == 0

    def test_get_categories(self, library):
        categories = library.get_categories()
        assert len(categories) > 0
        assert "trend_following" in categories
        assert "mean_reversion" in categories

    def test_categories_are_sorted(self, library):
        categories = library.get_categories()
        assert categories == sorted(categories)

    def test_all_presets_have_tags(self, library):
        for p in library.list_all():
            assert isinstance(p.tags, list)
            assert len(p.tags) > 0

    def test_all_presets_have_risk_level(self, library):
        valid_levels = {"low", "moderate", "aggressive"}
        for p in library.list_all():
            assert p.risk_level in valid_levels, f"Preset {p.id}: invalid risk_level '{p.risk_level}'"

    def test_presets_with_config_have_valid_fields(self, library):
        for p in library.list_all():
            if p.config:
                if "position_sizing" in p.config:
                    assert p.config["position_sizing"] in ("fixed", "atr")
                if "risk_per_trade" in p.config:
                    assert 0 < p.config["risk_per_trade"] <= 1

    def test_custom_path_invalid_raises(self):
        with pytest.raises(FileNotFoundError):
            PresetLibrary(path="/tmp/nonexistent.json")


# --- API endpoint tests ---


class TestPresetAPIEndpoints:
    """Tests for preset API endpoints."""

    def test_list_presets(self, client):
        response = client.get("/api/v1/presets")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10

    def test_list_presets_returns_json_array(self, client):
        response = client.get("/api/v1/presets")
        assert isinstance(response.json(), list)

    def test_list_presets_filter_category(self, client):
        response = client.get("/api/v1/presets?category=trend_following")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert all(p["category"] == "trend_following" for p in data)

    def test_list_presets_filter_strategy(self, client):
        response = client.get("/api/v1/presets?strategy=rsi")
        assert response.status_code == 200
        data = response.json()
        assert all(p["strategy"] == "rsi" for p in data)

    def test_list_presets_search(self, client):
        response = client.get("/api/v1/presets?q=golden")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_list_presets_empty_category(self, client):
        response = client.get("/api/v1/presets?category=nonexistent")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_get_preset_by_id(self, client):
        response = client.get("/api/v1/presets/golden-cross")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "golden-cross"
        assert data["strategy"] == "ma_crossover"
        assert data["params"]["fast"] == 50

    def test_get_preset_not_found(self, client):
        response = client.get("/api/v1/presets/nonexistent")
        assert response.status_code == 404

    def test_get_preset_rapidtrader(self, client):
        response = client.get("/api/v1/presets/rapidtrader-rsi")
        assert response.status_code == 200
        data = response.json()
        assert data["params"]["rsi_period"] == 14
        assert data["params"]["oversold_threshold"] == 30
        assert data["params"]["overbought_threshold"] == 55

    def test_get_categories(self, client):
        response = client.get("/api/v1/presets/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert "trend_following" in data
        assert "mean_reversion" in data

    def test_preset_response_shape(self, client):
        response = client.get("/api/v1/presets/golden-cross")
        data = response.json()
        required_fields = {"id", "name", "description", "category", "strategy", "params"}
        assert required_fields.issubset(set(data.keys()))

    def test_preset_with_config(self, client):
        response = client.get("/api/v1/presets/momentum-breakout")
        assert response.status_code == 200
        data = response.json()
        assert data["config"] is not None
        assert data["config"]["position_sizing"] == "atr"

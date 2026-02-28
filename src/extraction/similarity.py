"""Fuzzy matching for strategy names from LLM output."""

STRATEGY_ALIASES = {
    "ma_crossover": [
        "ma_crossover", "moving_average", "ma", "sma_crossover",
        "golden_cross", "death_cross", "dual_ma", "ma_cross",
    ],
    "rsi": [
        "rsi", "relative_strength", "rsi_mean_reversion",
        "mean_reversion", "relative_strength_index",
    ],
}


def resolve_strategy_name(name: str) -> str:
    """Resolve an alias to a canonical strategy name."""
    normalized = name.lower().strip().replace(" ", "_").replace("-", "_")
    for canonical, aliases in STRATEGY_ALIASES.items():
        if normalized in aliases or normalized == canonical:
            return canonical
    return normalized

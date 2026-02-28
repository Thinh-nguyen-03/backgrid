"""Prompt templates for LLM-based strategy extraction."""

SYSTEM_PROMPT = (
    "You are a trading strategy parameter extractor. Given text describing a "
    "trading strategy, extract the configuration parameters.\n\n"
    "Output valid JSON with this schema:\n"
    "{\n"
    '  "strategy": "ma_crossover" or "rsi",\n'
    '  "params": { ... strategy-specific params ... },\n'
    '  "config": { ... optional execution config ... },\n'
    '  "confidence": 0.0-1.0,\n'
    '  "reasoning": "brief explanation of what was extracted"\n'
    "}\n\n"
    "For ma_crossover: params must include \"fast\" (int) and \"slow\" (int).\n"
    "For rsi: params must include \"rsi_period\" (int), \"oversold_threshold\" "
    "(number), \"overbought_threshold\" (number). Optional: "
    "\"confirmation_window\" (int), \"min_confirmations\" (int).\n"
    "Config fields (all optional): \"initial_capital\", \"position_sizing\", "
    "\"risk_per_trade\", \"enable_transaction_costs\".\n\n"
    "If the text does not describe a recognizable strategy, return "
    "confidence < 0.3.\n"
    "Return ONLY the JSON object, no markdown fencing."
)

USER_PROMPT_TEMPLATE = (
    "Extract trading strategy parameters from this content:\n\n{content}"
)

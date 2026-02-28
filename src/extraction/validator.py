"""Validation for extracted strategy configurations."""

import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

VALID_STRATEGIES = {"ma_crossover", "rsi"}

MA_PARAM_RANGES = {
    "fast": (2, 200),
    "slow": (5, 500),
}

RSI_PARAM_RANGES = {
    "rsi_period": (2, 100),
    "oversold_threshold": (0, 100),
    "overbought_threshold": (0, 100),
    "confirmation_window": (1, 10),
    "min_confirmations": (1, 10),
}


class ExtractionValidator:
    """Validates and normalizes extracted strategy parameters."""

    def validate(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Validate extraction result.

        Returns:
            (is_valid, cleaned_data, errors)
        """
        errors: List[str] = []
        strategy = data.get("strategy")

        if strategy not in VALID_STRATEGIES:
            errors.append(f"Unknown strategy: {strategy}")
            return False, data, errors

        params = data.get("params", {})

        if strategy == "ma_crossover":
            params, param_errors = self._validate_ma_params(params)
            errors.extend(param_errors)
        elif strategy == "rsi":
            params, param_errors = self._validate_rsi_params(params)
            errors.extend(param_errors)

        data["params"] = params
        return len(errors) == 0, data, errors

    def _validate_ma_params(
        self, params: dict
    ) -> Tuple[dict, List[str]]:
        errors: List[str] = []
        fast = params.get("fast")
        slow = params.get("slow")

        if fast is None or slow is None:
            errors.append("MA params require 'fast' and 'slow'")
            return params, errors

        fast = int(fast)
        slow = int(slow)
        fast = max(MA_PARAM_RANGES["fast"][0], min(fast, MA_PARAM_RANGES["fast"][1]))
        slow = max(MA_PARAM_RANGES["slow"][0], min(slow, MA_PARAM_RANGES["slow"][1]))

        if fast >= slow:
            errors.append(f"fast ({fast}) must be less than slow ({slow})")

        return {"fast": fast, "slow": slow}, errors

    def _validate_rsi_params(
        self, params: dict
    ) -> Tuple[dict, List[str]]:
        errors: List[str] = []
        period = params.get("rsi_period", 14)
        oversold = params.get("oversold_threshold", 30)
        overbought = params.get("overbought_threshold", 70)

        period = int(
            max(RSI_PARAM_RANGES["rsi_period"][0],
                min(period, RSI_PARAM_RANGES["rsi_period"][1]))
        )
        oversold = float(max(0, min(oversold, 100)))
        overbought = float(max(0, min(overbought, 100)))

        if oversold >= overbought:
            errors.append(
                f"oversold ({oversold}) must be less than overbought ({overbought})"
            )

        result = {
            "rsi_period": period,
            "oversold_threshold": oversold,
            "overbought_threshold": overbought,
        }

        if "confirmation_window" in params:
            result["confirmation_window"] = int(
                max(1, min(params["confirmation_window"], 10))
            )
        if "min_confirmations" in params:
            result["min_confirmations"] = int(
                max(1, min(params["min_confirmations"], 10))
            )

        return result, errors

"""Historical S&P 500 constituent lookup with survivorship bias detection."""

import json
import logging
import os
from datetime import datetime, date, timezone
from typing import List, Optional, Tuple, Set, Dict, Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DEFAULT_PATH = os.path.join(_DATA_DIR, "sp500_intervals.json")


class MembershipDetail(BaseModel):
    """Per-symbol membership info within a queried date range."""
    symbol: str
    status: str  # "full", "partial", "non_member", "not_found"
    periods: List[List[Optional[str]]] = []
    coverage_pct: float = 0.0
    first_join_date: Optional[str] = None


class ValidationResult(BaseModel):
    """Result of validating symbols against a date range."""
    full_members: List[str] = []
    partial_members: List[MembershipDetail] = []
    non_members: List[MembershipDetail] = []
    not_found: List[str] = []
    survivorship_bias_risk: str = "unknown"
    bias_summary: str = ""
    earliest_overlap_date: Optional[str] = None


def convert_snapshots_to_intervals(
    rows: List[Tuple[str, Set[str]]],
) -> Dict[str, Any]:
    """Convert (date, ticker_set) snapshot pairs to compact interval format.

    Args:
        rows: Sorted list of (date_str, set_of_tickers) pairs.

    Returns:
        Dict with "meta" and "intervals" keys.
    """
    if not rows:
        return {"meta": {}, "intervals": {}}

    open_intervals: Dict[str, str] = {}
    closed_intervals: Dict[str, List[List[Optional[str]]]] = {}
    total_changes = 0

    first_date = rows[0][0]
    last_date = rows[-1][0]

    # Initialize: all symbols in first snapshot start with first_date
    for symbol in rows[0][1]:
        open_intervals[symbol] = first_date
        closed_intervals.setdefault(symbol, [])

    for i in range(1, len(rows)):
        date_b, set_b = rows[i]
        _, set_a = rows[i - 1]

        added = set_b - set_a
        removed = set_a - set_b

        for symbol in added:
            open_intervals[symbol] = date_b
            closed_intervals.setdefault(symbol, [])
            total_changes += 1

        for symbol in removed:
            start = open_intervals.pop(symbol, first_date)
            closed_intervals.setdefault(symbol, [])
            closed_intervals[symbol].append([start, date_b])
            total_changes += 1

    # Close remaining open intervals with null (still members)
    for symbol, start in open_intervals.items():
        closed_intervals.setdefault(symbol, [])
        closed_intervals[symbol].append([start, None])

    # Sort intervals per symbol by start date
    for symbol in closed_intervals:
        closed_intervals[symbol].sort(key=lambda x: x[0])

    all_symbols = set()
    for _, tickers in rows:
        all_symbols |= tickers

    meta = {
        "source": "csv_import",
        "last_updated": last_date,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "coverage_start": first_date,
        "coverage_end": last_date,
        "total_symbols": len(all_symbols),
        "total_changes": total_changes,
    }

    return {"meta": meta, "intervals": closed_intervals}


def _parse_date(date_str: str) -> date:
    """Parse YYYY-MM-DD string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


class SP500History:
    """In-memory lookup for historical S&P 500 constituent membership."""

    def __init__(self, data_path: Optional[str] = None):
        self._path = data_path or _DEFAULT_PATH
        self._meta: Dict[str, Any] = {}
        self._intervals: Dict[str, List[List[Optional[str]]]] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            logger.warning(f"sp500_intervals_file_not_found path={self._path}")
            self._meta = {}
            self._intervals = {}
            return

        with open(self._path, "r") as f:
            data = json.load(f)

        self._meta = data.get("meta", {})
        self._intervals = data.get("intervals", {})
        logger.info(
            f"sp500_history_loaded symbols={len(self._intervals)} "
            f"last_updated={self._meta.get('last_updated', 'unknown')}"
        )

    def reload(self, data_path: Optional[str] = None):
        """Reload interval data from disk."""
        if data_path:
            self._path = data_path
        self._load()

    def is_member(self, symbol: str, date_str: str) -> bool:
        """Check if symbol was in S&P 500 on a specific date."""
        intervals = self._intervals.get(symbol.upper(), [])
        if not intervals:
            return False

        d = _parse_date(date_str)
        for start, end in intervals:
            s = _parse_date(start)
            e = _parse_date(end) if end else date.max
            if s <= d <= e:
                return True
        return False

    def get_members_on_date(self, date_str: str) -> List[str]:
        """Return all S&P 500 members on a given date."""
        d = _parse_date(date_str)
        members = []
        for symbol, intervals in self._intervals.items():
            for start, end in intervals:
                s = _parse_date(start)
                e = _parse_date(end) if end else date.max
                if s <= d <= e:
                    members.append(symbol)
                    break
        return sorted(members)

    def get_membership_periods(
        self, symbol: str
    ) -> List[Tuple[str, Optional[str]]]:
        """Return all membership intervals for a symbol."""
        intervals = self._intervals.get(symbol.upper(), [])
        return [(s, e) for s, e in intervals]

    def get_first_join_date(self, symbol: str) -> Optional[str]:
        """Return the date when symbol first entered the S&P 500."""
        intervals = self._intervals.get(symbol.upper(), [])
        if not intervals:
            return None
        return intervals[0][0]

    def get_historical_universe(self, date_str: str) -> List[str]:
        """Return the full S&P 500 universe as-of a specific date."""
        return self.get_members_on_date(date_str)

    def get_data_coverage(self) -> Dict[str, Any]:
        """Return metadata about data coverage."""
        return {
            "coverage_start": self._meta.get("coverage_start"),
            "coverage_end": self._meta.get("coverage_end"),
            "last_updated": self._meta.get("last_updated"),
            "total_symbols": self._meta.get("total_symbols", len(self._intervals)),
            "source": self._meta.get("source"),
        }

    def validate_symbols(
        self, symbols: List[str], start: str, end: str
    ) -> ValidationResult:
        """Validate symbols against a date range for survivorship bias.

        Categorizes each symbol as full_member, partial, non_member, or not_found.
        Computes survivorship bias risk and earliest overlap date.
        """
        if not self._intervals:
            return ValidationResult(
                not_found=[s.upper() for s in symbols],
                survivorship_bias_risk="unknown",
                bias_summary="No historical constituent data available.",
            )

        coverage_start = self._meta.get("coverage_start")
        coverage_end = self._meta.get("coverage_end")
        start_d = _parse_date(start)
        end_d = _parse_date(end)

        # If entire range is before our data coverage
        if coverage_start and start_d < _parse_date(coverage_start) and end_d < _parse_date(coverage_start):
            return ValidationResult(
                not_found=[s.upper() for s in symbols],
                survivorship_bias_risk="unknown",
                bias_summary=f"Historical constituent data starts from {coverage_start}. Cannot validate for this period.",
            )

        full_members = []
        partial_members = []
        non_members = []
        not_found = []
        total_days = (end_d - start_d).days or 1

        for symbol in symbols:
            sym = symbol.upper()
            intervals = self._intervals.get(sym)

            if intervals is None:
                not_found.append(sym)
                continue

            if not intervals:
                # Symbol exists in data but with no intervals (never a member)
                non_members.append(MembershipDetail(
                    symbol=sym,
                    status="non_member",
                    periods=[],
                    coverage_pct=0.0,
                    first_join_date=None,
                ))
                continue

            # Calculate overlap between symbol's intervals and the query range
            member_days = 0
            overlapping_periods = []

            for s_str, e_str in intervals:
                s = _parse_date(s_str)
                e = _parse_date(e_str) if e_str else date.max

                overlap_start = max(s, start_d)
                overlap_end = min(e, end_d)

                if overlap_start <= overlap_end:
                    overlapping_periods.append([s_str, e_str])
                    member_days += (overlap_end - overlap_start).days

            first_join = intervals[0][0]
            coverage_pct = round(member_days / total_days, 4) if total_days > 0 else 0.0

            if not overlapping_periods:
                non_members.append(MembershipDetail(
                    symbol=sym,
                    status="non_member",
                    periods=[],
                    coverage_pct=0.0,
                    first_join_date=first_join,
                ))
            elif coverage_pct >= 0.99:
                full_members.append(sym)
            else:
                partial_members.append(MembershipDetail(
                    symbol=sym,
                    status="partial",
                    periods=overlapping_periods,
                    coverage_pct=coverage_pct,
                    first_join_date=first_join,
                ))

        # Compute earliest_overlap_date: latest first_join among S&P members
        join_dates = []
        for sym in symbols:
            s = sym.upper()
            if s in not_found:
                continue
            intervals = self._intervals.get(s, [])
            if not intervals:
                continue  # never a member, skip for overlap calc
            join_dates.append(_parse_date(intervals[0][0]))

        earliest_overlap = None
        if join_dates:
            latest_join = max(join_dates)
            if latest_join > start_d:
                earliest_overlap = latest_join.isoformat()

        # Risk scoring
        total = len(symbols)
        issues = len(partial_members) + len(non_members)

        if total == 0:
            risk = "none"
        elif not_found and len(not_found) == total:
            risk = "unknown"
        elif issues == 0:
            risk = "none"
        elif issues / total < 0.10:
            risk = "low"
        elif issues / total < 0.30:
            risk = "medium"
        else:
            risk = "high"

        # Summary
        if risk == "none":
            summary = f"All {total} symbols were S&P 500 members for the full period."
        elif risk == "unknown":
            summary = "No historical constituent data available for these symbols."
        else:
            summary = (
                f"{issues} of {total} symbols have survivorship bias concerns "
                f"({len(partial_members)} partial, {len(non_members)} not in S&P 500)."
            )

        return ValidationResult(
            full_members=full_members,
            partial_members=partial_members,
            non_members=non_members,
            not_found=not_found,
            survivorship_bias_risk=risk,
            bias_summary=summary,
            earliest_overlap_date=earliest_overlap,
        )


# Module-level singleton
_instance: Optional[SP500History] = None


def get_sp500_history() -> SP500History:
    """Get or create the SP500History singleton."""
    global _instance
    if _instance is None:
        _instance = SP500History()
    return _instance


def reset_sp500_history():
    """Reset singleton (for testing)."""
    global _instance
    _instance = None

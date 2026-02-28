"""S&P 500 constituent data updater.

Fetches the 'Changes to the index' table from Wikipedia and applies
additions/removals to the local interval data file.
"""

import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, date
from typing import List, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DEFAULT_PATH = os.path.join(_DATA_DIR, "sp500_intervals.json")

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


class ConstituentChange(BaseModel):
    """A single S&P 500 addition or removal."""
    action: str
    symbol: str
    effective_date: str


class UpdateStatus(BaseModel):
    """Current data freshness status."""
    last_updated: str
    days_since_update: int
    freshness: str
    coverage_start: str
    coverage_end: str
    total_symbols_tracked: int


class UpdateResult(BaseModel):
    """Result of an update operation."""
    success: bool
    previous_date: Optional[str] = None
    new_date: Optional[str] = None
    changes_applied: int = 0
    symbols_added: List[str] = []
    symbols_removed: List[str] = []
    error: Optional[str] = None


class SP500Updater:
    """Updates S&P 500 interval data by scraping Wikipedia's changes table."""

    def __init__(self, data_path: Optional[str] = None):
        self._path = data_path or _DEFAULT_PATH
        self._last_update_attempt: float = 0
        self._rate_limit_seconds = 3600  # 1 hour

    def check_for_updates(self) -> UpdateStatus:
        """Check current data freshness."""
        if not os.path.exists(self._path):
            return UpdateStatus(
                last_updated="none",
                days_since_update=999,
                freshness="outdated",
                coverage_start="none",
                coverage_end="none",
                total_symbols_tracked=0,
            )

        with open(self._path, "r") as f:
            data = json.load(f)

        meta = data.get("meta", {})
        last_updated = meta.get("last_updated", "unknown")
        coverage_start = meta.get("coverage_start", "unknown")
        coverage_end = meta.get("coverage_end", "unknown")
        total_symbols = meta.get("total_symbols", len(data.get("intervals", {})))

        if last_updated and last_updated != "unknown":
            last_date = datetime.strptime(last_updated, "%Y-%m-%d").date()
            days_since = (date.today() - last_date).days
        else:
            days_since = 999

        if days_since < 30:
            freshness = "fresh"
        elif days_since < 90:
            freshness = "stale"
        else:
            freshness = "outdated"

        return UpdateStatus(
            last_updated=last_updated,
            days_since_update=days_since,
            freshness=freshness,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
            total_symbols_tracked=total_symbols,
        )

    def is_rate_limited(self) -> bool:
        """Check if an update was attempted too recently."""
        return (time.time() - self._last_update_attempt) < self._rate_limit_seconds

    def update(self) -> UpdateResult:
        """Fetch new S&P 500 constituent changes from Wikipedia and apply them."""
        if self.is_rate_limited():
            return UpdateResult(
                success=False,
                error="Rate limited. Try again later.",
            )

        self._last_update_attempt = time.time()
        logger.info("sp500_update_started")

        try:
            if not os.path.exists(self._path):
                logger.error(f"sp500_update_no_data_file path={self._path}")
                return UpdateResult(
                    success=False,
                    error="No interval data file found. Run build script first.",
                )

            with open(self._path, "r") as f:
                data = json.load(f)

            meta = data.get("meta", {})
            previous_date = meta.get("last_updated", "unknown")

            logger.info(f"sp500_update_stage_1_wikipedia last_updated={previous_date}")
            all_changes = self._scrape_wikipedia_changes(previous_date)
            logger.info(f"sp500_update_stage_1_wikipedia_done changes={len(all_changes)}")

            if not all_changes:
                logger.info("sp500_update_complete no new changes found")
                return UpdateResult(
                    success=True,
                    previous_date=previous_date,
                    new_date=previous_date,
                    changes_applied=0,
                )

            for ch in all_changes:
                logger.info(
                    f"sp500_update_change action={ch.action} "
                    f"symbol={ch.symbol} date={ch.effective_date}"
                )

            logger.info("sp500_update_stage_2 applying changes to interval data")
            added, removed = self._apply_changes(data, all_changes)

            latest_date = max(c.effective_date for c in all_changes)
            if latest_date > previous_date:
                data["meta"]["last_updated"] = latest_date
                data["meta"]["coverage_end"] = latest_date

            data["meta"]["total_symbols"] = len(data["intervals"])

            self._write_atomic(data)
            logger.info(f"sp500_update_written path={self._path}")

            from .sp500_history import get_sp500_history
            get_sp500_history().reload()

            logger.info(
                f"sp500_update_complete added={added} removed={removed} "
                f"new_date={data['meta']['last_updated']}"
            )

            return UpdateResult(
                success=True,
                previous_date=previous_date,
                new_date=data["meta"]["last_updated"],
                changes_applied=len(all_changes),
                symbols_added=added,
                symbols_removed=removed,
            )

        except Exception as e:
            logger.error(f"sp500_update_failed error={e}", exc_info=True)
            return UpdateResult(success=False, error=str(e))

    def _scrape_wikipedia_changes(self, since_date: str) -> List[ConstituentChange]:
        """Fetch S&P 500 constituent changes from Wikipedia.

        Parses the 'Changes to the index' table on the S&P 500 Wikipedia article.
        Returns only changes dated after since_date. Uses plain HTTP — no
        headless browser or bot-detection risk.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; sp500-tracker/1.0; +research)",
            "Accept-Language": "en-US,en;q=0.9",
        }

        logger.info(f"sp500_wikipedia_fetching url={_WIKIPEDIA_URL}")
        resp = requests.get(_WIKIPEDIA_URL, headers=headers, timeout=20)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Locate the "Changes to the index" section by its heading/anchor
        changes_section = soup.find(id="Changes_to_the_index")
        if changes_section is None:
            changes_section = next(
                (
                    tag for tag in soup.find_all(["h2", "h3"])
                    if "changes" in tag.get_text(strip=True).lower()
                ),
                None,
            )

        if changes_section is None:
            raise ValueError("Could not find 'Changes to the index' section on Wikipedia")

        changes_table = changes_section.find_next("table")
        if changes_table is None:
            raise ValueError("Could not find changes table after section heading")

        # Parse column positions from the header row
        header_cells = changes_table.find("tr").find_all(["th", "td"])
        col_labels = [c.get_text(strip=True).lower() for c in header_cells]
        logger.info(f"sp500_wikipedia_table_headers labels={col_labels}")

        def _find_col(keywords: List[str]) -> int:
            for i, label in enumerate(col_labels):
                if all(kw in label for kw in keywords):
                    return i
            return -1

        date_col = _find_col(["date"])
        added_col = _find_col(["added", "ticker"])
        if added_col == -1:
            added_col = _find_col(["added"])
        removed_col = _find_col(["removed", "ticker"])
        if removed_col == -1:
            removed_col = _find_col(["removed"])

        missing = []
        if date_col == -1:
            missing.append("date")
        if added_col == -1:
            missing.append("added ticker")
        if removed_col == -1:
            missing.append("removed ticker")

        if missing:
            raise ValueError(
                f"Wikipedia changes table is missing expected columns: {missing}. "
                f"Found headers: {col_labels}. "
                "The page structure may have changed — update _find_col() keywords."
            )

        logger.info(
            f"sp500_wikipedia_cols date={date_col} added={added_col} removed={removed_col}"
        )

        since: Optional[date] = None
        if since_date and since_date not in ("unknown", "none"):
            since = datetime.strptime(since_date, "%Y-%m-%d").date()

        changes: List[ConstituentChange] = []
        skipped_old = 0

        for row in changes_table.find_all("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) <= max(date_col, added_col):
                continue

            date_text = cells[date_col].get_text(strip=True)
            change_date: Optional[date] = None
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%B %Y"):
                try:
                    change_date = datetime.strptime(date_text, fmt).date()
                    break
                except ValueError:
                    continue

            if change_date is None:
                continue

            if since and change_date <= since:
                skipped_old += 1
                continue

            date_str = change_date.strftime("%Y-%m-%d")

            def _clean(text: str) -> str:
                return re.sub(r"\[.*?\]|\s+", "", text).strip().upper()

            added = _clean(cells[added_col].get_text(strip=True))
            removed = (
                _clean(cells[removed_col].get_text(strip=True))
                if removed_col < len(cells)
                else ""
            )

            _empty = {"", "—", "-", "N/A", "–"}
            if added not in _empty:
                changes.append(ConstituentChange(
                    action="add", symbol=added, effective_date=date_str,
                ))
            if removed not in _empty:
                changes.append(ConstituentChange(
                    action="remove", symbol=removed, effective_date=date_str,
                ))

        logger.info(
            f"sp500_wikipedia_done changes={len(changes)} skipped_old={skipped_old}"
        )
        return changes

    def _apply_changes(
        self, data: Dict[str, Any], changes: List[ConstituentChange]
    ) -> tuple:
        """Apply constituent changes to interval data. Returns (added, removed) lists."""
        intervals = data["intervals"]
        added = []
        removed = []

        for change in changes:
            sym = change.symbol
            intervals.setdefault(sym, [])

            if change.action == "add":
                intervals[sym].append([change.effective_date, None])
                added.append(sym)

            elif change.action == "remove":
                for interval in reversed(intervals[sym]):
                    if interval[1] is None:
                        interval[1] = change.effective_date
                        break
                removed.append(sym)

        return added, removed

    def _write_atomic(self, data: Dict[str, Any]):
        """Write JSON file atomically using temp file + rename."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(self._path), suffix=".json"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f, indent=None, separators=(",", ":"))
            # On Windows, destination must be removed before rename
            if os.path.exists(self._path):
                os.remove(self._path)
            os.rename(tmp_path, self._path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

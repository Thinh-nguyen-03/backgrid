"""S&P 500 symbol data from us500.com with Wikipedia fallback."""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_US500_URL = "https://us500.com/sp500-companies-by-sector"
_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_CACHE_TTL_DAYS = 7
_CACHE: Dict[str, Any] = {"data": None, "fetched_at": None}

_SECTOR_MAP = {
    "Information Technology": "Technology",
    "Health Care": "Healthcare",
}

_HARDCODED_FALLBACK: List[Dict[str, str]] = [
    {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "sector": "Technology"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Communication Services"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer Discretionary"},
    {"symbol": "META", "name": "Meta Platforms Inc.", "sector": "Communication Services"},
    {"symbol": "TSLA", "name": "Tesla Inc.", "sector": "Consumer Discretionary"},
    {"symbol": "BRK.B", "name": "Berkshire Hathaway", "sector": "Financials"},
    {"symbol": "UNH", "name": "UnitedHealth Group", "sector": "Healthcare"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "sector": "Healthcare"},
]


def map_sector_name(raw: str) -> str:
    """Standardize GICS sector names."""
    return _SECTOR_MAP.get(raw, raw)


def fetch_us500_html(timeout: int = 10) -> str:
    """Fetch HTML from us500.com S&P 500 page."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(_US500_URL, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_us500_html(html: str) -> List[Dict[str, str]]:
    """Parse us500.com HTML table to extract symbols, names, and sectors."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        raise ValueError("No table found in us500.com HTML")

    tbody = table.find("tbody")
    if not tbody:
        raise ValueError("No tbody found in table")

    symbols = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        ticker = cells[1].get_text(strip=True)
        company = cells[2].get_text(strip=True)
        sector = cells[4].get_text(strip=True)

        if ticker and company and sector:
            symbols.append({
                "symbol": ticker,
                "name": company,
                "sector": map_sector_name(sector),
            })

    if len(symbols) < 400:
        raise ValueError(f"Unexpectedly few symbols parsed: {len(symbols)}")

    return symbols


def fetch_wikipedia_html(timeout: int = 10) -> str:
    """Fetch HTML from Wikipedia S&P 500 page."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(_WIKIPEDIA_URL, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_wikipedia_html(html: str) -> List[Dict[str, str]]:
    """Parse Wikipedia HTML table to extract symbols, names, and sectors."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "wikitable"})
    if not table:
        raise ValueError("No wikitable found in Wikipedia HTML")

    symbols = []
    rows = table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        ticker = cells[0].get_text(strip=True)
        company = cells[1].get_text(strip=True)
        sector = cells[2].get_text(strip=True)

        if ticker and company and sector:
            symbols.append({
                "symbol": ticker,
                "name": company,
                "sector": map_sector_name(sector),
            })

    if len(symbols) < 400:
        raise ValueError(f"Unexpectedly few symbols parsed: {len(symbols)}")

    return symbols


def get_sp500_symbols(force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    Get S&P 500 symbols from us500.com (primary) or Wikipedia (fallback).
    Results are cached in memory for 7 days.
    """
    now = datetime.now(timezone.utc)
    cached_at = _CACHE.get("fetched_at")

    if (
        not force_refresh
        and _CACHE["data"] is not None
        and cached_at is not None
        and (now - cached_at) < timedelta(days=_CACHE_TTL_DAYS)
    ):
        return _CACHE["data"]

    try:
        html = fetch_us500_html()
        symbols = parse_us500_html(html)
        _CACHE["data"] = symbols
        _CACHE["fetched_at"] = now
        logger.info(f"sp500_symbols_loaded_from_us500 count={len(symbols)}")
        return symbols
    except Exception as us500_exc:
        logger.warning(f"sp500_us500_fetch_failed_trying_wikipedia error={str(us500_exc)}")

        try:
            html = fetch_wikipedia_html()
            symbols = parse_wikipedia_html(html)
            _CACHE["data"] = symbols
            _CACHE["fetched_at"] = now
            logger.info(f"sp500_symbols_loaded_from_wikipedia count={len(symbols)}")
            return symbols
        except Exception as wiki_exc:
            logger.error(
                f"sp500_all_sources_failed_using_hardcoded_fallback "
                f"us500_error={str(us500_exc)} wikipedia_error={str(wiki_exc)}"
            )
            return _HARDCODED_FALLBACK

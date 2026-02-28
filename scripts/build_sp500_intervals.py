"""Convert S&P 500 historical components CSV to compact interval JSON.

Usage:
    python scripts/build_sp500_intervals.py --input "path/to/csv" --output data/sp500_intervals.json
"""

import argparse
import csv
import json
import os
import sys

# Add project root to path so we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sp500_history import convert_snapshots_to_intervals


def parse_csv(filepath: str):
    """Parse the S&P 500 historical components CSV.

    Expected format: date,"TICKER1,TICKER2,...,TICKER500"
    Returns sorted list of (date_str, set_of_tickers) pairs.
    """
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header row

        for row in reader:
            if len(row) < 2:
                continue
            date_str = row[0].strip()
            tickers_str = row[1].strip().strip('"')
            tickers = set(t.strip() for t in tickers_str.split(",") if t.strip())
            rows.append((date_str, tickers))

    rows.sort(key=lambda x: x[0])
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Convert S&P 500 historical CSV to interval JSON"
    )
    parser.add_argument("--input", required=True, help="Path to CSV file")
    parser.add_argument(
        "--output",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "sp500_intervals.json",
        ),
        help="Output JSON path (default: data/sp500_intervals.json)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    print(f"Reading CSV: {args.input}")
    rows = parse_csv(args.input)
    print(f"Parsed {len(rows)} snapshots")

    if not rows:
        print("Error: No data rows found in CSV")
        sys.exit(1)

    print(f"Date range: {rows[0][0]} to {rows[-1][0]}")
    print(f"Tickers in first snapshot: {len(rows[0][1])}")
    print(f"Tickers in last snapshot: {len(rows[-1][1])}")

    print("Converting to intervals...")
    result = convert_snapshots_to_intervals(rows)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    with open(args.output, "w") as f:
        json.dump(result, f, indent=None, separators=(",", ":"))

    file_size = os.path.getsize(args.output)
    meta = result["meta"]
    print(f"Written: {args.output} ({file_size / 1024:.1f} KB)")
    print(f"Total unique symbols: {meta['total_symbols']}")
    print(f"Total changes detected: {meta['total_changes']}")
    print(f"Last updated: {meta['last_updated']}")


if __name__ == "__main__":
    main()

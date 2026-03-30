#!/usr/bin/env python
"""
scripts/backfill_ohlcv.py — Backfill OHLCV history for a ticker list into DuckDB.

Usage:
    python scripts/backfill_ohlcv.py --tickers HPG,VCB,FPT --days 400
"""
from __future__ import annotations
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OHLCV into DuckDB cache")
    parser.add_argument("--tickers", required=True, help="Comma-separated ticker list")
    parser.add_argument("--days", type=int, default=400, help="History depth in trading days")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    print(f"Backfilling {len(tickers)} tickers ({args.days}d)…")

    # TODO: wire to tradingos.data.fetcher + tradingos.data.cache
    for ticker in tickers:
        print(f"  {ticker} — not yet implemented")


if __name__ == "__main__":
    main()

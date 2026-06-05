#!/usr/bin/env python
"""
scripts/backfill_ohlcv.py — Backfill OHLCV history for a ticker list into DuckDB.

Usage:
    python scripts/backfill_ohlcv.py --tickers HPG,VCB,FPT --days 400
    python scripts/backfill_ohlcv.py --file tickers.txt --days 400 --workers 4
"""
from __future__ import annotations
import argparse
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _backfill_one(ticker: str, days: int) -> tuple[str, int, str]:
    """Fetch and cache OHLCV for a single ticker. Returns (ticker, rows, status)."""
    from tradingos.data.fetcher import fetch_ohlcv
    from tradingos.data.cache import cache
    try:
        df = fetch_ohlcv(ticker, days=days)
        if df.empty:
            return ticker, 0, "EMPTY"
        cache.put_ohlcv(ticker, df)
        return ticker, len(df), "OK"
    except Exception as e:
        return ticker, 0, f"ERROR: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OHLCV into DuckDB cache")
    parser.add_argument("--tickers", help="Comma-separated ticker list")
    parser.add_argument("--file", help="Text file with one ticker per line")
    parser.add_argument("--days", type=int, default=400, help="History depth in trading days (default: 400)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel fetch workers (default: 4)")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay seconds between batches (default: 0.2)")
    args = parser.parse_args()

    tickers: list[str] = []
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if args.file:
        with open(args.file) as f:
            tickers += [line.strip().upper() for line in f if line.strip() and not line.startswith("#")]
    tickers = sorted(set(tickers))

    if not tickers:
        print("No tickers provided. Use --tickers or --file.")
        sys.exit(1)

    print(f"Backfilling {len(tickers)} tickers x {args.days}d | workers={args.workers}")
    ok = skipped = errors = total_rows = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_backfill_one, t, args.days): t for t in tickers}
        for i, future in enumerate(as_completed(futures), 1):
            ticker, rows, status = future.result()
            total_rows += rows
            if status == "OK":
                ok += 1
                print(f"  [{i:4d}/{len(tickers)}] {ticker:<8} OK -- {rows} rows")
            elif status == "EMPTY":
                skipped += 1
                print(f"  [{i:4d}/{len(tickers)}] {ticker:<8} EMPTY")
            else:
                errors += 1
                print(f"  [{i:4d}/{len(tickers)}] {ticker:<8} {status}")
            if i % args.workers == 0:
                time.sleep(args.delay)

    print(f"\nDone: {ok} OK | {skipped} empty | {errors} errors | {total_rows:,} rows cached")


if __name__ == "__main__":
    main()

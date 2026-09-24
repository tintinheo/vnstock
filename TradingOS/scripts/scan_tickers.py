"""
CLI Scanner — run a batch scan from the terminal.

Usage examples
--------------
# Scan a txt/csv file of tickers:
    python scripts/scan_tickers.py --file d:/portfolio/vnstock/data/Stickers_Full.txt

# Scan specific tickers inline:
    python scripts/scan_tickers.py --tickers VCB,HPG,SSI,AAM

# Scan full HOSE + HNX universe (default if no --file / --tickers):
    python scripts/scan_tickers.py

# Optional filters:
    python scripts/scan_tickers.py --file Stickers_Full.txt --action BUY WATCH STRONG_BUY --min-mfpm 40 --workers 6

# Save results to CSV:
    python scripts/scan_tickers.py --file Stickers_Full.txt --output results.csv
"""
from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path

# Ensure src/ is on path when run as a script
_src = Path(__file__).resolve().parents[1] / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import pandas as pd
from tradingos.engines.scanner_service import ScannerService
from tradingos.data.schemas import ScanRequest

_ACTION_ORDER = {
    "STRONG_BUY": 0, "BUY": 1, "WATCH": 2,
    "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5,
}
_ACTION_LABEL = {
    "STRONG_BUY": "[STRONG BUY]",
    "BUY":        "[BUY      ]",
    "WATCH":      "[WATCH    ]",
    "NO_ACTION":  "[--       ]",
    "EXIT":       "[EXIT     ]",
    "FORCED_EXIT":"[FORCE-OUT]",
}


def _parse_tickers_file(path: str) -> list[str]:
    """Read a .txt or .csv file — one ticker per line OR comma-separated."""
    text = Path(path).read_text(encoding="utf-8").strip()
    # Normalise: replace commas/semicolons/tabs → newlines, split
    for sep in (",", ";", "\t"):
        text = text.replace(sep, "\n")
    tickers = [t.strip().upper() for t in text.splitlines() if t.strip()]
    return list(dict.fromkeys(tickers))  # deduplicate preserving order


def _print_results(items, total_scanned: int, elapsed: float) -> None:
    sep = "-" * 72
    print(f"\n{sep}")
    print(f"  SCAN RESULTS  |  {len(items)} signals  /  {total_scanned} scanned  |  {elapsed:.1f}s")
    print(sep)
    if not items:
        print("  (no tickers matched the filter criteria)")
        print(sep)
        return

    header = f"  {'Ticker':<7} {'Action':<14} {'Conf':<8} {'MFPM':>5} {'SMS':>5} {'Mode':<9} {'Close':>10} {'Entry':>10} {'SL':>10} {'TP1':>10} {'R:R':>5}  Pattern"
    print(header)
    print(sep)
    for item in items:
        label = _ACTION_LABEL.get(item.action, f"[{item.action:<9}]")
        close  = f"{item.close:>10,.0f}" if item.close  else f"{'—':>10}"
        entry  = f"{item.entry:>10,.0f}" if item.entry  else f"{'—':>10}"
        sl     = f"{item.sl:>10,.0f}"    if item.sl     else f"{'—':>10}"
        tp1    = f"{item.tp1:>10,.0f}"   if item.tp1    else f"{'—':>10}"
        rr     = f"{item.rr:>5.1f}"      if item.rr     else f"{'—':>5}"
        pattern = item.best_pattern or "NONE"
        conf    = item.confidence or "—"
        print(
            f"  {item.ticker:<7} {label:<14} {conf:<8} {item.mfpm_score:>5} "
            f"{item.sms_raw:>5} {item.signal_mode:<9} {close} {entry} {sl} {tp1} {rr}  {pattern}"
        )
    print(sep)

    # Summary breakdown
    from collections import Counter
    breakdown = Counter(i.action for i in items)
    parts = [f"{_ACTION_LABEL.get(a,'?')} x{n}" for a, n in sorted(breakdown.items(), key=lambda x: _ACTION_ORDER.get(x[0], 9))]
    print("  " + "   ".join(parts))
    print(sep + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradingOS CLI Scanner — scan a list of VN tickers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", "-f", metavar="PATH",
                     help="Path to .txt or .csv file containing tickers")
    src.add_argument("--tickers", "-t", metavar="CSV",
                     help="Comma-separated tickers inline, e.g. VCB,HPG,SSI")

    parser.add_argument("--action", "-a", nargs="+",
                        metavar="ACTION",
                        choices=["STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"],
                        help="Show only these action types (default: all)")
    parser.add_argument("--min-mfpm", type=int, default=0, metavar="N",
                        help="Minimum MFPM score to include (default: 0)")
    parser.add_argument("--min-sms", type=int, default=0, metavar="N",
                        help="Minimum SMS score to include (default: 0)")
    parser.add_argument("--workers", "-w", type=int, default=6, metavar="N",
                        help="Parallel worker threads (default: 6)")
    parser.add_argument("--output", "-o", metavar="CSV_PATH",
                        help="Save results to a CSV file")
    parser.add_argument("--limit", type=int, default=500, metavar="N",
                        help="Max results to return (default: 500)")
    parser.add_argument("--explain", action="store_true",
                        help="Print full NLP advisory for WATCH/BUY/STRONG_BUY results")

    args = parser.parse_args()

    # ── Resolve ticker list ───────────────────────────────────────────────────
    if args.file:
        tickers = _parse_tickers_file(args.file)
        print(f"Loaded {len(tickers)} tickers from {args.file}")
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        print(f"Scanning {len(tickers)} tickers from command line")
    else:
        # Fetch full listed universe from both exchanges
        _src = Path(__file__).resolve().parents[1] / "src"
        if str(_src) not in sys.path:
            sys.path.insert(0, str(_src))
        from tradingos.data.fetcher import fetch_universe
        hose = fetch_universe("HOSE")
        hnx  = fetch_universe("HNX")
        tickers = list(dict.fromkeys(hose + hnx))   # deduplicate, HOSE first
        print(f"Full universe: HOSE={len(hose)}, HNX={len(hnx)} → {len(tickers)} tickers total")

    # ── Run scan ──────────────────────────────────────────────────────────────
    request = ScanRequest(
        tickers=tickers,
        min_mfpm_score=args.min_mfpm,
        min_sms=args.min_sms,
        limit=args.limit,
    )

    import time
    t0 = time.monotonic()
    svc = ScannerService(max_workers=args.workers)
    result = svc.scan(request)
    elapsed = time.monotonic() - t0

    # ── Filter by action ─────────────────────────────────────────────────────
    items = result.results
    if args.action:
        items = [i for i in items if i.action in args.action]

    # ── Print ─────────────────────────────────────────────────────────────────
    _print_results(items, result.tickers_scanned, elapsed)

    # ── NLP explanations ──────────────────────────────────────────────────────
    if args.explain:
        explain_actions = {"STRONG_BUY", "BUY", "WATCH"}
        explain_items = [i for i in items if i.action in explain_actions]
        if explain_items:
            from tradingos.engines.profiler_service import ProfilerService
            from tradingos.data.schemas import ProfilerRequest
            prof_svc = ProfilerService()
            print("\n" + "=" * 72)
            print("  NLP ADVISORY EXPLANATIONS")
            print("=" * 72)
            for item in explain_items:
                try:
                    profile = prof_svc.run(ProfilerRequest(ticker=item.ticker))
                    print(f"\n{'─' * 72}")
                    print(profile.advisory_text)
                except Exception as exc:
                    print(f"  {item.ticker}: could not generate advisory — {exc}")
            print("\n" + "=" * 72 + "\n")
        else:
            print("\n(no WATCH/BUY/STRONG_BUY results to explain)\n")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    if args.output and items:
        rows = []
        for item in items:
            rows.append({
                "ticker": item.ticker,
                "action": item.action,
                "confidence": item.confidence,
                "mfpm_score": item.mfpm_score,
                "mode_w_score": item.mode_w_score,
                "sms_raw": item.sms_raw,
                "sms_label": item.sms_label,
                "signal_mode": item.signal_mode,
                "close": item.close,
                "entry": item.entry,
                "sl": item.sl,
                "tp1": item.tp1,
                "rr": item.rr,
                "amf_decision": item.amf_decision,
                "best_pattern": item.best_pattern,
                "hmm_state": item.hmm_state,
                "stealth_accum": item.stealth_accum,
            })
        df = pd.DataFrame(rows)
        df.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"Saved {len(rows)} rows -> {args.output}")


if __name__ == "__main__":
    main()

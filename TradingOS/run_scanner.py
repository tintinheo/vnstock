"""
CLI scanner — run TradingOS scanner from terminal with a ticker file.

Usage
-----
  # from the TradingOS/ directory:
  python run_scanner.py tickers.txt
  python run_scanner.py tickers.txt --min-mfpm 40 --min-sms 30
  python run_scanner.py tickers.txt --action BUY WATCH --workers 12
  python run_scanner.py tickers.txt --output results.csv
  python run_scanner.py tickers.txt --json                 # machine-readable JSON

  # or pipe a comma-separated list directly (no file):
  python run_scanner.py --tickers VCB,HPG,SSI,VNM
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so emoji survive
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Ensure src/ is on path ────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── ANSI colours (degrade gracefully on Windows without VT mode) ──────────────
_COLOURS = {
    "STRONG_BUY": "\033[92m",   # bright green
    "BUY":        "\033[36m",   # cyan
    "WATCH":      "\033[93m",   # yellow
    "NO_ACTION":  "\033[90m",   # dark grey
    "EXIT":       "\033[91m",   # red
    "FORCED_EXIT":"\033[31m",   # dark red
    "RESET":      "\033[0m",
    "BOLD":       "\033[1m",
    "DIM":        "\033[2m",
    "HEADER":     "\033[95m",   # magenta
}

def _c(key: str, text: str, use_colour: bool) -> str:
    if not use_colour:
        return text
    return f"{_COLOURS.get(key, '')}{text}{_COLOURS['RESET']}"


def _enable_vt_mode() -> bool:
    """Enable ANSI escape codes on Windows terminal."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
        return True
    except Exception:
        return False


def _load_tickers_from_file(path: str) -> list[str]:
    content = Path(path).read_text(encoding="utf-8")
    # Accept: one-per-line, comma-separated, or mixed
    parts = content.replace("\n", ",").replace(";", ",").replace(" ", ",").split(",")
    tickers = [t.strip().upper() for t in parts if t.strip() and t.strip().isalpha()]
    return list(dict.fromkeys(tickers))  # dedupe, preserve order


def _action_icon(action: str) -> str:
    return {
        "STRONG_BUY": "[++]",
        "BUY":        "[+] ",
        "WATCH":      "[?] ",
        "NO_ACTION":  "[-] ",
        "EXIT":       "[X] ",
        "FORCED_EXIT":"[!!]",
    }.get(action, "[.] ")


def _print_header(use_colour: bool) -> None:
    line = "-" * 110
    print(_c("HEADER", line, use_colour))
    print(_c("BOLD", f"{'Ma':<6}  {'Action':<14} {'Conf':<7} {'MFPM':>4} {'SMS':>4} {'Mode':<9} "
                     f"{'Gia':>10} {'Vao':>10} {'SL':>10} {'TP1':>10} {'R:R':>5} {'HMM':<13} "
                     f"{'Pattern':<16} {'AMF':<5}", use_colour))
    print(_c("HEADER", line, use_colour))


def _fmt(val: float, zero: str = "—") -> str:
    """Format a float; show zero_str when value is 0."""
    if val == 0.0:
        return zero
    return f"{val:,.0f}"


def _print_row(item, use_colour: bool) -> None:
    icon  = _action_icon(item.action)
    rr    = f"1:{item.rr:.1f}" if item.rr else "—"
    line  = (
        f"{item.ticker:<6}  "
        f"{icon}{item.action:<11} "
        f"{item.confidence:<7} "
        f"{item.mfpm_score:>4} "
        f"{item.sms_raw:>4} "
        f"{item.signal_mode:<9} "
        f"{_fmt(item.close):>10} "
        f"{_fmt(item.entry):>10} "
        f"{_fmt(item.sl):>10} "
        f"{_fmt(item.tp1):>10} "
        f"{rr:>5} "
        f"{item.hmm_state:<13} "
        f"{item.best_pattern:<16} "
        f"{item.amf_decision:<5}"
    )
    print(_c(item.action, line, use_colour))


def _print_summary(items: list, elapsed: float, scanned: int, use_colour: bool) -> None:
    from collections import Counter
    breakdown = Counter(i.action for i in items)
    line = "-" * 110
    print(_c("HEADER", line, use_colour))
    parts = []
    for action in ["STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"]:
        if breakdown[action]:
            parts.append(_c(action, f"{_action_icon(action)} {action}: {breakdown[action]}", use_colour))
    print("  ".join(parts))
    print(_c("DIM", f"\n{elapsed:.1f}s  |  Queted {scanned} ma  ->  {len(items)} ket qua", use_colour))


def _export_csv(items: list, path: str) -> None:
    fields = [
        "ticker", "action", "confidence", "mfpm_score", "mode_w_score", "sms_raw",
        "sms_label", "signal_mode", "close", "entry", "sl", "tp1", "rr",
        "amf_decision", "best_pattern", "hmm_state", "stealth_accum",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({k: getattr(item, k, "") for k in fields})


def _export_json(items: list, path: str | None) -> None:
    rows = []
    for item in items:
        rows.append({
            "ticker": item.ticker, "action": item.action,
            "confidence": item.confidence, "mfpm_score": item.mfpm_score,
            "sms_raw": item.sms_raw, "signal_mode": item.signal_mode,
            "close": item.close, "entry": item.entry,
            "sl": item.sl, "tp1": item.tp1, "rr": item.rr,
            "amf_decision": item.amf_decision, "best_pattern": item.best_pattern,
            "hmm_state": item.hmm_state,
        })
    payload = json.dumps(rows, indent=2, ensure_ascii=False)
    if path:
        Path(path).write_text(payload, encoding="utf-8")
        print(f"Saved -> {path}", file=sys.stderr)
    else:
        print(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_scanner.py",
        description="TradingOS CLI Scanner — quét danh sách mã từ file .txt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "ticker_file",
        nargs="?",
        help="Path to .txt file (CSV or one-per-line tickers)",
    )
    src_group.add_argument(
        "--tickers", "-t",
        help="Comma-separated tickers directly, e.g. VCB,HPG,SSI",
    )

    parser.add_argument("--min-mfpm",   type=int,   default=0,   help="Minimum MFPM score (default 0)")
    parser.add_argument("--min-sms",    type=int,   default=0,   help="Minimum SMS score (default 0)")
    parser.add_argument("--workers",    type=int,   default=8,   help="Thread workers (default 8)")
    parser.add_argument(
        "--action", nargs="+",
        choices=["STRONG_BUY", "BUY", "WATCH", "NO_ACTION", "EXIT", "FORCED_EXIT"],
        help="Filter by action(s), e.g. --action BUY WATCH",
    )
    parser.add_argument("--output",  "-o", help="Save results to CSV file")
    parser.add_argument("--json",    "-j", action="store_true", help="Output as JSON (stdout)")
    parser.add_argument("--json-out",       help="Save results to JSON file")
    parser.add_argument("--no-colour",      action="store_true", help="Disable ANSI colours")
    parser.add_argument("--quiet", "-q",    action="store_true", help="Suppress progress lines")

    args = parser.parse_args()

    use_colour = not args.no_colour and _enable_vt_mode()

    # ── Load tickers ──────────────────────────────────────────────────────────
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        if not Path(args.ticker_file).exists():
            print(f"ERROR: file not found: {args.ticker_file}", file=sys.stderr)
            sys.exit(1)
        tickers = _load_tickers_from_file(args.ticker_file)

    if not tickers:
        print("ERROR: no tickers found.", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(_c("BOLD", f"\nTradingOS Scanner  --  {len(tickers)} tickers", use_colour))
        print(_c("DIM",  f"    min_mfpm={args.min_mfpm}  min_sms={args.min_sms}  workers={args.workers}\n", use_colour))

    # ── Import engine (deferred so --help is instant) ─────────────────────────
    try:
        from tradingos.engines.scanner_service import ScannerService
        from tradingos.data.schemas import ScanRequest
    except ModuleNotFoundError as e:
        print(f"ERROR: {e}\nRun from TradingOS/ directory or set PYTHONPATH=src", file=sys.stderr)
        sys.exit(1)

    request = ScanRequest(
        tickers=tickers,
        limit=len(tickers),
        min_mfpm_score=args.min_mfpm,
        min_sms=args.min_sms,
    )
    svc = ScannerService(max_workers=args.workers)

    t0 = time.perf_counter()
    result = svc.scan(request)
    elapsed = time.perf_counter() - t0

    items = result.results

    # Apply action filter
    if args.action:
        items = [i for i in items if i.action in args.action]

    # ── Output ────────────────────────────────────────────────────────────────
    if args.json or args.json_out:
        _export_json(items, args.json_out)
        if not args.json:
            _print_summary(items, elapsed, result.tickers_scanned, use_colour)
    else:
        _print_header(use_colour)
        for item in items:
            _print_row(item, use_colour)
        _print_summary(items, elapsed, result.tickers_scanned, use_colour)

    if args.output:
        _export_csv(items, args.output)
        print(f"Saved -> {args.output}")

    # Exit code: 0 if any actionable signals, 1 if all NO_ACTION
    has_signal = any(i.action not in ("NO_ACTION",) for i in items)
    sys.exit(0 if has_signal else 1)


if __name__ == "__main__":
    main()

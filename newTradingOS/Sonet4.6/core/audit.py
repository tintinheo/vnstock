"""
core/audit.py — NewTradingOS v14.0
Append-only audit log for all business-critical events.

Each event is a JSON line in data/audit.jsonl:
{
    "ts":        "2026-05-29T14:30:00.123",   # ISO datetime (local)
    "action":    "OPEN_POSITION",              # see ACTION_* constants
    "ticker":    "VCB",
    "timeframe": "1W",
    "detail":    {...},                        # action-specific payload
    "result":    "ok" | "fail",
    "user":      "captain"                     # placeholder
}

Actions:
  OPEN_POSITION   — position opened
  CLOSE_POSITION  — position closed (includes P&L)
  LOAD_DATA       — batch ticker data loaded
  UPDATE_MACRO    — macro / regime refreshed
  SCAN_SIGNAL     — scanner emitted a signal (optional, kept light)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger("TradingOS.audit")

AUDIT_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "audit.jsonl"
)

# ── Action constants ───────────────────────────────────────────
ACTION_OPEN    = "OPEN_POSITION"
ACTION_CLOSE   = "CLOSE_POSITION"
ACTION_LOAD    = "LOAD_DATA"
ACTION_MACRO   = "UPDATE_MACRO"
ACTION_SCAN    = "SCAN_SIGNAL"

# ── Write ──────────────────────────────────────────────────────
def log_event(
    action:    str,
    detail:    dict[str, Any] | None = None,
    ticker:    str | None = None,
    timeframe: str | None = None,
    result:    str = "ok",
) -> None:
    """Append one event to the audit log (non-blocking; silently swallows IO errors)."""
    event: dict[str, Any] = {
        "ts":        datetime.now().isoformat(timespec="milliseconds"),
        "action":    action,
        "ticker":    ticker or "",
        "timeframe": timeframe or "",
        "detail":    detail or {},
        "result":    result,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 — never crash the app for logging
        logger.warning("Audit write failed: %s", exc)


# ── Read & filter ──────────────────────────────────────────────
def load_events(path: str = AUDIT_FILE) -> list[dict]:
    """Return all events as a list of dicts, newest first."""
    if not os.path.exists(path):
        return []
    events: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    events.reverse()          # newest first
    return events


def filter_events(
    events:    list[dict],
    actions:   list[str] | None = None,
    tickers:   list[str] | None = None,
    timeframe: str | None = None,
    result:    str | None = None,
    date_from: str | None = None,   # ISO date "YYYY-MM-DD"
    date_to:   str | None = None,
) -> list[dict]:
    """Apply business filters to a list of events."""
    out = events
    if actions:
        out = [e for e in out if e.get("action") in actions]
    if tickers:
        tickers_upper = [t.upper() for t in tickers]
        out = [e for e in out if e.get("ticker", "").upper() in tickers_upper]
    if timeframe:
        out = [e for e in out if e.get("timeframe") == timeframe]
    if result:
        out = [e for e in out if e.get("result") == result]
    if date_from:
        out = [e for e in out if e.get("ts", "") >= date_from]
    if date_to:
        # include full day_to
        out = [e for e in out if e.get("ts", "") <= date_to + "T23:59:59"]
    return out

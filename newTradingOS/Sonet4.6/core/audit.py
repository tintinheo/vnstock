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
    SCAN_SIGNAL     — scanner run summary or per-ticker scan result
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


def get_event_detail_kind(event: dict[str, Any]) -> str:
    """Return the event detail subtype, inferring legacy scan events when needed."""
    detail = event.get("detail") or {}
    kind = str(detail.get("kind", "") or "")
    if kind:
        return kind
    if event.get("action") == ACTION_SCAN:
        return "result" if event.get("ticker") else "summary"
    return ""


def _normalise_event(entry: dict[str, Any], default_ts: str) -> dict[str, Any]:
    return {
        "ts": entry.get("ts") or default_ts,
        "action": entry.get("action", ""),
        "ticker": entry.get("ticker") or "",
        "timeframe": entry.get("timeframe") or "",
        "detail": entry.get("detail") or {},
        "result": entry.get("result") or "ok",
    }


def log_events(entries: list[dict[str, Any]]) -> None:
    """Append multiple events to the audit log in one file-open operation."""
    if not entries:
        return

    default_ts = datetime.now().isoformat(timespec="milliseconds")
    lines = [
        json.dumps(_normalise_event(entry, default_ts), ensure_ascii=False)
        for entry in entries
    ]

    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except Exception as exc:  # noqa: BLE001 — never crash the app for logging
        logger.warning("Audit write failed: %s", exc)

# ── Write ──────────────────────────────────────────────────────
def log_event(
    action:    str,
    detail:    dict[str, Any] | None = None,
    ticker:    str | None = None,
    timeframe: str | None = None,
    result:    str = "ok",
) -> None:
    """Append one event to the audit log (non-blocking; silently swallows IO errors)."""
    log_events([
        {
            "action": action,
            "ticker": ticker,
            "timeframe": timeframe,
            "detail": detail,
            "result": result,
        }
    ])


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
    detail_kinds: list[str] | None = None,
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
    if detail_kinds:
        expected_kinds = {str(kind).lower() for kind in detail_kinds if kind}
        out = [
            e for e in out
            if get_event_detail_kind(e).lower() in expected_kinds
        ]
    if date_from:
        out = [e for e in out if e.get("ts", "") >= date_from]
    if date_to:
        # include full day_to
        out = [e for e in out if e.get("ts", "") <= date_to + "T23:59:59"]
    return out

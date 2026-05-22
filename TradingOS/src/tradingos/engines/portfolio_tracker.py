"""Portfolio Tracker service — open position lifecycle + T+2.5 management."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pandas as pd

from tradingos.data.cache import cache
from tradingos.utils.dates import trading_day_offset, is_trading_day
from tradingos.core.t25_engine import t25_exit_check


class PortfolioTracker:
    """
    Manages the paper trading ledger with T+2.5 awareness.

    All writes go through cache.log_paper_trade / cache.close_paper_trade so
    the trade_ledger DuckDB table remains the single source of truth.
    """

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_open_positions(self) -> pd.DataFrame:
        """Return all OPEN positions from the ledger."""
        return cache.get_trade_ledger(only_open=True)

    def get_all_trades(self) -> pd.DataFrame:
        return cache.get_trade_ledger()

    # ── T+2.5 Exit Checks ────────────────────────────────────────────────────

    def get_positions_due_today(self) -> list[dict]:
        """
        Return open positions whose T+2 exit date (ATC) is today or overdue.
        """
        today = date.today()
        df = self.get_open_positions()
        if df.empty:
            return []

        due = []
        for _, row in df.iterrows():
            entry_d = _to_date(row.get("entry_date"))
            if entry_d is None:
                continue
            t2 = trading_day_offset(entry_d, 2)
            if today >= t2:
                due.append(row.to_dict())
        return due

    def get_exit_advisories(self) -> list[dict]:
        """
        Run t25_exit_check for every open position and return advisory list.
        """
        advisories = []
        df = self.get_open_positions()
        if df.empty:
            return advisories

        today = date.today()
        for _, row in df.iterrows():
            entry_d = _to_date(row.get("entry_date"))
            if entry_d is None:
                continue
            t2 = trading_day_offset(entry_d, 2)
            hold_days = max(0, (today - entry_d).days)

            entry_price = float(row.get("entry_price") or 0)
            initial_sl  = float(row.get("initial_sl") or 0)
            # Use entry_price as proxy for current if no RT available
            current_price = entry_price

            if entry_price <= 0:
                continue

            tp1 = entry_price * 1.06   # fallback estimate if not stored
            tp2 = entry_price * 1.12

            advisory = t25_exit_check(
                ticker=str(row.get("ticker", "")),
                entry_price=entry_price,
                current_price=current_price,
                entry_date=entry_d,  # type: ignore[arg-type]
                sl=initial_sl if initial_sl > 0 else entry_price * 0.94,
                tp1=tp1,
                tp2=tp2,
                hold_days=hold_days,
            )
            advisories.append({
                "ticker":        row.get("ticker"),
                "entry_date":    entry_d,
                "t2_date":       t2,
                "hold_days":     hold_days,
                "entry_price":   entry_price,
                "advisory":      advisory,
                "signal_mode":   row.get("signal_mode", ""),
                "mfpm_score":    int(row.get("mfpm_score") or 0),
            })
        return advisories

    # ── Write Operations ──────────────────────────────────────────────────────

    def add_position(
        self,
        ticker: str,
        entry_price: float,
        initial_sl: float,
        signal_mode: str = "",
        mfpm_score: int = 0,
        mc_prob: float = 0.0,
        entry_date: date | None = None,
        tp1: float = 0.0,
        tp2: float = 0.0,
        notes: str = "",
    ) -> str:
        """Add a new open position. Returns the trade_id."""
        trade_id = str(uuid.uuid4())
        cache.log_paper_trade({
            "trade_id":    trade_id,
            "ticker":      ticker,
            "entry_date":  entry_date or date.today(),
            "entry_price": entry_price,
            "initial_sl":  initial_sl,
            "signal_mode": signal_mode,
            "mfpm_score":  mfpm_score,
            "mc_prob":     mc_prob,
        })
        return trade_id

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_date: date | None = None,
    ) -> bool:
        """Close the most recent open position for ticker. Returns True if found."""
        rows_affected = cache.close_paper_trade(ticker, exit_price, exit_date)
        return rows_affected > 0

    # ── Summary Stats ─────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Return a dict of high-level portfolio stats."""
        df = self.get_all_trades()
        if df.empty:
            return {"open": 0, "closed": 0, "win_rate": 0.0, "avg_pnl": 0.0}

        open_df   = df[df["status"] == "OPEN"]
        closed_df = df[df["status"] == "CLOSED"].copy()

        win_rate = avg_pnl = 0.0
        if not closed_df.empty and "pnl_pct" in closed_df.columns:
            pnl = pd.to_numeric(closed_df["pnl_pct"], errors="coerce").dropna()
            win_rate = float((pnl > 0).mean()) if len(pnl) else 0.0
            avg_pnl  = float(pnl.mean()) if len(pnl) else 0.0

        return {
            "open":     len(open_df),
            "closed":   len(closed_df),
            "win_rate": win_rate,
            "avg_pnl":  avg_pnl,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        from datetime import datetime
        if hasattr(value, "date"):
            return value.date()
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


# Module-level singleton
portfolio_tracker = PortfolioTracker()

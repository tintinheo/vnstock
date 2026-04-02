"""T+2.5 Exit Engine — ATC window advisory (SRS §3.5, Module 5).

[H1 SRS CONSTRAINT] This module ONLY generates advisory recommendations.
It does NOT place orders.  Exit timing: 14:43–14:45 ATC session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

import numpy as np
import pandas as pd

from ..utils.config import cfg
from ..utils.dates import vn_now, vn_is_atc_time


@dataclass
class T25ExitAdvisory:
    ticker: str
    action: str              # HOLD / SELL_FULL_ATC / SELL_PARTIAL_ATC / EXTEND
    urgency: str             # HIGH / MEDIUM / LOW
    reason: str
    exit_window: str         # e.g. "ATC 14:43"
    exit_pct: float          # fraction to exit (0.0–1.0)
    remark: str = ""
    ts: datetime = field(default_factory=datetime.now)


def _is_atc_time() -> bool:
    return vn_is_atc_time()


def _session_phase() -> str:
    now = vn_now().time()
    if now < time(9, 15):
        return "PRE_OPEN"
    elif now < time(9, 30):
        return "ATO"
    elif now < time(14, 30):
        return "CONTINUOUS"
    elif now < time(14, 43):
        return "NEAR_CLOSE"
    elif now <= time(14, 45):
        return "ATC"
    else:
        return "CLOSED"


def t25_exit_check(
    ticker: str,
    entry_price: float,
    current_price: float,
    entry_date: datetime,
    sl: float,
    tp1: float,
    tp2: float,
    rsi_now: float = 50.0,
    volume_today: float = 0.0,
    avg_volume: float = 1.0,
    distribution_warning: str = "NONE",
    hold_days: int = 0,
) -> T25ExitAdvisory:
    """
    Evaluate T+2.5 exit decision.

    Decision tree (SRS §3.5):
    1. FORCED_EXIT conditions → SELL_FULL_ATC HIGH urgency
    2. SL breached → SELL_FULL_ATC HIGH
    3. TP1 hit & T>=3d → SELL_PARTIAL_ATC (40%)
    4. TP2 hit → SELL_FULL_ATC MEDIUM
    5. Weak hold → EXTEND LOW
    6. Default → HOLD
    """
    pnl_pct = (current_price - entry_price) / max(entry_price, 1)
    vol_ratio = volume_today / max(avg_volume, 1)
    phase = _session_phase()

    # Exit window preference: ATC for large sells
    exit_window = "ATC 14:43" if _is_atc_time() or phase in ("NEAR_CLOSE", "ATC") else "ATC today"

    # ── Forced exit ────────────────────────────────────────────────────────
    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="HIGH",
            reason=f"Distribution warning={distribution_warning}",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── SL breached ───────────────────────────────────────────────────────
    if current_price <= sl:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="HIGH",
            reason=f"Stop-loss breached: {current_price:.0f} ≤ {sl:.0f} (entry={entry_price:.0f})",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── TP2 hit ───────────────────────────────────────────────────────────
    if current_price >= tp2:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="MEDIUM",
            reason=f"TP2 hit: {current_price:.0f} ≥ {tp2:.0f} (+{pnl_pct:.1%})",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── TP1 hit + hold ≥ 3 days ──────────────────────────────────────────
    if current_price >= tp1 and hold_days >= 3:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_PARTIAL_ATC",
            urgency="MEDIUM",
            reason=f"TP1 hit ({current_price:.0f} ≥ {tp1:.0f}), hold_days={hold_days}. Lock 40% profit.",
            exit_window=exit_window,
            exit_pct=0.40,
            remark="Giữ 60% còn lại, trailing stop từ TP1.",
        )

    # ── Max hold exceeded ─────────────────────────────────────────────────
    max_hold = int(cfg.strategy("entry_exit", "max_hold_days", default=15))
    if hold_days >= max_hold:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="MEDIUM",
            reason=f"Max hold {max_hold}d exceeded. PnL={pnl_pct:+.1%}",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── Overbought + high vol surge (potential distribution) ──────────────
    if rsi_now > 80 and vol_ratio > 2.5:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_PARTIAL_ATC",
            urgency="MEDIUM",
            reason=f"RSI={rsi_now:.0f} overbought + vol_surge={vol_ratio:.1f}x",
            exit_window=exit_window,
            exit_pct=0.40,
            remark="Potential blow-off top. Lock partial gains.",
        )

    # ── Default: hold ─────────────────────────────────────────────────────
    return T25ExitAdvisory(
        ticker=ticker,
        action="HOLD",
        urgency="LOW",
        reason=f"PnL={pnl_pct:+.1%}, within range. No exit signal.",
        exit_window="—",
        exit_pct=0.0,
    )

"""Exit Engine — Progressive exit + trailing stop (SRS §3.6, Module 6)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..utils.config import cfg


@dataclass
class ExitStage:
    stage: int
    action: str               # HOLD / PARTIAL_EXIT / FULL_EXIT
    exit_pct: float           # fraction of remaining position
    reason: str
    trailing_stop: float      # updated trailing stop price


def compute_trailing_stop(
    entry: float,
    high_since_entry: float,
    atr: float,
    multiplier: float = 2.5,
) -> float:
    """
    Trailing stop = max(recent_high - ATR*mult, entry).
    Uses ATR multiplier from strategy.yaml.
    """
    mult = float(cfg.strategy("entry_exit", "trailing_stop_atr_mult", default=multiplier))
    ts = high_since_entry - atr * mult
    return max(ts, entry)  # never let trail drop below entry


def progressive_exit_plan(
    df: pd.DataFrame,
    entry: float,
    current_price: float,
    tp1: float,
    tp2: float,
    sl: float,
    hold_days: int,
    shares_held: int,
    atr: float | None = None,
) -> list[ExitStage]:
    """
    Progressive exit plan (SRS §3.6):
    - Stage 1 at TP1: exit 40%
    - Stage 2 at TP2: exit 40%
    - Stage 3 at trailing or max-hold: exit remaining 20%

    Returns a list of triggered ExitStages.
    """
    if atr is None and "ATR14" in df.columns:
        atr = float(df["ATR14"].iloc[-1])
    if atr is None or atr <= 0:
        atr = float(current_price * 0.02)

    high_since_entry = float(df["high"].iloc[-hold_days:].max()) if hold_days > 0 else current_price
    trail_stop = compute_trailing_stop(entry, high_since_entry, atr)

    stages: list[ExitStage] = []

    # ── Stage 1: TP1 ──────────────────────────────────────────────────────
    if current_price >= tp1 and hold_days >= 2:
        exit_shares_1 = int(shares_held * 0.40 // 100 * 100)
        stages.append(ExitStage(
            stage=1,
            action="PARTIAL_EXIT",
            exit_pct=0.40,
            reason=f"TP1={tp1:.0f} reached (+{(current_price/entry-1):.1%}). Chốt 40%.",
            trailing_stop=trail_stop,
        ))

    # ── Stage 2: TP2 ──────────────────────────────────────────────────────
    if current_price >= tp2:
        stages.append(ExitStage(
            stage=2,
            action="PARTIAL_EXIT",
            exit_pct=0.40,
            reason=f"TP2={tp2:.0f} reached. Chốt thêm 40%. Trailing stop còn lại.",
            trailing_stop=trail_stop,
        ))

    # ── Stage 3: Trailing / SL / max-hold ─────────────────────────────────
    max_hold = int(cfg.strategy("entry_exit", "max_hold_days", default=15))
    if current_price <= trail_stop and len(stages) >= 1:
        stages.append(ExitStage(
            stage=3,
            action="FULL_EXIT",
            exit_pct=1.0,
            reason=f"Trailing stop {trail_stop:.0f} hit. Thoát toàn bộ còn lại.",
            trailing_stop=trail_stop,
        ))
    elif current_price <= sl:
        stages.append(ExitStage(
            stage=3,
            action="FULL_EXIT",
            exit_pct=1.0,
            reason=f"Hard stop {sl:.0f} hit.",
            trailing_stop=sl,
        ))
    elif hold_days >= max_hold:
        stages.append(ExitStage(
            stage=3,
            action="FULL_EXIT",
            exit_pct=1.0,
            reason=f"Max hold {max_hold}d reached. Chốt hết.",
            trailing_stop=trail_stop,
        ))

    if not stages:
        stages.append(ExitStage(
            stage=0,
            action="HOLD",
            exit_pct=0.0,
            reason=f"Giữ vị thế. PnL={current_price/entry-1:+.1%}. Trail stop={trail_stop:.0f}.",
            trailing_stop=trail_stop,
        ))

    return stages

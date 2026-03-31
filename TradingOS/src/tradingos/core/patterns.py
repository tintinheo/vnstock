"""Pattern detection engine (SRS §3, Module 3).

Patterns: Wyckoff Spring, VCP, Cup-with-Handle, FVG, RSI Divergence, Order Block.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _find_swing_lows(close: pd.Series, window: int = 3) -> list[int]:
    """Return indices of local minima."""
    lows = []
    arr = close.values
    for i in range(window, len(arr) - window):
        if arr[i] == arr[i-window:i+window+1].min():
            lows.append(i)
    return lows


def _find_swing_highs(close: pd.Series, window: int = 3) -> list[int]:
    arr = close.values
    highs = []
    for i in range(window, len(arr) - window):
        if arr[i] == arr[i-window:i+window+1].max():
            highs.append(i)
    return highs


# ── Wyckoff Spring ────────────────────────────────────────────────────────────

def detect_spring(df: pd.DataFrame, lookback: int = 30) -> dict:
    """
    Wyckoff Spring: brief dip below support on low volume, followed by recovery.
    """
    if len(df) < lookback:
        return {"detected": False}

    recent = df.tail(lookback)
    support = recent["low"].quantile(0.10)

    last = recent.iloc[-1]
    prev = recent.iloc[-2] if len(recent) >= 2 else last
    avg_vol = recent["volume"].mean()

    # Spring: low pierced support, then closed above support on low volume
    pierced = last["low"] < support
    recovered = last["close"] > support
    low_vol = last["volume"] < avg_vol * 0.8

    if pierced and recovered and low_vol:
        est_target = float(recent["high"].max())
        return {
            "detected": True,
            "pattern": "WYCKOFF_SPRING",
            "support": round(float(support), 0),
            "est_target": est_target,
            "signal_text": f"Wyckoff Spring: dip dưới support {support:,.0f} rồi hồi",
        }
    return {"detected": False}


# ── VCP — Volatility Contraction Pattern ─────────────────────────────────────

def detect_vcp(df: pd.DataFrame, lookback: int = 60) -> dict:
    """
    VCP: series of progressively narrower price contractions on decreasing volume.
    3+ pivots with each contraction 50%-65% of previous.
    """
    if len(df) < lookback:
        return {"detected": False}

    recent = df.tail(lookback)
    swings_hi = _find_swing_highs(recent["close"], window=4)
    swings_lo = _find_swing_lows(recent["close"], window=4)

    if len(swings_hi) < 2 or len(swings_lo) < 2:
        return {"detected": False}

    hi_vals = [recent["close"].iloc[i] for i in swings_hi[-3:]]
    lo_vals = [recent["close"].iloc[i] for i in swings_lo[-3:]]

    # Check contractions are narrowing
    contractions = []
    for h, l in zip(hi_vals, lo_vals):
        contractions.append(h - l)

    if len(contractions) >= 2:
        narrowing = all(contractions[i] > contractions[i+1] for i in range(len(contractions)-1))
        latest_contraction = contractions[-1]
        pivot_contraction = contractions[0]
        ratio = latest_contraction / max(pivot_contraction, 1)

        if narrowing and 0.3 <= ratio <= 0.7:
            # Volume declining
            vol_mid = recent["volume"].iloc[len(recent)//2:].mean()
            vol_early = recent["volume"].iloc[:len(recent)//2].mean()
            vol_declining = vol_mid < vol_early

            if vol_declining:
                pivot_high = float(max(hi_vals))
                return {
                    "detected": True,
                    "pattern": "VCP",
                    "pivot_high": pivot_high,
                    "contractions": len(contractions),
                    "latest_ratio": round(ratio, 2),
                    "signal_text": f"VCP {len(contractions)}-pivot: contraction {ratio*100:.0f}% of pivot",
                }
    return {"detected": False}


# ── Cup-with-Handle ───────────────────────────────────────────────────────────

def detect_cup_with_handle(df: pd.DataFrame) -> dict:
    """Simplified CwH detection from weekly-level OHLCV."""
    if len(df) < 60:
        return {"detected": False}

    # Look for U-shaped low then consolidation near rim
    window = df.tail(120)
    cup_low = float(window["close"].min())
    cup_low_idx = window["close"].idxmin()
    rim_left = float(window["close"].iloc[0])
    rim_right = float(window["close"].iloc[-1])

    depth = (rim_left - cup_low) / max(rim_left, 1)

    # Cup: depth 15-35%, roughly symmetric
    if 0.12 <= depth <= 0.40 and rim_right > cup_low * 1.10:
        # Handle: last 10% of cup length should be tight
        handle = window.tail(max(10, len(window) // 10))
        handle_range = (handle["high"].max() - handle["low"].min()) / max(rim_right, 1)
        if handle_range < 0.08:
            pivot = float(window["high"].tail(max(10, len(window) // 10)).max())
            return {
                "detected": True,
                "pattern": "CUP_WITH_HANDLE",
                "pivot": pivot,
                "depth_pct": round(depth * 100, 1),
                "signal_text": f"Cup-with-Handle: sâu {depth*100:.0f}%, pivot {pivot:,.0f}",
            }
    return {"detected": False}


# ── FVG — Fair Value Gap ──────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame) -> list[dict]:
    """Find bullish/bearish Fair Value Gaps from last 20 bars."""
    fvgs = []
    if len(df) < 3:
        return fvgs

    recent = df.tail(20)
    for i in range(1, len(recent) - 1):
        c1 = recent.iloc[i-1]
        c3 = recent.iloc[i+1]
        # Bullish FVG: c1.high < c3.low
        if c1["high"] < c3["low"]:
            fvgs.append({
                "type": "BULLISH",
                "gap_low": float(c1["high"]),
                "gap_high": float(c3["low"]),
                "date": str(recent.iloc[i].get("date", i)),
            })
        # Bearish FVG: c1.low > c3.high
        elif c1["low"] > c3["high"]:
            fvgs.append({
                "type": "BEARISH",
                "gap_low": float(c3["high"]),
                "gap_high": float(c1["low"]),
                "date": str(recent.iloc[i].get("date", i)),
            })
    return fvgs


# ── RSI Divergence ────────────────────────────────────────────────────────────

def detect_rsi_divergence(df: pd.DataFrame) -> dict:
    """Bullish RSI divergence: price makes lower low, RSI makes higher low."""
    if len(df) < 30 or "RSI14" not in df.columns:
        return {"detected": False, "type": "NONE"}

    recent = df.tail(30)
    price_lows = _find_swing_lows(recent["close"], window=3)
    rsi_series = recent["RSI14"]

    if len(price_lows) >= 2:
        p_ll = price_lows[-2:]
        price_change = recent["close"].iloc[p_ll[1]] - recent["close"].iloc[p_ll[0]]
        rsi_change = rsi_series.iloc[p_ll[1]] - rsi_series.iloc[p_ll[0]]

        if price_change < 0 and rsi_change > 0:
            return {"detected": True, "type": "BULLISH", "signal_text": "Bullish RSI divergence: giá thấp hơn nhưng RSI cao hơn"}
        if price_change > 0 and rsi_change < 0:
            return {"detected": True, "type": "BEARISH", "signal_text": "Bearish RSI divergence: giá cao hơn nhưng RSI thấp hơn"}

    return {"detected": False, "type": "NONE"}


# ── Detect All Patterns ───────────────────────────────────────────────────────

def detect_all(df: pd.DataFrame) -> dict:
    """Run all pattern detectors and return combined result."""
    spring = detect_spring(df)
    vcp = detect_vcp(df)
    cwh = detect_cup_with_handle(df)
    fvgs = detect_fvg(df)
    rsi_div = detect_rsi_divergence(df)

    detected = []
    if spring.get("detected"):
        detected.append(spring)
    if vcp.get("detected"):
        detected.append(vcp)
    if cwh.get("detected"):
        detected.append(cwh)
    if rsi_div.get("detected"):
        detected.append(rsi_div)

    # Best pattern for MFPM bonus
    pattern_bonus = 0
    pattern_name = "NONE"
    for p in detected:
        ptype = p.get("pattern", p.get("type", ""))
        if ptype in ("WYCKOFF_SPRING", "VCP", "CUP_WITH_HANDLE"):
            pattern_bonus = 15
            pattern_name = ptype
            break
        elif ptype == "BULLISH":
            pattern_bonus = 8
            pattern_name = "RSI_DIV_BULLISH"

    return {
        "patterns_detected": detected,
        "fvgs": fvgs,
        "best_pattern": pattern_name,
        "pattern_bonus": pattern_bonus,
        "summary": " + ".join(p.get("pattern", p.get("type", "")) for p in detected) or "NONE",
    }

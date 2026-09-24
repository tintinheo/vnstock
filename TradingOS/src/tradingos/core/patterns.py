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


# ── Second Mouse Gate (Breakout Confirmation) ───────────────────────────────

def second_mouse_gate(df: pd.DataFrame, breakout_level: float, lookback: int = 5) -> dict:
    """
    [C7 NEW] Confirms a breakout by checking for a successful retest.
    "The first mouse gets the trap, the second mouse gets the cheese."

    Looks for:
    1. Price breaks above `breakout_level`.
    2. A small pullback (1-3 bars) that holds ABOVE the `breakout_level`.
    3. The pullback occurs on lower volume.
    4. Price starts to recover from the pullback.

    Returns:
        - confirmed (bool): True if the retest is successful.
        - retest_low (float): The low price of the retest.
        - days_since_breakout (int): How many bars ago the initial breakout happened.
    """
    if len(df) < lookback + 2:
        return {"confirmed": False, "reason": "Insufficient data"}

    recent = df.tail(lookback).copy()
    avg_vol = recent["volume"].mean()

    # Find the first bar that broke and closed above the level
    # [BUG-28 FIX] Start at i=1 to avoid iloc[i-1] wrapping to the last row when i=0,
    # which caused false breakout detection using an unrelated bar's low.
    breakout_bar_idx = -1
    for i in range(1, len(recent)):
        if recent["close"].iloc[i] > breakout_level and recent["low"].iloc[i-1] < breakout_level:
            breakout_bar_idx = i
            break

    if breakout_bar_idx == -1 or breakout_bar_idx >= len(recent) - 2:
        return {"confirmed": False, "reason": "No recent breakout or breakout is too new"}

    # Slice from the breakout bar onwards
    post_breakout_df = recent.iloc[breakout_bar_idx:]

    # Check for a pullback (a low after the breakout bar's high)
    breakout_high = post_breakout_df["high"].iloc[0]
    pullback_low = post_breakout_df["low"].iloc[1:].min()
    pullback_bar_idx = post_breakout_df["low"].iloc[1:].idxmin()

    if pd.isna(pullback_low):
        return {"confirmed": False, "reason": "No pullback after breakout"}

    # 1. Retest holds above breakout level
    retest_holds = pullback_low > breakout_level

    # 2. Pullback volume is lower than average and breakout volume
    pullback_volume = df.loc[pullback_bar_idx, "volume"]
    breakout_volume = post_breakout_df["volume"].iloc[0]
    volume_confirms = (pullback_volume < avg_vol * 0.9) and (pullback_volume < breakout_volume)

    # 3. Price is recovering from the pullback
    last_close = recent["close"].iloc[-1]
    recovering = last_close > pullback_low

    confirmed = retest_holds and volume_confirms and recovering

    return {
        "confirmed": confirmed,
        "retest_low": float(pullback_low) if confirmed else 0.0,
        "days_since_breakout": len(recent) - breakout_bar_idx,
        "reason": "OK" if confirmed else "Retest failed conditions",
    }


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
    # [VN-FIX V7] Differentiated by VN daily-data reliability.
    # VCP has the strictest structural requirements and the strongest backtested
    # edge on HOSE daily data.  Spring and CwH are valid but noisier (Spring can
    # trigger on a single wick; CwH was designed for weekly data).
    # RSI divergence is the weakest standalone signal.
    # Best-wins iteration: all detected patterns are evaluated; highest bonus kept.
    _PATTERN_BONUS: dict[str, int] = {
        "VCP": 18,             # tightest structure, strongest edge on VN daily data
        "WYCKOFF_SPRING": 12,  # valid but single-wick prone
        "CUP_WITH_HANDLE": 10, # weekly-level pattern on daily data, lower weight
        "RSI_DIV_BULLISH": 8,  # corroborating signal only
    }
    pattern_bonus = 0
    pattern_name = "NONE"
    for p in detected:
        ptype = p.get("pattern", p.get("type", ""))
        if ptype == "BULLISH":          # RSI divergence type key
            ptype = "RSI_DIV_BULLISH"
        b = _PATTERN_BONUS.get(ptype, 0)
        if b > pattern_bonus:
            pattern_bonus = b
            pattern_name = ptype

    return {
        "patterns_detected": detected,
        "fvgs": fvgs,
        "best_pattern": pattern_name,
        "pattern_bonus": pattern_bonus,
        "summary": " + ".join(p.get("pattern", p.get("type", "")) for p in detected) or "NONE",
    }

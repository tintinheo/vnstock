"""Gap Analysis + VWAP computations (SRS extension: F4 Gap, F8 VWAP)."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from ..utils.logging import get_logger

log = get_logger("gap_vwap")


# ── T+2.5 window helper ───────────────────────────────────────────────────────

def _t25_window_active() -> bool:
    """True if current VN time is within T+2.5 window 12:45–13:15."""
    try:
        from ..utils.dates import vn_now
        now = vn_now()
        cur_min = now.hour * 60 + now.minute
        return 12 * 60 + 45 <= cur_min <= 13 * 60 + 15
    except Exception:
        return False


# ── GAP ANALYSIS ─────────────────────────────────────────────────────────────

def detect_gaps(df: pd.DataFrame) -> dict:
    """
    Classify the latest overnight gap and compute gap-fill statistics.

    gap_pct:      (open[-1] - close[-2]) / close[-2] * 100
    gap_type:     GAP_UP (>+0.5%) | GAP_DOWN (<-0.5%) | NO_GAP
    avg_gap_pct:  mean |gap %| over last 20 bars
    gap_fill_pct: % of significant gaps (>0.5%) filled within 5 bars (0-100)
    """
    _empty = {"gap_pct": 0.0, "gap_type": "NO_GAP", "avg_gap_pct": 0.0, "gap_fill_pct": 0.0}
    try:
        if df is None or len(df) < 3:
            return _empty
        opens  = df["open"].values
        closes = df["close"].values
        highs  = df["high"].values
        lows   = df["low"].values

        # Latest bar gap
        gap_pct = (opens[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] != 0 else 0.0
        if   gap_pct >  0.5: gap_type = "GAP_UP"
        elif gap_pct < -0.5: gap_type = "GAP_DOWN"
        else:                gap_type = "NO_GAP"

        # Historical 20-bar stats
        n = min(20, len(df) - 1)
        abs_gaps: list[float] = []
        filled = 0
        valid  = 0
        for i in range(-(n + 1), -1):
            try:
                gp = (opens[i + 1] - closes[i]) / closes[i] * 100 if closes[i] != 0 else 0.0
                abs_gaps.append(abs(gp))
                if abs(gp) > 0.5:
                    valid += 1
                    fp = closes[i]          # gap fill target = previous close
                    for j in range(i + 1, min(i + 6, 0)):
                        if lows[j] <= fp <= highs[j]:
                            filled += 1
                            break
            except Exception:
                pass

        return {
            "gap_pct":      round(gap_pct, 2),
            "gap_type":     gap_type,
            "avg_gap_pct":  round(sum(abs_gaps) / len(abs_gaps), 2) if abs_gaps else 0.0,
            "gap_fill_pct": round(filled / valid * 100, 1) if valid > 0 else 0.0,
        }
    except Exception:
        return _empty


# ── DAILY VWAP RESULT ────────────────────────────────────────────────────────

def compute_vwap_result(df: pd.DataFrame, anchor_bars: int = 20) -> dict:
    """
    Extract VWAP summary from the pre-computed VWAP_daily column (or
    recompute from scratch if column not present).

    Returns: {vwap, price_vs_vwap_pct, vwap_dev}
    vwap_dev: ABOVE | BELOW | AT  (threshold ±0.5%)
    """
    _empty = {"vwap": None, "price_vs_vwap_pct": 0.0, "vwap_dev": "AT"}
    try:
        if df is None or len(df) < anchor_bars:
            return _empty
        if "VWAP_daily" in df.columns:
            vwap = float(df["VWAP_daily"].iloc[-1])
        else:
            sub  = df.tail(anchor_bars)
            tp   = (sub["high"] + sub["low"] + sub["close"]) / 3
            vol  = sub["volume"].clip(lower=1)
            vwap = float((tp * vol).sum() / vol.sum())

        if not np.isfinite(vwap) or vwap <= 0:
            return _empty

        price   = float(df["close"].iloc[-1])
        dev_pct = (price - vwap) / vwap * 100
        vwap_dev = "ABOVE" if dev_pct > 0.5 else "BELOW" if dev_pct < -0.5 else "AT"
        return {
            "vwap":               round(vwap, 0),
            "price_vs_vwap_pct":  round(dev_pct, 2),
            "vwap_dev":           vwap_dev,
        }
    except Exception:
        return _empty


# ── INTRADAY VWAP RESULT ─────────────────────────────────────────────────────

def compute_vwap_intraday_result(
    ticker: str,
    df_5m: pd.DataFrame | None = None,
) -> dict:
    """
    Cumulative intraday VWAP from 5-minute bars.
    Auto-fetches today's bars from SSI if df_5m is not provided.

    Returns:
        vwap_intraday:       float | None
        vwap_intraday_dev:   ABOVE | BELOW | AT
        vwap_intraday_slope: float (VND/bar from 6-bar linear regression)
        t25_window_now:      bool
        bars_available:      int
    """
    _empty = {
        "vwap_intraday":       None,
        "vwap_intraday_dev":   "AT",
        "vwap_intraday_slope": 0.0,
        "t25_window_now":      _t25_window_active(),
        "bars_available":      0,
    }
    try:
        if df_5m is None or df_5m.empty:
            df_5m = _fetch_intraday_today(ticker)
        if df_5m is None or len(df_5m) < 3:
            return _empty

        df = df_5m.copy()
        df["tp"]      = (df["high"] + df["low"] + df["close"]) / 3.0
        df["cum_pv"]  = (df["tp"] * df["volume"].clip(lower=1)).cumsum()
        df["cum_vol"] = df["volume"].clip(lower=1).cumsum()
        df["vwap"]    = df["cum_pv"] / df["cum_vol"]

        vwap_last = float(df["vwap"].iloc[-1])
        price_now = float(df["close"].iloc[-1])
        dev = (price_now - vwap_last) / vwap_last * 100 if vwap_last > 0 else 0.0
        vwap_intraday_dev = "ABOVE" if dev > 0.5 else "BELOW" if dev < -0.5 else "AT"

        vwap_vals = df["vwap"].dropna().values
        if len(vwap_vals) >= 6:
            y     = vwap_vals[-6:]
            slope = float(np.polyfit(np.arange(6), y, 1)[0])
        else:
            slope = 0.0

        return {
            "vwap_intraday":       round(vwap_last, 0),
            "vwap_intraday_dev":   vwap_intraday_dev,
            "vwap_intraday_slope": round(slope, 3),
            "t25_window_now":      _t25_window_active(),
            "bars_available":      len(df),
        }
    except Exception as e:
        log.debug(f"compute_vwap_intraday_result {ticker}: {e}")
        return _empty


def _fetch_intraday_today(ticker: str) -> pd.DataFrame:
    """Delegate to fetcher.fetch_intraday_5m and filter to today only."""
    try:
        from ..data.fetcher import fetch_intraday_5m
        df = fetch_intraday_5m(ticker)
        if df.empty:
            return df
        # Ensure DatetimeIndex for date filtering
        if not isinstance(df.index, pd.DatetimeIndex):
            for col in ("date", "time"):
                if col in df.columns:
                    df = df.set_index(pd.to_datetime(df[col]))
                    break
        today_str = datetime.now().strftime("%Y-%m-%d")
        df = df[df.index.strftime("%Y-%m-%d") == today_str]
        return df
    except Exception as e:
        log.debug(f"intraday 5m fetch failed for {ticker}: {e}")
        return pd.DataFrame()


# ── MONTHLY PIVOTS ────────────────────────────────────────────────────────────

def compute_monthly_pivots(df: pd.DataFrame) -> dict:
    """
    Classic monthly pivot points from the last 20 bars (≈1 calendar month).
    Returns {monthly_pp, monthly_r1, monthly_r2, monthly_s1, monthly_s2},
    or {} if insufficient data.
    """
    if df is None or len(df) < 20:
        return {}
    last20 = df.tail(20)
    H  = float(last20["high"].max())
    L  = float(last20["low"].min())
    C  = float(df["close"].iloc[-1])
    PP = (H + L + C) / 3
    return {
        "monthly_pp": round(PP, 0),
        "monthly_r1": round(2 * PP - L, 0),
        "monthly_r2": round(PP + (H - L), 0),
        "monthly_s1": round(2 * PP - H, 0),
        "monthly_s2": round(PP - (H - L), 0),
    }


# ── FIBONACCI LEVELS ──────────────────────────────────────────────────────────

def compute_fibonacci_levels(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Fibonacci retracement from the recent swing high/low.
    Returns {fib_swing_high, fib_swing_low, fib_382, fib_500, fib_618},
    or {} if insufficient data.
    """
    if df is None or len(df) < lookback:
        return {}
    window = df.tail(lookback)
    sh = float(window["high"].max())
    sl = float(window["low"].min())
    rng = sh - sl
    if rng <= 0:
        return {}
    return {
        "fib_swing_high": round(sh, 0),
        "fib_swing_low":  round(sl, 0),
        "fib_382":        round(sh - 0.382 * rng, 0),
        "fib_500":        round(sh - 0.500 * rng, 0),
        "fib_618":        round(sh - 0.618 * rng, 0),
    }

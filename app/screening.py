"""
screening.py — CANSLIM filter, breakout detection, and manipulation scoring.

Implements the CANSLIM Quant & Market Manipulation Detection System proposal,
adapted for the Vietnam stock market (HOSE/HNX/UPCOM).

Key Vietnam adaptations vs US CANSLIM:
  • EPS growth threshold: 15% (US: 25%) — VN reporting lags & data availability
  • ROE threshold: 12% (US: 17%) — fewer large-cap VN stocks sustain >17%
  • Pivot lookback: 50 daily bars (~10 weeks) — shorter than O'Neil's 7-65 weeks
    because VN bases tend to be shallower & faster-forming
  • Institutional criterion ("I"): NOT implemented — VN foreign ownership updates
    weekly/monthly, not in real-time. Deferred.
  • RS Rating: NOT implemented — requires full-universe benchmark. Deferred.

All price inputs are in thousands-VND (internal convention of Quant_Profiler).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from qp_config import (
    CANSLIM_EPS_GROWTH_MIN,
    CANSLIM_ROE_MIN,
    CANSLIM_PIVOT_BARS,
    CANSLIM_VOL_CONFIRM_X,
    MANIP_VOL_ZSCORE_THRESH,
    MANIP_REVERSAL_BARS,
)

_log = logging.getLogger("screening")


# ── Pivot breakout detection ──────────────────────────────────────────────────

def get_pivot_breakout(df: pd.DataFrame) -> dict:
    """
    Detect O'Neil-style pivot-point breakout.

    Pivot = highest high over the last CANSLIM_PIVOT_BARS bars (excluding today).
    Breakout confirmation requires:
        1. Close > pivot price
        2. Volume ≥ CANSLIM_VOL_CONFIRM_X × 50-bar average volume

    Very-low-volume breakouts (< 0.7× average) are flagged as false breakouts.

    Args:
        df: Daily OHLCV DataFrame with columns High, Low, Close, Volume.
            Must have at least CANSLIM_PIVOT_BARS + 1 rows.

    Returns:
        dict:
            is_breakout    : bool   — True if close > pivot AND volume confirms
            pivot_price    : float  — pivot reference price (thousands-VND)
            vol_ratio      : float  — current volume / 50-bar avg volume
            false_breakout : bool   — True if breakout on low volume (< 0.7×)
            base_depth_pct : float  — % depth of the base (pivot - base_low) / pivot
    """
    empty = {
        "is_breakout":    False,
        "pivot_price":    None,
        "vol_ratio":      None,
        "false_breakout": False,
        "base_depth_pct": None,
    }
    try:
        if df is None or len(df) < CANSLIM_PIVOT_BARS + 1:
            return empty

        close   = pd.to_numeric(df["Close"],  errors="coerce")
        high    = pd.to_numeric(df["High"],   errors="coerce")
        volume  = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

        # Pivot: max high over lookback window (exclude last bar = today)
        lookback = high.iloc[-(CANSLIM_PIVOT_BARS + 1):-1]
        pivot    = float(lookback.max())

        price_now = float(close.iloc[-1])
        vol_now   = float(volume.iloc[-1])

        # 50-bar average volume (O'Neil benchmark)
        vol_ma50 = float(volume.iloc[-51:-1].mean()) if len(volume) >= 51 else float(volume.mean())
        vol_ratio = (vol_now / vol_ma50) if vol_ma50 > 0 else 0.0

        # Base depth: how deep did the consolidation go?
        base_low   = float(df["Low"].iloc[-(CANSLIM_PIVOT_BARS + 1):-1].min())
        base_depth = (pivot - base_low) / pivot * 100 if pivot > 0 else 0.0

        is_breakout    = price_now > pivot and vol_ratio >= CANSLIM_VOL_CONFIRM_X
        false_breakout = price_now > pivot and vol_ratio < 0.7

        return {
            "is_breakout":    bool(is_breakout),
            "pivot_price":    round(pivot, 2),
            "vol_ratio":      round(vol_ratio, 2),
            "false_breakout": bool(false_breakout),
            "base_depth_pct": round(base_depth, 1),
        }
    except Exception as e:
        _log.debug("get_pivot_breakout: %s", e)
        return empty


# ── CANSLIM fundamental filter ────────────────────────────────────────────────

def filter_canslim(financials: dict) -> dict:
    """
    Apply CANSLIM C + A criteria to a financials dict.

    Input dict (from ssi_fetcher.fetch_financials or analyse_ticker result):
        eps          : float  — latest EPS (raw VND per share)
        eps_prev     : float  — prior period EPS (optional, for growth calc)
        eps_growth   : float  — pre-computed YoY growth fraction (optional)
        roe          : float  — ROE as fraction (0.27 = 27%)
        pe           : float  — P/E ratio
        debt_equity  : float  — D/E ratio

    CANSLIM score breakdown (0-100):
        C (Current earnings growth)  : 40 pts
        A (Annual earnings growth)   : 30 pts (uses same eps_growth proxy)
        L (Leader vs laggard)        : 20 pts  — uses P/E position (proxy)
        M (Market direction)         : 10 pts  — deferred (needs regime input)

    Institutional (I) and RS (N) criteria are NOT scored here:
        I: foreign ownership data is weekly/monthly in VN — no real-time signal
        N: RS Rating requires full-universe benchmark — deferred
    """
    empty = {
        "canslim_eligible": False,
        "canslim_score":    0,
        "eps_growth_ok":    False,
        "roe_ok":           False,
        "eps_growth":       None,
        "detail":           "insufficient_data",
    }
    if not financials:
        return empty

    try:
        roe = float(financials.get("roe") or 0.0)
        pe  = float(financials.get("pe")  or 0.0)
        de  = float(financials.get("debt_equity") or 0.0)

        # EPS growth: use pre-computed if available, else derive from eps/eps_prev
        eps_growth = financials.get("eps_growth")
        if eps_growth is None:
            eps      = float(financials.get("eps", 0) or 0)
            eps_prev = float(financials.get("eps_prev", 0) or 0)
            if eps_prev and abs(eps_prev) > 0:
                eps_growth = (eps - eps_prev) / abs(eps_prev)
            else:
                eps_growth = None  # cannot determine

        eps_growth_ok = eps_growth is not None and eps_growth >= CANSLIM_EPS_GROWTH_MIN
        roe_ok        = roe >= CANSLIM_ROE_MIN

        # Score: C criterion (0-40)
        score_c = 0
        if eps_growth is not None:
            if eps_growth >= 0.30:   score_c = 40
            elif eps_growth >= 0.20: score_c = 30
            elif eps_growth >= 0.15: score_c = 20
            elif eps_growth >= 0.05: score_c = 10

        # Score: A criterion (0-30) — same proxy as C in absence of multi-year data
        score_a = 0
        if eps_growth is not None:
            if eps_growth >= 0.25:   score_a = 30
            elif eps_growth >= 0.15: score_a = 20
            elif eps_growth >= 0.05: score_a = 10

        # Score: L criterion (0-20) — low (healthy) P/E is a leadership proxy
        # For VN: P/E 8-16 = reasonable leader; >25 = extended; <8 = value trap risk
        score_l = 0
        if 8 <= pe <= 16:   score_l = 20
        elif 16 < pe <= 22: score_l = 12
        elif 22 < pe <= 28: score_l = 6
        elif pe > 0:        score_l = 0

        # Penalty: high leverage reduces quality
        penalty = min(10, de * 2) if de > 2.0 else 0

        canslim_score = max(0, score_c + score_a + score_l - int(penalty))
        # ROE requirement changes eligible threshold
        canslim_eligible = roe_ok and eps_growth_ok and canslim_score >= 40

        return {
            "canslim_eligible": bool(canslim_eligible),
            "canslim_score":    int(canslim_score),
            "eps_growth_ok":    bool(eps_growth_ok),
            "roe_ok":           bool(roe_ok),
            "eps_growth":       round(float(eps_growth), 4) if eps_growth is not None else None,
            "detail":           "ok",
        }
    except Exception as e:
        _log.debug("filter_canslim: %s", e)
        return empty


# ── Manipulation / pump-dump detection ───────────────────────────────────────

def compute_manipulation_score(df: pd.DataFrame) -> dict:
    """
    Score the probability of price manipulation (pump-and-dump or spoofing).

    Detection criteria:
        1. Volume Z-score > MANIP_VOL_ZSCORE_THRESH (= unusual volume spike)
        2. Large intraday price move (|close - open| / open > 4%)
        3. Price reversal within MANIP_REVERSAL_BARS sessions after a large up-move
           — rapid reversal back into the base is a classic "dump" pattern

    Score interpretation:
        > 3.0  : High probability of manipulation → check fundamentals before acting
        1.5-3  : Elevated — could be genuine breakout, monitor next session
        < 1.5  : Normal activity

    Args:
        df: Daily OHLCV DataFrame. Requires Close, Open, Volume columns.
            Minimum 22 rows for reliable Z-score.

    Returns:
        dict:
            manip_score  : float — composite manipulation score
            manip_flag   : bool  — True if score > MANIP_VOL_ZSCORE_THRESH
            vol_zscore   : float — volume Z-score (last bar vs 20-bar window)
            price_spike  : float — |close - open| / open (last bar)
            dump_signal  : bool  — rapid reversal detected
    """
    empty = {
        "manip_score":  0.0,
        "manip_flag":   False,
        "vol_zscore":   0.0,
        "price_spike":  0.0,
        "dump_signal":  False,
    }
    try:
        if df is None or len(df) < 22:
            return empty

        close  = pd.to_numeric(df["Close"],  errors="coerce")
        open_  = pd.to_numeric(df["Open"],   errors="coerce")
        volume = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

        # Volume Z-score (last bar vs 20-bar rolling window)
        vol_mean20 = float(volume.iloc[-21:-1].mean())
        vol_std20  = float(volume.iloc[-21:-1].std())
        vol_last   = float(volume.iloc[-1])
        vol_zscore = (vol_last - vol_mean20) / vol_std20 if vol_std20 > 0 else 0.0

        # Intraday price spike (absolute close-open change)
        price_open  = float(open_.iloc[-1]) or 1.0
        price_close = float(close.iloc[-1])
        price_spike = abs(price_close - price_open) / price_open

        # Dump signal: price closed up strongly N bars ago, now reversed down
        dump_signal = False
        if len(close) >= MANIP_REVERSAL_BARS + 2:
            prev_chg = float(close.iloc[-(MANIP_REVERSAL_BARS + 1)] - close.iloc[-(MANIP_REVERSAL_BARS + 2)])
            curr_chg = float(close.iloc[-1] - close.iloc[-2])
            big_up   = prev_chg / (float(close.iloc[-(MANIP_REVERSAL_BARS + 2)]) or 1.0) > 0.04
            now_down = curr_chg < 0
            dump_signal = bool(big_up and now_down and vol_zscore > 2.0)

        # Composite score: vol spike (50%) + price spike (scaled 40%) + dump (10%)
        manip_score = (
            vol_zscore * 0.5
            + (price_spike * 20.0) * 0.4  # scale pct to ~0-2 range
            + (1.0 if dump_signal else 0.0)
        )

        return {
            "manip_score":  round(manip_score, 2),
            "manip_flag":   bool(manip_score > MANIP_VOL_ZSCORE_THRESH),
            "vol_zscore":   round(vol_zscore, 2),
            "price_spike":  round(price_spike * 100, 2),   # as %
            "dump_signal":  bool(dump_signal),
        }
    except Exception as e:
        _log.debug("compute_manipulation_score: %s", e)
        return empty


# ── Pump & Dump advanced detection ───────────────────────────────────────────

def detect_pump_dump_advanced(df: pd.DataFrame) -> dict:
    """
    4-factor Pump & Dump fingerprint model — advanced version for Optimal T+ tab.

    Factors:
        1. Volume Z-score spike       — weight 0.40
        2. 5-day price acceleration   — weight 0.30
        3. Consecutive ceiling-hit days — weight 0.20
        4. Rapid dump reversal signal — weight 0.10

    Thresholds (Vietnam market calibrated):
        pump_score > 75  → EXTREME PUMP — do NOT chase, high dump risk
        pump_score 50-75 → ELEVATED     — caution, monitor next session
        pump_score < 50  → NORMAL       — no abnormal behaviour detected

    Args:
        df: Daily OHLCV DataFrame with Close, Open, High, Low, Volume columns.
            Minimum 22 rows for reliable Z-score.

    Returns:
        dict:
            pump_score          : float  0–100 composite pump probability
            pump_flag           : bool   True when score > 75
            dump_risk           : bool   True when factor 4 (rapid reversal) detected
            pump_vol_factor     : float  volume Z-score contribution (0–40)
            pump_price_factor   : float  5-day accel contribution (0–30)
            pump_ceiling_factor : float  ceiling-hit contribution (0–20)
            pump_dump_factor    : float  dump reversal contribution (0–10)
    """
    empty = {
        "pump_score":          0.0,
        "pump_flag":           False,
        "dump_risk":           False,
        "pump_vol_factor":     0.0,
        "pump_price_factor":   0.0,
        "pump_ceiling_factor": 0.0,
        "pump_dump_factor":    0.0,
    }
    try:
        if df is None or len(df) < 22:
            return empty

        close  = pd.to_numeric(df["Close"],  errors="coerce")
        open_  = pd.to_numeric(df["Open"],   errors="coerce")
        high   = pd.to_numeric(df["High"],   errors="coerce")
        volume = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

        # ── Factor 1: Volume Z-score (0–40 pts) ──────────────────────────────
        vol_mean20 = float(volume.iloc[-21:-1].mean())
        vol_std20  = float(volume.iloc[-21:-1].std())
        vol_last   = float(volume.iloc[-1])
        vol_z      = (vol_last - vol_mean20) / vol_std20 if vol_std20 > 0 else 0.0
        # Z > 2 = unusual, Z > 4 = extreme
        f1 = min(40.0, max(0.0, (vol_z - 0.5) / 3.5 * 40.0))

        # ── Factor 2: 5-day price acceleration (0–30 pts) ─────────────────────
        if len(close) >= 6:
            price_5d_ago = float(close.iloc[-6])
            price_now    = float(close.iloc[-1])
            accel_pct    = (price_now - price_5d_ago) / price_5d_ago * 100 if price_5d_ago > 0 else 0.0
        else:
            accel_pct = 0.0
        # +15% in 5 days → full 30 pts (HoSE +7%/day ceiling makes this realistic)
        f2 = min(30.0, max(0.0, accel_pct / 15.0 * 30.0))

        # ── Factor 3: Consecutive ceiling-hit days in last 5 sessions (0–20 pts)
        # A "ceiling hit" = close >= reference * 1.065 (at or within 0.5% of +7% limit)
        # Reference = previous day close; approximate using daily return > 6%
        ceiling_hits = 0
        lookback = min(5, len(close) - 1)
        for i in range(-lookback, 0):
            try:
                prev  = float(close.iloc[i - 1])
                curr  = float(close.iloc[i])
                daily_ret = (curr - prev) / prev if prev > 0 else 0.0
                if daily_ret >= 0.06:
                    ceiling_hits += 1
            except Exception:
                pass
        # 2+/5 ceiling hits = elevated; 4+/5 = extreme
        f3 = min(20.0, ceiling_hits / 5.0 * 20.0)

        # ── Factor 4: Rapid dump reversal (0–10 pts) ──────────────────────────
        # Classic P&D dump: price was strongly up N days ago, now reversed down hard
        dump_risk   = False
        f4          = 0.0
        if len(close) >= 4:
            strong_prev = float(close.iloc[-3] - close.iloc[-4]) / max(float(close.iloc[-4]), 1.0) > 0.04
            down_now    = float(close.iloc[-1]) < float(close.iloc[-2])
            high_vol_dump = vol_z > 1.5
            if strong_prev and down_now and high_vol_dump:
                dump_risk = True
                f4        = 10.0

        pump_score = round(f1 + f2 + f3 + f4, 1)

        return {
            "pump_score":          pump_score,
            "pump_flag":           bool(pump_score > 75),
            "dump_risk":           dump_risk,
            "pump_vol_factor":     round(f1, 1),
            "pump_price_factor":   round(f2, 1),
            "pump_ceiling_factor": round(f3, 1),
            "pump_dump_factor":    round(f4, 1),
        }
    except Exception as e:
        _log.debug("detect_pump_dump_advanced: %s", e)
        return empty


# ── False Breakout probability ────────────────────────────────────────────────

def detect_false_breakout(df: pd.DataFrame, r: dict) -> dict:
    """
    5-criteria false breakout probability model.

    Only meaningful when a pivot breakout has already been detected
    (is_breakout == True from get_pivot_breakout). Call after get_pivot_breakout.

    Criteria (each worth 1 point toward a REAL breakout):
        1. Volume confirmation  — current vol ≥ 1.3× 20-bar average
        2. Close above pivot    — daily close ≥ pivot_price (no intraday rejection)
        3. RSI not overbought   — RSI14 < 75 at breakout bar
        4. No vol divergence    — 3-bar volume trend is NOT declining before breakout
        5. Multi-bar confirm    — signal_confirm_bars ≥ 2 from result dict

    Scoring:
        5/5 → false_breakout_prob ≈ 0.10  (Grade A, strong)
        4/5 → false_breakout_prob ≈ 0.25  (Grade B, good)
        3/5 → false_breakout_prob ≈ 0.45  (Grade C, borderline)
        <3  → false_breakout_prob ≈ 0.75  (Risk, do NOT chase)

    Args:
        df: Daily OHLCV DataFrame with Close, High, Low, Volume, RSI columns.
        r:  analyse_ticker result dict (for signal_confirm_bars, pivot_price,
            vol_ratio, rsi fields).

    Returns:
        dict:
            false_breakout_prob : float  0.0–1.0 probability of fakeout
            fb_criteria_met     : int    0–5 number of criteria confirmed
            fb_grade            : str    "A"/"B"/"C"/"RISKY"
            fb_criteria         : list   bool list [c1..c5]
    """
    empty = {
        "false_breakout_prob": 0.5,
        "fb_criteria_met":     0,
        "fb_grade":            "RISKY",
        "fb_criteria":         [False] * 5,
    }
    try:
        if df is None or len(df) < 22:
            return empty

        volume = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        close  = pd.to_numeric(df["Close"],  errors="coerce")

        vol_now   = float(volume.iloc[-1])
        vol_ma20  = float(volume.iloc[-21:-1].mean()) if len(volume) >= 21 else float(volume.mean())
        rsi_now   = float(r.get("rsi") or 50.0)
        pivot     = float(r.get("pivot_price") or r.get("t_rec_entry_high") or close.iloc[-1])
        price_now = float(close.iloc[-1])
        confirm_bars = int(r.get("signal_confirm_bars") or 0)

        # C1: Volume ≥ 1.3× average
        c1 = bool(vol_ma20 > 0 and vol_now >= vol_ma20 * 1.3)

        # C2: Close above pivot (no intraday rejection)
        c2 = bool(price_now >= pivot)

        # C3: RSI not overbought (<75 VN-adjusted)
        c3 = bool(rsi_now < 75)

        # C4: No 3-bar volume divergence — volume NOT declining 3 bars before breakout
        c4 = True
        if len(volume) >= 4:
            v3 = [float(volume.iloc[-4]), float(volume.iloc[-3]), float(volume.iloc[-2])]
            if v3[0] > v3[1] > v3[2]:  # 3 consecutive declining bars before today
                c4 = False

        # C5: At least 2 confirmation bars (price held above breakout level)
        c5 = bool(confirm_bars >= 2)

        criteria = [c1, c2, c3, c4, c5]
        met      = sum(criteria)

        # Map met count → false breakout probability and grade
        _prob_map  = {5: 0.10, 4: 0.25, 3: 0.45, 2: 0.65, 1: 0.80, 0: 0.90}
        _grade_map = {5: "A",  4: "B",  3: "C",  2: "RISKY", 1: "RISKY", 0: "RISKY"}

        return {
            "false_breakout_prob": _prob_map.get(met, 0.90),
            "fb_criteria_met":     met,
            "fb_grade":            _grade_map.get(met, "RISKY"),
            "fb_criteria":         criteria,
        }
    except Exception as e:
        _log.debug("detect_false_breakout: %s", e)
        return empty

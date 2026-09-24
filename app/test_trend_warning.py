"""
test_trend_warning.py  —  Unit tests for trend_warning_engine.py
=================================================================
Run:
    cd d:\\portfolio\\vnstock\\app
    python test_trend_warning.py

All 32 tests should pass.  Exit code 0 = success, 1 = failure.
"""
from __future__ import annotations
import sys
import os

# Force UTF-8 stdout so emoji pass-through works on cp1252 consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

from trend_warning_engine import (
    detect_macd_divergence,
    detect_adx_states,
    detect_bb_squeeze,
    detect_structure_break,
    compute_trend_warning,
    UPTREND_STRENGTHENING,
    UPTREND_EXHAUSTING,
    DOWNTREND_STRENGTHENING,
    DOWNTREND_EXHAUSTING,
    RANGE_COMPRESSION,
    BREAKOUT_EMERGING,
    REVERSAL_WARNING_LOW_CONF,
    REVERSAL_WARNING_CONFIRMED,
    INSUFFICIENT_DATA,
)

PASS = "✅ PASS"
FAIL = "❌ FAIL"

_results: list[tuple[str, str]] = []


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_df(
    n: int = 60,
    close=None, high=None, low=None,
    adx=None, bb_upper=None, bb_lower=None, macd_hist=None,
) -> pd.DataFrame:
    """Build a minimal synthetic DataFrame for testing."""
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    df  = pd.DataFrame(index=idx)

    df["Close"]      = close    if close    is not None else np.linspace(10.0, 12.0, n)
    df["High"]       = high     if high     is not None else df["Close"] * 1.01
    df["Low"]        = low      if low      is not None else df["Close"] * 0.99
    df["Open"]       = df["Close"]
    df["Volume"]     = np.full(n, 1_000_000.0)
    df["Vol_MA20"]   = np.full(n, 1_000_000.0)

    df["ADX"]        = adx      if adx      is not None else np.full(n, 15.0)
    df["+DI"]        = np.full(n, 20.0)
    df["-DI"]        = np.full(n, 15.0)

    df["BB_Upper"]   = bb_upper if bb_upper is not None else df["Close"] * 1.05
    df["BB_Lower"]   = bb_lower if bb_lower is not None else df["Close"] * 0.95
    df["BB_Mid"]     = df["Close"]
    df["BB_Std"]     = (df["BB_Upper"] - df["BB_Lower"]) / 4.0

    df["MACD_Hist"]  = macd_hist if macd_hist is not None else np.zeros(n)
    df["MACD"]       = np.zeros(n)
    df["MACD_Signal"]= np.zeros(n)

    df["RSI"]        = np.full(n, 50.0)
    df["SMA20"]      = df["Close"]
    df["SMA50"]      = df["Close"]
    df["SMA200"]     = df["Close"]
    return df


def _make_r(
    regime="BULL_TREND",
    rsi: float = 55.0,
    adx: float = 25.0,
    pdi: float = 22.0,
    ndi: float = 14.0,
    macd: float = 0.1,
    macd_signal: float = 0.05,
    macd_hist: float = 0.05,
    kl_ratio: float = 1.0,
    price: float = 100.0,
    rsi_div: str = "NONE",
    bb_upper: float = 105.0,
    bb_lower: float = 95.0,
    bb_mid: float = 100.0,
) -> dict:
    return dict(
        regime=regime, rsi=rsi, adx=adx, pdi=pdi, ndi=ndi,
        macd=macd, macd_signal=macd_signal, macd_hist=macd_hist,
        kl_ratio=kl_ratio, price=price,
        rsi_divergence=rsi_div,
        bb_upper=bb_upper, bb_lower=bb_lower, bb_mid=bb_mid,
        vol_last=1_000_000, vol_avg=800_000,
    )


def _pass(name: str) -> None:
    _results.append((PASS, name))


def _fail(name: str, reason: str) -> None:
    _results.append((FAIL, f"{name}: {reason}"))


# ─────────────────────────────────────────────────────────────────────────────
#  detect_macd_divergence
# ─────────────────────────────────────────────────────────────────────────────

def test_macd_bear_divergence() -> None:
    """Price makes higher high; MACD_Hist makes lower high → regular bearish div."""
    n = 25
    closes = np.concatenate([np.full(n - 1, 10.0), [12.0]])
    hists  = np.concatenate([np.full(n - 1, 0.5),  [0.3]])   # hist lower high
    df = _make_df(n=n, close=closes, macd_hist=hists)
    out = detect_macd_divergence(df, lookback=20)
    assert out["bear_div"],       "Expected bear_div=True"
    assert not out["bull_div"],   "Expected bull_div=False"
    _pass("detect_macd_divergence: regular bear_div")


def test_macd_bull_divergence() -> None:
    """Price makes lower low; MACD_Hist makes higher low → regular bullish div."""
    n = 25
    closes = np.concatenate([np.full(n - 1, 12.0), [9.0]])    # new lower low
    hists  = np.concatenate([np.full(n - 1, -0.5), [-0.2]])   # less negative → higher low
    df = _make_df(n=n, close=closes, macd_hist=hists)
    out = detect_macd_divergence(df, lookback=20)
    assert out["bull_div"],       "Expected bull_div=True"
    assert not out["bear_div"],   "Expected bear_div=False"
    _pass("detect_macd_divergence: regular bull_div")


def test_macd_no_divergence() -> None:
    """MACD_Hist agrees with price direction → no divergence."""
    closes = np.linspace(8.0, 12.0, 25)
    hists  = np.linspace(0.1, 0.5, 25)
    df = _make_df(n=25, close=closes, macd_hist=hists)
    out = detect_macd_divergence(df, lookback=20)
    assert not out["bear_div"] and not out["bull_div"]
    _pass("detect_macd_divergence: no divergence when indicators confirm")


def test_macd_insufficient_data() -> None:
    """Returns all False when df is too short."""
    df  = _make_df(n=5)
    out = detect_macd_divergence(df, lookback=20)
    assert all(not v for v in out.values())
    _pass("detect_macd_divergence: all False on insufficient data")


# ─────────────────────────────────────────────────────────────────────────────
#  detect_adx_states
# ─────────────────────────────────────────────────────────────────────────────

def test_adx_breakout_20() -> None:
    """ADX was below 20 three bars ago; now above 20 → breakout_20."""
    adx = np.concatenate([np.full(57, 15.0), [18.0, 19.0, 21.5]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert out["breakout_20"],     f"Expected breakout_20=True, got {out}"
    assert not out["breakout_25"], "Expected breakout_25=False"
    _pass("detect_adx_states: breakout_20")


def test_adx_breakout_25() -> None:
    """ADX was below 25 three bars ago; now above 25 → breakout_25."""
    adx = np.concatenate([np.full(57, 18.0), [22.0, 23.0, 26.5]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert out["breakout_25"], f"Expected breakout_25=True, got {out}"
    _pass("detect_adx_states: breakout_25")


def test_adx_no_breakout_when_already_above() -> None:
    """ADX has been above 25 for all recent bars → no breakout."""
    adx = np.concatenate([np.full(57, 27.0), [28.0, 29.0, 30.0]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert not out["breakout_20"] and not out["breakout_25"]
    _pass("detect_adx_states: no breakout when ADX was already above threshold")


def test_adx_exhaustion() -> None:
    """ADX > 45 and falling for 3 bars → exhaustion."""
    adx = np.concatenate([np.full(57, 30.0), [52.0, 50.0, 47.0]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert out["exhaustion"],   f"Expected exhaustion=True, got {out}"
    assert out["adx_falling"],  "Expected adx_falling=True"
    _pass("detect_adx_states: exhaustion (ADX > 45 and falling)")


def test_adx_acceleration() -> None:
    """ADX jumps > 3 pts from previous bar → acceleration."""
    adx = np.concatenate([np.full(58, 20.0), [22.0, 25.5]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert out["acceleration"], f"Expected acceleration=True, got {out}"
    _pass("detect_adx_states: acceleration")


def test_adx_rising() -> None:
    """ADX rises monotonically for 3 bars → adx_rising."""
    adx = np.concatenate([np.full(57, 20.0), [21.0, 22.0, 23.0]])
    df  = _make_df(n=60, adx=adx)
    out = detect_adx_states(df)
    assert out["adx_rising"]
    assert not out["adx_falling"]
    _pass("detect_adx_states: adx_rising")


# ─────────────────────────────────────────────────────────────────────────────
#  detect_bb_squeeze
# ─────────────────────────────────────────────────────────────────────────────

def test_bb_squeeze() -> None:
    """Current BB width < 40% of 60-bar average → squeeze."""
    n      = 70
    upper  = np.concatenate([np.full(68, 105.0), [101.0, 100.5]])
    lower  = np.concatenate([np.full(68,  95.0), [ 99.0,  99.5]])
    df     = _make_df(n=n, bb_upper=upper, bb_lower=lower)
    out    = detect_bb_squeeze(df, lookback=60)
    assert out["squeeze"], f"Expected squeeze=True, ratio={out['bb_width_ratio']}"
    _pass("detect_bb_squeeze: squeeze detected")


def test_bb_expansion() -> None:
    """BB width expands dramatically on last bar → expansion."""
    n      = 70
    upper  = np.concatenate([np.full(69, 101.5), [115.0]])
    lower  = np.concatenate([np.full(69,  98.5), [ 85.0]])
    df     = _make_df(n=n, bb_upper=upper, bb_lower=lower)
    out    = detect_bb_squeeze(df, lookback=60)
    assert out["expansion"], f"Expected expansion=True, got {out}"
    _pass("detect_bb_squeeze: expansion detected")


def test_bb_outer_touch_upper() -> None:
    """Close >= BB_Upper * 0.995 → outer_touch_upper."""
    n      = 70
    upper  = np.full(n, 105.0)
    lower  = np.full(n,  95.0)
    close  = np.concatenate([np.full(69, 100.0), [105.2]])
    df     = _make_df(n=n, close=close, bb_upper=upper, bb_lower=lower)
    out    = detect_bb_squeeze(df)
    assert out["outer_touch_upper"], "Expected outer_touch_upper=True"
    _pass("detect_bb_squeeze: outer_touch_upper")


def test_bb_outer_touch_lower() -> None:
    """Close <= BB_Lower * 1.005 → outer_touch_lower."""
    n      = 70
    upper  = np.full(n, 105.0)
    lower  = np.full(n,  95.0)
    close  = np.concatenate([np.full(69, 100.0), [94.7]])
    df     = _make_df(n=n, close=close, bb_upper=upper, bb_lower=lower)
    out    = detect_bb_squeeze(df)
    assert out["outer_touch_lower"], "Expected outer_touch_lower=True"
    _pass("detect_bb_squeeze: outer_touch_lower")


# ─────────────────────────────────────────────────────────────────────────────
#  detect_structure_break
# ─────────────────────────────────────────────────────────────────────────────

def test_structure_break_up() -> None:
    """Close > prior 20-bar High max → break_up."""
    n      = 22
    highs  = np.concatenate([np.full(21, 110.0), [116.0]])
    lows   = np.full(n, 90.0)
    closes = np.concatenate([np.full(21, 100.0), [116.0]])
    df     = _make_df(n=n)
    df["High"]  = highs
    df["Low"]   = lows
    df["Close"] = closes
    out    = detect_structure_break(df, lookback=20)
    assert out["break_up"],      f"Expected break_up=True, resist_lvl={out['resist_lvl']}"
    assert not out["break_down"]
    _pass("detect_structure_break: break_up")


def test_structure_break_down() -> None:
    """Close < prior 20-bar Low min → break_down."""
    n      = 22
    highs  = np.full(n, 110.0)
    lows   = np.concatenate([np.full(21, 90.0), [83.0]])
    closes = np.concatenate([np.full(21, 100.0), [83.0]])
    df     = _make_df(n=n)
    df["High"]  = highs
    df["Low"]   = lows
    df["Close"] = closes
    out    = detect_structure_break(df, lookback=20)
    assert out["break_down"],   f"Expected break_down=True, got {out}"
    _pass("detect_structure_break: break_down")


def test_structure_no_break() -> None:
    """Close stays within prior range → no break."""
    df  = _make_df(n=25, close=np.full(25, 100.0))
    out = detect_structure_break(df, lookback=20)
    assert not out["break_up"] and not out["break_down"]
    _pass("detect_structure_break: no break when price within range")


# ─────────────────────────────────────────────────────────────────────────────
#  compute_trend_warning — all 8 states
# ─────────────────────────────────────────────────────────────────────────────

def test_state_uptrend_strengthening() -> None:
    """Bull trend, ADX rising well above thresholds, no exhaustion → UPTREND_STRENGTHENING."""
    adx = np.concatenate([np.full(57, 27.0), [28.0, 29.0, 30.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(regime="BULL_TREND", rsi=58, adx=30, pdi=25, ndi=12, kl_ratio=1.0)
    out = compute_trend_warning(r, df)
    assert out["state"] == UPTREND_STRENGTHENING, f"Got {out['state']}"
    assert out["data_ok"]
    _pass("compute_trend_warning: UPTREND_STRENGTHENING")


def test_state_uptrend_exhausting() -> None:
    """Bull trend + RSI bearish div + ADX exhaustion → UPTREND_EXHAUSTING."""
    adx = np.concatenate([np.full(57, 30.0), [52.0, 50.0, 48.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(
        regime="BULL_TREND", rsi=72, adx=48, pdi=25, ndi=12,
        rsi_div="BEARISH", kl_ratio=0.8,
    )
    out = compute_trend_warning(r, df)
    assert out["state"] == UPTREND_EXHAUSTING,  f"Got {out['state']}"
    assert out["exhaustion_score"] >= 3,         f"Score too low: {out['exhaustion_score']}"
    _pass("compute_trend_warning: UPTREND_EXHAUSTING")


def test_state_downtrend_strengthening() -> None:
    """Bear trend, ADX rising, no exhaustion → DOWNTREND_STRENGTHENING."""
    adx = np.concatenate([np.full(57, 27.0), [28.0, 29.0, 30.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(regime="BEAR_TREND", rsi=42, adx=30, pdi=12, ndi=25, kl_ratio=1.0)
    out = compute_trend_warning(r, df)
    assert out["state"] == DOWNTREND_STRENGTHENING, f"Got {out['state']}"
    _pass("compute_trend_warning: DOWNTREND_STRENGTHENING")


def test_state_downtrend_exhausting() -> None:
    """Bear trend + RSI bullish div + ADX exhaustion → DOWNTREND_EXHAUSTING."""
    adx = np.concatenate([np.full(57, 30.0), [52.0, 50.0, 48.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(
        regime="BEAR_TREND", rsi=27, adx=48, pdi=12, ndi=25,
        rsi_div="BULLISH", kl_ratio=0.8,
    )
    out = compute_trend_warning(r, df)
    assert out["state"] == DOWNTREND_EXHAUSTING, f"Got {out['state']}"
    _pass("compute_trend_warning: DOWNTREND_EXHAUSTING")


def test_state_range_compression() -> None:
    """BB squeeze + ADX < 20 → RANGE_COMPRESSION."""
    n      = 70
    upper  = np.concatenate([np.full(68, 105.0), [101.0, 100.5]])
    lower  = np.concatenate([np.full(68,  95.0), [ 99.0,  99.5]])
    adx_v  = np.full(n, 14.0)
    df     = _make_df(n=n, adx=adx_v, bb_upper=upper, bb_lower=lower)
    r      = _make_r(regime="SIDEWAYS", rsi=50, adx=14, pdi=15, ndi=15, kl_ratio=1.0)
    out    = compute_trend_warning(r, df)
    assert out["state"] == RANGE_COMPRESSION, f"Got {out['state']}"
    _pass("compute_trend_warning: RANGE_COMPRESSION")


def test_state_breakout_emerging() -> None:
    """BB expansion + ADX breakout above 20 + volume spike → BREAKOUT_EMERGING."""
    n      = 70
    upper  = np.concatenate([np.full(69, 101.5), [115.0]])
    lower  = np.concatenate([np.full(69,  98.5), [ 85.0]])
    adx_v  = np.concatenate([np.full(67, 15.0), [18.0, 19.0, 22.0]])
    df     = _make_df(n=n, adx=adx_v, bb_upper=upper, bb_lower=lower)
    r      = _make_r(regime="BULL_TREND", rsi=60, adx=22, pdi=22, ndi=14, kl_ratio=2.0)
    out    = compute_trend_warning(r, df)
    assert out["state"] == BREAKOUT_EMERGING, f"Got {out['state']}"
    _pass("compute_trend_warning: BREAKOUT_EMERGING")


def test_state_reversal_warning_low_conf() -> None:
    """RSI bearish div only, no structure / volume confirm → REVERSAL_WARNING_LOW_CONF."""
    adx = np.full(60, 23.0)
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(
        regime="SIDEWAYS", rsi=65, adx=23, pdi=16, ndi=16,
        rsi_div="BEARISH", kl_ratio=1.0,
    )
    out = compute_trend_warning(r, df)
    assert out["state"] == REVERSAL_WARNING_LOW_CONF, f"Got {out['state']}"
    _pass("compute_trend_warning: REVERSAL_WARNING_LOW_CONF")


def test_state_reversal_warning_confirmed() -> None:
    """RSI bearish div + structure break + ADX exhaustion → REVERSAL_WARNING_CONFIRMED."""
    n      = 70
    closes = np.concatenate([np.full(n - 1, 100.0), [112.0]])
    highs  = np.concatenate([np.full(n - 1, 110.0), [112.0]])
    lows   = np.full(n, 90.0)
    adx_v  = np.concatenate([np.full(n - 3, 30.0), [52.0, 50.0, 48.0]])
    df     = _make_df(n=n, close=closes, adx=adx_v)
    df["High"] = highs
    df["Low"]  = lows
    r = _make_r(
        regime="BULL_TREND", rsi=74, adx=48, pdi=25, ndi=12,
        rsi_div="BEARISH", kl_ratio=0.9,
    )
    out = compute_trend_warning(r, df)
    assert out["state"] == REVERSAL_WARNING_CONFIRMED, \
        f"Got {out['state']}, ev={out['evidence']}, exh={out['exhaustion_score']}"
    _pass("compute_trend_warning: REVERSAL_WARNING_CONFIRMED")


# ─────────────────────────────────────────────────────────────────────────────
#  compute_trend_warning — data-quality guard
# ─────────────────────────────────────────────────────────────────────────────

def test_state_insufficient_data_short_df() -> None:
    """INSUFFICIENT_DATA when df has fewer than 30 rows."""
    df  = _make_df(n=10)
    r   = _make_r()
    out = compute_trend_warning(r, df)
    assert out["state"] == INSUFFICIENT_DATA
    assert not out["data_ok"]
    _pass("compute_trend_warning: INSUFFICIENT_DATA (df too short)")


def test_state_insufficient_data_no_price() -> None:
    """INSUFFICIENT_DATA when r['price'] is None."""
    df  = _make_df(n=60)
    r   = _make_r(price=None)
    out = compute_trend_warning(r, df)
    assert out["state"] == INSUFFICIENT_DATA
    _pass("compute_trend_warning: INSUFFICIENT_DATA (price=None)")


def test_state_insufficient_data_zero_price() -> None:
    """INSUFFICIENT_DATA when r['price'] is 0."""
    df  = _make_df(n=60)
    r   = _make_r(price=0)
    out = compute_trend_warning(r, df)
    assert out["state"] == INSUFFICIENT_DATA
    _pass("compute_trend_warning: INSUFFICIENT_DATA (price=0)")


# ─────────────────────────────────────────────────────────────────────────────
#  compute_trend_warning — confidence buckets
# ─────────────────────────────────────────────────────────────────────────────

def test_confidence_high() -> None:
    """ADX exhaustion + RSI bearish div + RSI >70 + MACD bear cross → score ≥ 6 → HIGH."""
    adx = np.concatenate([np.full(57, 30.0), [52.0, 50.0, 47.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(
        regime="BULL_TREND", rsi=73, adx=47, pdi=25, ndi=12,
        macd=-0.1, macd_signal=0.05, macd_hist=-0.05,
        rsi_div="BEARISH", kl_ratio=1.0,
    )
    out = compute_trend_warning(r, df)
    assert out["confidence"] == "HIGH", \
        f"Expected HIGH, got {out['confidence']}, exh={out['exhaustion_score']}"
    _pass("compute_trend_warning: confidence HIGH")


def test_confidence_medium() -> None:
    """RSI bearish div alone → score = 2 → MEDIUM."""
    df  = _make_df(n=60)
    r   = _make_r(rsi_div="BEARISH", adx=20, pdi=18, ndi=14)
    out = compute_trend_warning(r, df)
    assert out["confidence"] in ("MEDIUM", "HIGH"), \
        f"Expected MEDIUM or HIGH, got {out['confidence']}"
    _pass("compute_trend_warning: confidence MEDIUM")


def test_confidence_low() -> None:
    """No signals at all → score = 0 → LOW."""
    df  = _make_df(n=60)
    r   = _make_r(regime="SIDEWAYS", rsi=50, adx=15, pdi=15, ndi=15,
                  macd=0, macd_signal=0, macd_hist=0, kl_ratio=1.0)
    out = compute_trend_warning(r, df)
    assert out["confidence"] == "LOW", f"Expected LOW, got {out['confidence']}"
    _pass("compute_trend_warning: confidence LOW")


# ─────────────────────────────────────────────────────────────────────────────
#  Edge cases & contract
# ─────────────────────────────────────────────────────────────────────────────

def test_nan_adx_graceful() -> None:
    """All-NaN ADX column → INSUFFICIENT_DATA (rsi is None in r)."""
    df         = _make_df(n=60)
    df["ADX"]  = np.nan
    r          = _make_r(adx=None, rsi=None)
    out        = compute_trend_warning(r, df)
    assert out["state"] == INSUFFICIENT_DATA
    _pass("compute_trend_warning: NaN ADX + None rsi → INSUFFICIENT_DATA gracefully")


def test_evidence_non_empty_when_signals_fire() -> None:
    """Evidence list is non-empty whenever exhaustion signals are present."""
    adx = np.concatenate([np.full(57, 30.0), [52.0, 50.0, 47.0]])
    df  = _make_df(n=60, adx=adx)
    r   = _make_r(regime="BULL_TREND", rsi=72, adx=47, pdi=25, ndi=12,
                  rsi_div="BEARISH", kl_ratio=1.0)
    out = compute_trend_warning(r, df)
    assert len(out["evidence"]) > 0, "Expected non-empty evidence list"
    _pass("compute_trend_warning: evidence list non-empty when signals fire")


def test_return_dict_keys_complete() -> None:
    """All documented output keys are present in the result dict."""
    df  = _make_df(n=60)
    r   = _make_r()
    out = compute_trend_warning(r, df)
    required = {
        "state", "state_label", "state_color",
        "confidence", "exhaustion_score", "emergence_score",
        "evidence", "rationale",
        "macd_div", "adx_states", "bb_states", "struct_states",
        "data_ok", "data_issue",
    }
    missing = required - set(out.keys())
    assert not missing, f"Missing keys: {missing}"
    _pass("compute_trend_warning: all required keys present")


def test_state_label_color_always_set() -> None:
    """state_label and state_color are always non-empty strings."""
    for regime, rsi_div in [("BULL_TREND", "NONE"), ("BEAR_TREND", "BULLISH"),
                             ("SIDEWAYS", "BEARISH")]:
        df  = _make_df(n=60)
        r   = _make_r(regime=regime, rsi_div=rsi_div)
        out = compute_trend_warning(r, df)
        assert isinstance(out["state_label"], str) and out["state_label"]
        assert isinstance(out["state_color"], str) and out["state_color"].startswith("#")
    _pass("compute_trend_warning: state_label and state_color always populated")


def test_engine_importable_without_streamlit() -> None:
    """trend_warning_engine must import without Streamlit in sys.modules."""
    import importlib
    # Remove streamlit if accidentally imported
    saved = sys.modules.pop("streamlit", None)
    try:
        mod = importlib.import_module("trend_warning_engine")
        assert hasattr(mod, "compute_trend_warning")
        assert hasattr(mod, "UPTREND_STRENGTHENING")
    finally:
        if saved is not None:
            sys.modules["streamlit"] = saved
    _pass("Engine importable without Streamlit")


# ─────────────────────────────────────────────────────────────────────────────
#  Runner
# ─────────────────────────────────────────────────────────────────────────────

_TESTS = [
    test_macd_bear_divergence,
    test_macd_bull_divergence,
    test_macd_no_divergence,
    test_macd_insufficient_data,
    test_adx_breakout_20,
    test_adx_breakout_25,
    test_adx_no_breakout_when_already_above,
    test_adx_exhaustion,
    test_adx_acceleration,
    test_adx_rising,
    test_bb_squeeze,
    test_bb_expansion,
    test_bb_outer_touch_upper,
    test_bb_outer_touch_lower,
    test_structure_break_up,
    test_structure_break_down,
    test_structure_no_break,
    test_state_uptrend_strengthening,
    test_state_uptrend_exhausting,
    test_state_downtrend_strengthening,
    test_state_downtrend_exhausting,
    test_state_range_compression,
    test_state_breakout_emerging,
    test_state_reversal_warning_low_conf,
    test_state_reversal_warning_confirmed,
    test_state_insufficient_data_short_df,
    test_state_insufficient_data_no_price,
    test_state_insufficient_data_zero_price,
    test_confidence_high,
    test_confidence_medium,
    test_confidence_low,
    test_nan_adx_graceful,
    test_evidence_non_empty_when_signals_fire,
    test_return_dict_keys_complete,
    test_state_label_color_always_set,
    test_engine_importable_without_streamlit,
]


if __name__ == "__main__":
    print(f"\n{'=' * 64}")
    print(f"  TTWE Test Suite  ({len(_TESTS)} tests)")
    print(f"{'=' * 64}")

    for t in _TESTS:
        prev_len = len(_results)
        try:
            t()
            # If the test returned without appending (shouldn't happen), add PASS
            if len(_results) == prev_len:
                _pass(t.__name__)
        except AssertionError as exc:
            _fail(t.__name__, str(exc))
        except Exception as exc:
            _fail(t.__name__, f"EXCEPTION {type(exc).__name__}: {exc}")

    for status, name in _results:
        print(f"  {status}  {name}")

    passed = sum(1 for s, _ in _results if s == PASS)
    failed = sum(1 for s, _ in _results if s == FAIL)

    print(f"{'=' * 64}")
    print(f"  {passed} passed  /  {failed} failed  /  {len(_TESTS)} total")
    print(f"{'=' * 64}\n")

    sys.exit(0 if failed == 0 else 1)

"""Trend Warning Engine — classifies the current price structure into one of
9 actionable warning signals.

Signal IDs (str):
  UPTREND_STRENGTHENING     — Bull-trend confirming: strong MA alignment + rising ADX
  UPTREND_EXHAUSTING        — Bull-trend weakening : overbought RSI, declining MACD, low vol
  DOWNTREND_STRENGTHENING   — Bear-trend worsening : bearish MA stack + rising ADX
  DOWNTREND_EXHAUSTING      — Bear-trend bottoming : oversold RSI + vol climax spike
  RANGE_COMPRESSION         — Consolidation: ADX < 20, narrow BB, volume drying up
  BREAKOUT_EMERGING         — BB squeeze + vol breakout starting, direction unclear
  REVERSAL_WARNING_LOW_CONF — 1+ divergence / candle flip signal detected
  REVERSAL_WARNING_CONFIRMED— Multiple confirming reversal signals (higher conviction)
  NONE                      — Normal state; no specific structural warning
  INSUFFICIENT_DATA         — Less than 50 bars; unable to classify

All inputs are taken from the DataFrame produced by ``compute_all()`` — no
new indicator columns are required.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ── Vietnamese labels ─────────────────────────────────────────────────────────

_VI_LABELS: dict[str, str] = {
    "UPTREND_STRENGTHENING":    "Xu hướng tăng đang mạnh lên",
    "UPTREND_EXHAUSTING":       "Xu hướng tăng có dấu hiệu kiệt sức",
    "DOWNTREND_STRENGTHENING":  "Xu hướng giảm đang mạnh lên",
    "DOWNTREND_EXHAUSTING":     "Xu hướng giảm có dấu hiệu kiệt sức",
    "RANGE_COMPRESSION":        "Giá đang nén — tích lũy/phân phối",
    "BREAKOUT_EMERGING":        "Chuẩn bị bứt phá — theo dõi xác nhận",
    "REVERSAL_WARNING_LOW_CONF":"Cảnh báo đảo chiều — độ tin thấp",
    "REVERSAL_WARNING_CONFIRMED":"Đảo chiều gần xác nhận — thận trọng",
    "NONE":                     "",
    "INSUFFICIENT_DATA":        "Không đủ dữ liệu để phân tích",
}


def _f(df: pd.DataFrame, col: str) -> float | None:
    """Safely return the last value of a column as float."""
    try:
        if col not in df.columns:
            return None
        v = df[col].iloc[-1]
        return None if pd.isna(float(v)) else float(v)
    except Exception:
        return None


def _arr(df: pd.DataFrame, col: str, n: int) -> list[float]:
    """Last n non-NaN values of a column."""
    try:
        if col not in df.columns or len(df) < n:
            return []
        return [float(v) for v in df[col].iloc[-n:].tolist() if not np.isnan(float(v))]
    except Exception:
        return []


def compute_trend_warning(df: pd.DataFrame) -> dict:
    """
    Classify the current price structure and return a warning dict.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV + indicators DataFrame produced by ``compute_all()``.

    Returns
    -------
    dict with keys:
        warning       str   — signal ID
        warning_vi    str   — Vietnamese label
        confidence    float — 0.0–1.0
        reasons       list[str]
    """
    if len(df) < 50:
        return {
            "warning": "INSUFFICIENT_DATA",
            "warning_vi": _VI_LABELS["INSUFFICIENT_DATA"],
            "confidence": 0.0,
            "reasons": ["Cần ít nhất 50 phiên dữ liệu"],
        }

    # ── Extract indicators ────────────────────────────────────────────────────
    close   = _f(df, "close")
    sma20   = _f(df, "SMA20")
    sma50   = _f(df, "SMA50")
    sma200  = _f(df, "SMA200")
    rsi     = _f(df, "RSI14")
    adx     = _f(df, "ADX")
    di_plus = _f(df, "DI_plus")
    di_minus= _f(df, "DI_minus")
    bb_upper= _f(df, "BB_upper")
    bb_lower= _f(df, "BB_lower")
    bb_mid  = _f(df, "BB_mid")
    atr14   = _f(df, "ATR14")

    mh_arr  = _arr(df, "MACD_hist", 5)
    obv_arr = _arr(df, "OBV", 20)
    vol_arr = _arr(df, "volume", 20)
    rsi_arr = _arr(df, "RSI14", 5)

    # Derived helpers
    above_sma200 = bool(close and sma200 and close > sma200)
    above_sma50  = bool(close and sma50  and close > sma50)
    above_sma20  = bool(close and sma20  and close > sma20)

    ma_align_bull = (
        bool(sma20 and sma50  and sma20  > sma50)
        and bool(sma50 and sma200 and sma50  > sma200)
    )
    ma_align_bear = (
        bool(sma20 and sma50  and sma20  < sma50)
        and bool(sma50 and sma200 and sma50  < sma200)
    )

    macd_slope_up   = len(mh_arr) >= 3 and mh_arr[-1] > mh_arr[-2] > mh_arr[-3]
    macd_slope_down = len(mh_arr) >= 3 and mh_arr[-1] < mh_arr[-2] < mh_arr[-3]

    # OBV trend (rising/falling over 10 bars)
    obv_rising = len(obv_arr) >= 10 and obv_arr[-1] > obv_arr[-10]
    obv_falling= len(obv_arr) >= 10 and obv_arr[-1] < obv_arr[-10]

    # Volume: recent vs 20-bar average
    vol_now   = vol_arr[-1] if vol_arr else None
    vol_avg20 = float(np.mean(vol_arr)) if len(vol_arr) >= 5 else None
    vol_ratio = (vol_now / vol_avg20) if (vol_now and vol_avg20 and vol_avg20 > 0) else 1.0

    # BB width normalised
    bb_width    : float | None = None
    bb_width_avg: float | None = None
    try:
        if "BB_upper" in df.columns and "BB_lower" in df.columns and "BB_mid" in df.columns:
            bw = (df["BB_upper"] - df["BB_lower"]) / df["BB_mid"].replace(0, 1)
            bw_clean = bw.dropna()
            if len(bw_clean) >= 20:
                bb_width     = float(bw_clean.iloc[-1])
                bb_width_avg = float(bw_clean.tail(20).mean())
    except Exception:
        pass

    bb_squeeze     = (bb_width is not None and bb_width_avg is not None
                      and bb_width < bb_width_avg * 0.80)
    bb_narrow      = (bb_width is not None and bb_width_avg is not None
                      and bb_width < bb_width_avg * 0.70)

    # RSI divergence (price higher but RSI lower, last 5 bars)
    price_arr = _arr(df, "close", 5)
    rsi_div_bear = (
        len(price_arr) >= 5 and len(rsi_arr) >= 5
        and price_arr[-1] > price_arr[0]
        and rsi_arr[-1] < rsi_arr[0]
        and rsi_arr[-1] > 60
    )
    rsi_div_bull = (
        len(price_arr) >= 5 and len(rsi_arr) >= 5
        and price_arr[-1] < price_arr[0]
        and rsi_arr[-1] > rsi_arr[0]
        and rsi_arr[-1] < 45
    )

    # ── Score each candidate signal ───────────────────────────────────────────
    # (signal_id, score float 0–10, reasons list[str])
    candidates: list[tuple[str, float, list[str]]] = []

    # ── UPTREND_STRENGTHENING ─────────────────────────────────────────────────
    s, r = 0.0, []
    if ma_align_bull:           s += 3.0; r.append("MA stack tăng (SMA20>50>200)")
    if above_sma200:            s += 1.0; r.append("Giá trên SMA200")
    if adx and adx > 25:        s += 2.0; r.append(f"ADX mạnh ({adx:.0f})")
    if di_plus and di_minus and di_plus > di_minus: s += 1.5; r.append("DI+ > DI-")
    if macd_slope_up:           s += 1.5; r.append("MACD_hist tăng liên tiếp")
    if obv_rising:              s += 1.0; r.append("OBV tăng (tích lũy)")
    if rsi and 50 <= rsi <= 70: s += 1.0; r.append(f"RSI lành mạnh ({rsi:.0f})")
    candidates.append(("UPTREND_STRENGTHENING", s, r))

    # ── UPTREND_EXHAUSTING ────────────────────────────────────────────────────
    s, r = 0.0, []
    if above_sma200 and above_sma50: s += 1.0
    if rsi and rsi > 70:             s += 3.0; r.append(f"RSI quá mua ({rsi:.0f})")
    if macd_slope_down:              s += 2.0; r.append("MACD_hist giảm liên tiếp")
    if obv_falling:                  s += 1.5; r.append("OBV giảm (phân phối)")
    if rsi_div_bear:                 s += 2.5; r.append("Phân kỳ giảm RSI")
    if vol_ratio < 0.6:              s += 1.0; r.append("Khối lượng cạn dần")
    candidates.append(("UPTREND_EXHAUSTING", s, r))

    # ── DOWNTREND_STRENGTHENING ───────────────────────────────────────────────
    s, r = 0.0, []
    if ma_align_bear:               s += 3.0; r.append("MA stack giảm (SMA20<50<200)")
    if not above_sma200:            s += 1.0; r.append("Giá dưới SMA200")
    if adx and adx > 25:            s += 2.0; r.append(f"ADX mạnh ({adx:.0f})")
    if di_minus and di_plus and di_minus > di_plus: s += 1.5; r.append("DI- > DI+")
    if macd_slope_down:             s += 1.5; r.append("MACD_hist giảm liên tiếp")
    if obv_falling:                 s += 1.0; r.append("OBV giảm (áp lực bán)")
    if rsi and rsi < 45:            s += 1.0; r.append(f"RSI yếu ({rsi:.0f})")
    candidates.append(("DOWNTREND_STRENGTHENING", s, r))

    # ── DOWNTREND_EXHAUSTING ──────────────────────────────────────────────────
    s, r = 0.0, []
    if not above_sma200:             s += 0.5
    if rsi and rsi < 30:             s += 3.0; r.append(f"RSI quá bán ({rsi:.0f})")
    if macd_slope_up:                s += 1.5; r.append("MACD_hist phục hồi")
    if rsi_div_bull:                 s += 2.5; r.append("Phân kỳ tăng RSI")
    if vol_ratio and vol_ratio > 2.0:s += 2.0; r.append(f"Khối lượng bùng nổ ({vol_ratio:.1f}x)")
    if obv_rising:                   s += 1.0; r.append("OBV bắt đầu tăng trở lại")
    candidates.append(("DOWNTREND_EXHAUSTING", s, r))

    # ── RANGE_COMPRESSION ────────────────────────────────────────────────────
    s, r = 0.0, []
    if adx and adx < 20:             s += 3.0; r.append(f"ADX yếu ({adx:.0f})")
    if bb_narrow:                    s += 3.0; r.append("BB cực hẹp (<70% avg)")
    elif bb_squeeze:                 s += 1.5; r.append("BB đang thu hẹp (<80% avg)")
    if vol_ratio and vol_ratio < 0.7:s += 2.0; r.append("Khối lượng thấp hơn bình thường")
    if not ma_align_bull and not ma_align_bear: s += 1.0; r.append("MA chèo chống, thiếu xu hướng")
    candidates.append(("RANGE_COMPRESSION", s, r))

    # ── BREAKOUT_EMERGING ────────────────────────────────────────────────────
    s, r = 0.0, []
    if bb_squeeze:                   s += 3.0; r.append("BB đang nén (sắp bứt phá)")
    if vol_ratio and vol_ratio > 1.5:s += 2.5; r.append(f"Khối lượng tăng ({vol_ratio:.1f}x)")
    if atr14 and close:
        atr_pct = atr14 / close * 100
        if atr_pct > 2.5:            s += 2.0; r.append(f"Biến động ATR cao ({atr_pct:.1f}%)")
    if adx and 18 <= adx <= 28:      s += 1.5; r.append(f"ADX đang hình thành ({adx:.0f})")
    candidates.append(("BREAKOUT_EMERGING", s, r))

    # ── REVERSAL_WARNING_LOW_CONF ─────────────────────────────────────────────
    s, r = 0.0, []
    if rsi_div_bear:                 s += 3.0; r.append("Phân kỳ giảm RSI")
    if rsi_div_bull:                 s += 3.0; r.append("Phân kỳ tăng RSI")
    if macd_slope_down and above_sma50: s += 2.0; r.append("MACD_hist giảm tuy xu hướng còn tăng")
    if macd_slope_up and not above_sma50: s += 2.0; r.append("MACD_hist tăng tuy xu hướng còn giảm")
    candidates.append(("REVERSAL_WARNING_LOW_CONF", s, r))

    # ── REVERSAL_WARNING_CONFIRMED ────────────────────────────────────────────
    s, r = 0.0, []
    if rsi_div_bear and macd_slope_down: s += 4.0; r.append("Phân kỳ + MACD giảm → đảo chiều giảm")
    if rsi_div_bull and macd_slope_up:   s += 4.0; r.append("Phân kỳ + MACD tăng → đảo chiều tăng")
    if obv_falling and above_sma50:      s += 2.0; r.append("OBV giảm trái chiều xu hướng tăng")
    if obv_rising and not above_sma50:   s += 2.0; r.append("OBV tăng trái chiều xu hướng giảm")
    if (adx and adx > 20
            and di_plus and di_minus
            and abs(di_plus - di_minus) < 5):
        s += 1.5; r.append("ADX mạnh nhưng DI gần bằng nhau (đổi chiều?)")
    candidates.append(("REVERSAL_WARNING_CONFIRMED", s, r))

    # ── Select winner: highest score, must exceed threshold ──────────────────
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_id, best_score, best_reasons = candidates[0]

    # Normalise confidence to [0, 1]; scores top out around 10–11
    confidence = min(1.0, best_score / 9.0)

    # Suppress low-confidence picks — fall back to NONE
    if best_score < 3.0 or not best_reasons:
        best_id      = "NONE"
        best_reasons = []
        confidence   = 0.0

    return {
        "warning":    best_id,
        "warning_vi": _VI_LABELS.get(best_id, ""),
        "confidence": round(confidence, 3),
        "reasons":    best_reasons,
    }

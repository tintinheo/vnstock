"""Intraday Cumulative Volume Delta (CVD) engine.

Computes real-flow CVD when buy/sell aggressor volume columns (bu, sd) are
available (FiinQuant data), or falls back to an OHLCV sign proxy when only
standard OHLCV bars are present.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_score(v: float) -> float:
    """Clamp to [0.0, 10.0] and round to 1 dp."""
    return round(float(np.clip(v, 0.0, 10.0)), 1)


def compute_intraday_cvd(bars_df: pd.DataFrame) -> dict:
    """Compute intraday CVD metrics from a bar DataFrame.

    If columns ``bu`` and ``sd`` are present (FiinQuant realtime data),
    real buy/sell aggressor volume is used.  Otherwise a signed-volume
    proxy is derived from (close − open) × volume.

    Args:
        bars_df: OHLCV DataFrame, optionally with ``bu``/``sd`` columns.

    Returns:
        Dict with keys:
          cvd_raw               — signed float; ∑(buy_vol − sell_vol).
                                  Passed directly to compute_smart_money_score
                                  as ``cvd_today``.
          cvd_score             — display score 0–10 (5 = neutral)
          cvd_signal            — "BUYING" | "NEUTRAL" | "DISTRIBUTING"
          cvd_divergence        — "BULLISH_DIV" | "BEARISH_DIV" | "NONE"
          buying_pressure_pct   — % bars with positive delta
          data_quality          — "REAL_FLOW" | "OHLCV_PROXY"
          cvd_trend             — "RISING" | "FALLING" | "FLAT"
    """
    _defaults: dict = {
        "cvd_raw": 0.0,
        "cvd_score": 5.0,
        "cvd_signal": "NEUTRAL",
        "cvd_divergence": "NONE",
        "buying_pressure_pct": 50.0,
        "data_quality": "NONE",
        "cvd_trend": "FLAT",
    }

    if bars_df is None or bars_df.empty:
        return _defaults

    df = bars_df.copy()
    df.columns = [c.lower() for c in df.columns]

    # ── Determine delta vector ────────────────────────────────────────────────
    has_real_flow = "bu" in df.columns and "sd" in df.columns
    if has_real_flow:
        delta = df["bu"].fillna(0) - df["sd"].fillna(0)
        data_quality = "REAL_FLOW"
    else:
        if not {"close", "open", "volume"}.issubset(df.columns):
            return _defaults
        direction = np.sign(df["close"] - df["open"]).fillna(0)
        delta = direction * df["volume"].fillna(0)
        data_quality = "OHLCV_PROXY"

    if delta.empty:
        return _defaults

    cvd_raw = float(delta.sum())
    total_vol = float(df["volume"].fillna(0).sum()) if "volume" in df.columns else float(delta.abs().sum())
    if total_vol <= 0:
        total_vol = 1.0  # guard against divide-by-zero

    # ── CVD score (0 = all-selling, 5 = neutral, 10 = all-buying) ────────────
    ratio = cvd_raw / total_vol          # ≈ in range [−1, 1]
    cvd_score = _safe_score((ratio + 1) / 2 * 10)

    # ── Signal (±5 % of total volume) ────────────────────────────────────────
    threshold = total_vol * 0.05
    if cvd_raw > threshold:
        cvd_signal = "BUYING"
    elif cvd_raw < -threshold:
        cvd_signal = "DISTRIBUTING"
    else:
        cvd_signal = "NEUTRAL"

    # ── Divergence ───────────────────────────────────────────────────────────
    first_open = float(df["open"].iloc[0]) if "open" in df.columns else float(df["close"].iloc[0])
    last_close = float(df["close"].iloc[-1])
    price_change = last_close - first_open
    if cvd_raw > 0 and price_change < 0:
        cvd_divergence = "BULLISH_DIV"    # money flows in while price drops
    elif cvd_raw < 0 and price_change > 0:
        cvd_divergence = "BEARISH_DIV"    # distribution while price rises
    else:
        cvd_divergence = "NONE"

    # ── Buying pressure % ────────────────────────────────────────────────────
    buying_pressure_pct = round(float((delta > 0).mean() * 100), 1)

    # ── CVD trend (slope of cumsum over last ≤10 bars) ───────────────────────
    cvd_trend = "FLAT"
    if len(delta) >= 3:
        cumsum = delta.cumsum()
        tail = cumsum.tail(min(10, len(cumsum)))
        slope = np.polyfit(range(len(tail)), tail.values.astype(float), 1)[0]
        slope_threshold = total_vol * 0.001
        if slope > slope_threshold:
            cvd_trend = "RISING"
        elif slope < -slope_threshold:
            cvd_trend = "FALLING"

    return {
        "cvd_raw": cvd_raw,
        "cvd_score": cvd_score,
        "cvd_signal": cvd_signal,
        "cvd_divergence": cvd_divergence,
        "buying_pressure_pct": buying_pressure_pct,
        "data_quality": data_quality,
        "cvd_trend": cvd_trend,
    }

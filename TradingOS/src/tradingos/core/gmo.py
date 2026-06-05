"""GMO — Global Market Omega + HMM State Detection (SRS §2, Module 1)."""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── Simple HMM State (3-state: STEADY_BULL / TRANSITIONAL / STEADY_BEAR) ─────

def detect_hmm_state(df: pd.DataFrame, lookback: int = 60) -> str:
    """
    Simplified HMM-like state detection using price momentum + volatility regime.
    Returns: STEADY_BULL | TRANSITIONAL | STEADY_BEAR
    """
    if len(df) < lookback:
        return "TRANSITIONAL"

    recent = df.tail(lookback)
    close = recent["close"]

    # Price trend
    trend = close.iloc[-1] / close.iloc[0] - 1

    # Volatility (normalised ATR)
    if "ATR14" in recent.columns:
        atr_norm = recent["ATR14"].iloc[-1] / max(close.iloc[-1], 1)
    else:
        atr_norm = (recent["high"] - recent["low"]).mean() / max(close.mean(), 1)

    # RSI trend confirmation
    if "RSI14" in recent.columns:
        rsi_avg = recent["RSI14"].tail(10).mean()
        rsi_bull = rsi_avg > 55
        rsi_bear = rsi_avg < 45
    else:
        rsi_bull = trend > 0.03
        rsi_bear = trend < -0.03

    # OBV confirmation
    if "OBV" in recent.columns:
        obv_trend = recent["OBV"].iloc[-1] / max(abs(recent["OBV"].iloc[0]), 1) - 1
        obv_confirm = obv_trend > 0.02
    else:
        obv_confirm = trend > 0

    if trend > 0.04 and rsi_bull and obv_confirm and atr_norm < 0.025:
        return "STEADY_BULL"
    elif trend < -0.04 and rsi_bear and not obv_confirm:
        return "STEADY_BEAR"
    else:
        return "TRANSITIONAL"


# ── Omega (Market Breadth Proxy) ──────────────────────────────────────────────

def compute_omega(
    df: pd.DataFrame,
    vn30_df: pd.DataFrame | None = None,
) -> float:
    """
    GMO Omega: proxy for market breadth / institutional conviction.
    Range 0.0 – 1.0; > 0.5 = bullish market regime.

    If vn30_df provided, uses VN30 correlation.
    Otherwise uses local Hurst + RSI proxy.
    """
    if df.empty:
        return 0.5

    score = 0.0
    count = 0

    # Hurst > 0.55 = trending
    if "Hurst" in df.columns:
        h = float(df["Hurst"].iloc[-1])
        score += min(h, 1.0)
        count += 1

    # RSI above 50
    if "RSI14" in df.columns and len(df) >= 14:
        rsi_now = float(df["RSI14"].iloc[-1])
        score += min(rsi_now / 100, 1.0)
        count += 1

    # Price above SMA50
    if "SMA50" in df.columns:
        above = float(df["close"].iloc[-1] > df["SMA50"].iloc[-1])
        score += above
        count += 1

    # VN30 corelation if available
    if vn30_df is not None and not vn30_df.empty and len(vn30_df) >= 5:
        vn30_trend = vn30_df["close"].iloc[-1] / vn30_df["close"].iloc[-5] - 1
        score += float(np.clip(vn30_trend * 10 + 0.5, 0, 1))
        count += 1

    return round(score / max(count, 1), 2)


# ── VN30F Basis ───────────────────────────────────────────────────────────────

def compute_vn30f_basis(spot_price: float, futures_price: float) -> dict:
    """
    VN30F basis = (futures - spot) / spot.
    Positive basis = bullish premium; negative = contango discount.
    """
    if spot_price <= 0:
        return {"basis_pct": 0.0, "signal": "NEUTRAL"}
    basis_pct = (futures_price - spot_price) / spot_price * 100
    if basis_pct > 0.5:
        signal = "BULLISH_PREMIUM"
    elif basis_pct < -0.5:
        signal = "BEARISH_DISCOUNT"
    else:
        signal = "NEUTRAL"
    return {"basis_pct": round(basis_pct, 2), "signal": signal}

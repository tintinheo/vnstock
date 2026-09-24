import pandas as pd

from app.models import Regime


def detect_regime(features: pd.DataFrame) -> Regime:
    latest = features.iloc[-1]
    close = latest["close"]
    sma_20 = latest.get("sma_20")
    sma_50 = latest.get("sma_50")
    adx_14 = latest.get("adx_14")
    vol = latest.get("volatility_20")

    if pd.isna(sma_20) or pd.isna(sma_50):
        return Regime.unknown
    if pd.notna(vol) and vol > 0.65:
        return Regime.volatile
    if close > sma_20 > sma_50 and pd.notna(adx_14) and adx_14 >= 18:
        return Regime.uptrend
    if close < sma_20 < sma_50 and pd.notna(adx_14) and adx_14 >= 18:
        return Regime.downtrend
    return Regime.sideway


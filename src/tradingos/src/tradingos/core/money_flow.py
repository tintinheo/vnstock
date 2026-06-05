import pandas as pd
import numpy as np

def compute_multiday_whale_flow(daily_flow_df: pd.DataFrame, lookback_days: int = 20) -> dict:
    """Computes multi-day cumulative volume delta (M-CVD) and its trend."""
    if len(daily_flow_df) < lookback_days:
        return {"mcvd_5d": 0, "mcvd_20d": 0, "mcvd_trend": "FLAT", "mcvd_vs_price": "UNKNOWN", "consistency": 0.5}

    recent = daily_flow_df.tail(lookback_days)
    whale_series = recent['whale_net'].fillna(0)

    mcvd_5d = int(whale_series.tail(5).sum())
    mcvd_20d = int(whale_series.sum())

    x = np.arange(len(whale_series))
    slope, _ = np.polyfit(x, whale_series.values, 1)
    
    # Normalize slope by average daily shares
    avg_daily_shares = recent['volume'].mean() if 'volume' in recent else 1e-9
    slope_normalized = slope / max(avg_daily_shares / lookback_days, 1)

    if slope_normalized > 0.01:
        mcvd_trend = "UP"
    elif slope_normalized < -0.01:
        mcvd_trend = "DOWN"
    else:
        mcvd_trend = "FLAT"

    price_slope = (recent['close'].iloc[-1] / recent['close'].iloc[0]) - 1 if 'close' in recent else 0

    if (mcvd_trend == "UP" and price_slope > 0) or (mcvd_trend == "DOWN" and price_slope < 0):
        mcvd_vs_price = "CONFIRM"
    elif mcvd_trend == "UP" and price_slope < 0:
        mcvd_vs_price = "DIVERGE_BULLISH"
    elif mcvd_trend == "DOWN" and price_slope > 0:
        mcvd_vs_price = "DIVERGE_BEARISH"
    else:
        mcvd_vs_price = "UNKNOWN"

    consistency = float((whale_series > 0).sum() / len(whale_series))

    return {
        "mcvd_5d": mcvd_5d,
        "mcvd_20d": mcvd_20d,
        "mcvd_slope": round(slope_normalized, 4),
        "mcvd_trend": mcvd_trend,
        "mcvd_vs_price": mcvd_vs_price,
        "consistency": round(consistency, 2),
    }

def detect_stealth_accumulation(df: pd.DataFrame, daily_flow_df: pd.DataFrame, lookback: int = 15) -> dict:
    """Detects stealth accumulation preceding Wyckoff Springs."""
    if len(df) < lookback:
        return {"detected": False, "confidence": "LOW", "days_active": 0}

    recent = df.tail(lookback)
    
    atr_avg = recent['ATR14'].mean() if 'ATR14' in recent else (recent['High'] - recent['Low']).mean()
    price_range_pct = atr_avg / recent['Close'].mean()
    tight_range = price_range_pct < 0.015

    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=lookback)
    whale_accumulating = mcvd["mcvd_trend"] == "UP" or mcvd["mcvd_vs_price"] == "DIVERGE_BULLISH"

    obv_change = (recent['OBV'].iloc[-1] - recent['OBV'].iloc[0]) / max(abs(recent['OBV'].iloc[0]), 1)
    obv_rising = obv_change > 0.03

    z_vol_max = recent['Z_vol'].max() if 'Z_vol' in recent.columns else 1.0
    no_spike = z_vol_max < 1.5

    amd_phase = daily_flow_df.get('amd_phase', ["RANGING"])[-1] if 'amd_phase' in daily_flow_df else "RANGING"
    amd_ok = amd_phase in ("ACCUMULATION", "RANGING")

    detected = tight_range and whale_accumulating and obv_rising and no_spike and amd_ok

    if detected:
        score = sum([tight_range, whale_accumulating, obv_rising, no_spike, amd_ok])
        confidence = "HIGH" if score == 5 else ("MEDIUM" if score >= 4 else "LOW")
        
        days_active = sum(1 for z in recent['Z_vol'] if z < 1.5) if 'Z_vol' in recent else lookback
        est_target = float(df['High'].tail(60).max()) if len(df) >= 60 else None
        
        sig = f"Tích lũy bí mật {days_active} phiên: OBV +{obv_change*100:.1f}%, M-CVD {mcvd['mcvd_trend']}, giá hẹp {price_range_pct*100:.1f}%ATR"
        return {"detected": True, "confidence": confidence, "days_active": days_active, "est_target": est_target, "signal_text": sig}

    return {"detected": False, "confidence": "LOW", "days_active": 0}
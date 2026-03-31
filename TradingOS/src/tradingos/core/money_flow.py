"""FR-6: Large Money Flow module.

Implements:
  FR-6.1  compute_multiday_whale_flow (M-CVD) — SRS §8.2
  FR-6.2  compute_smart_money_score (SMS)    — SRS §8.3
  FR-6.3  detect_stealth_accumulation        — SRS §8.4
  FR-6.4  detect_sector_rotation             — SRS §8.5
  FR-6.5  mode_w_entry_params                — SRS §8.6
  FR-6.6  detect_whale_distribution          — SRS §8.7
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.config import cfg
from .anti_manip import volume_quality_score


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_last(series_or_list, default="RANGING"):
    if isinstance(series_or_list, (list, pd.Series)):
        return series_or_list[-1] if len(series_or_list) > 0 else default
    return series_or_list if series_or_list is not None else default


# ── Proxy whale flow (no tick data) ──────────────────────────────────────────

def proxy_whale_net_from_daily(df: pd.DataFrame) -> pd.DataFrame:
    """
    Estimate whale_net from OHLCV daily (SRS §8.2 proxy).

    Returns DataFrame with columns [whale_net_proxy, whale_net, close, volume].
    """
    c = df.copy()
    high_range = c["high"] - c["low"]
    c["range_pct"] = (c["close"] - c["low"]) / (high_range + 1e-9)
    mu = c["volume"].rolling(20).mean().fillna(c["volume"].mean())
    sigma = c["volume"].rolling(20).std().fillna(1)
    c["z_vol"] = (c["volume"] - mu) / sigma
    c["whale_net_proxy"] = c.apply(
        lambda r: int(r["volume"] * 0.3 * np.sign(r["range_pct"] - 0.5))
        if r["z_vol"] > 0.5 else 0,
        axis=1,
    )
    c["whale_net"] = c["whale_net_proxy"]
    return c[["whale_net_proxy", "whale_net", "close", "volume"]]


# ── FR-6.1: M-CVD ────────────────────────────────────────────────────────────

def compute_multiday_whale_flow(
    daily_flow_df: pd.DataFrame,
    lookback_days: int = 20,
) -> dict:
    """
    Multi-day CVD tracking (SRS §8.2).

    Expected columns: date, whale_net, [volume, close, fol_net, OBV]
    """
    cfg_ld = cfg.strategy("whale", "mcvd_lookback_days", default=20)
    lookback_days = lookback_days or int(cfg_ld)
    flat_thr = cfg.strategy("whale", "mcvd_flat_threshold", default=0.01)

    if len(daily_flow_df) < lookback_days:
        return {
            "mcvd_5d": 0, "mcvd_20d": 0, "mcvd_slope": 0.0,
            "mcvd_trend": "FLAT", "mcvd_vs_price": "UNKNOWN", "consistency": 0.5,
        }

    recent = daily_flow_df.tail(lookback_days).copy()

    # Use whale_net if present, else proxy
    if "whale_net" in recent.columns and recent["whale_net"].notna().any():
        whale_series = recent["whale_net"].fillna(0)
        data_source = "TICK_REAL"
    elif "whale_net_proxy" in recent.columns:
        whale_series = recent["whale_net_proxy"].fillna(0)
        data_source = "PROXY_OHLCV"
    else:
        whale_series = pd.Series(np.zeros(len(recent)), index=recent.index)
        data_source = "PROXY_OHLCV"

    mcvd_5d = int(whale_series.tail(5).sum())
    mcvd_20d = int(whale_series.sum())

    # Linear regression slope — normalised by avg daily shares [C4 FIX]
    x = np.arange(len(whale_series))
    try:
        slope, _ = np.polyfit(x, whale_series.values, 1)
    except Exception:
        slope = 0.0

    avg_daily_shares = recent["volume"].mean() if "volume" in recent.columns else max(abs(mcvd_20d) / lookback_days, 1)
    slope_normalized = slope / max(avg_daily_shares / lookback_days, 1)

    if slope_normalized > flat_thr:
        mcvd_trend = "UP"
    elif slope_normalized < -flat_thr:
        mcvd_trend = "DOWN"
    else:
        mcvd_trend = "FLAT"

    # Price-CVD agreement
    if "close" in recent.columns:
        price_slope = recent["close"].iloc[-1] / max(recent["close"].iloc[0], 1) - 1
    else:
        price_slope = 0.0

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
        "mcvd_slope": round(float(slope_normalized), 4),
        "mcvd_trend": mcvd_trend,
        "mcvd_vs_price": mcvd_vs_price,
        "consistency": round(consistency, 2),
        "data_source": data_source,
    }


# ── FR-6.2: SMS ───────────────────────────────────────────────────────────────

def compute_smart_money_score(
    ticker: str,
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    order_book: dict | None = None,
    quote: dict | None = None,
    amd_phase: str = "RANGING",
    cvd_today: int | None = None,
) -> dict:
    """
    Composite Smart Money Score 0–100 (SRS §8.3).

    Components (max 100):
      1. M-CVD Trend  0-25
      2. VQS          0-20
      3. FOL Net 5d   0-20
      4. OBV Slope    0-15
      5. AMD Align    0-10
      6. Intraday CVD 0-10
    """
    comps: dict[str, int] = {}

    # 1. M-CVD Trend (0–25)
    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=20)
    if mcvd["mcvd_trend"] == "UP" and mcvd["consistency"] >= 0.60:
        comps["mcvd"] = 25
    elif mcvd["mcvd_trend"] == "UP":
        comps["mcvd"] = 15
    elif mcvd["mcvd_trend"] == "FLAT":
        comps["mcvd"] = 5
    elif mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH":
        comps["mcvd"] = 0
    else:
        comps["mcvd"] = 0

    # 2. VQS (0–20)
    vqs_result = volume_quality_score(df, order_book or {})
    vqs = vqs_result["vqs_score"]
    comps["vqs"] = max(0, int((vqs + 1.0) / 2.0 * 20))

    # 3. FOL Net 5-day (0–20)
    fol_net_5d = 0
    if "fol_net" in daily_flow_df.columns:
        fol_net_5d = int(daily_flow_df["fol_net"].tail(5).sum())
    avg_vol = df["volume"].tail(20).mean() if not df.empty else 1
    fol_ratio = fol_net_5d / max(avg_vol * 5, 1)
    if fol_ratio > 0.05:
        comps["fol"] = 20
    elif fol_ratio > 0.02:
        comps["fol"] = 12
    elif fol_ratio > 0:
        comps["fol"] = 6
    elif fol_ratio < -0.02:
        comps["fol"] = 0
    else:
        comps["fol"] = 4

    # 4. OBV Slope (0–15)
    if "OBV" in df.columns and len(df) >= 10:
        obv_10 = df["OBV"].iloc[-10]
        obv_now = df["OBV"].iloc[-1]
        obv_slope = (obv_now - obv_10) / max(abs(obv_10), 1)
        if obv_slope > 0.05:
            comps["obv"] = 15
        elif obv_slope > 0.01:
            comps["obv"] = 8
        elif obv_slope < -0.05:
            comps["obv"] = 0
        else:
            comps["obv"] = 4
    else:
        comps["obv"] = 4

    # 5. AMD Phase Alignment (0–10)
    amd_bonus = {
        "ACCUMULATION": 10, "MARKUP": 8, "RANGING": 4,
        "DISTRIBUTION": 0, "MARKDOWN": 0,
    }
    comps["amd"] = amd_bonus.get(amd_phase, 4)

    # 6. Intraday CVD (0–10)
    if cvd_today is not None:
        comps["cvd_today"] = 10 if cvd_today > 0 else (5 if cvd_today == 0 else 0)
    else:
        comps["cvd_today"] = 5

    sms = sum(comps.values())
    sms = max(0, min(100, sms))

    # Label
    if sms >= 70 and comps["mcvd"] >= 20:
        label = "WHALE_BUYING"
    elif sms <= 25 or (mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH" and comps["mcvd"] == 0):
        label = "WHALE_DISTRIBUTING"
    elif comps.get("vqs", 0) >= 15 and comps.get("obv", 0) >= 8:
        label = "MIXED"
    else:
        label = "RETAIL_DRIVEN"

    return {
        "sms": sms,
        "sms_label": label,
        "components": comps,
        "mcvd_detail": mcvd,
        "fol_net_5d": fol_net_5d,
        "whale_pct_vol": round(max(0, fol_ratio) * 100, 1),
    }


# ── FR-6.3: Stealth Accumulation ─────────────────────────────────────────────

def detect_stealth_accumulation(
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    lookback: int = 15,
    amd_phase: str = "RANGING",
) -> dict:
    """
    Detect silent institutional accumulation (SRS §8.4).

    [C5 FIX] no_spike is mandatory in detected condition.
    Confidence: HIGH if score==5, MEDIUM if score>=4, LOW otherwise.
    """
    stealth_atr_pct = cfg.strategy("whale", "stealth_max_atr_pct", default=0.015)
    stealth_obv_min = cfg.strategy("whale", "stealth_obv_min_chg", default=0.03)
    stealth_z_max = cfg.strategy("whale", "stealth_z_vol_max", default=1.5)

    if len(df) < lookback:
        return {"detected": False, "confidence": "LOW", "days_active": 0}

    recent = df.tail(lookback).copy()

    # Cond 1: Tight price range
    atr_avg = recent["ATR14"].mean() if "ATR14" in recent.columns else (
        (recent["high"] - recent["low"]).mean()
    )
    price_range_pct = atr_avg / max(recent["close"].mean(), 1)
    tight_range = price_range_pct < stealth_atr_pct

    # Cond 2: M-CVD trend (whale buying, price not reflecting yet)
    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=lookback)
    whale_accumulating = (
        mcvd["mcvd_trend"] == "UP" or
        mcvd["mcvd_vs_price"] == "DIVERGE_BULLISH"
    )

    # Cond 3: OBV rising
    if "OBV" in recent.columns:
        obv_change = (recent["OBV"].iloc[-1] - recent["OBV"].iloc[0]) / max(abs(recent["OBV"].iloc[0]), 1)
    else:
        obv_change = 0.0
    obv_rising = obv_change > stealth_obv_min

    # Cond 4: No volume spike [C5: mandatory gate for "stealth" by definition]
    z_vol_max = recent["Z_vol"].max() if "Z_vol" in recent.columns else 1.0
    no_spike = z_vol_max < stealth_z_max

    # Cond 5: AMD phase compatible
    amd_ok = amd_phase in ("ACCUMULATION", "RANGING")

    # [C5 FIX] no_spike is mandatory (not just scoring)
    detected = tight_range and whale_accumulating and obv_rising and no_spike and amd_ok

    if detected:
        score = sum([tight_range, whale_accumulating, obv_rising, no_spike, amd_ok])
        confidence = "HIGH" if score == 5 else ("MEDIUM" if score >= 4 else "LOW")

        est_target = float(df["high"].tail(60).max()) if len(df) >= 60 else None

        # Count consecutive days active
        days_active = 0
        for i in range(len(df) - 1, max(len(df) - 60, -1), -1):
            row_z = df["Z_vol"].iloc[i] if "Z_vol" in df.columns else 1.0
            if row_z < stealth_z_max:
                days_active += 1
            else:
                break

        signal_text = (
            f"Tích lũy bí mật {days_active} phiên: "
            f"OBV +{obv_change*100:.1f}%, "
            f"M-CVD {mcvd['mcvd_trend']}, "
            f"ATR/Price {price_range_pct*100:.1f}%"
        )
        return {
            "detected": True,
            "confidence": confidence,
            "days_active": days_active,
            "est_target": est_target,
            "signal_text": signal_text,
            "mcvd_detail": mcvd,
            "score": score,
        }

    return {"detected": False, "confidence": "LOW", "days_active": 0}


# ── FR-6.4: Sector Rotation ───────────────────────────────────────────────────

def detect_sector_rotation(
    sector_ohlcv_map: dict[str, pd.DataFrame],
    sector_sms_map: dict[str, list[float]],
    lookback: int = 10,
) -> dict:
    """
    Sector money flow rotation analysis (SRS §8.5).
    """
    inflow_thr = float(cfg.strategy("sectors", "inflow_threshold", default=20))
    outflow_thr = float(cfg.strategy("sectors", "outflow_threshold", default=-20))

    rankings = []
    for sector, df in sector_ohlcv_map.items():
        if len(df) < lookback:
            continue

        mom_5d = df["close"].iloc[-1] / max(df["close"].iloc[-5], 1) - 1

        obv_slope = 0.0
        if "OBV" in df.columns and len(df) >= 10:
            obv_base = df["OBV"].iloc[-10]
            obv_slope = (df["OBV"].iloc[-1] - obv_base) / max(abs(obv_base), 1)

        sms_scores = sector_sms_map.get(sector, [50.0])
        sms_avg = float(np.mean(sms_scores)) if sms_scores else 50.0

        inflow_score = (mom_5d * 40) + (obv_slope * 30) + ((sms_avg - 50) / 50 * 30)
        inflow_score = float(np.clip(inflow_score * 100, -100, 100))

        if inflow_score >= inflow_thr:
            flow_status = "INFLOW"
        elif inflow_score <= outflow_thr:
            flow_status = "OUTFLOW"
        else:
            flow_status = "NEUTRAL"

        rankings.append({
            "sector": sector,
            "inflow_score": round(inflow_score, 1),
            "sms_avg": round(sms_avg, 1),
            "momentum_5d": round(mom_5d * 100, 2),
            "flow_status": flow_status,
        })

    rankings.sort(key=lambda x: x["inflow_score"], reverse=True)
    hot_sectors = [r["sector"] for r in rankings[:3] if r["flow_status"] == "INFLOW"]
    cold_sectors = [r["sector"] for r in rankings[-3:] if r["flow_status"] == "OUTFLOW"]

    inflow_count = sum(1 for r in rankings if r["flow_status"] == "INFLOW")
    outflow_count = sum(1 for r in rankings if r["flow_status"] == "OUTFLOW")
    n = max(len(rankings), 1)

    if inflow_count >= n * 0.6:
        rotation_phase = "RISK_ON"
    elif outflow_count >= n * 0.6:
        rotation_phase = "RISK_OFF"
    elif hot_sectors and cold_sectors:
        rotation_phase = "ROTATION"
    else:
        rotation_phase = "MIXED"

    return {
        "rankings": rankings,
        "hot_sectors": hot_sectors,
        "cold_sectors": cold_sectors,
        "rotation_phase": rotation_phase,
    }


# ── FR-6.5: Mode W Entry Params ───────────────────────────────────────────────

def mode_w_entry_params(df: pd.DataFrame, sms_result: dict) -> dict:
    """
    Entry/SL/TP calculation for Mode W (Follow-the-Whale) — SRS §8.6.
    """
    if df.empty:
        return {"entry": 0, "sl": 0, "sl_pct": 0, "tp1": 0, "tp2": 0, "rr": 0}

    last = df.iloc[-1]
    atr = float(last.get("ATR14", (df["high"] - df["low"]).tail(14).mean()))

    sl_mult = float(cfg.get("strategy", "atr_sl_mult") or cfg.strategy("entry_exit", "atr_sl_mult", default=1.5))
    tp1_mult = float(cfg.strategy("entry_exit", "atr_tp1_mult", default=4.0))
    tp2_mult = float(cfg.strategy("entry_exit", "atr_tp2_mult", default=8.0))

    entry = float(last["close"])
    ema9 = float(last.get("EMA9", entry))
    if entry > ema9 * 1.01:  # rebalance entry toward EMA9
        entry = round(ema9 * 1.005 / 100) * 100

    sl = round((entry - atr * sl_mult) / 100) * 100
    sl_pct = (sl - entry) / max(entry, 1) * 100

    # Use stealth target if available
    stealth = sms_result.get("stealth_detail", {})
    est_target = stealth.get("est_target")
    if isinstance(est_target, float) and est_target > entry * 1.05:
        tp1 = round((entry + (est_target - entry) * 0.5) / 100) * 100
        tp2 = round(est_target / 100) * 100
    else:
        tp1 = round((entry + atr * tp1_mult) / 100) * 100
        tp2 = round((entry + atr * tp2_mult) / 100) * 100

    rr = abs((tp1 - entry) / (sl - entry)) if sl != entry else 0

    return {
        "entry": entry,
        "sl": sl,
        "sl_pct": round(sl_pct, 2),
        "tp1": tp1,
        "tp2": tp2,
        "rr": round(rr, 2),
    }


# ── FR-6.6: Whale Distribution Warning ───────────────────────────────────────

def detect_whale_distribution(
    df: pd.DataFrame,
    daily_flow_df: pd.DataFrame,
    lookback: int = 10,
    amd_phase: str = "RANGING",
) -> dict:
    """
    Early warning of institutional distribution (SRS §8.7).

    Returns: warning_level (NONE|WATCH|CAUTION|EXIT|FORCED_EXIT), flags, score.
    """
    flags: list[str] = []
    score = 0

    if df.empty:
        return {"warning_level": "NONE", "flags": [], "score": 0, "explanation": ""}

    mcvd = compute_multiday_whale_flow(daily_flow_df, lookback_days=lookback)

    # Signal 1: M-CVD bearish divergence (price up, whale net down)
    if mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH":
        flags.append("DELTA_DIVERGE_BEARISH")
        score += 3

    # Signal 2: OBV negative turn
    if "OBV" in df.columns and len(df) >= 5:
        obv_now = df["OBV"].iloc[-1]
        obv_prev = df["OBV"].iloc[-5]
        if obv_prev != 0 and (obv_now - obv_prev) / abs(obv_prev) < -0.03:
            flags.append("OBV_NEGATIVE_TURN")
            score += 2

    # Signal 3: AMD Distribution phase
    if amd_phase == "DISTRIBUTION":
        flags.append("AMD_DISTRIBUTION")
        score += 2

    # Signal 4: Foreign net sell 5d
    avg_vol = df["volume"].tail(20).mean() if not df.empty else 1
    fol_net_5d = 0
    if "fol_net" in daily_flow_df.columns:
        fol_net_5d = int(daily_flow_df["fol_net"].tail(5).sum())
    if fol_net_5d < -avg_vol * 0.02 * 5:
        flags.append("FOREIGN_NET_SELL_5D")
        score += 1

    if score >= 5:
        level = "EXIT"
    elif score >= 3:
        level = "CAUTION"
    elif score >= 1:
        level = "WATCH"
    else:
        level = "NONE"

    explanation = ""
    if level != "NONE":
        explanation = (
            f"⚠️ Cảnh báo phân phối: {', '.join(flags)}. "
            f"Cân nhắc thu hẹp position hoặc dời SL lên breakeven."
        )

    return {
        "level": level,           # primary key used by callers
        "warning_level": level,   # alias for backward compat
        "flags": flags,
        "score": score,
        "explanation": explanation,
    }

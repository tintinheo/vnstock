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
from ..data.normalizer import round_to_tick, tick_size as _tick_sz
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
    # [NEW-4 FIX] fillna(1) handles NaN (first 19 bars) but NOT zero (all-same-volume
    # windows).  If std=0, division produces inf/ZeroDivisionError, causing false whale
    # z_vol > 0.5 signals on halted or stagnant-volume stocks.  Added .replace(0, 1).
    sigma = c["volume"].rolling(20).std().fillna(1).replace(0, 1)
    c["z_vol"] = (c["volume"] - mu) / sigma
    # [VN-FIX VN-B2] Old z_vol > 0.5 caught ~30% of all sessions as "whale",
    # inflating SMS scores on normal trading days. Config-driven threshold
    # (default 1.5) requires statistically significant volume deviation.
    _z_min = float(cfg.strategy("whale", "proxy_z_vol_min", default=1.5))
    c["whale_net_proxy"] = c.apply(
        lambda r: int(r["volume"] * 0.3 * np.sign(r["range_pct"] - 0.5))
        if r["z_vol"] > _z_min else 0,
        axis=1,
    )
    c["whale_net"] = c["whale_net_proxy"]
    # Include date column so callers can merge foreign-flow data by date
    cols = ["whale_net_proxy", "whale_net", "close", "volume"]
    if "date" in c.columns:
        cols = ["date"] + cols
    return c[cols]


def compute_whale_net_from_pt_deals(
    pt_deals_df: pd.DataFrame,
    df_ohlcv: pd.DataFrame,
) -> pd.DataFrame:
    """
    Upgrade whale_net estimate using real put-through (block) deal data.

    Put-through deals are directly observable institutional transactions, making
    this a PARTIAL_PROXY (penalty=0.5) vs pure OHLCV proxy (penalty=1.0).

    Expected pt_deals_df columns: date, value, volume  (positive = buy, negative = sell)
    Returns a DataFrame compatible with proxy_whale_net_from_daily():
      [whale_net_proxy, whale_net, close, volume, data_source]
    """
    if pt_deals_df is None or pt_deals_df.empty:
        result = proxy_whale_net_from_daily(df_ohlcv)
        result["data_source"] = "PROXY_OHLCV"
        return result

    base = proxy_whale_net_from_daily(df_ohlcv).copy()

    # Aggregate PT deals by date, map to OHLCV index
    pt = pt_deals_df.copy()
    if "date" in pt.columns:
        pt["date"] = pd.to_datetime(pt["date"]).dt.date

    if "value" not in pt.columns and "volume" in pt.columns and "price" in pt.columns:
        pt["value"] = pt["volume"] * pt["price"]

    if "date" in pt.columns and "value" in pt.columns:
        pt_daily = pt.groupby("date")["value"].sum()
        # Align to base index: use the "date" column if present (clean_ohlcv always
        # produces it), otherwise fall back to the DataFrame's DatetimeIndex.
        if "date" in df_ohlcv.columns:
            base_dates = pd.to_datetime(df_ohlcv["date"])
        elif df_ohlcv.index.dtype != "int64":
            base_dates = pd.to_datetime(df_ohlcv.index)
        else:
            # No date info available — cannot align; skip blending
            base_dates = pd.Series([], dtype="datetime64[ns]")
        for i, row_date in enumerate(base_dates):
            d = row_date.date() if hasattr(row_date, "date") else row_date
            if d in pt_daily.index:
                pt_val = pt_daily[d]
                # Convert VND value to share-equivalent using the day's close price
                close_price = float(df_ohlcv.iloc[i]["close"])
                pt_shares = int(pt_val / max(close_price, 1))
                # Blend: use PT net as the whale_net signal (more reliable than proxy)
                base.iloc[i, base.columns.get_loc("whale_net")] = pt_shares

    base["data_source"] = "PARTIAL_PROXY"
    return base


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

    # [NEW-6 FIX] Sort by date before tail() to guarantee chronological order.
    # If upstream merges produce non-sorted rows (e.g. FOL merge reindexing),
    # whale trend/slope is computed on wrong windows.
    if "date" in daily_flow_df.columns:
        daily_flow_df = daily_flow_df.sort_values("date").reset_index(drop=True)
    recent = daily_flow_df.tail(lookback_days).copy()

    # Respect .data_source column forwarded by proxy functions; only fall back to
    # column-presence heuristic when the column is absent.  "whale_net" being
    # present does NOT mean the data is real tick-data — it is also set by the
    # OHLCV proxy functions, so naively labelling it TICK_REAL is wrong.
    if "data_source" in recent.columns:
        data_source = str(recent["data_source"].iloc[-1])
    elif "whale_net_proxy" not in recent.columns and "whale_net" in recent.columns:
        # Only a genuine non-proxy feed omits whale_net_proxy
        data_source = "TICK_REAL"
    else:
        data_source = "PROXY_OHLCV"

    # Select the best available whale series
    if "whale_net" in recent.columns and recent["whale_net"].notna().any():
        whale_series = recent["whale_net"].fillna(0)
    elif "whale_net_proxy" in recent.columns:
        whale_series = recent["whale_net_proxy"].fillna(0)
    else:
        whale_series = pd.Series(np.zeros(len(recent)), index=recent.index)

    mcvd_5d = int(whale_series.tail(5).sum())
    mcvd_20d = int(whale_series.sum())

    # Linear regression slope — normalised by avg daily shares [C4 FIX]
    x = np.arange(len(whale_series))
    try:
        slope, _ = np.polyfit(x, whale_series.values, 1)
    except Exception:
        slope = 0.0

    avg_daily_shares = recent["volume"].mean() if "volume" in recent.columns else max(abs(mcvd_20d) / lookback_days, 1)
    # [BUG-9 FIX] Correct normalizer is avg_daily_shares (total daily volume).
    # Old bug: divided by lookback_days making denominator 20× too small
    # and inflating slope_normalized 20× → FLAT trends mis-classified as UP/DOWN.
    slope_normalized = slope / max(avg_daily_shares, 1)

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
    pt_deals_df: pd.DataFrame | None = None,  # [C6] Add put-through data
    order_book: dict | None = None,
    quote: dict | None = None,
    amd_phase: str = "RANGING",
    cvd_today: int | None = None,
    cvd_data_quality: str = "NONE",
) -> dict:
    """
    Composite Smart Money Score 0–100 (SRS §8.3).

    Components (max 100):
      1. M-CVD Trend  0-20
      2. VQS          0-15
      3. FOL Net 5d   0-15
      4. OBV Slope    0-15
      5. AMD Align    0-10
      6. Intraday CVD 0-10
      7. PT Flow      0-15 [C6]
    """
    comps: dict[str, int] = {}

    # 1. M-CVD Trend (0–20) - [C6] Weight reduced from 25
    # [NEW-5 FIX] Do NOT pass lookback_days=20 explicitly here.
    # compute_multiday_whale_flow uses `lookback_days or cfg_ld`, so passing a
    # truthy 20 always overrides the config.  Omitting the arg lets the function
    # read mcvd_lookback_days from strategy.yaml (default still 20 when unconfigured).
    mcvd = compute_multiday_whale_flow(daily_flow_df)
    if mcvd["mcvd_trend"] == "UP" and mcvd["consistency"] >= 0.60:
        comps["mcvd"] = 20
    elif mcvd["mcvd_trend"] == "UP":
        comps["mcvd"] = 12
    elif mcvd["mcvd_trend"] == "FLAT":
        comps["mcvd"] = 5
    elif mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH":
        comps["mcvd"] = 0
    else:
        comps["mcvd"] = 0

    # 2. VQS (0–15) - [C6] Weight reduced from 20
    vqs_result = volume_quality_score(df, order_book or {})
    vqs = vqs_result["vqs_score"]
    comps["vqs"] = max(0, int((vqs + 1.0) / 2.0 * 15))

    # 3. FOL Net 5-day (0–15) - [C6] Weight reduced from 20
    fol_net_5d = 0
    has_fol_data = "fol_net" in daily_flow_df.columns
    if has_fol_data:
        fol_net_5d = int(daily_flow_df["fol_net"].tail(5).sum())
    avg_vol = df["volume"].tail(20).mean() if not df.empty else 1
    fol_ratio = fol_net_5d / max(avg_vol * 5, 1)
    # [BUG3 FIX] No fol_net column → no information; score 0 not 3
    if not has_fol_data:
        # [VN-FIX V4] When no foreign-flow data, use a neutral score (5/15) instead
        # of OBV-slope proxy. OBV slope measures price-direction pressure, not foreign
        # ownership level (FOL) — they are semantically unrelated signals. A domestic
        # stock with rising price was incorrectly receiving a "foreigners buying" bonus.
        # Neutral score 5/15 means "no edge information" without penalising or inflating.
        comps["fol"] = 5
    elif fol_ratio > 0.05:
        comps["fol"] = 15
    elif fol_ratio > 0.02:
        comps["fol"] = 10
    elif fol_ratio > 0:
        comps["fol"] = 5
    elif fol_ratio < -0.02:
        comps["fol"] = 0
    else:
        comps["fol"] = 0  # exactly zero net — neutral, no edge signal

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
    # Proxy OHLCV direction is useful for timing, but it must not carry the same
    # weight as real aggressor-flow data.  Cap proxy influence to a narrow band
    # around neutral; allow only REAL_FLOW to reach the full 0–10 range.
    if cvd_today is not None:
        intensity = abs(float(cvd_today)) / max(float(avg_vol), 1.0)
        if cvd_data_quality == "REAL_FLOW":
            if cvd_today > 0:
                comps["cvd_today"] = 10 if intensity >= 0.12 else (8 if intensity >= 0.05 else 6)
            elif cvd_today < 0:
                comps["cvd_today"] = 0 if intensity >= 0.12 else (2 if intensity >= 0.05 else 4)
            else:
                comps["cvd_today"] = 5
        elif cvd_data_quality == "OHLCV_PROXY":
            # [VN-FIX V8] Cap proxy CVD at 6 (never reaches the W-6 gate of ≥7).
            # OHLCV direction is a price-derived proxy, not real aggressor flow.
            # Allowing it to score 7 let scanner-only runs satisfy Mode W's intraday-
            # flow pre-condition without any actual institutional confirmation.
            if cvd_today > 0:
                comps["cvd_today"] = 6
            elif cvd_today < 0:
                comps["cvd_today"] = 3 if intensity >= 0.12 else 4
            else:
                comps["cvd_today"] = 5
        else:
            comps["cvd_today"] = 5
    else:
        comps["cvd_today"] = 5

    # 7. Put-through Flow (0-15) [C6 NEW]
    pt_net_5d = 0
    pt_ratio = 0.0
    if pt_deals_df is not None and not pt_deals_df.empty:
        pt_net_5d = pt_deals_df["value"].sum()
        avg_val_5d = (df["volume"] * df["close"]).tail(5).mean()
        pt_ratio = pt_net_5d / max(avg_val_5d * 5, 1)
        if pt_ratio > 0.1:  # PT net buy > 10% of 5d avg value
            comps["pt_flow"] = 15
        elif pt_ratio > 0.03: # PT net buy > 3% of 5d avg value
            comps["pt_flow"] = 10
        elif pt_ratio > 0:
            comps["pt_flow"] = 5
        else: # Net selling or insignificant
            comps["pt_flow"] = 0
    else:
        # [VN-FIX VN-B3] No PT data → neutral (5/15), consistent with FOL fallback.
        # Old value 0 penalised stocks that simply don't have PT deals — most mid/small caps.
        comps["pt_flow"] = 5  # No data — neutral (no information edge)

    sms = sum(comps.values())
    # [VN-FIX V9] All-neutral quality cap: when every flow-information component
    # (FOL, PT, CVD) returns the neutral fallback of 5 (no real data), the SMS
    # inflates by 15 "free" points that carry zero information.  Subtract 5 to
    # distinguish "neutral-because-no-data" from "neutral-because-balanced-flow".
    # This only fires in scanner-only runs where none of the three components have
    # real institutional data; live profiler runs with any real flow are unaffected.
    if comps.get("fol", 0) == 5 and comps.get("pt_flow", 0) == 5 and comps.get("cvd_today", 0) == 5:
        sms = max(0, sms - 5)
    sms = max(0, min(100, sms))

    # Label
    if sms >= 70 and (comps.get("mcvd", 0) >= 15 or comps.get("pt_flow", 0) >= 10):
        label = "WHALE_BUYING"
    elif sms <= 30 or (mcvd["mcvd_vs_price"] == "DIVERGE_BEARISH" and comps["mcvd"] == 0):
        label = "WHALE_DISTRIBUTING"
    elif comps.get("vqs", 0) >= 12 and comps.get("obv", 0) >= 8:
        label = "MIXED"
    else:
        label = "RETAIL_DRIVEN"

    return {
        "sms": sms,
        "sms_label": label,
        "components": comps,
        "mcvd_detail": mcvd,
        "fol_net_5d": fol_net_5d,
        # [VN-10 FIX] Keep signed fol_pct so downstream logic can detect persistent
        # net-sell pressure (negative = foreign outflow). Old max(0.0, ...) hid
        # sell-side flow, making sustained foreign exit invisible to callers.
        "fol_pct": round(fol_ratio * 100, 2),
        "fol_direction": "NET_BUY" if fol_ratio > 0.01 else ("NET_SELL" if fol_ratio < -0.01 else "NEUTRAL"),
        "pt_net_5d": pt_net_5d,
        "pt_ratio_5d": round(pt_ratio, 3),
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

        # [NEW-7 FIX] True 5-session momentum compares today (iloc[-1]) to 5 sessions
        # ago (iloc[-6], 6th from end).  The old iloc[-5] compared to 4 days ago,
        # overstating recent momentum by one bar.
        if len(df) < 6:
            continue
        mom_5d = df["close"].iloc[-1] / max(df["close"].iloc[-6], 1) - 1

        obv_slope = 0.0
        if "OBV" in df.columns and len(df) >= 10:
            obv_base = df["OBV"].iloc[-10]
            obv_slope = (df["OBV"].iloc[-1] - obv_base) / max(abs(obv_base), 1)

        sms_scores = sector_sms_map.get(sector, [50.0])
        sms_avg = float(np.mean(sms_scores)) if sms_scores else 50.0

        inflow_score = (mom_5d * 40) + (obv_slope * 30) + ((sms_avg - 50) / 50 * 30)
        inflow_score = float(np.clip(inflow_score, -100, 100))

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

def mode_w_entry_params(df: pd.DataFrame, sms_result: dict, signal_mode: str = "MODE_W") -> dict:
    """
    Entry/SL/TP calculation for the active signal mode — SRS §8.6.

    signal_mode : "MODE_W" | "MODE_A" | "MODE_B"
        MODE_W — Follow-the-Whale: entry rebalances toward EMA9 (wait for retest).
        MODE_A — Pullback: entry at or near SMA20/EMA20 support; EMA9 rebalance is
                 acceptable since close is already at a pullback level.
        MODE_B — Breakout: entry IS the breakout close; EMA9 pullback is WRONG
                 here because it would mean entering below the breakout confirm point.
    """
    if df.empty:
        return {"entry": 0, "sl": 0, "sl_pct": 0, "tp1": 0, "tp2": 0, "rr": 0}

    last = df.iloc[-1]
    atr = float(last.get("ATR14", (df["high"] - df["low"]).tail(14).mean()))

    sl_mult = float(cfg.get("strategy", "atr_sl_mult") or cfg.strategy("entry_exit", "atr_sl_mult", default=1.5))
    tp1_mult = float(cfg.strategy("entry_exit", "atr_tp1_mult", default=4.0))
    tp2_mult = float(cfg.strategy("entry_exit", "atr_tp2_mult", default=8.0))

    close = float(last["close"])
    entry = round_to_tick(close)    # always align to exchange tick
    # [BUG-22 FIX] EMA9 pullback rebalance is Mode W-specific (follow-whale reentry
    # near EMA9). For Mode B breakout, the entry IS the breakout close; pulling back
    # to EMA9 would mean entering BEFORE the breakout confirms — incorrect semantics.
    # For Mode A pullback this rebalance is acceptable; for MODE_W it is intended.
    if signal_mode != "MODE_B":
        ema9 = float(last.get("EMA9", entry))
        if entry > ema9 * 1.01:  # rebalance entry toward EMA9
            ema9_entry = round_to_tick(ema9 * 1.005)
            # Cap pullback to 2% below close — prevents un-actionable entries on EMA9 lag
            entry = round_to_tick(max(ema9_entry, close * 0.98))

    # Minimum SL distance: 3% of entry (prevents noise-level SL on sub-5K VND stocks)
    sl_dist = max(atr * sl_mult, entry * 0.03)
    # Floor SL to the tick below the raw level so tick rounding never shrinks the gap
    _sl_raw = entry - sl_dist
    _t = _tick_sz(_sl_raw)
    sl = float(int(_sl_raw // _t) * _t)
    sl_pct = (sl - entry) / max(entry, 1) * 100

    # Use stealth target if available
    stealth = sms_result.get("stealth_detail", {})
    est_target = stealth.get("est_target")
    if isinstance(est_target, float) and est_target > entry * 1.05:
        tp1 = round_to_tick(entry + (est_target - entry) * 0.5)
        tp2 = round_to_tick(est_target)
    else:
        tp1 = round_to_tick(entry + atr * tp1_mult)
        tp2 = round_to_tick(entry + atr * tp2_mult)

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
    if "OBV" in df.columns and len(df) >= 6:
        obv_now = df["OBV"].iloc[-1]
        # [NEW-7 FIX] Use iloc[-6] for true 5-session OBV lookback (iloc[-5] was 4 days).
        obv_prev = df["OBV"].iloc[-6]
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


# ── FR-NEW: Normalized CVD (NCVD) ────────────────────────────────────────────

def calculate_ncvd(
    raw_cvd: float,
    adtv_20d: float,
    window_days: int = 5,
) -> dict:
    """
    Normalize raw M-CVD by Average Daily Trading Volume to make it comparable
    across tickers with vastly different liquidity profiles.

    NCVD = raw_CVD / (ADTV × window_days)

    Interpretation bands:
      > +0.50 : VERY_BULLISH  (net accumulation > 50% of expected ADTV window)
      > +0.10 : BULLISH
      -0.10 to +0.10 : NEUTRAL
      < -0.10 : BEARISH
      < -0.50 : VERY_BEARISH
    """
    if adtv_20d <= 0 or window_days <= 0:
        return {
            "raw_cvd": raw_cvd, "adtv_20d": adtv_20d, "ncvd": 0.0,
            "ncvd_pct": "0.0%", "label": "NEUTRAL",
        }

    expected_volume = adtv_20d * window_days
    ncvd = raw_cvd / expected_volume

    if ncvd > 0.50:
        label = "VERY_BULLISH"
    elif ncvd > 0.10:
        label = "BULLISH"
    elif ncvd > -0.10:
        label = "NEUTRAL"
    elif ncvd > -0.50:
        label = "BEARISH"
    else:
        label = "VERY_BEARISH"

    return {
        "raw_cvd": raw_cvd,
        "adtv_20d": adtv_20d,
        "ncvd": round(ncvd, 4),
        "ncvd_pct": f"{ncvd * 100:.2f}%",
        "label": label,
    }


# ── FR-NEW: CVD Multi-Timeframe Conflict Resolution ───────────────────────────

def resolve_cvd_conflict(
    cvd_5d_trend: str,
    cvd_20d_trend: str,
    amd_phase: str = "RANGING",
) -> dict:
    """
    Resolve a potential conflict between 5-day and 20-day M-CVD trend signals
    using a Wyckoff-informed multi-timeframe priority matrix.

    cvd_5d_trend / cvd_20d_trend : 'UP' | 'DOWN' | 'FLAT'
    amd_phase                    : 'ACCUMULATION' | 'MARKUP' | 'DISTRIBUTION' | 'MARKDOWN' | 'RANGING'

    Returns a dict with:
      pattern, interpretation, action, confidence, dominant_timeframe, note
    """
    _MATRIX = {
        ("UP",   "UP"):   ("FULL_BULL_ALIGNMENT",    "ENTRY_FAVORABLE",     "HIGH"),
        ("UP",   "DOWN"): ("BOUNCE_IN_DISTRIBUTION",  "NO_NEW_ENTRY",        "HIGH"),
        ("UP",   "FLAT"): ("EARLY_BREAKOUT",           "MONITOR_20D",         "MEDIUM"),
        ("DOWN", "UP"):   ("PULLBACK_IN_ACCUM",        "WATCH_FOR_ENTRY",     "MEDIUM"),
        ("DOWN", "DOWN"): ("FULL_BEAR_ALIGNMENT",      "AVOID",               "HIGH"),
        ("DOWN", "FLAT"): ("LOSING_MOMENTUM",          "WAIT",                "LOW"),
        ("FLAT", "UP"):   ("PAUSING_ACCUM",            "WAIT_RESUME",         "MEDIUM"),
        ("FLAT", "DOWN"): ("DISTRIBUTION_SLOWING",     "NEUTRAL_WATCH",       "LOW"),
        ("FLAT", "FLAT"): ("NO_DIRECTIONAL_SIGNAL",    "NO_ACTION",           "VERY_LOW"),
    }

    t5 = str(cvd_5d_trend).upper() if cvd_5d_trend in ("UP", "DOWN", "FLAT") else "FLAT"
    t20 = str(cvd_20d_trend).upper() if cvd_20d_trend in ("UP", "DOWN", "FLAT") else "FLAT"
    interpretation, action, confidence = _MATRIX.get(
        (t5, t20), ("UNKNOWN", "NO_ACTION", "VERY_LOW")
    )

    note = f"AMD={amd_phase}"

    # AMD override: if AMD=DISTRIBUTION, ENTRY_FAVORABLE is downgraded
    if amd_phase == "DISTRIBUTION" and action == "ENTRY_FAVORABLE":
        action = "CAUTION_AMD_DISTRIBUTION"
        confidence = "MEDIUM"
        note += " → ENTRY_FAVORABLE overridden by DISTRIBUTION"

    # Wyckoff Spring: AMD=ACCUMULATION but short-term CVD is down (retail selling)
    if amd_phase == "ACCUMULATION" and action == "NO_NEW_ENTRY":
        interpretation = interpretation + "_POSSIBLE_WYCKOFF_SPRING"
        action = "WATCH_SPRING_REVERSAL"
        note += " → Possible institutional absorption of retail selling"

    dominant = "20D" if t20 != "FLAT" else "5D"

    return {
        "pattern": f"CVD5d_{t5}__CVD20d_{t20}",
        "interpretation": interpretation,
        "action": action,
        "confidence": confidence,
        "dominant_timeframe": dominant,
        "note": note,
    }

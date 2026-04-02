"""Anti-Manipulation Filter (AMF) + VQS + AMD + CVD intraday.

Implements SRS §2.9, §2.10 — defensive layer that blocks manipulated signals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.config import cfg


# ── VQS — Volume Quality Score ────────────────────────────────────────────────

def volume_quality_score(df: pd.DataFrame, order_book: dict) -> dict:
    """
    Volume Quality Score [-1, +1].

    Components:
    - OFI ratio: (buy_volume - sell_volume) / total_volume
    - Price-Volume correlation (20 bars)
    - OBV momentum
    """
    if df.empty or len(df) < 5:
        return {"vqs_score": 0.0, "ofi_ratio": 0.0}

    # OFI proxy
    delta = df["close"].diff().fillna(0)
    buy_v = df["volume"].where(delta > 0, 0).tail(20).sum()
    sell_v = df["volume"].where(delta < 0, 0).tail(20).sum()
    total = buy_v + sell_v
    ofi_ratio = (buy_v - sell_v) / max(total, 1)

    # Price-volume correlation
    pv_corr = df["close"].tail(20).corr(df["volume"].tail(20))
    pv_corr = 0.0 if np.isnan(pv_corr) else pv_corr

    # OBV slope normalised
    if "OBV" in df.columns and len(df) >= 10:
        obv_s = df["OBV"].tail(10)
        obv_slope = (obv_s.iloc[-1] - obv_s.iloc[0]) / max(abs(obv_s.iloc[0]), 1)
        obv_score = float(np.clip(obv_slope * 5, -1, 1))
    else:
        obv_score = 0.0

    vqs = (ofi_ratio * 0.5 + pv_corr * 0.3 + obv_score * 0.2)
    vqs = float(np.clip(vqs, -1.0, 1.0))

    return {"vqs_score": vqs, "ofi_ratio": ofi_ratio, "obv_score": obv_score}


# ── AMD Phase Detection ───────────────────────────────────────────────────────

def detect_amd_phase(df: pd.DataFrame, lookback: int = 60) -> str:
    """
    Detect Wyckoff AMD phase from price/volume structure.

    Returns: ACCUMULATION | MARKUP | DISTRIBUTION | MARKDOWN | RANGING
    """
    if len(df) < lookback:
        return "RANGING"

    recent = df.tail(lookback)
    close = recent["close"]
    volume = recent["volume"]

    # Price trend
    price_change = close.iloc[-1] / close.iloc[0] - 1

    # OBV trend
    if "OBV" in recent.columns:
        obv_first = recent["OBV"].iloc[0]
        obv_last  = recent["OBV"].iloc[-1]
        # H4: guard near-zero denominator — use range-based normalisation when
        # abs(OBV[0]) is too small relative to the series range, to avoid
        # obv_change blowing up to raw-share-count magnitudes.
        obv_range = recent["OBV"].abs().max()
        denominator = max(abs(obv_first), obv_range * 0.05, 1)
        obv_change = (obv_last - obv_first) / denominator
    else:
        from .indicators import obv as compute_obv
        obv_s = compute_obv(recent)
        obv_range = obv_s.abs().max()
        denominator = max(abs(obv_s.iloc[0]), obv_range * 0.05, 1)
        obv_change = (obv_s.iloc[-1] - obv_s.iloc[0]) / denominator

    # Volume on down vs up days
    up_days = recent[recent["close"] > recent["close"].shift()]
    dn_days = recent[recent["close"] < recent["close"].shift()]
    up_vol = up_days["volume"].mean() if not up_days.empty else 0
    dn_vol = dn_days["volume"].mean() if not dn_days.empty else 0

    # Classification rules
    # MARKUP: strong: price > 5% AND OBV > 5%; early: price > 1% AND OBV > 2%
    if price_change > 0.05 and obv_change > 0.05 and up_vol > dn_vol:
        return "MARKUP"
    # Early-stage markup: price rising modestly with positive OBV confirmation
    elif price_change > 0.01 and obv_change > 0.02 and up_vol > dn_vol:
        return "MARKUP"
    elif price_change < -0.05 and obv_change < -0.05 and dn_vol > up_vol:
        return "MARKDOWN"
    # ACCUMULATION: price flat (|change| ≤ 1%) but OBV rising — stealth buying
    elif abs(price_change) <= 0.01 and obv_change > 0.02:
        return "ACCUMULATION"
    # Broader accumulation: price range-bound (≤ 5%) with positive OBV divergence
    elif abs(price_change) <= 0.05 and obv_change > 0.02 and up_vol >= dn_vol:
        return "ACCUMULATION"
    elif abs(price_change) <= 0.05 and obv_change < -0.02:
        return "DISTRIBUTION"
    else:
        return "RANGING"


# ── CVD Intraday ──────────────────────────────────────────────────────────────

def compute_cvd_intraday(df_5m: pd.DataFrame) -> int:
    """
    Compute end-of-session Cumulative Volume Delta from 5-minute bars.
    Proxy: positive delta = bullish (close > open), negative = bearish.
    NOTE: This is a PROXY_CVD estimate.  Close-vs-open bar classification
    mis-attributes volume on shooting-star / hammer candles.  Treat the
    result as directional guidance only, not a precise tick-level CVD.
    Returns net signed volume (shares).
    """
    if df_5m.empty:
        return 0
    delta = df_5m["close"] - df_5m["open"]
    bull = df_5m["volume"].where(delta > 0, 0)
    bear = df_5m["volume"].where(delta < 0, 0)
    return int((bull - bear).sum())


def cvd_data_quality() -> str:
    """Return data quality label for CVD intraday (always a proxy without tick feed)."""
    return "PROXY_CVD"


# ── AMF — Anti-Manipulation Filter ───────────────────────────────────────────

def run_amf(df: pd.DataFrame, order_book: dict | None = None) -> dict:
    """
    4-layer Anti-Manipulation Filter pipeline.

    Returns:
        decision    : PASS | WARN | BLOCK
        flags       : list of triggered flags
        details     : per-layer results
    """
    flags: list[str] = []
    order_book = order_book or {}

    if df.empty or len(df) < 5:
        return {"decision": "PASS", "flags": [], "details": {}}

    # ── Layer 1: Open Spike ────────────────────────────────────────────────
    open_spike_thr = cfg.strategy("amf", "open_spike_threshold", default=0.06)
    last = df.iloc[-1]
    prev_close = df.iloc[-2]["close"] if len(df) >= 2 else last["close"]
    open_gap = abs(last["open"] - prev_close) / max(prev_close, 1)
    if open_gap > open_spike_thr:
        flags.append(f"OPEN_SPIKE_{open_gap*100:.1f}pct")

    # ── Layer 2: Wash-Sale Volume ──────────────────────────────────────────
    wash_mult = cfg.strategy("amf", "wash_sale_volume_mult", default=3.0)
    avg_vol_20 = df["volume"].tail(20).mean()
    z_vol_last = df["Z_vol"].iloc[-1] if "Z_vol" in df.columns else (
        (last["volume"] - avg_vol_20) / max(df["volume"].tail(20).std(), 1)
    )
    if z_vol_last > wash_mult:
        flags.append(f"WASH_SALE_VOLUME_Z{z_vol_last:.1f}")

    # ── Layer 3: Bid-Ask Imbalance ─────────────────────────────────────────
    bid_ask_thr = cfg.strategy("amf", "bid_ask_imbalance", default=0.70)
    if order_book:
        bid_qty = sum(order_book.get("bids", {}).values()) or 1
        ask_qty = sum(order_book.get("asks", {}).values()) or 1
        total_ob = bid_qty + ask_qty
        imbalance = max(bid_qty, ask_qty) / total_ob
        if imbalance > bid_ask_thr:
            side = "BID" if bid_qty > ask_qty else "ASK"
            flags.append(f"ORDER_BOOK_IMBALANCE_{side}_{imbalance*100:.0f}pct")

    # ── Layer 4: VWAP Deviation ────────────────────────────────────────────
    vwap_dev_thr = cfg.strategy("amf", "vwap_deviation", default=0.03)
    if "VWAP_daily" in df.columns:
        vwap_now = df["VWAP_daily"].iloc[-1]
        close_now = last["close"]
        dev = abs(close_now - vwap_now) / max(vwap_now, 1)
        if dev > vwap_dev_thr:
            flags.append(f"VWAP_DEV_{dev*100:.1f}pct")

    # ── Decision ──────────────────────────────────────────────────────────
    if len(flags) >= 3:
        decision = "BLOCK"
    elif len(flags) >= 1:
        decision = "WARN"
    else:
        decision = "PASS"

    return {
        "decision": decision,
        "flags": flags,
        "details": {
            "open_gap_pct": round(open_gap * 100, 2),
            "z_vol": round(float(z_vol_last), 2),
        },
    }


# ── VSA Analysis ──────────────────────────────────────────────────────────────

def detect_vsa_patterns(df: pd.DataFrame) -> list[str]:
    """
    Volume Spread Analysis: detect key VSA patterns.
    Returns list of detected patterns.
    """
    patterns: list[str] = []
    if len(df) < 3:
        return patterns

    last = df.iloc[-1]
    prev = df.iloc[-2]
    avg_vol = df["volume"].tail(20).mean()

    spread = last["high"] - last["low"]
    avg_spread = (df["high"] - df["low"]).tail(20).mean()

    # No-demand bar: narrow spread + low volume on upbar
    if last["close"] > prev["close"] and spread < avg_spread * 0.7 and last["volume"] < avg_vol * 0.7:
        patterns.append("NO_DEMAND")

    # No-supply bar: narrow spread + low volume on downbar
    if last["close"] < prev["close"] and spread < avg_spread * 0.7 and last["volume"] < avg_vol * 0.7:
        patterns.append("NO_SUPPLY")

    # Effort-without-result: high volume + narrow spread
    if last["volume"] > avg_vol * 1.5 and spread < avg_spread * 0.5:
        patterns.append("EFFORT_WITHOUT_RESULT")

    # Stopping volume: very high volume + long lower wick
    lower_wick = last["close"] - last["low"]
    if last["volume"] > avg_vol * 2 and lower_wick > spread * 0.6:
        patterns.append("STOPPING_VOLUME")

    return patterns

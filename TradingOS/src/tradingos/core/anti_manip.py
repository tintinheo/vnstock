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

def run_amf(
    df: pd.DataFrame,
    order_book: dict | None = None,
    intraday_data: dict | None = None,
) -> dict:
    """
    4-layer Anti-Manipulation Filter pipeline.

    Args:
        df             : OHLCV DataFrame
        order_book     : optional legacy bid/ask dict (bids/asks as {price: vol})
        intraday_data  : optional dict from fetch_intraday_features(); provides
                         tfi (Trade Flow Imbalance) and obi_l3 for wash-sale
                         directionality classification.

    Returns:
        decision    : PASS | WARN | BLOCK
        flags       : list of triggered flags
        wash_side   : BUY_WASH | SELL_WASH | NEUTRAL_WASH | NONE
        details     : per-layer results (open_gap_pct, z_vol, tfi, obi_l3)
    """
    flags: list[str] = []
    order_book = order_book or {}
    intraday_data = intraday_data or {}

    if df.empty or len(df) < 5:
        return {"decision": "PASS", "flags": [], "wash_side": "NONE", "details": {}}

    # ── Layer 1: Open Spike ────────────────────────────────────────────────
    # [BUG-4 FIX] Default raised from 0.06 → 0.09.
    # HOSE circuit breaker is ±7% (±10% for UpCom). A gap of 5-6% is normal
    # post-earnings or news-driven and does NOT indicate manipulation.
    # 9% sits just inside the circuit breaker and only catches genuine wash gaps.
    open_spike_thr = cfg.strategy("amf", "open_spike_threshold", default=0.09)
    last = df.iloc[-1]
    prev_close = df.iloc[-2]["close"] if len(df) >= 2 else last["close"]
    open_gap = abs(last["open"] - prev_close) / max(prev_close, 1)
    if open_gap > open_spike_thr:
        flags.append(f"OPEN_SPIKE_{open_gap*100:.1f}pct")

    # ── Layer 2: Wash-Sale Volume + Directionality ────────────────────────
    # TFI threshold ±0.20: TCBS aggressor accuracy is ~80-85%; tighter
    # thresholds produce too many false NEUTRAL_WASH classifications.
    wash_mult       = cfg.strategy("amf", "wash_sale_volume_mult", default=3.0)
    tfi_threshold   = float(cfg.strategy("amf", "wash_tfi_threshold", default=0.20))
    avg_vol_20 = df["volume"].tail(20).mean()
    z_vol_last = df["Z_vol"].iloc[-1] if "Z_vol" in df.columns else (
        (last["volume"] - avg_vol_20) / max(df["volume"].tail(20).std(), 1)
    )
    wash_side = "NONE"
    if z_vol_last > wash_mult:
        tfi = float(intraday_data.get("tfi", 0.0))
        if tfi > tfi_threshold:
            # Buy-aggressor dominated: artificial price inflation (manipulation UP)
            flags.append(f"WASH_SALE_BUY_DRIVEN_Z{z_vol_last:.1f}")
            wash_side = "BUY_WASH"
        elif tfi < -tfi_threshold:
            # Sell-aggressor dominated: artificial price suppression (Wyckoff spring candidate)
            flags.append(f"WASH_SALE_SELL_DRIVEN_Z{z_vol_last:.1f}")
            wash_side = "SELL_WASH"
        else:
            # No intraday data or TFI near zero — direction unknown
            flags.append(f"WASH_SALE_VOLUME_Z{z_vol_last:.1f}")
            wash_side = "NEUTRAL_WASH"

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
    # [BUG-4 FIX] Default raised from 0.03 → 0.05.
    # Rolling 20-bar VWAP vs daily close deviates 3-4% routinely for VN stocks
    # with any intraday volatility (bluechips included). 5% better represents
    # abnormal close-vs-VWAP divergence consistent with end-of-day manipulation.
    vwap_dev_thr = cfg.strategy("amf", "vwap_deviation", default=0.05)
    if "VWAP_daily" in df.columns:
        vwap_now = df["VWAP_daily"].iloc[-1]
        close_now = last["close"]
        dev = abs(close_now - vwap_now) / max(vwap_now, 1)
        if dev > vwap_dev_thr:
            flags.append(f"VWAP_DEV_{dev*100:.1f}pct")

    # ── Decision ──────────────────────────────────────────────────────────
    # [P4.4] Weighted decision: sum flag severity weights instead of counting raw flags.
    # This prevents mild flags (VWAP drift, sell-wash) from triggering BLOCK
    # when combined with other mild flags.  Three equal-medium-weight flags still
    # produce BLOCK; confirmed wash-trade + any second signal still BLOCK.
    _flag_weights_cfg = cfg.strategy("amf", "flag_weights", default={}) or {}
    _block_thr        = float(cfg.strategy("amf", "block_weighted_threshold", default=3.0))
    _warn_thr         = float(cfg.strategy("amf", "warn_weighted_threshold",  default=0.5))
    _DEFAULT_WEIGHTS  = {
        "OPEN_SPIKE":            2.0,
        "WASH_SALE_BUY_DRIVEN":  1.5,
        "WASH_SALE_VOLUME":      1.0,
        "WASH_SALE_SELL_DRIVEN": 0.5,
        "ORDER_BOOK_IMBALANCE":  1.0,
        "VWAP_DEV":              0.5,
    }
    # Config overrides defaults; unknown prefixes fall back to 1.0
    _weights = {**_DEFAULT_WEIGHTS, **{str(k): float(v) for k, v in _flag_weights_cfg.items()}}

    def _flag_weight(flag: str) -> float:
        for prefix, w in _weights.items():
            if flag.startswith(prefix):
                return w
        return 1.0

    weighted_score = sum(_flag_weight(f) for f in flags)
    if weighted_score >= _block_thr:
        decision = "BLOCK"
    elif weighted_score >= _warn_thr:
        decision = "WARN"
    else:
        decision = "PASS"

    return {
        "decision": decision,
        "flags": flags,
        "wash_side": wash_side,
        "details": {
            "open_gap_pct":    round(open_gap * 100, 2),
            "z_vol":           round(float(z_vol_last), 2),
            "tfi":             round(float(intraday_data.get("tfi", 0.0)), 4),
            "obi_l3":          round(float(intraday_data.get("obi_l3", 0.0)), 4),
            "obi_reconstructed": round(float(intraday_data.get("obi_reconstructed", 0.0)), 4),
            "mcvd":            int(intraday_data.get("mcvd", 0)),
        },
    }

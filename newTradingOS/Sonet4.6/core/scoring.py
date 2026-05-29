"""
core/scoring.py — NewTradingOS v14.0
Multi-timeframe signal scoring engine.
Returns normalised 0-100 score + action + full breakdown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import TIMEFRAME_CONFIG, score_to_action
from core.indicators import compute_all


@dataclass
class SignalResult:
    ticker:      str
    timeframe:   str
    score:       float          # 0 – 100
    action:      str            # STRONG BUY / BUY / HOLD / WATCH / SELL
    price:       float
    stop_loss:   float
    take_profit: float
    rr_ratio:    float
    atr:         float
    breakdown:   dict = field(default_factory=dict)
    indicators:  dict = field(default_factory=dict)   # snapshot of key values
    regime_ok:   bool = True
    manip_flag:  bool = False
    message:     str  = ""


def compute_score(
    df: pd.DataFrame,
    tf: str,
    regime: str = "bull",
    foreign_flow_net: float = 0.0,
    macro_score: float = 5.0,
    ticker: str = "UNKNOWN",
) -> SignalResult:
    """
    Compute multi-component signal score for one ticker + timeframe.

    Score components (total 100 pts):
    ─────────────────────────────────
      Trend      25 pts  — SMA cross, price vs SMAs, EMA alignment
      Momentum   20 pts  — MACD histogram, MACD vs zero, ROC
      RSI        15 pts  — zone quality (oversold recovery = best)
      Volume     20 pts  — spike, accumulation, MFI
      Foreign     5 pts  — net flow direction (1M+ only)
      Macro      10 pts  — regime + macro_score
      ADX         5 pts  — trend strength confirmation
    ─────────────────────────────────

    Parameters
    ----------
    df             : OHLCV DataFrame (at least cfg['sma_slow'] + 20 rows)
    tf             : one of '1W','2W','1M','3M','5M'
    regime         : current market regime ('bull'|'sideways'|'bear')
    foreign_flow_net: net foreign buy value in VND (positive = buy)
    macro_score    : 0-10 from macro_data.get_macro_score()
    ticker         : symbol for labelling
    """
    cfg  = TIMEFRAME_CONFIG[tf]
    min_rows = cfg["sma_slow"] + 20

    if df is None or len(df) < min_rows:
        return SignalResult(
            ticker=ticker, timeframe=tf, score=0, action="HOLD",
            price=0, stop_loss=0, take_profit=0, rr_ratio=0, atr=0,
            message=f"Insufficient data (need {min_rows} rows, got {len(df) if df is not None else 0})",
        )

    # Compute all indicators
    df = compute_all(df.copy(), cfg)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    price = float(last["Close"])

    # ── 1. TREND  (25 pts) ────────────────────────────────────
    trend = 0.0
    if price > last["SMA_fast"]:      trend += 6
    if price > last["SMA_slow"]:      trend += 7
    if last["SMA_fast"] > last["SMA_slow"]: trend += 6   # golden zone
    if last["EMA_fast"] > last["EMA_slow"]: trend += 6
    # Uptrend slope: SMA_fast increasing
    if last["SMA_fast"] > df["SMA_fast"].iloc[-3]:  trend += 5  # bonus: accelerating
    trend = min(trend, 25.0)

    # ── 2. MOMENTUM  (20 pts) ─────────────────────────────────
    mom = 0.0
    # MACD cross up
    if last["MACD"] > last["MACD_signal"]:     mom += 7
    # Histogram improving
    if last["MACD_hist"] > prev["MACD_hist"]:  mom += 6
    # MACD above zero
    if last["MACD"] > 0:                       mom += 4
    # ROC positive
    if last["ROC"] > 0:                        mom += 3
    mom = min(mom, 20.0)

    # ── 3. RSI  (15 pts) ──────────────────────────────────────
    rsi_v   = float(last["RSI"]) if not pd.isna(last["RSI"]) else 50.0
    rsi_pts = 0.0
    if 30 <= rsi_v < 40:     rsi_pts = 15   # oversold recovery — best
    elif 40 <= rsi_v <= 55:  rsi_pts = 12   # sweet spot
    elif 55 < rsi_v <= 65:   rsi_pts = 8    # momentum
    elif rsi_v < 30:         rsi_pts = 10   # deep oversold (contrarian)
    elif 65 < rsi_v <= 75:   rsi_pts = 4    # elevated, caution
    # RSI divergence bonus: price new high but RSI not → skip for simplicity
    rsi_score = rsi_pts

    # ── 4. VOLUME  (20 pts) ───────────────────────────────────
    vol_r  = float(last["Vol_ratio"]) if not pd.isna(last["Vol_ratio"]) else 1.0
    mfi_v  = float(last["MFI"])       if not pd.isna(last["MFI"])       else 50.0
    vol    = 0.0
    if vol_r > 1.5:   vol += 7
    if vol_r > 2.5:   vol += 5   # extra for very strong spike
    if vol_r > 2.0 and price > last["SMA_fast"]: vol += 3  # breakout volume
    # Accumulation (3-day avg > 1.2× SMA)
    recent_vol_ma = df["Volume"].iloc[-3:].mean()
    if recent_vol_ma > df["Volume"].rolling(cfg["volume_ma"]).mean().iloc[-1] * 1.2:
        vol += 3
    if mfi_v > 50: vol += 2
    vol = min(vol, 20.0)

    # ── 5. FOREIGN FLOW  (5 pts, meaningful for 1M+) ─────────
    ff_pts = 0.0
    if tf in ("1M", "3M", "5M"):
        if foreign_flow_net > 1e10:    ff_pts = 5
        elif foreign_flow_net > 0:     ff_pts = 3
        elif foreign_flow_net < -1e10: ff_pts = 0
        else:                          ff_pts = 1

    # ── 6. MACRO REGIME  (10 pts) ─────────────────────────────
    macro_pts = (macro_score / 10.0) * 10
    macro_pts = min(macro_pts, 10.0)

    # ── 7. ADX  (5 pts) ───────────────────────────────────────
    adx_v   = float(last["ADX"]) if not pd.isna(last["ADX"]) else 0.0
    adx_pts = 0.0
    if adx_v > 30:   adx_pts = 5
    elif adx_v > 20: adx_pts = 3
    elif adx_v > 15: adx_pts = 1

    # ── TOTAL ─────────────────────────────────────────────────
    score = trend + mom + rsi_score + vol + ff_pts + macro_pts + adx_pts
    score = round(min(score, 100.0), 2)

    # ── REGIME FILTER ─────────────────────────────────────────
    regime_ok = regime in cfg["regime_filter"]

    # ── ACTION ────────────────────────────────────────────────
    action = score_to_action(score)
    if not regime_ok and action in ("STRONG BUY", "BUY"):
        action = "WATCH"

    # ── ATR STOP / TARGET ─────────────────────────────────────
    atr_v       = float(last["ATR"]) if not pd.isna(last["ATR"]) else price * 0.02
    stop_loss   = round(price - cfg["stop_atr_mult"] * atr_v, 0)
    take_profit = round(price + cfg["stop_atr_mult"] * atr_v * cfg["target_rr"], 0)

    # ── MANIPULATION CHECK ────────────────────────────────────
    manip_v    = float(last["Manip_score"]) if not pd.isna(last["Manip_score"]) else 0.0
    manip_flag = manip_v > 65

    # Downgrade if manipulation suspected
    if manip_flag and action == "STRONG BUY":
        action = "BUY"

    breakdown = {
        "Trend":   round(trend, 1),
        "Momentum":round(mom, 1),
        "RSI":     round(rsi_score, 1),
        "Volume":  round(vol, 1),
        "Foreign": round(ff_pts, 1),
        "Macro":   round(macro_pts, 1),
        "ADX":     round(adx_pts, 1),
    }

    indicators = {
        "RSI":        round(rsi_v, 1),
        "MACD":       round(float(last["MACD"]), 2)       if not pd.isna(last["MACD"]) else None,
        "MACD_hist":  round(float(last["MACD_hist"]), 2)  if not pd.isna(last["MACD_hist"]) else None,
        "BB_%B":      round(float(last["BB_pctB"]), 3)    if not pd.isna(last["BB_pctB"]) else None,
        "ADX":        round(adx_v, 1),
        "Vol_ratio":  round(vol_r, 2),
        "MFI":        round(mfi_v, 1),
        "ATR":        round(atr_v, 0),
        "SMA_fast":   round(float(last["SMA_fast"]), 0)   if not pd.isna(last["SMA_fast"]) else None,
        "SMA_slow":   round(float(last["SMA_slow"]), 0)   if not pd.isna(last["SMA_slow"]) else None,
        "Manip_score":round(manip_v, 1),
    }

    return SignalResult(
        ticker=ticker,
        timeframe=tf,
        score=score,
        action=action,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        rr_ratio=cfg["target_rr"],
        atr=round(atr_v, 0),
        breakdown=breakdown,
        indicators=indicators,
        regime_ok=regime_ok,
        manip_flag=manip_flag,
    )


def batch_score(
    data_dict: dict[str, tuple[pd.DataFrame, str]],
    tf: str,
    regime: str = "bull",
    macro_score: float = 5.0,
    foreign_flows: Optional[dict] = None,
    min_score: Optional[float] = None,
) -> list[SignalResult]:
    """
    Score a dictionary of {ticker: (df, source)} for a given timeframe.
    Returns list sorted by score descending.
    """
    results = []
    ff = foreign_flows or {}

    for ticker, (df, _src) in data_dict.items():
        if df is None or df.empty:
            continue
        sig = compute_score(
            df, tf,
            regime=regime,
            foreign_flow_net=ff.get(ticker, {}).get("net_buy_value", 0.0),
            macro_score=macro_score,
            ticker=ticker,
        )
        results.append(sig)

    results.sort(key=lambda s: s.score, reverse=True)

    if min_score is not None:
        results = [r for r in results if r.score >= min_score]

    return results

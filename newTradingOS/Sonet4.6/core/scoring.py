"""
core/scoring.py — NewTradingOS v14.0
Multi-timeframe signal scoring engine.
Returns normalised 0-100 score + action + full breakdown.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import TIMEFRAME_CONFIG, score_to_action, round_to_tick, get_tick_size
from core.indicators import compute_all

logger = logging.getLogger("TradingOS.scoring")


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
    foreign_flow_net_20d: float = 0.0,
    macro_score: float = 5.0,
    ticker: str = "UNKNOWN",
    exchange: str = "HOSE",
    _precomputed: bool = False,
) -> SignalResult:
    """
    Compute multi-component signal score for one ticker + timeframe.

    Score components (total 100 pts):
    ─────────────────────────────────
      Trend      30 pts  — SMA cross, Supertrend, EMA alignment
      Momentum   15 pts  — MACD histogram, MACD vs zero, ROC
      RSI        10 pts  — zone quality (oversold recovery = best)
      Volume     20 pts  — OBV trend, volume spike, MFI
      Foreign    10 pts  — Standardized net flow (vs. avg volume)
      Macro      10 pts  — regime + macro_score
      ADX         5 pts  — trend strength confirmation
    ─────────────────────────────────

    Parameters
    ----------
    df                 : OHLCV DataFrame (at least cfg['sma_slow'] + 20 rows)
    tf                 : one of '1W','2W','1M','3M','5M'
    regime             : current market regime ('bull'|'sideways'|'bear')
    foreign_flow_net   : net foreign buy value today in VND (positive = buy)
    foreign_flow_net_20d: cumulative net foreign buy over 20 sessions in VND.
                         When available (from fetch_foreign_flow_ticker), uses
                         the 20-day trend instead of a single day for a more
                         stable foreign flow signal. Falls back to foreign_flow_net.
    macro_score        : 0-10 from macro_data.get_macro_score()
    ticker             : symbol for labelling
    exchange           : 'HOSE' |’HNX' | 'UPCOM' — controls price-limit threshold
                         for Streak indicator (fixed: was always HOSE before).
    _precomputed       : set True khi df đã được compute_all() xử lý sẵn.
                         Backtest engine dùng flag này để tránh tính lại chỉ báo
                         O(n²) trong vòng loop — giảm từ O(n²) xuống O(n).
                         Tất cả rolling indicators đều có tính causal: giá trị tại
                         bar i không phụ thuộc bars tương lai nên an toàn khi
                         dùng df toàn bộ thay vì df.iloc[:i+1].
    """
    cfg  = TIMEFRAME_CONFIG[tf]
    min_rows = cfg["sma_slow"] + 20

    if df is None or len(df) < min_rows:
        return SignalResult(
            ticker=ticker, timeframe=tf, score=0, action="HOLD",
            price=0, stop_loss=0, take_profit=0, rr_ratio=0, atr=0,
            message=f"Insufficient data (need {min_rows} rows, got {len(df) if df is not None else 0})",
        )

    # Compute all indicators (bỏ qua nếu caller đã tính sẵn — backtest loop dùng _precomputed=True)
    if not _precomputed:
        df = compute_all(df.copy(), cfg, exchange=exchange)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    price = float(last["Close"])

    # ── Component Scores ───────────────────────────────────────
    breakdown = {}

    # 1. Trend Score (30 pts)
    # ─────────────────────────────────
    trend_score = 0
    # a. Supertrend (15 pts) - NEW
    if 'supertrend' in last and last["supertrend_dir"] == 1 and last["close"] > last["supertrend"]:
        trend_score += 15
    elif 'supertrend' in last and last["supertrend_dir"] == -1 and last["close"] < last["supertrend"]:
        trend_score -= 15 # Penalize sell signal

    # b. SMA Fast vs Slow (10 pts)
    if last["sma_fast"] > last["sma_slow"]:
        trend_score += 10
    # c. Price vs SMAs (5 pts)
    if last["close"] > last["sma_fast"]:
        trend_score += 5
    breakdown["Trend"] = trend_score

    # 2. Momentum Score (15 pts)
    # ─────────────────────────────────
    mom_score = 0
    # a. MACD Histogram (10 pts)
    if last["macd_hist"] > 0 and last["macd_hist"] > prev["macd_hist"]:
        mom_score += 10  # Histogram is positive and rising
    # b. MACD vs Zero line (5 pts)
    if last["macd"] > 0:
        mom_score += 5
    breakdown["Momentum"] = mom_score

    # 3. RSI Score (10 pts)
    # ─────────────────────────────────
    rsi_score = 0
    if 30 < last["rsi"] < 70:
        rsi_score += 5
    if last["rsi"] > prev["rsi"] and last["rsi"] < 70: # Rising RSI
        rsi_score += 5
    breakdown["RSI"] = rsi_score

    # 4. Volume Score (20 pts)
    # ─────────────────────────────────
    vol_score = 0
    # a. OBV Trend (10 pts) - NEW
    if 'obv' in last and 'obv_sma' in last and last['obv'] > last['obv_sma']:
        vol_score += 10 # OBV is above its moving average, confirming upward volume pressure
    # b. Volume Spike (5 pts)
    if last["volume"] > last["sma_volume_fast"] * 1.5:
        vol_score += 5
    # c. MFI (5 pts)
    if last["mfi"] < 80: # Not overbought
        vol_score += 5
    breakdown["Volume"] = vol_score

    # 5. Foreign Flow Score (10 pts) - REVISED
    # ─────────────────────────────────
    ff_score = 0
    avg_vol_20d = last.get("sma_volume_slow", 0) # Use sma_slow as proxy for 20d avg vol
    if avg_vol_20d > 0:
        # Use 20-day net flow if available, otherwise fallback to today's net
        net_flow_to_use = foreign_flow_net_20d if foreign_flow_net_20d != 0 else foreign_flow_net
        # Standardize by price to get net volume, then compare to avg volume
        avg_price_20d = last.get("sma_slow", last['close'])
        if avg_price_20d > 0:
            net_flow_volume = net_flow_to_use / avg_price_20d
            flow_ratio = net_flow_volume / avg_vol_20d

            if flow_ratio > 0.05: # Net buy > 5% of avg volume
                ff_score = 10
            elif flow_ratio > 0.02: # Net buy > 2% of avg volume
                ff_score = 5
            elif flow_ratio < -0.05: # Net sell > 5% of avg volume
                ff_score = -10 # Penalize heavy selling
    breakdown["Foreign Flow"] = ff_score

    # 6. Macro Score (10 pts)
    # ─────────────────────────────────
    macro_pts = 0
    if regime == "bull":
        macro_pts = macro_score  # 0-10 pts
    elif regime == "sideways":
        macro_pts = macro_score / 2 # 0-5 pts
    # Bear market gets 0 points from macro
    breakdown["Macro"] = macro_pts

    # 7. ADX Score (5 pts)
    # ─────────────────────────────────
    adx_score = 0
    if last["adx"] > 25:
        adx_score = 5
    breakdown["ADX"] = adx_score

    # Final Score Calculation
    # ─────────────────────────────────
    total_score = (
        trend_score
        + mom_score
        + rsi_score
        + vol_score
        + ff_score
        + macro_pts
        + adx_score
    )
    # Normalize to 0-100 scale. Max possible score is 30+15+10+20+10+10+5 = 100
    # Min possible score can be negative, so clip at 0.
    final_score = max(0, min(100, total_score))

    # ── Indicators Snapshot ────────────────────────────────────
    indicators_snapshot = {
        "rsi": last["rsi"], "mfi": last["mfi"], "adx": last["adx"],
        "macd_hist": last["macd_hist"], "volume_ratio": last["volume"] / last["sma_volume_fast"] if last["sma_volume_fast"] > 0 else 0,
        "supertrend_dir": last.get("supertrend_dir", 0),
        "obv_trend": 1 if 'obv' in last and 'obv_sma' in last and last['obv'] > last['obv_sma'] else 0,
    }

    # ── Risk/Reward Calculation ────────────────────────────────
    atr_v       = float(last["ATR"]) if not pd.isna(last["ATR"]) else price * 0.02
    stop_raw    = price - cfg["stop_atr_mult"] * atr_v
    target_raw  = price + cfg["stop_atr_mult"] * atr_v * cfg["target_rr"]
    # Round to valid VN exchange tick (HOSE: 10/50/100 VND by price band;
    # HNX/UPCOM: 100 VND flat). Prevents broker order-rejection on invalid prices.
    stop_loss   = round_to_tick(stop_raw,   exchange)
    take_profit = round_to_tick(target_raw, exchange)
    # Safety: stop must be strictly below price, target above
    tick = get_tick_size(price, exchange)
    if stop_loss  >= price:   stop_loss   = price - tick
    if take_profit <= price:  take_profit = price + tick

    # ── MANIPULATION CHECK ────────────────────────────────────
    manip_v    = float(last["Manip_score"]) if not pd.isna(last["Manip_score"]) else 0.0
    manip_flag = manip_v > 65

    # Persistent floor streak also flags potential forced-sell / distribution
    if streak_v <= -3:
        manip_flag = True

    # Downgrade if manipulation suspected
    if manip_flag and action == "STRONG BUY":
        action = "BUY"

    return SignalResult(
        ticker=ticker,
        timeframe=tf,
        score=final_score,
        action=action,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        rr_ratio=cfg["target_rr"],
        atr=round(atr_v, 0),
        breakdown=breakdown,
        indicators=indicators_snapshot,
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
    exchange_map: Optional[dict] = None,
) -> list[SignalResult]:
    """
    Score a dictionary of {ticker: (df, source)} for a given timeframe.
    Returns list sorted by score descending.

    Parameters
    ----------
    exchange_map : optional dict of {ticker: exchange_str}
        When provided, each ticker uses the correct price-limit for its
        exchange (HOSE ±7%, HNX ±10%, UPCoM ±15%) in the Streak indicator.
        Defaults to HOSE for all tickers when not provided.
    """
    ff = foreign_flows or {}
    ex = exchange_map or {}

    def _score_one(item: tuple) -> Optional[SignalResult]:
        ticker, (df, _src) = item
        if df is None or df.empty:
            return None
        ff_ticker  = ff.get(ticker, {})
        exchange   = ex.get(ticker, "HOSE")
        try:
            return compute_score(
                df, tf,
                regime=regime,
                foreign_flow_net=ff_ticker.get("net_buy_value", 0.0),
                foreign_flow_net_20d=ff_ticker.get("net_20d", 0.0),
                macro_score=macro_score,
                ticker=ticker,
                exchange=exchange,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("batch_score: %s skipped — %s", ticker, exc)
            return None

    n_workers = min(6, max(1, len(data_dict)))
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        results = [
            sig for sig in pool.map(_score_one, data_dict.items())
            if sig is not None
        ]

    results.sort(key=lambda s: s.score, reverse=True)

    if min_score is not None:
        results = [r for r in results if r.score >= min_score]

    return results

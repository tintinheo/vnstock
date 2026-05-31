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

from config import (
    ACTIONABLE_MIN_ADV_VND,
    TIMEFRAME_CONFIG,
    score_to_action,
    round_to_tick,
    get_tick_size,
)
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
      Trend      25 pts  — SMA cross, price vs SMAs, EMA alignment
      Momentum   20 pts  — MACD histogram, MACD vs zero, ROC
      RSI        15 pts  — zone quality (oversold recovery = best)
      Volume     20 pts  — spike, accumulation, MFI
      Foreign     5 pts  — net flow direction (1M+ only, uses 20d trend)
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

    # ── 1. TREND  (25 pts) ────────────────────────────────────
    trend = 0.0
    if price > last["SMA_fast"]:
        trend += 5
    if price > last["SMA_slow"]:
        trend += 6
    if last["SMA_fast"] > last["SMA_slow"]:
        trend += 5
    if last["EMA_fast"] > last["EMA_slow"]:
        trend += 5
    if last["SMA_fast"] > df["SMA_fast"].iloc[-3]:
        trend += 4
    st_dir = float(last["ST_dir"]) if "ST_dir" in df.columns and not pd.isna(last["ST_dir"]) else 0.0
    if st_dir == 1.0:
        trend += 4
    trend = min(trend, 25.0)

    # ── 2. MOMENTUM  (20 pts) ─────────────────────────────────
    mom = 0.0
    if last["MACD"] > last["MACD_signal"]:
        mom += 7
    if last["MACD_hist"] > prev["MACD_hist"]:
        mom += 6
    if last["MACD"] > 0:
        mom += 4
    if last["ROC"] > 0:
        mom += 3
    mom = min(mom, 20.0)

    # ── 3. RSI  (15 pts) — VN-tuned zones ─────────────────────
    # VN stocks can stay RSI 60-75 for weeks during a trend run.
    # Penalising RSI>65 too harshly causes the scanner to miss the bulk
    # of the trending phase. Deep oversold (<30) is dangerous in VN
    # because margin-call cascades can persist for weeks.
    rsi_v   = float(last["RSI"]) if not pd.isna(last["RSI"]) else 50.0
    rsi_pts = 0.0
    if 45 <= rsi_v < 65:
        rsi_pts = 15
    elif 30 <= rsi_v < 45:
        rsi_pts = 12
    elif 65 <= rsi_v <= 75:
        rsi_pts = 10
    elif rsi_v < 30:
        rsi_pts = 4
    elif 75 < rsi_v <= 85:
        rsi_pts = 5
    else:
        rsi_pts = 2
    rsi_score = rsi_pts

    # ── 4. VOLUME / FLOW  (20 pts) — VN-enhanced ───────────────
    # CMF and Streak are VN-specific additions:
    #   CMF: gap-adjusted smart-money inflow (better than OBV for VN gaps)
    #   Streak: consecutive price-limit hits (unique to VN ±7% rule)
    vol_r  = float(last["Vol_ratio"]) if not pd.isna(last["Vol_ratio"]) else 1.0
    mfi_v  = float(last["MFI"]) if not pd.isna(last["MFI"]) else 50.0
    cmf_v  = float(last["CMF"]) if "CMF" in df.columns and not pd.isna(last["CMF"]) else 0.0
    streak_v = int(last["Streak"]) if "Streak" in df.columns and not pd.isna(last["Streak"]) else 0
    vol    = 0.0
    if vol_r > 1.5:
        vol += 5
    if vol_r > 2.5:
        vol += 3
    if vol_r > 2.0 and price > last["SMA_fast"]:
        vol += 2
    recent_vol_avg = df["Volume"].iloc[-3:].mean()
    vol_ma_last = float(df["Vol_MA"].iloc[-1]) if "Vol_MA" in df.columns and not pd.isna(df["Vol_MA"].iloc[-1]) else 0.0
    if vol_ma_last > 0 and recent_vol_avg > vol_ma_last * 1.2:
        vol += 2
    if mfi_v > 50:
        vol += 2
    if cmf_v > 0.05:
        vol += 3
    if cmf_v > 0.15:
        vol += 1
    if streak_v >= 2:
        vol += 2
    if streak_v <= -2:
        vol -= 3
    bb_pctb = float(last["BB_pctB"]) if "BB_pctB" in df.columns and not pd.isna(last["BB_pctB"]) else 0.5
    if bb_pctb > 0.8 and vol_r > 1.5:
        vol += 2
    elif bb_pctb < 0.15 and streak_v >= 0:
        vol += 1
    vol = min(vol, 20.0)
    vol = max(vol, -5.0)

    # ── 5. FOREIGN FLOW  (5 pts, meaningful for 2W+) ───────────────
    # Use 20d trend if available — more robust than single-day signal.
    # Falls back to today's net flow when net_20d is zero (not provided).
    # 2W included: 10-session hold is long enough for FF trends to matter;
    # a 2-week sustained foreign sell-off is clearly a negative signal.
    ff_pts = 0.0
    if tf in ("2W", "1M", "3M", "5M"):
        ff_ref = foreign_flow_net_20d if foreign_flow_net_20d != 0.0 else foreign_flow_net
        if ff_ref > 1e10:
            ff_pts = 5
        elif ff_ref > 0:
            ff_pts = 3
        elif ff_ref < -1e10:
            ff_pts = 0
        else:
            ff_pts = 1

    # ── 6. MACRO REGIME  (10 pts) ─────────────────────────────
    macro_pts = (macro_score / 10.0) * 10
    macro_pts = min(macro_pts, 10.0)

    # ── 7. ADX  (5 pts) ───────────────────────────────────────
    adx_v   = float(last["ADX"]) if not pd.isna(last["ADX"]) else 0.0
    adx_pts = 0.0
    if adx_v > 30:
        adx_pts = 5
    elif adx_v > 20:
        adx_pts = 3
    elif adx_v > 15:
        adx_pts = 1

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
    atr_v = float(last["ATR"]) if not pd.isna(last["ATR"]) else price * 0.02
    stop_raw = price - cfg["stop_atr_mult"] * atr_v
    target_raw = price + cfg["stop_atr_mult"] * atr_v * cfg["target_rr"]
    # Round to valid VN exchange tick (HOSE: 10/50/100 VND by price band;
    # HNX/UPCOM: 100 VND flat). Prevents broker order-rejection on invalid prices.
    stop_loss = round_to_tick(stop_raw, exchange)
    take_profit = round_to_tick(target_raw, exchange)
    tick = get_tick_size(price, exchange)
    if stop_loss >= price:
        stop_loss = price - tick
    if take_profit <= price:
        take_profit = price + tick

    # ── MANIPULATION CHECK ────────────────────────────────────
    manip_v = float(last["Manip_score"]) if not pd.isna(last["Manip_score"]) else 0.0
    manip_flag = manip_v > 65

    # Persistent floor streak also flags potential forced-sell / distribution
    if streak_v <= -3:
        manip_flag = True

    # Downgrade if manipulation suspected
    if manip_flag and action == "STRONG BUY":
        action = "BUY"

    # ── LIQUIDITY GATE ────────────────────────────────────────
    adv_window = min(20, len(df))
    adv20_vnd = float((df["Close"].tail(adv_window) * df["Volume"].tail(adv_window)).mean())
    low_liquidity = adv20_vnd < ACTIONABLE_MIN_ADV_VND
    message = ""
    if low_liquidity and action in ("STRONG BUY", "BUY"):
        action = "WATCH"
        message = (
            f"Low liquidity gate: ADV20 {adv20_vnd / 1e9:.2f}B VND "
            f"< {ACTIONABLE_MIN_ADV_VND / 1e9:.0f}B VND"
        )

    breakdown = {
        "Trend": round(trend, 1),
        "Momentum": round(mom, 1),
        "RSI": round(rsi_score, 1),
        "Volume": round(vol, 1),
        "Foreign": round(ff_pts, 1),
        "Macro": round(macro_pts, 1),
        "ADX": round(adx_pts, 1),
    }

    indicators = {
        "RSI": round(rsi_v, 1),
        "MACD": round(float(last["MACD"]), 2) if not pd.isna(last["MACD"]) else None,
        "MACD_hist": round(float(last["MACD_hist"]), 2) if not pd.isna(last["MACD_hist"]) else None,
        "BB_%B": round(float(last["BB_pctB"]), 3) if not pd.isna(last["BB_pctB"]) else None,
        "ADX": round(adx_v, 1),
        "Vol_ratio": round(vol_r, 2),
        "MFI": round(mfi_v, 1),
        "ATR": round(atr_v, 0),
        "ADV20_bn": round(adv20_vnd / 1e9, 2),
        "SMA_fast": round(float(last["SMA_fast"]), 0) if not pd.isna(last["SMA_fast"]) else None,
        "SMA_slow": round(float(last["SMA_slow"]), 0) if not pd.isna(last["SMA_slow"]) else None,
        "EMA_fast": round(float(last["EMA_fast"]), 0) if not pd.isna(last["EMA_fast"]) else None,
        "EMA_slow": round(float(last["EMA_slow"]), 0) if not pd.isna(last["EMA_slow"]) else None,
        "Manip_score": round(manip_v, 1),
        "CMF": round(cmf_v, 3),
        "ST_dir": int(st_dir),
        "Streak": streak_v,
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
        message=message,
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
        history_sessions = int(ff_ticker.get("history_sessions", 0) or 0)
        is_20d_proxy = bool(ff_ticker.get("is_20d_proxy", False))
        ff_net_20d = float(ff_ticker.get("net_20d", 0.0) or 0.0)
        if is_20d_proxy or history_sessions < 20:
            ff_net_20d = 0.0
        try:
            return compute_score(
                df, tf,
                regime=regime,
                foreign_flow_net=ff_ticker.get("net_buy_value", 0.0),
                foreign_flow_net_20d=ff_net_20d,
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
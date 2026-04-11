"""T+2.5 Exit Engine — ATC window advisory (SRS §3.5, Module 5).

[H1 SRS CONSTRAINT] This module ONLY generates advisory recommendations.
It does NOT place orders.  Exit timing: 14:43–14:45 ATC session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

import numpy as np
import pandas as pd

from ..utils.config import cfg
from ..utils.dates import vn_now, vn_is_atc_time


@dataclass
class T25ExitAdvisory:
    ticker: str
    action: str              # HOLD / SELL_FULL_ATC / SELL_PARTIAL_ATC / EXTEND
    urgency: str             # HIGH / MEDIUM / LOW
    reason: str
    exit_window: str         # e.g. "ATC 14:43"
    exit_pct: float          # fraction to exit (0.0–1.0)
    remark: str = ""
    ts: datetime = field(default_factory=datetime.now)


def _is_atc_time() -> bool:
    return vn_is_atc_time()


def _session_phase() -> str:
    now = vn_now().time()
    if now < time(9, 15):
        return "PRE_OPEN"
    elif now < time(9, 30):
        return "ATO"
    elif now < time(14, 30):
        return "CONTINUOUS"
    elif now < time(14, 43):
        return "NEAR_CLOSE"
    elif now <= time(14, 45):
        return "ATC"
    else:
        return "CLOSED"


def t25_exit_check(
    ticker: str,
    entry_price: float,
    current_price: float,
    entry_date: datetime,
    sl: float,
    tp1: float,
    tp2: float,
    rsi_now: float = 50.0,
    volume_today: float = 0.0,
    avg_volume: float = 1.0,
    distribution_warning: str = "NONE",
    hold_days: int = 0,
) -> T25ExitAdvisory:
    """
    Evaluate T+2.5 exit decision.

    Decision tree (SRS §3.5):
    1. FORCED_EXIT conditions → SELL_FULL_ATC HIGH urgency
    2. SL breached → SELL_FULL_ATC HIGH
    3. TP1 hit & T>=3d → SELL_PARTIAL_ATC (40%)
    4. TP2 hit → SELL_FULL_ATC MEDIUM
    5. Weak hold → EXTEND LOW
    6. Default → HOLD
    """
    pnl_pct = (current_price - entry_price) / max(entry_price, 1)
    vol_ratio = volume_today / max(avg_volume, 1)
    phase = _session_phase()

    # Exit window preference: ATC for large sells
    exit_window = "ATC 14:43" if _is_atc_time() or phase in ("NEAR_CLOSE", "ATC") else "ATC today"

    # ── Forced exit ────────────────────────────────────────────────────────
    if distribution_warning in ("EXIT", "FORCED_EXIT"):
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="HIGH",
            reason=f"Distribution warning={distribution_warning}",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── SL breached ───────────────────────────────────────────────────────
    if current_price <= sl:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="HIGH",
            reason=f"Stop-loss breached: {current_price:.0f} ≤ {sl:.0f} (entry={entry_price:.0f})",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── TP2 hit ───────────────────────────────────────────────────────────
    if current_price >= tp2:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="MEDIUM",
            reason=f"TP2 hit: {current_price:.0f} ≥ {tp2:.0f} (+{pnl_pct:.1%})",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── TP1 hit + hold ≥ 3 days ──────────────────────────────────────────
    if current_price >= tp1 and hold_days >= 3:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_PARTIAL_ATC",
            urgency="MEDIUM",
            reason=f"TP1 hit ({current_price:.0f} ≥ {tp1:.0f}), hold_days={hold_days}. Lock 40% profit.",
            exit_window=exit_window,
            exit_pct=0.40,
            remark="Giữ 60% còn lại, trailing stop từ TP1.",
        )

    # ── Max hold exceeded ─────────────────────────────────────────────────
    max_hold = int(cfg.strategy("entry_exit", "max_hold_days", default=15))
    if hold_days >= max_hold:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_FULL_ATC",
            urgency="MEDIUM",
            reason=f"Max hold {max_hold}d exceeded. PnL={pnl_pct:+.1%}",
            exit_window=exit_window,
            exit_pct=1.0,
        )

    # ── Overbought + high vol surge (potential distribution) ──────────────
    if rsi_now > 80 and vol_ratio > 2.5:
        return T25ExitAdvisory(
            ticker=ticker,
            action="SELL_PARTIAL_ATC",
            urgency="MEDIUM",
            reason=f"RSI={rsi_now:.0f} overbought + vol_surge={vol_ratio:.1f}x",
            exit_window=exit_window,
            exit_pct=0.40,
            remark="Potential blow-off top. Lock partial gains.",
        )

    # ── Default: hold ─────────────────────────────────────────────────────
    return T25ExitAdvisory(
        ticker=ticker,
        action="HOLD",
        urgency="LOW",
        reason=f"PnL={pnl_pct:+.1%}, within range. No exit signal.",
        exit_window="—",
        exit_pct=0.0,
    )


# ── T+2.5 ENTRY SCORE ────────────────────────────────────────────────────────

def compute_t25_entry_score(
    df: pd.DataFrame,
    pattern_result: dict | None = None,
) -> dict:
    """
    VN-Swing Alpha T+2.5 composite entry score (adapted for TradingOS).

    Uses lowercase TradingOS column names: RSI14, MACD_hist, STOCH_K/D,
    WILLIAMS_R, CCI, ADX, DI_plus, DI_minus, SMA20/50/200, EMA9/21,
    BB_lower/mid.

    Groups (regime-adjusted weights):
      A: MOMENTUM   raw 0–20  weight 0.35–0.45
      B: STRUCTURE  raw 0–20  weight 0.30–0.40
      C: CONFIRM    raw 0–10  weight 0.25–0.30

    Returns dict:
      t25_score        float  0–100
      t25_signal       str    T25_BUY | T25_WATCH | T25_NEUTRAL | T25_AVOID
      t25_momo_score   float
      t25_struct_score float
      t25_conf_score   float
      t25_confirms     list[str]
      t25_regime       str
    """
    from .gap_vwap import compute_monthly_pivots, compute_fibonacci_levels

    # ── helpers ──────────────────────────────────────────────────────────────
    def _f(col: str) -> float | None:
        try:
            v = df[col].iloc[-1] if col in df.columns else np.nan
            return None if pd.isna(float(v)) else float(v)
        except Exception:
            return None

    def _arr(col: str, n: int) -> list[float]:
        try:
            if col not in df.columns or len(df) < n:
                return []
            return [float(v) for v in df[col].iloc[-n:].values if not np.isnan(float(v))]
        except Exception:
            return []

    def _nbar(col: str, offset: int) -> float | None:
        try:
            if col not in df.columns or len(df) <= offset:
                return None
            v = df[col].iloc[-offset]
            return None if pd.isna(float(v)) else float(v)
        except Exception:
            return None

    # ── indicator extraction ─────────────────────────────────────────────────
    price    = _f("close")
    rsi      = _f("RSI14")
    rsi_5bar = _nbar("RSI14", 5)
    mh_arr   = _arr("MACD_hist", 4)
    stoch_k  = _f("STOCH_K")
    stoch_k_arr = _arr("STOCH_K", 3)
    stoch_d_arr = _arr("STOCH_D", 3)
    wr       = _f("WILLIAMS_R")
    wr_5bar  = _nbar("WILLIAMS_R", 5)
    cci_now  = _f("CCI")
    cci_4bar = _nbar("CCI", 4)
    ema9     = _f("EMA9");  ema21    = _f("EMA21")
    sma20    = _f("SMA20"); sma50    = _f("SMA50"); sma200 = _f("SMA200")
    bb_lower = _f("BB_lower"); bb_mid = _f("BB_mid")
    adx      = _f("ADX");     di_plus = _f("DI_plus"); di_minus = _f("DI_minus")

    vol_last  = _f("volume")
    vol_avg20 = float(df["volume"].tail(20).mean()) if "volume" in df.columns else None
    vol_ratio = (vol_last / vol_avg20) if (vol_last and vol_avg20 and vol_avg20 > 0) else None
    pct_chg   = None
    try:
        pct_chg = float(df["close"].pct_change().iloc[-1]) * 100
    except Exception:
        pass

    # SMA200 slope (%/20 bars)
    sma200_slope = 0.0
    try:
        s200 = df["SMA200"].dropna()
        if len(s200) >= 20:
            sma200_slope = float((s200.iloc[-1] - s200.iloc[-20]) / s200.iloc[-20] * 100)
    except Exception:
        pass

    # Detect regime inline (avoids circular imports)
    regime = "SIDEWAYS"
    try:
        above_s200 = bool(sma200 and price and price > sma200)
        trending   = bool(adx and adx > 25)
        bull_di    = bool(di_plus and di_minus and di_plus > di_minus)
        if trending and above_s200 and sma200_slope > 0 and bull_di:
            regime = "BULL_TREND"
        elif trending and (not above_s200 or bool(di_plus and di_minus and di_minus > di_plus)):
            regime = "BEAR_TREND"
    except Exception:
        pass

    pivots     = compute_monthly_pivots(df)
    fibs       = compute_fibonacci_levels(df)
    monthly_s1 = pivots.get("monthly_s1")
    fib_618    = fibs.get("fib_618")
    candle_pts = int((pattern_result or {}).get("candle_pts", 0))
    div_pts    = int((pattern_result or {}).get("rsi_div_pts", 0))

    # ── Group A: MOMENTUM (max 20 pts) ───────────────────────────────────────
    A: float = 0.0
    A_c: list[str] = []
    mh = mh_arr
    if len(mh) >= 3:
        if   mh[-1] > mh[-2] > mh[-3]: A += 4; A_c.append("MACD_slope↑")
        elif mh[-1] < mh[-2] < mh[-3]: A -= 4
    if len(mh) >= 3:
        if   mh[-3] < 0 < mh[-1]:  A += 4; A_c.append("MACD_cross↑")
        elif mh[-3] > 0 > mh[-1]:  A -= 2
    if rsi is not None and rsi_5bar is not None:
        if   40 <= rsi <= 60 and rsi > rsi_5bar: A += 3; A_c.append(f"RSI_rec={rsi:.0f}")
        elif 35 <= rsi < 40:                      A += 5; A_c.append(f"RSI_deep={rsi:.0f}")
    if vol_ratio is not None and pct_chg is not None:
        if   vol_ratio > 2.0 and pct_chg > 0: A += 5; A_c.append(f"BreakoutVol={vol_ratio:.1f}x")
        elif vol_ratio > 1.5 and pct_chg > 0: A += 3; A_c.append(f"BullVol={vol_ratio:.1f}x")
    try:
        if (stoch_k is not None and len(stoch_k_arr) >= 2 and len(stoch_d_arr) >= 2
                and stoch_k_arr[-1] > stoch_d_arr[-1]
                and stoch_k_arr[-2] < stoch_d_arr[-2]
                and stoch_k < 40):
            A += 3; A_c.append(f"Stoch_cross={stoch_k:.0f}")
    except Exception:
        pass
    if wr is not None and -80 <= wr <= -50 and wr_5bar is not None and wr > wr_5bar:
        A += 2; A_c.append(f"W%R_rec={wr:.0f}")
    if cci_now is not None and cci_4bar is not None:
        if   cci_now > 0 and cci_4bar < 0:  A += 2; A_c.append("CCI_cross↑0")
        elif cci_now < 0 and cci_4bar > 0:  A -= 2
    A = max(0.0, min(20.0, A))

    # ── Group B: STRUCTURE (max 20 pts) ──────────────────────────────────────
    B: float = 0.0
    B_c: list[str] = []
    ma_lay = sum([
        bool(ema9  and ema21  and ema9  > ema21),
        bool(ema21 and sma50  and ema21 > sma50),
        bool(sma50 and sma200 and sma50 > sma200),
    ])
    B += ma_lay * 1.5
    if ma_lay >= 2: B_c.append(f"MA_align={ma_lay}/3")
    _above_s200 = bool(sma200 and price and price > sma200)
    if   _above_s200 and sma200_slope > 2.0:     B += 4; B_c.append("AboveSMA200+slope↑")
    elif _above_s200:                             B += 2; B_c.append("AboveSMA200")
    elif sma200_slope > 2.0:                     B += 1; B_c.append("SMA200_rising")
    if price and sma20:
        p2s = (price - sma20) / sma20 * 100
        if   -3 <= p2s <= 2: B += 4; B_c.append(f"SMA20_pull={p2s:+.1f}%")
        elif  0 < p2s <= 5:  B += 3; B_c.append(f"SMA20_ok={p2s:+.1f}%")
    if fib_618 and price and price <= fib_618 * 1.02:
        B += 3; B_c.append("Fib_618")
    elif monthly_s1 and price and monthly_s1 * 0.99 <= price <= monthly_s1 * 1.02:
        B += 2; B_c.append("Pivot_S1")
    if price and bb_lower:
        if   price <= bb_lower:                    B += 5; B_c.append("Below_BB")
        elif bb_mid and price <= bb_mid * 0.99:    B += 3; B_c.append("BB_lower_zone")
    if adx and di_plus and di_minus:
        if   adx > 25  and di_plus > di_minus: B += 3; B_c.append(f"ADX_strong={adx:.0f}")
        elif adx >= 20 and di_plus > di_minus: B += 2; B_c.append(f"ADX_emerge={adx:.0f}")
    B = max(0.0, min(20.0, B))

    # ── Group C: CONFIRMATION (max 10 pts) ───────────────────────────────────
    C: float = float(max(0, candle_pts))
    C_c: list[str] = []
    if candle_pts > 0: C_c.append(f"candle+{candle_pts}")
    if div_pts    > 0: C += 4; C_c.append("RSI_div↑")
    if   regime in ("BULL_TREND", "SIDEWAYS"): C += 2; C_c.append("regime_ok")
    elif "BULL" in regime:                     C += 1
    C = max(0.0, min(10.0, C))

    # ── Regime-adjusted weights ───────────────────────────────────────────────
    if   regime == "BULL_TREND": w_m, w_s, w_c = 0.35, 0.40, 0.25
    elif regime == "SIDEWAYS":   w_m, w_s, w_c = 0.45, 0.30, 0.25
    elif regime == "BEAR_TREND": w_m, w_s, w_c = 0.40, 0.30, 0.30
    else:                        w_m, w_s, w_c = 0.40, 0.35, 0.25

    t25 = round(
        w_m * (A / 20 * 100) + w_s * (B / 20 * 100) + w_c * (C / 10 * 100), 1
    )

    # ── Signal thresholds (regime-adjusted) ──────────────────────────────────
    if regime == "BEAR_TREND":
        if   t25 >= 74.8: sig = "T25_BUY"
        elif t25 >= 46.0: sig = "T25_WATCH"
        elif t25 <= 32.0: sig = "T25_AVOID"
        else:             sig = "T25_NEUTRAL"
    else:
        _av = 28.0 if regime == "SIDEWAYS" else 32.0
        if   t25 >= 68.0: sig = "T25_BUY"
        elif t25 >= 55.0: sig = "T25_WATCH"
        elif t25 <= _av:  sig = "T25_AVOID"
        else:             sig = "T25_NEUTRAL"

    return {
        "t25_score":        t25,
        "t25_signal":       sig,
        "t25_momo_score":   round(A, 1),
        "t25_struct_score": round(B, 1),
        "t25_conf_score":   round(C, 1),
        "t25_confirms":     A_c + B_c + C_c,
        "t25_regime":       regime,
    }


# ── T+2.5 MULTI-FRAME SESSION ANALYSIS ───────────────────────────────────────

def compute_t25_multiframe(
    df: pd.DataFrame,
    t25_entry_result: dict | None = None,
    vwap_intraday: dict | None = None,
) -> dict:
    """
    Score the T+2.5 exit/entry opportunity across the three VN trading
    session windows using daily indicator data as a proxy.

    Windows:
      morning   09:15–11:30  best for breakout/momentum buys
      midday    12:45–13:15  T+2.5 settlement window (key for 3-day holders)
      afternoon 13:00–14:30  continuation / ATC fade

    Since we operate on daily bars (no live intraday feed by default),
    each window score is derived from indicator proxies rather than
    real-time tick data.  If ``vwap_intraday`` is supplied it upgrades
    the midday window reliability.

    Parameters
    ----------
    df : pd.DataFrame
        Daily OHLCV + indicators from compute_all().
    t25_entry_result : dict, optional
        Output of compute_t25_entry_score() for this ticker.
    vwap_intraday : dict, optional
        Output of compute_vwap_intraday_result() — may contain
        vwap_intraday_slope (float).

    Returns
    -------
    dict:
        morning_score    float  0–100
        midday_score     float  0–100
        afternoon_score  float  0–100
        best_window      str    "morning" | "midday" | "afternoon" | ""
        mf_signal        str    MF_STRONG_BUY | MF_BUY | MF_WATCH | MF_AVOID
        mf_reasons       list[str]
    """
    t25  = t25_entry_result or {}
    vwap = vwap_intraday    or {}

    base_score = float(t25.get("t25_score") or 0.0)
    t25_sig    = str(t25.get("t25_signal", "T25_NEUTRAL"))
    regime     = str(t25.get("t25_regime", "SIDEWAYS"))

    # ── Extract indicator proxies from last daily bar ──────────────────────
    def _f(col: str) -> float | None:
        try:
            if col not in df.columns:
                return None
            v = df[col].iloc[-1]
            return None if pd.isna(float(v)) else float(v)
        except Exception:
            return None

    rsi      = _f("RSI14")
    mh_last  = _f("MACD_hist")
    adx      = _f("ADX")
    di_plus  = _f("DI_plus")
    di_minus = _f("DI_minus")
    stoch_k  = _f("STOCH_K")
    vol_now  = _f("volume")
    try:
        vol_avg20 = float(df["volume"].tail(20).mean()) if "volume" in df.columns else None
    except Exception:
        vol_avg20 = None
    vol_ratio = (vol_now / vol_avg20) if (vol_now and vol_avg20 and vol_avg20 > 0) else 1.0

    vwap_slope = float(vwap.get("vwap_intraday_slope") or 0.0)

    reasons: list[str] = []

    # ── Morning window score ───────────────────────────────────────────────
    # Momentum + structure alignment → favours breakout entries at open
    morning = base_score * 0.55  # inherit 55% from T+2.5 entry score
    if rsi and 40 <= rsi <= 65:
        morning += 10; reasons.append("RSI vùng tích lũy — sáng phù hợp mua breakout")
    if mh_last and mh_last > 0:
        morning += 8
    if adx and adx > 25:
        morning += 7
    if t25_sig == "T25_BUY":
        morning += 15; reasons.append("T+2.5 tín hiệu mua mạnh — sáng là cửa sổ tốt")
    elif t25_sig == "T25_WATCH":
        morning += 7
    morning = min(100.0, max(0.0, morning))

    # ── Midday window score (T+2.5 settlement focus) ───────────────────────
    # Critical for 3-day holders needing to clear at settlement
    midday = base_score * 0.50
    if t25_sig in ("T25_BUY", "T25_WATCH"):
        midday += 20; reasons.append("Giữa phiên: cửa sổ thanh lý T+2.5 thuận lợi")
    if vwap_slope > 0:
        midday += 10; reasons.append(f"VWAP nội phiên đi lên (slope={vwap_slope:+.2f})")
    elif vwap_slope < 0:
        midday -= 8
    if rsi and rsi < 45:
        midday += 5  # oversold = potential bounce at midday
    if stoch_k and stoch_k < 30:
        midday += 8; reasons.append("Stoch quá bán — bounce giữa phiên có thể xảy ra")
    midday = min(100.0, max(0.0, midday))

    # ── Afternoon window score (continuation / ATC fade) ──────────────────
    # Favours either distributing before ATC or strong continuation buys
    afternoon = base_score * 0.45
    if t25_sig in ("T25_BUY",):
        afternoon += 12
    if adx and di_plus and di_minus and adx > 20 and di_plus > di_minus:
        afternoon += 10; reasons.append("Xu hướng tăng rõ — chiều là cửa sổ tích cực")
    if vol_ratio > 1.5:
        afternoon += 8; reasons.append(f"Khối lượng chiều cao ({vol_ratio:.1f}x)")
    if rsi and rsi > 70:
        afternoon -= 8  # overbought — risky to buy near ATC
    afternoon = min(100.0, max(0.0, afternoon))

    # ── Best window ────────────────────────────────────────────────────────
    scores = {"morning": morning, "midday": midday, "afternoon": afternoon}
    best_window = max(scores, key=lambda k: scores[k]) if any(v > 0 for v in scores.values()) else ""

    # ── Multi-frame signal ─────────────────────────────────────────────────
    best_score = scores.get(best_window, 0.0) if best_window else 0.0
    if   best_score >= 70: mf_sig = "MF_STRONG_BUY"
    elif best_score >= 55: mf_sig = "MF_BUY"
    elif best_score >= 40: mf_sig = "MF_WATCH"
    else:                  mf_sig = "MF_AVOID"

    return {
        "morning_score":   round(morning,   1),
        "midday_score":    round(midday,    1),
        "afternoon_score": round(afternoon, 1),
        "best_window":     best_window,
        "mf_signal":       mf_sig,
        "mf_reasons":      reasons[:5],
    }


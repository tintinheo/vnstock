"""MFPM Engine — Multi-Factor Pullback & Momentum scoring (SRS §3.7, Module 4).

Implements Mode A / Mode B / Mode W scoring with MC gate and Kelly guard.
4-layer Action & Confidence mapping v1.1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.config import cfg
from .indicators import rsi as compute_rsi
from .money_flow import compute_smart_money_score, mode_w_entry_params


# ── Mode A Score (Pullback entry) ─────────────────────────────────────────────

def score_mode_a(df: pd.DataFrame) -> int:
    """
    Mode A: RSI cross-up from ≤50 zone.
    Max score contribution: 60.
    """
    if len(df) < 14:
        return 0
    score = 0

    last = df.iloc[-1]
    prev = df.iloc[-2]
    rsi_now = last.get("RSI14", compute_rsi(df["close"], 14).iloc[-1])
    rsi_prev = prev.get("RSI14", compute_rsi(df["close"], 14).iloc[-2])

    # RSI cross-up from ≤50
    if rsi_prev is not None and rsi_now is not None:
        if float(rsi_prev) <= 50 and float(rsi_now) > 50:
            score += 25
        elif 45 <= float(rsi_now) <= 55:
            score += 10

    # Price near SMA20 (pullback to support)
    if "SMA20" in df.columns:
        sma20 = float(last.get("SMA20", df["close"].rolling(20).mean().iloc[-1]))
        price = float(last["close"])
        pct_from_sma = (price - sma20) / max(sma20, 1)
        if -0.02 <= pct_from_sma <= 0.03:
            score += 15

    # Trend: price above SMA50
    if "SMA50" in df.columns:
        sma50 = float(last.get("SMA50", df["close"].rolling(50).mean().iloc[-1]))
        if float(last["close"]) > sma50:
            score += 10

    # Volume confirmation
    avg_vol = df["volume"].tail(20).mean()
    if float(last["volume"]) > avg_vol * 0.8:
        score += 10

    return min(score, 60)


# ── Mode B Score (Breakout entry) ─────────────────────────────────────────────

def score_mode_b(df: pd.DataFrame) -> int:
    """
    Mode B: Close > Pivot high + Volume surge.
    Max score contribution: 60.
    """
    if len(df) < 20:
        return 0
    score = 0

    last = df.iloc[-1]
    pivot_high = float(df["high"].tail(20).iloc[:-1].max())
    avg_vol = df["volume"].tail(20).mean()

    # Breakout above pivot
    if float(last["close"]) > pivot_high:
        score += 25

    # Volume surge
    vol_ratio = float(last["volume"]) / max(avg_vol, 1)
    if vol_ratio > 1.5:
        score += 20
    elif vol_ratio > 1.2:
        score += 10

    # ATR expansion (momentum)
    if "ATR14" in df.columns:
        atr_now = float(last.get("ATR14", 0))
        atr_avg = float(df["ATR14"].tail(20).mean())
        if atr_now > atr_avg * 1.2:
            score += 10

    # RSI not overbought
    if "RSI14" in df.columns:
        rsi_now = float(last.get("RSI14", 50))
        if 55 <= rsi_now <= 75:
            score += 5

    return min(score, 60)


# ── Mode W Score (Follow-the-Whale) ───────────────────────────────────────────

def score_mode_w(sms_result: dict, pattern_bonus: int = 0, sector_inflow: bool = False) -> int:
    """
    ModeW_score = SMS_components + stealth_bonus + sector_bonus.

    [C1 FIX] ModeW_score != SMS_raw. SMS_raw is one input; ModeW_score is computed.
    Implements Layer 1 from SRS §3.7.
    Max: 115 (100 base + 10 stealth + 5 sector).
    """
    comps = sms_result.get("components", {})

    # SMS component totals (max 100)
    component_total = sum(comps.values())

    # Stealth accumulation bonus
    stealth_det = sms_result.get("stealth_detail", {})
    stealth_conf = stealth_det.get("confidence", "LOW") if stealth_det.get("detected") else "LOW"
    if stealth_conf == "HIGH":
        stealth_bonus = 10
    elif stealth_conf == "MEDIUM":
        stealth_bonus = 5
    else:
        stealth_bonus = 0

    # Sector INFLOW bonus
    sector_bonus = 5 if sector_inflow else 0

    # Distribution veto
    mcvd = sms_result.get("mcvd_detail", {})
    dist_veto = -30 if mcvd.get("mcvd_vs_price") == "DIVERGE_BEARISH" else 0

    mode_w_score = component_total + stealth_bonus + sector_bonus + dist_veto + pattern_bonus
    return int(np.clip(mode_w_score, 0, 115))


# ── Monte Carlo Win Probability ───────────────────────────────────────────────

def monte_carlo_win_prob(
    df: pd.DataFrame,
    entry: float,
    sl: float,
    tp: float,
    n_sim: int = 500,
    horizon: int = 10,
) -> float:
    """
    Quick Monte Carlo: simulate price paths using historical returns.
    Returns probability that price reaches TP before SL.
    """
    if df.empty or entry <= 0 or sl >= entry or tp <= entry:
        return 0.5

    returns = df["close"].pct_change().dropna().tail(252)
    if len(returns) < 30:
        return 0.5

    mu = float(returns.mean())
    sigma = float(returns.std())

    wins = 0
    rng = np.random.default_rng(42)
    for _ in range(n_sim):
        price = entry
        for _ in range(horizon):
            r = rng.normal(mu, sigma)
            price *= (1 + r)
            if price <= sl:
                break
            if price >= tp:
                wins += 1
                break

    return round(wins / n_sim, 3)


# ── ModeW Pre-condition Check ─────────────────────────────────────────────────

def check_mode_w_preconditions(
    sms_raw: int,
    mcvd_trend: str,
    mcvd_consistency: float,
    amf_decision: str,
    hmm_state: str,
    amd_phase: str,
    stealth_accum: bool,
    cvd_today_positive: bool,
    sector_flow: str,
) -> tuple[bool, list[str]]:
    """
    Check Mode W pre-conditions W-1 through W-7 (SRS §8.6).
    Returns (passed, list_of_failed_conditions).
    """
    sms_gate = int(cfg.strategy("whale", "mode_w_sms_gate") or
                   cfg.strategy("mfpm", "mode_w_sms_gate", default=60))
    failures = []

    if sms_raw < sms_gate:            failures.append(f"W-1: SMS_raw={sms_raw} < {sms_gate}")
    if not (mcvd_trend == "UP" and mcvd_consistency >= 0.55):
                                       failures.append(f"W-2: M-CVD {mcvd_trend} consistency={mcvd_consistency:.2f}")
    if amf_decision == "BLOCK":        failures.append("W-3: AMF=BLOCK")
    if hmm_state == "STEADY_BEAR":     failures.append("W-4: HMM=STEADY_BEAR")
    if amd_phase not in ("ACCUMULATION", "MARKUP"):
                                       failures.append(f"W-5: AMD={amd_phase}")
    if not (stealth_accum or cvd_today_positive):
                                       failures.append("W-6: no stealth AND CVD<=0")
    if sector_flow == "OUTFLOW":       failures.append("W-7: sector OUTFLOW")

    return len(failures) == 0, failures


# ── MFPM Engine ───────────────────────────────────────────────────────────────

def compute_mfpm(
    df: pd.DataFrame,
    sms_result: dict,
    amf_result: dict,
    pattern_result: dict,
    hmm_state: str = "TRANSITIONAL",
    amd_phase: str = "RANGING",
    sector_flow: str = "NEUTRAL",
    horizons: list[int] | None = None,
) -> dict:
    """
    Full MFPM scoring pipeline.

    Returns:
        mode_a_score, mode_b_score, mode_w_score, mfpm_score
        action, confidence, signal_mode
        entry, sl, tp1, tp2, rr_ratio, mc_win_prob
        horizons: list of HorizonRecommendation dicts
    """
    horizons = horizons or [2, 3, 4, 5, 7, 10, 15]

    # Base scores
    a = score_mode_a(df)
    b = score_mode_b(df)
    pattern_bonus = pattern_result.get("pattern_bonus", 0)

    # SMS bonus for Mode A/B
    sms_raw = sms_result.get("sms", 0)
    sms_bonus = 0
    if sms_raw >= 75:
        sms_bonus = 20
    elif sms_raw >= 60:
        sms_bonus = 12
    elif sms_raw >= 40:
        sms_bonus = 5
    elif sms_raw < 20:
        sms_bonus = -10

    mcvd_detail = sms_result.get("mcvd_detail", {})
    if mcvd_detail.get("mcvd_vs_price") == "DIVERGE_BEARISH":
        sms_bonus = -25

    base_mfpm = max(a, b) + sms_bonus + pattern_bonus

    # Mode W
    stealth_det = sms_result.get("stealth_detail", {})
    stealth_accum = bool(stealth_det.get("detected", False))
    sector_inflow = sector_flow == "INFLOW"
    w = score_mode_w(sms_result, pattern_bonus=pattern_bonus, sector_inflow=sector_inflow)

    # Determine primary signal mode
    sms_gate = int(cfg.strategy("mfpm", "mode_w_sms_gate", default=60))
    amf_decision = amf_result.get("decision", "PASS")

    mode_w_pass, w_fails = check_mode_w_preconditions(
        sms_raw=sms_raw,
        mcvd_trend=mcvd_detail.get("mcvd_trend", "FLAT"),
        mcvd_consistency=mcvd_detail.get("consistency", 0.0),
        amf_decision=amf_decision,
        hmm_state=hmm_state,
        amd_phase=amd_phase,
        stealth_accum=stealth_accum,
        cvd_today_positive=(sms_result.get("components", {}).get("cvd_today", 5) >= 7),
        sector_flow=sector_flow,
    )

    if mode_w_pass and sms_raw >= sms_gate:
        mfpm_score = max(base_mfpm, w)
        signal_mode = "MODE_W"
    elif a >= b:
        mfpm_score = base_mfpm
        signal_mode = "MODE_A"
    else:
        mfpm_score = base_mfpm
        signal_mode = "MODE_B"

    mfpm_score = int(np.clip(mfpm_score, 0, 120))

    # ── Layer 2: Action decision ───────────────────────────────────────────
    mc_prob_strong = float(cfg.strategy("mfpm", "mc_min_prob_strong", default=0.60))
    mc_prob_buy = float(cfg.strategy("mfpm", "mc_min_prob_buy", default=0.55))
    mode_w_strong = int(cfg.strategy("mode_w", "strong_buy_score", default=95))
    mode_w_buy = int(cfg.strategy("mode_w", "buy_score", default=80))
    mode_w_watch = int(cfg.strategy("mode_w", "watch_score", default=60))

    # Determine entry params first (for MC calc)
    params = mode_w_entry_params(df, sms_result)
    entry = params["entry"]
    sl = params["sl"]
    tp1 = params["tp1"]
    tp2 = params["tp2"]

    mc_prob = monte_carlo_win_prob(df, entry, sl, tp1)

    # Distribution warning override
    dist_warning = sms_result.get("distribution_warning", "NONE")

    if dist_warning in ("EXIT", "FORCED_EXIT"):
        action = dist_warning
        confidence = "—"
    elif amf_decision == "BLOCK" and dist_warning in ("EXIT",):
        action = "FORCED_EXIT"
        confidence = "—"
    elif signal_mode == "MODE_W":
        if w >= mode_w_strong and amf_decision == "PASS" and mc_prob >= mc_prob_strong:
            action = "STRONG_BUY"
        elif w >= mode_w_buy:
            action = "BUY"
        elif w >= mode_w_watch:
            action = "WATCH"
        else:
            action = "NO_ACTION"
    else:
        min_score = int(cfg.strategy("mfpm", "min_score_buy", default=50))
        if mfpm_score >= 70 and amf_decision == "PASS" and mc_prob >= mc_prob_buy:
            action = "BUY"
        elif mfpm_score >= min_score:
            action = "WATCH"
        elif amf_decision == "BLOCK":
            action = "NO_ACTION"
        else:
            action = "NO_ACTION"

    # ── Layer 3: Confidence ────────────────────────────────────────────────
    if action in ("NO_ACTION", "EXIT", "FORCED_EXIT"):
        confidence = "—"
    elif signal_mode == "MODE_W":
        if w >= mode_w_strong and hmm_state == "STEADY_BULL" and mc_prob >= 0.65:
            confidence = "HIGH"
        elif w >= mode_w_buy and amf_decision == "PASS" and mc_prob >= mc_prob_buy:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
    else:
        if mfpm_score >= 80 and hmm_state == "STEADY_BULL":
            confidence = "HIGH"
        elif mfpm_score >= 60:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    # ── Layer 4: Proxy penalty ────────────────────────────────────────────
    data_source = sms_result.get("mcvd_detail", {}).get("data_source", "PROXY_OHLCV")
    penalty = float(cfg.strategy("proxy_confidence_penalty", data_source, default=0))
    if penalty >= 1 and confidence == "HIGH":
        confidence = "MEDIUM"
    elif penalty >= 1 and confidence == "MEDIUM":
        confidence = "LOW"
    elif penalty >= 0.5 and confidence == "MEDIUM":
        confidence = "LOW"

    # Horizon projections
    horizon_recs = _build_horizons(horizons, action, confidence, params, signal_mode, mfpm_score, mc_prob)

    return {
        "mode_a_score": a,
        "mode_b_score": b,
        "mode_w_score": w,
        "mfpm_score": mfpm_score,
        "action": action,
        "confidence": confidence,
        "signal_mode": signal_mode,
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "sl_pct": params.get("sl_pct", 0),
        "rr_ratio": params.get("rr", 0),
        "mc_win_prob": mc_prob,
        "mode_w_failed_conditions": w_fails,
        "horizons": horizon_recs,
    }


def _build_horizons(
    horizons: list[int],
    base_action: str,
    base_confidence: str,
    params: dict,
    signal_mode: str,
    mfpm_score: int,
    mc_prob: float,
) -> list[dict]:
    """Build HorizonRecommendation dicts for each horizon."""
    from ..data.schemas import HorizonRecommendation
    results = []

    label_map = {
        2: "Siêu ngắn hạn (T+2–T+3)",
        3: "Siêu ngắn hạn (T+2–T+3)",
        4: "Ngắn hạn (T+4–T+5)",
        5: "Ngắn hạn (T+4–T+5)",
        7: "Trung hạn (T+7–T+10)",
        10: "Trung hạn (T+7–T+10)",
        12: "Dài hạn (T+12–T+15)",
        15: "Dài hạn (T+12–T+15)",
    }

    for h in horizons:
        # Short horizons may downgrade confidence
        action = base_action
        conf = base_confidence

        # T+2-3: prefer ATC entry
        if h <= 3 and action in ("BUY", "STRONG_BUY"):
            entry_window = "ATC 14:43"
        elif h <= 5:
            entry_window = "14:05–14:20"
        else:
            entry_window = "09:30–10:00 (sau xác nhận mở cửa)"

        # Long horizon requires higher conviction
        if h >= 12 and base_action == "BUY":
            action = "WATCH"  # hold opinion, need reconfirmation
            conf = "LOW"

        entry = params.get("entry", 0)
        sl = params.get("sl", 0)
        sl_pct = params.get("sl_pct", 0)
        tp1 = params.get("tp1", 0)
        tp2 = params.get("tp2", 0)
        rr = params.get("rr", 0)

        rec = {
            "horizon_days": h,
            "period_label": label_map.get(h, f"T+{h}"),
            "action": action,
            "confidence": conf,
            "entry_price": entry,
            "entry_window": entry_window,
            "stop_loss": sl,
            "sl_pct": sl_pct,
            "tp1": tp1,
            "tp2": tp2,
            "rr_ratio": rr,
            "expected_hold_days": h,
            "exit_condition": f"TP1 T+{h//2} sau vào, trailing stop sau TP1",
            "sms_contribution": f"SMS={mfpm_score} | Mode={signal_mode} | MC={mc_prob:.0%}",
            "notes": "",
        }
        results.append(rec)

    return results

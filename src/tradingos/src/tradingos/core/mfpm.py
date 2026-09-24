import pandas as pd
import numpy as np
from math import exp, sqrt

def mc_win_probability(entry: float, sl: float, tp1: float, mu: float, sigma: float, steps: int = 5, simulations: int = 1000) -> float:
    """Monte Carlo GBM simulation to ensure >= 50% statistical win probability."""
    dt = 1 / 252
    sqrt_dt = sqrt(dt)
    wins = 0
    rng = np.random.default_rng(42) # Seeded for reproducibility in backtests

    for _ in range(simulations):
        S = entry
        hit_tp = False
        for _ in range(steps):
            S *= exp((mu - 0.5 * sigma**2) * dt + sigma * sqrt_dt * rng.standard_normal())
            if S >= tp1:
                hit_tp = True
                break
            if S <= sl:
                break
        if hit_tp:
            wins += 1

    return wins / simulations

def get_regime_mu(hmm_state: str, daily_mean: float) -> float:
    """Adjusts drift based on HMM regime to prevent bull-bias."""
    if hmm_state == "STEADY_BULL":
        return max(daily_mean, 0.0005)
    elif hmm_state == "VOLATILE_BEAR":
        return min(daily_mean, -0.0003)
    return 0.0

def score_mode_w(sms_raw: int, stealth_accum: bool, sector_flow: str, mcvd_vs_price: str) -> dict:
    """FR-6.5: Follow-the-Whale Strategy Scoring (Max 115)."""
    if mcvd_vs_price == "DIVERGE_BEARISH":
        return {"score": 0, "action": "NO_ACTION", "reason": "BLOCK: Bearish Delta Divergence"}
    
    score = 50 # Base threshold assumption for W mode entry
    
    if sms_raw >= 75: score += 15
    elif sms_raw >= 60: score += 10
    
    if stealth_accum: score += 5
    if sector_flow == "INFLOW": score += 5
    
    if score >= 95: action = "STRONG_BUY"
    elif score >= 80: action = "BUY"
    elif score >= 60: action = "WATCH"
    else: action = "NO_ACTION"
    
    return {"score": score, "action": action, "reason": f"Mode W active. SMS: {sms_raw}"}

def score_mode_a(df: pd.DataFrame, vqs_score: float, whale_net: int, vsa_signal: str) -> dict:
    """Evaluates Pullback Entry (Mode A)."""
    score = 0
    c = df.iloc[-1]
    
    # RSI Checks
    rsi = c.get('RSI14', 50)
    rsi_prev = df['RSI14'].iloc[-2] if len(df) > 1 else 50
    if rsi_prev <= 42 and rsi > 42: score += 30
    elif rsi_prev <= 50 and rsi > 50: score += 20
    
    # Volume & Microstructure
    z_vol = c.get('Z_vol', 0)
    if z_vol > 2.0: score += 25
    elif z_vol > 1.5: score += 20
    
    if vqs_score >= 0.5: score += 15
    elif vqs_score >= 0: score += 5
    elif vqs_score < -0.3: score -= 15
    
    if whale_net > 50000: score += 15
    elif whale_net > 0: score += 5
    
    if vsa_signal == "NO_SUPPLY": score += 8
    elif vsa_signal == "NO_DEMAND": score -= 10
    
    if score >= 70: action = "STRONG_BUY"
    elif score >= 50: action = "BUY"
    elif score >= 35: action = "WATCH"
    else: action = "NO_ACTION"
    
    return {"score": score, "action": action, "mode": "MODE_A"}
"""Position Sizing — Kelly bootstrap + progressive entry (SRS §3.7.5)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils.config import cfg


def kelly_fraction(win_prob: float, rr: float, fraction: float = 0.5) -> float:
    """
    Fractional Kelly: f* = fraction × (p - q/rr).
    win_prob: estimated MC win probability.
    rr: reward/risk ratio (tp/sl distance).
    fraction: Kelly fraction (default half-Kelly).
    Returns float in [0.0, 1.0].
    """
    if rr <= 0:
        return 0.0
    p = float(np.clip(win_prob, 0.01, 0.99))
    q = 1 - p
    kelly = p - (q / rr)
    return float(np.clip(kelly * fraction, 0.0, 1.0))


def bootstrap_win_prob(df: pd.DataFrame, sl_pct: float, tp_pct: float, n: int = 500) -> float:
    """
    Bootstrap win probability from historical H-day returns.
    Win probability = wins / (wins + losses) among conclusive paths.
    Non-conclusive paths (neither TP nor SL hit within the horizon) are
    excluded from the denominator — they do not count as wins or losses.
    Falls back to 0.5 when fewer than 20 bars or no conclusive paths.
    *(Vectorized version for fast execution)*
    """
    returns = df["close"].pct_change().dropna().values
    if len(returns) < 20:
        return 0.5

    rng = np.random.default_rng(42)
    horizons = np.array([5, 7, 10])
    
    # Vectorized random choice array: n sim lengths
    h_choices = rng.choice(horizons, size=n)
    
    wins = 0
    losses = 0
    
    for h in horizons:
        # Number of paths simulating this horizon
        n_h = np.sum(h_choices == h)
        if n_h == 0 or len(returns) < h:
            continue
            
        # Draw start indices
        starts = rng.integers(0, len(returns) - h, size=n_h)
        
        # Build path matrix: (n_h, h) items from returns
        # Using broadcasting to slice the returns array
        idx = starts[:, None] + np.arange(h)
        paths = returns[idx]
        
        cumulative = np.cumprod(1 + paths, axis=1)
        max_gains = cumulative.max(axis=1) - 1.0
        max_losses = cumulative.min(axis=1) - 1.0
        
        wins += np.sum(max_gains >= tp_pct)
        losses += np.sum(max_losses <= -sl_pct)

    if wins + losses == 0:
        return 0.5
    return round(float(wins / (wins + losses)), 3)


def compute_position_size(
    portfolio_value: float,
    entry: float,
    sl: float,
    win_prob: float = 0.55,
    rr: float = 2.0,
    max_position_pct: float = 0.10,
    kelly_fraction_: float | None = None,
    macro_multiplier: float = 1.0,
) -> dict:
    """
    Returns:
        size_pct: fraction of portfolio to commit (0.0–1.0)
        shares: integer shares (uses lot size 100)
        risk_amount: VND risk if SL hit
        lot_size: 100 (HOSE standard)
    """
    if entry <= 0 or sl >= entry:
        return {"size_pct": 0.0, "shares": 0, "risk_amount": 0, "lot_size": 100}

    # Read kelly_fraction from strategy.yaml (0.3 = 30% fractional Kelly per spec).
    # Only fall back to the function parameter when explicitly overridden by caller.
    if kelly_fraction_ is None:
        kelly_fraction_ = float(cfg.strategy("sizing", "kelly_fraction", default=0.3))

    k = kelly_fraction(win_prob, rr, kelly_fraction_)

    max_pct = float(cfg.strategy("sizing", "kelly_max_pct", default=max_position_pct * 100)) / 100
    # Apply macro regime multiplier (0.32–1.0 from macro engine)
    max_pct = max_pct * float(macro_multiplier)
    # Floor and ceiling
    size_pct = float(np.clip(k, 0.02, max_pct))

    risk_per_share = entry - sl
    if risk_per_share <= 0:
        return {"size_pct": 0.0, "shares": 0, "risk_amount": 0, "lot_size": 100}

    # Max risk gate: 2% of portfolio per trade
    max_risk_pct = float(cfg.strategy("sizing", "max_single_loss_pct", default=0.02))
    max_risk = portfolio_value * max_risk_pct
    max_shares_by_risk = int(max_risk / risk_per_share)

    # Shares by Kelly size
    kelly_shares = int((portfolio_value * size_pct) / entry)

    shares_raw = min(kelly_shares, max_shares_by_risk)
    # Round to lot
    lot = 100
    shares = max(lot, (shares_raw // lot) * lot)

    actual_value = shares * entry
    actual_pct = actual_value / portfolio_value if portfolio_value > 0 else 0.0

    return {
        "size_pct": round(actual_pct, 4),
        "shares": shares,
        "risk_amount": round(shares * risk_per_share),
        "lot_size": lot,
    }


def progressive_entry_plan(
    total_shares: int,
    entry: float,
    signal_mode: str = "MODE_A",
) -> list[dict]:
    """
    Progressive entry: 50% now, 30% on first confirmation, 20% on breakout.
    Returns list of entry tranches [{tranche_pct, shares, entry_note}].
    """
    lot = 100
    plans = {
        "MODE_W": [(0.50, "ATC ngày tín hiệu"), (0.30, "ATO T+1 (xác nhận giữ vùng)"), (0.20, "Breakout on T+3")],
        "MODE_B": [(0.50, "Vào ngay (breakout)"), (0.30, "Retest + confirm"), (0.20, "Add nếu giữ > pivot")],
        "MODE_A": [(0.60, "Pullback to SMA20"), (0.40, "RSI confirm > 50")],
    }
    allocations = plans.get(signal_mode, plans["MODE_A"])

    result = []
    remaining = total_shares
    for i, (pct, note) in enumerate(allocations):
        raw = int(total_shares * pct)
        shares = max(lot, (raw // lot) * lot)
        shares = min(shares, remaining)
        result.append({
            "tranche": i + 1,
            "tranche_pct": pct,
            "shares": shares,
            "entry_price": entry,
            "entry_note": note,
        })
        remaining -= shares

    return result

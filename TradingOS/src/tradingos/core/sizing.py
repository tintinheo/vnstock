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

    # [BUG-1 FIX] Do NOT use a fixed seed in production — deterministic MC gives
    # identical results across calls and defeats statistical sampling.
    rng = np.random.default_rng()
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
    # [BUG-16 FIX] No floor: Kelly ≤ 0 means no statistical edge — return zero size.
    # Old code clipped to 0.02 minimum, forcing 2% allocation even when edge is absent.
    size_pct = float(np.clip(k, 0.0, max_pct))

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
    # Round down to lot (100 shares).  [BUG-8 FIX] Never force a minimum lot:
    # if risk budget only supports < 1 lot, return 0 shares so the risk
    # cap is respected.  Old code: max(lot, ...) could allocate 100 shares
    # when shares_raw=0, violating the 2% max-loss policy.
    lot = 100
    shares = (shares_raw // lot) * lot

    # [BUG-B FIX] Enforce min_position_pct gate from strategy.yaml.
    # Do not open a position too small to be meaningful — it wastes a position slot
    # and produces unrealistically low commission-adjusted returns.
    # If the computed allocation would be below the minimum, return zero shares.
    if shares > 0 and portfolio_value > 0:
        min_pos_pct = float(cfg.strategy("sizing", "min_position_pct", default=0.0)) / 100
        provisional_pct = (shares * entry) / portfolio_value
        if min_pos_pct > 0 and provisional_pct < min_pos_pct:
            shares = 0

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
    n_tranches = len(allocations)
    for i, (pct, note) in enumerate(allocations):
        is_last = (i == n_tranches - 1)
        if is_last:
            # [BUG-19 FIX] Last tranche absorbs all remaining to prevent lot-rounding leakage.
            shares = (remaining // lot) * lot
        else:
            raw = int(total_shares * pct)
            # Round down to lot — no forced minimum; see BUG-19 fix.
            shares = (raw // lot) * lot
        if shares == 0 and remaining >= lot:
            shares = lot  # absorb into this tranche if any full lots remain
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


# ── ATR-Based Position Sizing ─────────────────────────────────────────────────

def compute_atr_position_size(
    entry_price: float,
    atr14: float,
    portfolio_value: float,
    risk_pct: float | None = None,
    atr_mult: float | None = None,
    amf_decision: str = "PASS",
) -> dict:
    """
    ATR-based position sizing (proposal §Phase II).

    Formula:
        stop_distance  = ATR14 × atr_mult
        stop_price     = entry_price - stop_distance
        risk_amount    = portfolio_value × risk_pct
        shares_raw     = risk_amount / stop_distance
        shares         = floor(shares_raw / 100) × 100   (lot-rounded)

    AMF gating:
        BLOCK → 0 shares (no position allowed)
        WARN  → shares × warn_size_multiplier (default 0.5 = half size)
        PASS  → full shares

    Args:
        entry_price      : current / expected entry price (VND)
        atr14            : 14-day Average True Range from indicators (VND)
        portfolio_value  : total portfolio value (VND)
        risk_pct         : fraction of portfolio to risk per trade (default from config)
        atr_mult         : ATR multiplier for stop distance (default from config)
        amf_decision     : "PASS" | "WARN" | "BLOCK" from run_amf()

    Returns dict:
        atr_position_shares  : int   — lot-rounded share count
        atr_stop_price       : float — calculated stop-loss level
        atr_stop_distance    : float — VND distance (ATR × mult)
        atr_position_value   : float — position notional (shares × entry)
        atr_risk_amount      : float — VND risk if stop is hit
        atr_risk_pct_actual  : float — actual risk as fraction of portfolio
        atr_size_pct         : float — position value as fraction of portfolio
    """
    _zero = {
        "atr_position_shares": 0,
        "atr_stop_price": 0.0,
        "atr_stop_distance": 0.0,
        "atr_position_value": 0.0,
        "atr_risk_amount": 0.0,
        "atr_risk_pct_actual": 0.0,
        "atr_size_pct": 0.0,
    }

    if entry_price <= 0 or atr14 <= 0 or portfolio_value <= 0:
        return _zero

    # AMF BLOCK: no position
    if amf_decision == "BLOCK":
        return _zero

    # Load config
    if risk_pct is None:
        risk_pct = float(cfg.strategy("position_sizing", "risk_pct", default=0.01))
    if atr_mult is None:
        atr_mult = float(cfg.strategy("position_sizing", "atr_mult", default=2.0))

    stop_distance = atr14 * atr_mult
    stop_price    = entry_price - stop_distance

    if stop_distance <= 0:
        return _zero

    risk_amount  = portfolio_value * risk_pct
    shares_raw   = risk_amount / stop_distance

    # Lot-round (HOSE standard 100 shares)
    lot = 100
    shares = int(shares_raw // lot) * lot

    # AMF WARN: half size
    if amf_decision == "WARN":
        warn_mult = float(cfg.strategy("position_sizing", "warn_size_multiplier", default=0.5))
        shares = int((shares * warn_mult) // lot) * lot

    if shares <= 0:
        return _zero

    position_value   = shares * entry_price
    actual_risk      = shares * stop_distance
    actual_risk_pct  = actual_risk / portfolio_value
    size_pct         = position_value / portfolio_value

    return {
        "atr_position_shares": shares,
        "atr_stop_price":      round(stop_price, 1),
        "atr_stop_distance":   round(stop_distance, 1),
        "atr_position_value":  round(position_value),
        "atr_risk_amount":     round(actual_risk),
        "atr_risk_pct_actual": round(actual_risk_pct, 4),
        "atr_size_pct":        round(size_pct, 4),
    }


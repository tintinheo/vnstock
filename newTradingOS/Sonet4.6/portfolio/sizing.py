"""
portfolio/sizing.py — NewTradingOS v14.0
Kelly Criterion position sizing & portfolio risk budget allocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np

from config import (
    TIMEFRAME_CONFIG, PORTFOLIO_PROFILES,
    BUY_TOTAL, SELL_TOTAL, LOT_SIZE,
    annualization_sessions_per_year,
)


# ─────────────────────────────────────────────────────────────
# KELLY CRITERION
# ─────────────────────────────────────────────────────────────
def kelly_fraction(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    kelly_fraction: float = 0.5,    # half-Kelly
    max_fraction: float  = 0.25,
    min_fraction: float  = 0.03,
) -> float:
    """
    Compute optimal position fraction via Kelly Criterion.

    f* = (p*b - q) / b    where b = avg_win / avg_loss, q = 1 - p

    Parameters
    ----------
    win_rate       : historical win rate [0, 1]
    avg_win_pct    : average winning trade return (e.g. 0.08 for 8%)
    avg_loss_pct   : average losing trade loss (e.g. 0.04 for 4%, positive)
    kelly_fraction : fraction of full Kelly to use (0.5 = half-Kelly)
    max_fraction   : hard cap on position size
    min_fraction   : minimum position size
    """
    if avg_loss_pct <= 0 or win_rate <= 0 or win_rate >= 1:
        return min_fraction
    b = avg_win_pct / avg_loss_pct
    p = win_rate
    q = 1 - p
    full_kelly = (p * b - q) / b
    adjusted   = full_kelly * kelly_fraction
    return float(np.clip(adjusted, min_fraction, max_fraction))


def position_size_vnd(
    capital: float,
    fraction: float,
    price: float,
    lot_size: int = LOT_SIZE,
) -> tuple[int, float]:
    """
    Convert Kelly fraction to VN lot-size aligned shares and VND amount.

    Returns
    -------
    (n_shares, vnd_amount)
    """
    target_vnd = capital * fraction
    raw_shares = target_vnd / price
    # VN minimum order = 1 lot (100 shares). If the capital allocation
    # cannot afford even 1 lot, return (0, 0.0) so the caller can skip
    # the trade rather than silently overcapitalising the account.
    if raw_shares < lot_size:
        return 0, 0.0
    n_lots   = int(raw_shares // lot_size)
    n_shares = n_lots * lot_size
    vnd_amt  = n_shares * price * (1 + BUY_TOTAL)
    return n_shares, round(vnd_amt, 0)


# ─────────────────────────────────────────────────────────────
# TRADE METRICS TRACKER
# ─────────────────────────────────────────────────────────────
@dataclass
class TradeStats:
    n_trades:      int   = 0
    n_wins:        int   = 0
    n_losses:      int   = 0
    total_pnl_pct: float = 0.0
    avg_win_pct:   float = 0.0
    avg_loss_pct:  float = 0.0

    @property
    def win_rate(self) -> float:
        return self.n_wins / self.n_trades if self.n_trades > 0 else 0.5

    @property
    def profit_factor(self) -> float:
        gross_win  = self.avg_win_pct  * self.n_wins   if self.n_wins   > 0 else 0
        gross_loss = self.avg_loss_pct * self.n_losses if self.n_losses > 0 else 1e-9
        return gross_win / gross_loss

    @property
    def kelly(self) -> float:
        return kelly_fraction(self.win_rate, self.avg_win_pct, self.avg_loss_pct)

    def update(self, pnl_pct: float) -> None:
        self.n_trades      += 1
        self.total_pnl_pct += pnl_pct
        if pnl_pct > 0:
            self.n_wins += 1
            # Running average
            self.avg_win_pct = (self.avg_win_pct * (self.n_wins - 1) + pnl_pct) / self.n_wins
        else:
            self.n_losses += 1
            self.avg_loss_pct = (self.avg_loss_pct * (self.n_losses - 1) + abs(pnl_pct)) / self.n_losses


# ─────────────────────────────────────────────────────────────
# PORTFOLIO BUDGET ALLOCATION
# ─────────────────────────────────────────────────────────────
def allocate_budget(
    total_capital: float,
    profile: str = "balanced",
) -> dict[str, float]:
    """
    Return capital budget per timeframe bucket.

    Returns
    -------
    dict[timeframe → VND budget]
    """
    cfg = PORTFOLIO_PROFILES.get(profile, PORTFOLIO_PROFILES["balanced"])
    return {
        tf: round(total_capital * alloc, 0)
        for tf, alloc in cfg["alloc"].items()
    }


def compute_portfolio_metrics(
    equity_curve: list[float],
    trades: list[dict],
    date_index=None,
) -> dict:
    """
    Compute key portfolio performance metrics.

    Parameters
    ----------
    equity_curve : list of portfolio values (one per session)
    trades       : list of trade dicts with 'pnl_pct' key

    Returns
    -------
    dict with sharpe, calmar, max_dd, win_rate, profit_factor, cagr
    """
    eq = np.array(equity_curve, dtype=float)
    if len(eq) < 2:
        return {}

    returns   = np.diff(eq) / eq[:-1]
    total_ret = (eq[-1] / eq[0]) - 1
    n_sessions = len(eq)
    metric_dates = None
    if date_index is not None:
        normalized_dates = [value for value in date_index if value is not None]
        if len(normalized_dates) == len(eq):
            metric_dates = normalized_dates[1:]
        elif len(normalized_dates) >= len(returns):
            metric_dates = normalized_dates[-len(returns):]
        elif normalized_dates:
            metric_dates = normalized_dates
    annual_sessions = annualization_sessions_per_year(metric_dates)
    cagr       = (1 + total_ret) ** (annual_sessions / n_sessions) - 1

    # Sharpe (annualised)
    # Lãi suất phi rủi ro tham chiếu: tiền gửi VN 2025 dao động 4.5-5.5%/năm (NHNN).
    # Dùng 4.5% để phản ánh đúng chi phí cơ hội thực tế của nhà đầu tư VN.
    rf_daily = 0.045 / annual_sessions  # 4.5% VN deposit rate (NHNN benchmark)
    excess   = returns - rf_daily
    sharpe   = (excess.mean() / (excess.std() + 1e-9)) * np.sqrt(annual_sessions)

    # Max Drawdown
    peak    = np.maximum.accumulate(eq)
    dd      = (eq - peak) / peak
    max_dd  = float(dd.min())

    # Calmar
    calmar  = cagr / abs(max_dd) if max_dd != 0 else 0.0

    # Trade-level
    pnls    = [t["pnl_pct"] for t in trades if "pnl_pct" in t]
    wins    = [p for p in pnls if p > 0]
    losses  = [p for p in pnls if p <= 0]
    win_rt  = len(wins) / len(pnls) if pnls else 0.0
    pf      = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else 0.0

    return {
        "cagr":           round(cagr * 100, 2),
        "total_return":   round(total_ret * 100, 2),
        "sharpe":         round(float(sharpe), 3),
        "calmar":         round(calmar, 3),
        "max_dd":         round(max_dd * 100, 2),
        "win_rate":       round(win_rt * 100, 2),
        "profit_factor":  round(pf, 3),
        "n_trades":       len(pnls),
        "annual_sessions": annual_sessions,
        "avg_win":        round(np.mean(wins) * 100, 2) if wins else 0,
        "avg_loss":       round(np.mean(losses) * 100, 2) if losses else 0,
    }


# ─────────────────────────────────────────────────────────────
# RISK BUDGET CHECK
# ─────────────────────────────────────────────────────────────
def _position_risk_vnd(position: dict) -> float:
    """Estimate VND at risk for one position using stop distance.

    Preferred input is ``stop_loss_pct`` as a decimal fraction. When unavailable,
    derive the risk from ``entry_price`` and ``stop_loss`` so callers that store
    price levels still get a correct risk-budget check.
    """
    size_vnd = float(position.get("size_vnd", 0.0) or 0.0)
    stop_loss_pct = position.get("stop_loss_pct")

    if stop_loss_pct is None:
        entry_price = float(position.get("entry_price", 0.0) or 0.0)
        stop_loss = position.get("stop_loss")
        if entry_price > 0 and stop_loss is not None:
            stop_loss_pct = 1.0 - (float(stop_loss) / entry_price)
        else:
            stop_loss_pct = 0.05

    stop_loss_pct = float(stop_loss_pct)
    if stop_loss_pct > 1.0:
        stop_loss_pct /= 100.0
    stop_loss_pct = float(np.clip(stop_loss_pct, 0.0, 1.0))
    return size_vnd * stop_loss_pct


def check_risk_budget(
    open_positions: list[dict],
    new_trade: dict,
    total_capital: float,
    tf: str,
    max_portfolio_risk_pct: float = 0.20,
) -> tuple[bool, str]:
    """
    Check if a new trade fits within risk budget.

    Returns
    -------
    (allowed: bool, reason: str)
    """
    cfg = TIMEFRAME_CONFIG[tf]

    # Count positions in this timeframe bucket
    tf_positions = [p for p in open_positions if p.get("tf") == tf]
    if len(tf_positions) >= cfg["max_positions"]:
        return False, f"Max positions for {tf} reached ({cfg['max_positions']})"

    # Check total capital at risk
    total_at_risk = sum(_position_risk_vnd(p) for p in open_positions)
    new_at_risk = _position_risk_vnd(new_trade)
    if (total_at_risk + new_at_risk) / total_capital > max_portfolio_risk_pct:
        return False, "Portfolio risk budget exceeded"

    return True, "OK"

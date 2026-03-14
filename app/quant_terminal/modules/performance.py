"""
Performance analytics — Sharpe, Sortino, Max Drawdown, Trade Stats, Monthly P&L.
All functions operate on pandas Series / DataFrames and return plain Python dicts.
"""
import math
import logging
import datetime as dt
from collections import deque
from typing import Optional

import pandas as pd
import numpy as np

_log = logging.getLogger("performance")

# VN risk-free rate: SBV 1-year T-bond approximate yield
VN_RISK_FREE = 0.045   # 4.5% p.a.


# ─── RETURNS-BASED METRICS ────────────────────────────────────────────────────

def compute_sharpe(returns: pd.Series, rf: float = VN_RISK_FREE) -> float:
    """
    Annualised Sharpe ratio.
    returns : daily simple returns (decimal), e.g. 0.015 for +1.5%
    rf      : annual risk-free rate (decimal)
    Returns NaN when insufficient data (<10 observations).
    """
    r = returns.dropna()
    if len(r) < 10:
        return float("nan")
    rf_daily = (1 + rf) ** (1 / 252) - 1
    excess   = r - rf_daily
    std      = excess.std()
    if std == 0 or math.isnan(std):
        return float("nan")
    return float(excess.mean() / std * math.sqrt(252))


def compute_sortino(returns: pd.Series, rf: float = VN_RISK_FREE) -> float:
    """
    Annualised Sortino ratio (uses downside semi-deviation only).
    Returns NaN when insufficient data or no negative returns.
    """
    r = returns.dropna()
    if len(r) < 10:
        return float("nan")
    rf_daily = (1 + rf) ** (1 / 252) - 1
    excess   = r - rf_daily
    downside = excess[excess < 0]
    if len(downside) < 2:
        return float("nan")
    downside_std = math.sqrt(float((downside ** 2).mean()))
    if downside_std == 0:
        return float("nan")
    return float(excess.mean() / downside_std * math.sqrt(252))


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum drawdown from rolling peak, expressed as a percentage.
    Returns a negative number, e.g. -18.5 means -18.5% max drawdown.
    equity_curve : cumulative portfolio values indexed by date.
    """
    eq = equity_curve.dropna()
    if len(eq) < 2:
        return 0.0
    rolling_peak = eq.cummax()
    with np.errstate(invalid="ignore", divide="ignore"):
        drawdowns = (eq - rolling_peak) / rolling_peak * 100
    val = float(drawdowns.min())
    return val if not math.isnan(val) else 0.0


# ─── TRADE-LOG METRICS ────────────────────────────────────────────────────────

def compute_trade_stats(df_log: pd.DataFrame) -> dict:
    """
    Compute win rate, profit factor, average R:R, and avg P&L % from trade log.
    Uses FIFO matching to pair Mua → Bán trades by symbol.

    df_log must have columns: date, symbol, side ("Mua"|"Bán"), qty, price
    Returns dict with keys: total, wins, losses, win_rate, profit_factor,
                             avg_rr, avg_win_pct, avg_loss_pct
    """
    if df_log is None or df_log.empty:
        return _empty_trade_stats()

    df = df_log.copy()
    df["price"]  = pd.to_numeric(df.get("price",  0), errors="coerce").fillna(0)
    df["qty"]    = pd.to_numeric(df.get("qty",    0), errors="coerce").fillna(0)
    df["side"]   = df.get("side",   "").astype(str)
    df["symbol"] = df.get("symbol", "").astype(str)

    # Sort by date then FIFO
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.sort_values("date")

    buys: dict = {}   # symbol → deque of (cost_price, qty)
    completed_trades: list = []

    for _, row in df.iterrows():
        sym   = row["symbol"]
        side  = row["side"]
        price = float(row["price"])
        qty   = float(row["qty"])

        if side == "Mua":
            if sym not in buys:
                buys[sym] = deque()
            buys[sym].append((price, qty))

        elif side == "Bán" and sym in buys and buys[sym]:
            remaining = qty
            total_cost = 0.0
            matched_qty = 0.0
            while remaining > 0 and buys[sym]:
                buy_price, buy_qty = buys[sym][0]
                take = min(remaining, buy_qty)
                total_cost  += buy_price * take
                matched_qty += take
                remaining   -= take
                if take >= buy_qty:
                    buys[sym].popleft()
                else:
                    buys[sym][0] = (buy_price, buy_qty - take)
            if matched_qty > 0:
                avg_cost = total_cost / matched_qty
                pnl_pct  = (price / avg_cost - 1) * 100 if avg_cost > 0 else 0
                completed_trades.append(pnl_pct)

    if not completed_trades:
        return _empty_trade_stats()

    wins   = [t for t in completed_trades if t > 0]
    losses = [t for t in completed_trades if t <= 0]
    total  = len(completed_trades)

    win_rate      = len(wins) / total if total > 0 else 0.0
    avg_win_pct   = float(np.mean(wins))   if wins   else 0.0
    avg_loss_pct  = float(np.mean(losses)) if losses else 0.0   # negative value
    sum_wins      = sum(wins)
    sum_losses    = abs(sum(losses))
    profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else 0.0
    avg_rr        = round(abs(avg_win_pct / avg_loss_pct), 2) if avg_loss_pct != 0 else 0.0

    return {
        "total":         total,
        "wins":          len(wins),
        "losses":        len(losses),
        "win_rate":      round(win_rate * 100, 1),
        "profit_factor": profit_factor,
        "avg_rr":        avg_rr,
        "avg_win_pct":   round(avg_win_pct, 2),
        "avg_loss_pct":  round(avg_loss_pct, 2),
    }


def _empty_trade_stats() -> dict:
    return {
        "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
        "profit_factor": 0.0, "avg_rr": 0.0,
        "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
    }


# ─── MONTHLY P&L CALENDAR ────────────────────────────────────────────────────

def build_monthly_pnl(df_log: pd.DataFrame) -> pd.DataFrame:
    """
    Build month × year P&L summary from trade log.
    Approximation: P&L per month = sell_value - buy_value within that month.

    Returns DataFrame with columns: year, month, pnl_vnd, n_trades
    Suitable for a Plotly calendar heatmap (pivot on year × month).
    """
    if df_log is None or df_log.empty:
        return pd.DataFrame(columns=["year", "month", "pnl_vnd", "n_trades"])

    df = df_log.copy()
    df["date"]  = pd.to_datetime(df.get("date",  ""), errors="coerce")
    df["value"] = pd.to_numeric(df.get("value", 0),  errors="coerce").fillna(0)
    df["side"]  = df.get("side", "").astype(str)
    df = df.dropna(subset=["date"])

    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month

    def _month_pnl(grp: pd.DataFrame) -> pd.Series:
        sell = grp.loc[grp["side"] == "Bán", "value"].sum()
        buy  = grp.loc[grp["side"] == "Mua", "value"].sum()
        return pd.Series({"pnl_vnd": sell - buy, "n_trades": len(grp)})

    result = (
        df.groupby(["year", "month"], group_keys=False)
          .apply(_month_pnl, include_groups=False)
          .reset_index()
    )
    return result

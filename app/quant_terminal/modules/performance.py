"""
Performance — Sharpe, Sortino, max drawdown, trade stats, monthly P&L.
"""
import logging
import math

import numpy as np
import pandas as pd

_log = logging.getLogger("performance")

_RISK_FREE_RATE_ANNUAL = 0.045   # 4.5% VN deposit rate proxy
_TRADING_DAYS          = 252


def _annual_rf() -> float:
    return _RISK_FREE_RATE_ANNUAL / _TRADING_DAYS


# ── RATIOS ────────────────────────────────────────────────────────────────────

def compute_sharpe(returns: pd.Series) -> float:
    """Annualised Sharpe ratio from daily returns series."""
    if returns is None or len(returns) < 10:
        return float("nan")
    try:
        r = pd.to_numeric(returns, errors="coerce").dropna()
        if len(r) < 10:
            return float("nan")
        excess = r - _annual_rf()
        std    = float(excess.std())
        if std == 0:
            return float("nan")
        return round(float(excess.mean() / std * math.sqrt(_TRADING_DAYS)), 3)
    except Exception as e:
        _log.warning("compute_sharpe: %s", e)
        return float("nan")


def compute_sortino(returns: pd.Series) -> float:
    """Annualised Sortino ratio (downside deviation only)."""
    if returns is None or len(returns) < 10:
        return float("nan")
    try:
        r = pd.to_numeric(returns, errors="coerce").dropna()
        if len(r) < 10:
            return float("nan")
        excess    = r - _annual_rf()
        downside  = excess[excess < 0]
        down_std  = float(downside.std()) if len(downside) > 1 else float("nan")
        if not down_std or math.isnan(down_std) or down_std == 0:
            return float("nan")
        return round(float(excess.mean() / down_std * math.sqrt(_TRADING_DAYS)), 3)
    except Exception as e:
        _log.warning("compute_sortino: %s", e)
        return float("nan")


def compute_max_drawdown(equity: pd.Series) -> float:
    """Maximum drawdown in % from equity curve (any units, same throughout)."""
    if equity is None or len(equity) < 2:
        return 0.0
    try:
        eq       = pd.to_numeric(equity, errors="coerce").dropna()
        if len(eq) < 2:
            return 0.0
        rolling_max = eq.cummax()
        dd          = (eq / rolling_max - 1) * 100
        return round(float(dd.min()), 2)
    except Exception as e:
        _log.warning("compute_max_drawdown: %s", e)
        return 0.0


# ── TRADE STATS ───────────────────────────────────────────────────────────────

def compute_trade_stats(trade_df: pd.DataFrame) -> dict:
    """
    Compute win rate, profit factor, and average R:R from a trade log.
    trade_df expected columns: symbol, side, qty, price, value.
    Pairs Mua + Bán per symbol to compute realized P&L.
    """
    EMPTY = {
        "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
        "profit_factor": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "avg_rr": 0.0,
    }
    if trade_df is None or trade_df.empty:
        return EMPTY

    df = trade_df.copy()
    required = {"side", "qty", "price"}
    if not required.issubset(set(df.columns)):
        return EMPTY

    df["qty"]   = pd.to_numeric(df["qty"],   errors="coerce").fillna(0)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)

    # Match buys to sells per symbol
    wins = []
    loss = []

    for sym, grp in df.groupby("symbol") if "symbol" in df.columns else [("all", df)]:
        buys  = grp[grp["side"].str.lower().isin(["mua", "buy"])].copy()
        sells = grp[grp["side"].str.lower().isin(["bán", "ban", "sell"])].copy()
        if buys.empty or sells.empty:
            continue

        avg_cost = float((buys["price"] * buys["qty"]).sum() / buys["qty"].sum()) if buys["qty"].sum() > 0 else 0
        for _, sell in sells.iterrows():
            sell_price = float(sell["price"])
            if avg_cost > 0 and sell_price > 0:
                pnl_pct = (sell_price / avg_cost - 1) * 100
                if pnl_pct >= 0:
                    wins.append(pnl_pct)
                else:
                    loss.append(abs(pnl_pct))

    total  = len(wins) + len(loss)
    if total == 0:
        return EMPTY

    win_rate  = len(wins) / total * 100
    avg_win   = float(np.mean(wins))  if wins else 0.0
    avg_loss  = float(np.mean(loss))  if loss else 0.0
    pf        = (sum(wins) / sum(loss)) if sum(loss) > 0 else float("inf")
    avg_rr    = (avg_win / avg_loss)   if avg_loss > 0 else float("inf")

    return {
        "total":          total,
        "wins":           len(wins),
        "losses":         len(loss),
        "win_rate":       round(win_rate, 1),
        "profit_factor":  round(min(pf, 999), 2),
        "avg_win_pct":    round(avg_win,  2),
        "avg_loss_pct":   round(avg_loss, 2),
        "avg_rr":         round(min(avg_rr, 999), 2),
    }


# ── MONTHLY P&L ───────────────────────────────────────────────────────────────

def build_monthly_pnl(trade_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build monthly P&L calendar from trade log.
    Returns DataFrame with columns: month, year, pnl_vnd.
    """
    if trade_df is None or trade_df.empty:
        return pd.DataFrame()
    if "date" not in trade_df.columns or "side" not in trade_df.columns:
        return pd.DataFrame()
    if "price" not in trade_df.columns or "qty" not in trade_df.columns:
        return pd.DataFrame()

    df = trade_df.copy()
    df["date"]  = pd.to_datetime(df["date"],  errors="coerce")
    df["price"] = pd.to_numeric(df["price"],  errors="coerce").fillna(0)
    df["qty"]   = pd.to_numeric(df["qty"],    errors="coerce").fillna(0)
    df["value"] = df["price"] * df["qty"]
    df = df.dropna(subset=["date"])

    # Net cash flow per sell trade as proxy for realized P&L
    sells = df[df["side"].str.lower().isin(["bán", "ban", "sell"])].copy()
    if sells.empty:
        return pd.DataFrame()

    sells["month"] = sells["date"].dt.month
    sells["year"]  = sells["date"].dt.year

    monthly = (
        sells.groupby(["year", "month"])["value"]
        .sum()
        .reset_index()
        .rename(columns={"value": "pnl_vnd"})
    )
    return monthly

"""
backtest/engine.py — NewTradingOS v14.0
Realistic multi-timeframe backtesting engine for VN market.

Features:
- T+2 settlement (counts actual trading sessions)
- Realistic costs: buy fee, sell fee, 0.1% transfer tax, slippage
- ATR-based stop loss + take profit
- Signal-based exits
- Equity curve, drawdown, per-trade records
- Multi-timeframe support
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    BUY_TOTAL, SELL_TOTAL, INITIAL_CAPITAL,
    TIMEFRAME_CONFIG, VN_SESSIONS_YEAR, LOT_SIZE,
)
from core.indicators import compute_all, atr as _atr
from core.scoring import compute_score
from portfolio.sizing import compute_portfolio_metrics, TradeStats, position_size_vnd

logger = logging.getLogger("TradingOS.backtest")


# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────
@dataclass
class BacktestTrade:
    entry_idx:    int
    exit_idx:     int
    entry_date:   str
    exit_date:    str
    entry_price:  float
    exit_price:   float
    stop_loss:    float
    take_profit:  float
    pnl_pct:      float
    pnl_vnd:      float
    hold_sessions:int
    exit_reason:  str   # 'stop' | 'target' | 'time' | 'signal'
    n_shares:     int   = 0  # VN lot-size-aligned share count (multiple of LOT_SIZE)


@dataclass
class BacktestResult:
    ticker:       str
    timeframe:    str
    trades:       list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float]         = field(default_factory=list)
    metrics:      dict                = field(default_factory=dict)
    params:       dict                = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────
# CORE ENGINE
# ─────────────────────────────────────────────────────────────
def run_backtest(
    df: pd.DataFrame,
    tf: str,
    ticker: str = "UNKNOWN",
    initial_capital: float = INITIAL_CAPITAL,
    regime: str = "bull",
    macro_score: float = 6.0,
    position_pct: Optional[float] = None,
) -> BacktestResult:
    """
    Run a single-stock backtest for a given timeframe.

    Parameters
    ----------
    df              : OHLCV DataFrame (must have enough rows for indicators)
    tf              : '1W' | '2W' | '1M' | '3M' | '5M'
    ticker          : symbol label
    initial_capital : starting capital in VND
    regime          : market regime to use for all signals (simplification)
    macro_score     : macro score for signal computation
    position_pct    : override config position_pct if provided
    """
    cfg     = TIMEFRAME_CONFIG[tf]
    min_rows = cfg["sma_slow"] + 30

    if df is None or len(df) < min_rows:
        return BacktestResult(
            ticker=ticker, timeframe=tf,
            metrics={"error": f"Insufficient data: {len(df) if df is not None else 0} < {min_rows}"},
        )

    pos_pct  = position_pct or cfg["position_pct"]
    df       = compute_all(df.copy(), cfg)
    df       = df.dropna(subset=["SMA_slow", "ATR"])

    capital      = initial_capital
    equity       = [capital]
    trades       = []
    trade_stats  = TradeStats()

    in_trade     = False
    entry_px     = 0.0
    entry_idx    = 0
    stop_loss    = 0.0
    take_profit  = 0.0
    _n_shares    = 0        # lot-aligned share count for current open trade
    _vnd_committed = 0.0   # actual VND invested (lot-aligned) for current trade

    # Warm-up: need enough rows to compute all indicators
    warm_up = cfg["sma_slow"] + 10

    for i in range(warm_up, len(df)):
        row  = df.iloc[i]
        price = float(row["Close"])

        if not in_trade:
            # Compute signal on data up to and including bar i
            sig = compute_score(
                df.iloc[: i + 1], tf,
                regime=regime,
                macro_score=macro_score,
                ticker=ticker,
            )

            if sig.action in ("BUY", "STRONG BUY") and sig.regime_ok:
                entry_px    = price * (1 + BUY_TOTAL)   # slippage + fee per share
                entry_idx   = i
                stop_loss   = sig.stop_loss
                take_profit = sig.take_profit
                # VN LOT_SIZE enforcement: position size rounded down to nearest
                # 100-share lot so simulated trades match real broker constraints.
                _n_shares, _vnd_committed = position_size_vnd(
                    capital, pos_pct, price, lot_size=LOT_SIZE
                )
                if _n_shares == 0:
                    continue   # Cannot afford minimum 1 VN lot — skip signal
                in_trade    = True

        else:
            sessions_held = i - entry_idx

            # T+2 enforcement: can only sell after 2 sessions
            if sessions_held < 2:
                equity.append(equity[-1])
                continue

            exit_reason: Optional[str] = None

            # Stop loss hit (use Low of bar)
            if float(row["Low"]) <= stop_loss:
                exit_reason = "stop"
                exit_px     = min(price, stop_loss)   # realistic fill

            # Take profit hit (use High of bar)
            elif float(row["High"]) >= take_profit:
                exit_reason = "target"
                exit_px     = max(price, take_profit)

            # Time exit: held max hold_sessions
            elif sessions_held >= cfg["hold_sessions"]:
                exit_reason = "time"
                exit_px     = price

            # Signal exit: sell signal
            else:
                sig_exit = compute_score(
                    df.iloc[: i + 1], tf,
                    regime=regime,
                    macro_score=macro_score,
                    ticker=ticker,
                )
                if sig_exit.action == "SELL":
                    exit_reason = "signal"
                    exit_px     = price

            if exit_reason:
                exit_px_net = exit_px * (1 - SELL_TOTAL)
                trade_pnl   = (exit_px_net / entry_px) - 1
                # Use lot-size-aligned position value for realistic VND P&L.
                # This prevents fractional-share overstatement on small accounts.
                trade_vnd   = _vnd_committed * trade_pnl

                capital     += trade_vnd
                capital      = max(capital, 1)   # prevent negative

                t = BacktestTrade(
                    entry_idx    = entry_idx,
                    exit_idx     = i,
                    entry_date   = str(df.index[entry_idx].date()),
                    exit_date    = str(df.index[i].date()),
                    entry_price  = round(entry_px / (1 + BUY_TOTAL), 0),  # clean price
                    exit_price   = round(exit_px, 0),
                    stop_loss    = round(stop_loss, 0),
                    take_profit  = round(take_profit, 0),
                    pnl_pct      = round(trade_pnl, 6),
                    pnl_vnd      = round(trade_vnd, 0),
                    hold_sessions= sessions_held,
                    exit_reason  = exit_reason,
                    n_shares     = _n_shares,
                )
                trades.append(t)
                trade_stats.update(trade_pnl)
                in_trade = False

        equity.append(capital)

    # Handle open position at end (mark to market)
    if in_trade and len(df) > 0:
        last_price = float(df["Close"].iloc[-1])
        last_px_net = last_price * (1 - SELL_TOTAL)
        open_pnl    = (last_px_net / entry_px) - 1
        open_vnd    = capital * pos_pct * open_pnl
        # Don't add to capital — just note it

    metrics = compute_portfolio_metrics(equity, [{"pnl_pct": t.pnl_pct} for t in trades])
    metrics["n_trades"]   = len(trades)
    metrics["trade_stats"]= {
        "win_rate":    round(trade_stats.win_rate * 100, 1),
        "avg_win_pct": round(trade_stats.avg_win_pct * 100, 2),
        "avg_loss_pct":round(trade_stats.avg_loss_pct * 100, 2),
        "kelly":       round(trade_stats.kelly * 100, 1),
    }

    return BacktestResult(
        ticker=ticker,
        timeframe=tf,
        trades=trades,
        equity_curve=equity,
        metrics=metrics,
        params={
            "tf":              tf,
            "initial_capital": initial_capital,
            "position_pct":    pos_pct,
            "regime":          regime,
            "macro_score":     macro_score,
            "n_bars":          len(df),
            "date_from":       str(df.index[0].date()),
            "date_to":         str(df.index[-1].date()),
        },
    )


def run_multi_tf_backtest(
    df: pd.DataFrame,
    ticker: str = "UNKNOWN",
    initial_capital: float = INITIAL_CAPITAL,
) -> dict[str, BacktestResult]:
    """
    Run backtest for all 5 timeframes on the same OHLCV data.

    Returns
    -------
    dict[tf → BacktestResult]
    """
    results = {}
    for tf in TIMEFRAME_CONFIG:
        results[tf] = run_backtest(
            df.copy(), tf, ticker=ticker, initial_capital=initial_capital
        )
    return results


# ─────────────────────────────────────────────────────────────
# AGGREGATE METRICS TABLE
# ─────────────────────────────────────────────────────────────
def summarise_results(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """
    Build a summary DataFrame comparing performance across timeframes.
    """
    rows = []
    for tf, res in results.items():
        m = res.metrics
        if "error" in m:
            rows.append({"TF": tf, "Error": m["error"]})
            continue
        rows.append({
            "TF":          tf,
            "CAGR %":      m.get("cagr", 0),
            "Total Ret %": m.get("total_return", 0),
            "Sharpe":      m.get("sharpe", 0),
            "Calmar":      m.get("calmar", 0),
            "Max DD %":    m.get("max_dd", 0),
            "Win Rate %":  m.get("win_rate", 0),
            "PF":          m.get("profit_factor", 0),
            "# Trades":    m.get("n_trades", 0),
            "Avg Win %":   m.get("trade_stats", {}).get("avg_win_pct", 0),
            "Avg Loss %":  m.get("trade_stats", {}).get("avg_loss_pct", 0),
            "Kelly %":     m.get("trade_stats", {}).get("kelly", 0),
        })
    return pd.DataFrame(rows)


def trades_to_df(result: BacktestResult) -> pd.DataFrame:
    """Convert BacktestResult trades to display DataFrame."""
    rows = []
    for t in result.trades:
        rows.append({
            "Entry":     t.entry_date,
            "Exit":      t.exit_date,
            "Entry Px":  t.entry_price,
            "Exit Px":   t.exit_price,
            "Stop":      t.stop_loss,
            "Target":    t.take_profit,
            "Hold (Ses)":t.hold_sessions,
            "PnL %":     round(t.pnl_pct * 100, 2),
            "PnL VND":   t.pnl_vnd,
            "Reason":    t.exit_reason,
        })
    return pd.DataFrame(rows)

"""Backtest Engine — VN-constrained + walk-forward + mode comparison (SRS §3.10)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from ..data.fetcher import fetch_earnings_calendar, fetch_financial_statements
from ..utils.config import cfg
from .earnings import compute_earnings_risk
from .fundamental import compute_fundamental_snapshot
from .indicators import rsi as compute_rsi, atr as compute_atr
from .mfpm import compute_mfpm


# Settlement and LOCK_SAN are read from config at runtime; these are fallbacks.
_T_SETTLE_DEFAULT = 3
_LOCK_SAN_DEFAULT = 0.02


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: int
    mode: str                    # MODE_A / MODE_B / MODE_W
    pnl: float
    pnl_pct: float
    hold_days: int
    exit_reason: str
    matched: bool = True         # False = LOCK_SAN (synthetic miss)


@dataclass
class BacktestResult:
    ticker: str
    mode: str
    start_date: str
    end_date: str
    n_trades: int
    win_rate: float
    avg_pnl_pct: float
    max_drawdown: float
    sharpe: float
    total_return: float
    trades: list[BacktestTrade] = field(default_factory=list)
    walk_forward_windows: list[dict] = field(default_factory=list)


def _simulate_single_trade(
    df: pd.DataFrame,
    entry_idx: int,
    sl_pct: float,
    tp1_pct: float,
    tp2_pct: float,
    max_hold: int = 15,
    mode: str = "MODE_A",
    avg_vol_20d: float | None = None,
) -> BacktestTrade | None:
    """
    Simulate one trade from entry_idx with SL/TP.
    VN constraints: T+2/T+3 settlement, LOCK_SAN, commission+slippage+tax costs.
    avg_vol_20d: used to select the correct tiered lock_san probability.
    """
    # Load cost params from config
    commission_bps = float(cfg.strategy("backtest", "commission_bps", default=15)) / 10000
    slippage_bps   = float(cfg.strategy("backtest", "slippage_bps",   default=5))  / 10000
    tax_sell_bps   = float(cfg.strategy("backtest", "tax_sell_bps",   default=10)) / 10000
    t2_settlement  = bool(cfg.strategy("backtest", "t2_settlement",   default=False))
    t_settle = 2 if t2_settlement else _T_SETTLE_DEFAULT  # noqa: F841 (used in run_backtest)

    # Tiered lock_san probability by liquidity (small-caps lock-san far more often)
    tiers = cfg.strategy("backtest", "lock_san_by_liquidity", default={})
    if avg_vol_20d is not None and isinstance(tiers, dict):
        if avg_vol_20d > 1_000_000:
            lock_san_prob = float(tiers.get("liquid",   0.01))
        elif avg_vol_20d > 100_000:
            lock_san_prob = float(tiers.get("normal",   0.03))
        else:
            lock_san_prob = float(tiers.get("illiquid", 0.08))
    else:
        lock_san_prob = float(cfg.strategy("backtest", "lock_san_prob", default=_LOCK_SAN_DEFAULT))

    # Round-trip cost: buy cost (entry side) + sell cost (exit side)
    entry_cost_pct  = commission_bps + slippage_bps
    exit_cost_pct   = commission_bps + slippage_bps + tax_sell_bps

    rng = np.random.default_rng(entry_idx)

    if entry_idx >= len(df) - 2:
        return None

    entry_row = df.iloc[entry_idx]
    raw_entry   = float(entry_row["close"])
    entry_price = raw_entry * (1 + entry_cost_pct)   # effective cost basis
    # H2: prefer the 'date' column (real ISO date after run_backtest preserves it)
    entry_date  = str(entry_row.get("date", entry_row.name))[:10]

    sl  = raw_entry * (1 - sl_pct)
    tp1 = raw_entry * (1 + tp1_pct)
    tp2 = raw_entry * (1 + tp2_pct)

    # Simulate LOCK_SAN [SYNTHETIC — calibration: strategy.yaml lock_san_prob]
    locked = rng.random() < lock_san_prob

    exit_price = entry_price
    exit_reason = "MAX_HOLD"
    exit_idx = min(entry_idx + max_hold, len(df) - 1)

    partial_exit_price = None

    for i in range(entry_idx + 1, min(entry_idx + max_hold + 1, len(df))):
        row = df.iloc[i]
        hi = float(row["high"])
        lo = float(row["low"])
        cl = float(row["close"])

        if lo <= sl:
            # [BUG-17 FIX] Read limit-down pct from config instead of hardcoding 0.93
            # for all tickers. HOSE = ±7% (floor 0.93), HNX = ±10%, UPCOM = ±15%.
            # Defaulting to HOSE 0.93 is reasonable for most VN stocks, but can be
            # overridden via strategy.yaml backtest.limit_down_pct.
            limit_down_pct = float(cfg.strategy("backtest", "limit_down_pct", default=0.07))
            prev_close = float(df.iloc[i - 1]["close"]) if i > 0 else raw_entry
            limit_floor = prev_close * (1 - limit_down_pct)
            exit_price = max(sl, limit_floor)
            exit_reason = "SL"
            exit_idx = i
            break
        if hi >= tp2:
            exit_price = tp2 if not locked else cl
            exit_reason = "TP2"
            exit_idx = i
            break
        if hi >= tp1 and partial_exit_price is None:
            partial_exit_price = tp1
            # 40% partial at TP1, then continue for TP2
        if i == entry_idx + max_hold:
            exit_price = cl
            exit_reason = "MAX_HOLD"
            exit_idx = i
            break

    if partial_exit_price is not None and exit_reason not in ("SL", "TP2"):
        # Weighted exit (40% TP1, 60% MAX_HOLD)
        exit_price = 0.4 * partial_exit_price + 0.6 * exit_price
        exit_reason = "PARTIAL_TP1_THEN_HOLD"

    hold_days = exit_idx - entry_idx
    effective_exit = exit_price * (1 - exit_cost_pct)
    pnl_pct = (effective_exit - entry_price) / entry_price
    # [BUG-18 FIX] pnl must be total trade VND for 100 shares, not per-share.
    # Old: pnl_pct * raw_entry = per-share gain (100× understated vs real money).
    pnl = round(pnl_pct * raw_entry * 100, 0)  # total VND for 1 lot (100 shares)

    return BacktestTrade(
        ticker=str(df.iloc[0].get("ticker", "—")) if "ticker" in df.columns else "—",
        entry_date=entry_date,
        exit_date=str(df.iloc[exit_idx].get("date", df.iloc[exit_idx].name))[:10],
        entry_price=entry_price,
        exit_price=exit_price,
        shares=100,
        mode=mode,
        pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 4),
        hold_days=hold_days,
        exit_reason=exit_reason,
        matched=not locked,
    )


def run_backtest(
    df: pd.DataFrame,
    ticker: str = "N/A",
    mode: str = "MODE_A",
    sl_pct: float = 0.06,
    tp1_pct: float = 0.08,
    tp2_pct: float = 0.15,
    signal_col: str | None = None,   # column in df with entry signals (1=long)
    walk_forward_windows: int = 5,
) -> BacktestResult:
    """
    VN-constrained backtest.
    If signal_col is None, uses simple RSI cross-up rule.
    Walk-forward: splits data into N windows.
    """
    if df.empty or len(df) < 40:
        return BacktestResult(
            ticker=ticker, mode=mode,
            start_date="", end_date="",
            n_trades=0, win_rate=0.0,
            avg_pnl_pct=0.0, max_drawdown=0.0, sharpe=0.0, total_return=0.0,
        )

    # H2: preserve date column before reset_index so trade dates remain ISO strings
    _date_col: pd.Series | None = None
    if "date" in df.columns:
        _date_col = df["date"].copy()
    df = df.copy().reset_index(drop=True)
    if _date_col is not None:
        df["date"] = _date_col.values

    # C3: compute per-ticker avg volume for tiered lock-san selection
    avg_vol_20d = float(df["volume"].tail(20).mean()) if "volume" in df.columns else None

    max_hold = int(cfg.strategy("backtest", "max_hold_days", default=15))
    t2_settlement = bool(cfg.strategy("backtest", "t2_settlement", default=False))
    t_settle = 2 if t2_settlement else _T_SETTLE_DEFAULT

    # ── Generate entry signals ─────────────────────────────────────────────
    if signal_col and signal_col in df.columns:
        entry_indices = df.index[df[signal_col] == 1].tolist()
    else:
        # Default: RSI crosses up from ≤50 (Mode A)
        rsi = compute_rsi(df["close"], 14)
        crosses = (rsi.shift(1) <= 50) & (rsi > 50)
        entry_indices = df.index[crosses].tolist()

    # ── Simulate trades ───────────────────────────────────────────────────
    trades: list[BacktestTrade] = []
    last_exit = 0

    for idx in entry_indices:
        if idx < last_exit + t_settle:  # T+2 or T+3 capital lockup (from config)
            continue
        trade = _simulate_single_trade(
            df, idx, sl_pct, tp1_pct, tp2_pct, max_hold, mode,
            avg_vol_20d=avg_vol_20d,  # C3: wire tiered lock-san
        )
        if trade is None:
            continue
        trade.ticker = ticker
        trades.append(trade)
        last_exit = idx + trade.hold_days

    # ── Metrics ───────────────────────────────────────────────────────────
    # Helper: extract a date string regardless of .name type or 'date' column
    def _date_str(row_idx: int) -> str:
        row = df.iloc[row_idx]
        if "date" in df.columns:
            return str(row["date"])[:10]
        return str(row.name)[:10]  # fallback (may be int after reset_index)

    if not trades:
        return BacktestResult(
            ticker=ticker, mode=mode,
            start_date=_date_str(0),
            end_date=_date_str(len(df) - 1),
            n_trades=0, win_rate=0.0,
            avg_pnl_pct=0.0, max_drawdown=0.0, sharpe=0.0, total_return=0.0,
        )

    pnls = [t.pnl_pct for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    # Equity curve
    equity = np.cumprod(1 + np.array(pnls))
    total_ret = float(equity[-1] - 1)
    drawdowns = 1 - equity / np.maximum.accumulate(equity)
    max_dd = float(drawdowns.max())

    # Sharpe (annualized, 250 trading days)
    avg_ret = float(np.mean(pnls))
    std_ret = float(np.std(pnls)) if len(pnls) > 1 else abs(avg_ret) + 1e-9
    trades_per_year = 250 / max(max_hold, 5)
    sharpe = (avg_ret * trades_per_year) / (std_ret * np.sqrt(trades_per_year) + 1e-9)
    sharpe = float(np.clip(sharpe, -20, 20))  # cap extreme values (1 trade edge case)

    # ── Walk-forward windows (H1: non-overlapping IS/OOS) ───────────────────────────
    # [BUG-C FIX] Use walk_forward_is_days and walk_forward_oos_days from
    # strategy.yaml to size windows properly.  Old code divided data into
    # (walk_forward_windows + 1) equal blocks that shrank as the window count
    # grew, making the OOS block as small as ~20 days for walk_forward_windows=5.
    # New: IS starts at 0, grows by _oos_days each window; OOS = next _oos_days block.
    wf_results = []
    n = len(df)
    _is_days  = int(cfg.strategy("backtest", "walk_forward_is_days",  default=252))
    _oos_days = int(cfg.strategy("backtest", "walk_forward_oos_days", default=63))
    _max_windows = max(0, (n - _is_days) // max(_oos_days, 1)) if n > _is_days else 0
    _wf_count = min(walk_forward_windows, _max_windows)
    for w in range(_wf_count):
        is_start  = 0
        is_end    = _is_days + w * _oos_days   # IS grows by one OOS block per window
        oos_start = is_end
        oos_end   = min(oos_start + _oos_days, n)
        if oos_start >= n:
            break
        oos_df = df.iloc[oos_start:oos_end]
        if len(oos_df) < 10:
            break
        wf_bt = run_backtest(oos_df, ticker, mode, sl_pct, tp1_pct, tp2_pct, walk_forward_windows=0)
        wf_results.append({
            "window":  w + 1,
            "start":   _date_str(oos_start),
            "end":     _date_str(min(oos_end, n) - 1),
            "n_trades":    wf_bt.n_trades,
            "win_rate":    wf_bt.win_rate,
            "total_return":wf_bt.total_return,
        })

    return BacktestResult(
        ticker=ticker,
        mode=mode,
        start_date=_date_str(0),
        end_date=_date_str(len(df) - 1),
        n_trades=len(trades),
        win_rate=round(wins / len(trades), 3),
        avg_pnl_pct=round(avg_ret, 4),
        max_drawdown=round(max_dd, 4),
        sharpe=round(float(sharpe), 2),
        total_return=round(total_ret, 4),
        trades=trades,
        walk_forward_windows=wf_results,
    )


def _build_mode_signal_col(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """
    Inject a mode-specific entry-signal column into df.
    MODE_A: RSI cross-up from ≤50 (pullback)
    MODE_B: Close breaks above rolling 20-day high with volume surge (breakout)
    MODE_W: OBV trend proxy — OBV > OBV.mean() AND close > EMA20 (whale-proxy)
    """
    out = df.copy()
    if mode == "MODE_A":
        rsi = compute_rsi(out["close"], 14)
        out["_signal"] = ((rsi.shift(1) <= 50) & (rsi > 50)).astype(int)
    elif mode == "MODE_B":
        roll_high = out["high"].rolling(20).max().shift(1)
        avg_vol = out["volume"].rolling(20).mean()
        breakout = (out["close"] > roll_high) & (out["volume"] > avg_vol * 1.3)
        out["_signal"] = breakout.fillna(False).astype(int)
    else:  # MODE_W
        ema20 = out["close"].ewm(span=20, adjust=False).mean()
        obv_ma = out["OBV"].rolling(20).mean() if "OBV" in out.columns else out["volume"].rolling(20).mean()
        whale_proxy = (
            (out["close"] > ema20)
            & (out["OBV"] > obv_ma if "OBV" in out.columns else out["volume"] > obv_ma)
            & (out["close"].pct_change(5) > 0)
        )
        out["_signal"] = whale_proxy.fillna(False).astype(int)
    return out


def _apply_overlay_signal_filters(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Apply earnings and fundamental overlays to the generated entry signal column."""
    out = df.copy()
    if "_signal" not in out.columns or "date" not in out.columns:
        return out

    try:
        earnings_df = fetch_earnings_calendar(ticker, lookforward_days=365)
    except Exception:
        earnings_df = pd.DataFrame()

    try:
        statements = fetch_financial_statements(ticker, quarters=8)
    except Exception:
        statements = {}

    row_dates = pd.to_datetime(out["date"], errors="coerce").dt.date
    filtered_signal: list[int] = []
    for idx, raw_signal in enumerate(out["_signal"].tolist()):
        if not raw_signal:
            filtered_signal.append(0)
            continue

        current_date = row_dates.iloc[idx]
        if current_date is None:
            filtered_signal.append(int(raw_signal))
            continue

        macro_regime = str(out.iloc[idx].get("macro_regime", "")).upper()
        if macro_regime == "RESTRICTIVE":
            filtered_signal.append(0)
            continue

        earnings_risk = compute_earnings_risk(ticker, current_date=current_date, earnings_df=earnings_df)
        if earnings_risk.rollover_risk.value == "HIGH_RISK":
            filtered_signal.append(0)
            continue

        fundamental_snapshot = compute_fundamental_snapshot(
            ticker,
            current_date=current_date,
            statements=statements,
        )
        if (
            fundamental_snapshot.fundamental_score is not None
            and fundamental_snapshot.fundamental_score < 35
        ):
            filtered_signal.append(0)
            continue

        filtered_signal.append(int(raw_signal))

    out["_signal"] = filtered_signal
    return out


def compare_modes(
    df: pd.DataFrame,
    ticker: str = "N/A",
    sl_pct: float = 0.06,
    tp1_pct: float = 0.08,
    tp2_pct: float = 0.15,
) -> dict[str, BacktestResult]:
    """Run backtest for all three modes using mode-specific entry signals."""
    results = {}
    for mode in ("MODE_A", "MODE_B", "MODE_W"):
        df_with_sig = _build_mode_signal_col(df, mode)
        df_with_sig = _apply_overlay_signal_filters(df_with_sig, ticker)
        results[mode] = run_backtest(
            df_with_sig, ticker, mode, sl_pct, tp1_pct, tp2_pct,
            signal_col="_signal",
        )
    return results

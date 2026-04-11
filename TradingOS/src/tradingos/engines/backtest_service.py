"""Backtest Service — mode comparison + walk-forward (SRS §3.6)."""
from __future__ import annotations

import pandas as pd

from ..data.fetcher import fetch_ohlcv, fetch_usdvnd, fetch_vn10y_bond_yield
from ..core import compute_indicators
from ..core.backtest import run_backtest, compare_modes, BacktestResult
from ..core.macro import build_macro_regime_series
from ..data.schemas import BacktestRequest
from ..data.cache import cache
from ..utils.logging import get_logger
from ..utils.config import cfg

log = get_logger("backtest_service")


class BacktestService:
    def run(self, request: BacktestRequest) -> dict[str, BacktestResult]:
        """
        Run backtest for ticker + all 3 modes.
        Returns {mode: BacktestResult}.
        """
        ticker = request.ticker.upper()
        log.info(f"Backtest {ticker} {request.start_date}–{request.end_date}")

        df = fetch_ohlcv(ticker, days=520)
        if df.empty:
            log.warning(f"No data for {ticker}")
            return {}

        # Date filter — reset index to ensure we can compare dates regardless
        # of whether the index is a DatetimeIndex or a RangeIndex
        if "date" not in df.columns and df.index.dtype != "int64":
            df = df.copy()
            df.index = pd.to_datetime(df.index)
        elif "date" not in df.columns:
            df = df.reset_index()
            if "index" in df.columns:
                df = df.rename(columns={"index": "date"})

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            if request.start_date:
                df = df[df["date"] >= pd.to_datetime(request.start_date)]
            if request.end_date:
                df = df[df["date"] <= pd.to_datetime(request.end_date)]
        else:
            # DatetimeIndex path
            if request.start_date:
                df = df[df.index >= pd.to_datetime(request.start_date)]
            if request.end_date:
                df = df[df.index <= pd.to_datetime(request.end_date)]

        if len(df) < 40:
            log.warning(f"Insufficient data for backtest {ticker}")
            return {}

        df = compute_indicators(df)

        try:
            macro_days = max(len(df) + 30, 90)
            macro_series = build_macro_regime_series(
                trading_dates=df["date"] if "date" in df.columns else df.index,
                usdvnd_df=fetch_usdvnd(days=macro_days),
                bond_yield_df=fetch_vn10y_bond_yield(days=macro_days),
            )
            if not macro_series.empty and "date" in df.columns:
                macro_series["date"] = pd.to_datetime(macro_series["date"])
                df = df.merge(macro_series, on="date", how="left")
                df["macro_regime"] = df["macro_regime"].ffill().fillna("NEUTRAL")
        except Exception as e:
            log.debug(f"Macro series build skipped for {ticker}: {e}")

        sl_pct  = request.sl_pct or float(cfg.strategy("entry_exit", "initial_sl_pct", default=0.06))
        tp1_pct = sl_pct * float(getattr(request, "tp1_mult", None) or cfg.strategy("entry_exit", "tp1_rr", default=1.5))
        tp2_pct = sl_pct * float(getattr(request, "tp2_mult", None) or cfg.strategy("entry_exit", "tp2_rr", default=2.5))

        results = compare_modes(df, ticker=ticker, sl_pct=sl_pct, tp1_pct=tp1_pct, tp2_pct=tp2_pct)

        for mode, bt in results.items():
            log.info(
                f"  {mode}: trades={bt.n_trades} win={bt.win_rate:.0%} "
                f"total_ret={bt.total_return:.1%} sharpe={bt.sharpe:.2f}"
            )

        cache.put_audit({
            "event_type": "BACKTEST",
            "ticker": ticker,
            "action": f"{len(results)} modes",
            "mfpm_score": 0,
            "sms_raw": 0,
            "confidence": "—",
        })

        return results

    def to_dataframe(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """Convert BacktestResult dict to summary DataFrame."""
        rows = []
        for mode, bt in results.items():
            rows.append({
                "mode": mode,
                "n_trades": bt.n_trades,
                "win_rate": bt.win_rate,
                "avg_pnl_pct": bt.avg_pnl_pct,
                "total_return": bt.total_return,
                "max_drawdown": bt.max_drawdown,
                "sharpe": bt.sharpe,
            })
        return pd.DataFrame(rows)

"""Backtest Service — mode comparison + walk-forward (SRS §3.6)."""
from __future__ import annotations

import pandas as pd

from ..data.fetcher import fetch_ohlcv
from ..core import compute_indicators
from ..core.backtest import run_backtest, compare_modes, BacktestResult
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

        # Date filter
        if request.start_date:
            df = df[df.index >= request.start_date]
        if request.end_date:
            df = df[df.index <= request.end_date]

        if len(df) < 40:
            log.warning(f"Insufficient data for backtest {ticker}")
            return {}

        df = compute_indicators(df)

        sl_pct = request.sl_pct or float(cfg.strategy("entry_exit", "initial_sl_pct", default=0.06))
        tp1_pct = sl_pct * float(cfg.strategy("entry_exit", "tp1_rr", default=1.5))
        tp2_pct = sl_pct * float(cfg.strategy("entry_exit", "tp2_rr", default=2.5))

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

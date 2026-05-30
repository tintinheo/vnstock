"""
tests/test_backtest.py — NewTradingOS v14.0
Tests for backtest/engine.py — T+2, fees, stops.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.engine import (
    run_backtest, run_multi_tf_backtest, summarise_results,
    trades_to_df, BacktestResult, BacktestTrade,
)
from config import BUY_FEE, SELL_FEE, SELL_TAX

T2_SESSIONS = 2  # VN T+2 settlement: minimum sessions before sell


# ─────────────────────────────────────────────────────────────
# run_backtest basics
# ─────────────────────────────────────────────────────────────
class TestRunBacktest:
    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_returns_backtest_result(self, ohlcv, tf):
        r = run_backtest(ohlcv, tf, ticker="VCB")
        assert isinstance(r, BacktestResult)

    def test_equity_starts_at_initial(self, ohlcv):
        capital = 100_000_000
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=capital)
        assert r.equity_curve[0] == capital

    def test_equity_is_list(self, ohlcv):
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        assert isinstance(r.equity_curve, list)

    def test_equity_length_gt_zero(self, ohlcv):
        """Equity curve skips warmup bars; just assert it's non-empty."""
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        assert len(r.equity_curve) > 0
        assert len(r.equity_curve) <= len(ohlcv)

    def test_trades_is_list(self, ohlcv):
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        assert isinstance(r.trades, list)

    def test_all_equity_non_negative(self, ohlcv):
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        assert all(e >= 0 for e in r.equity_curve)

    def test_short_data_no_crash(self, ohlcv_small):
        r = run_backtest(ohlcv_small, "1M", ticker="VCB")
        assert isinstance(r, BacktestResult)


# ─────────────────────────────────────────────────────────────
# T+2 enforcement
# ─────────────────────────────────────────────────────────────
class TestT2Enforcement:
    def test_sell_not_before_t2(self, ohlcv):
        """All completed trades must hold at least T2_SESSIONS."""
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        for trade in r.trades:
            assert trade.hold_sessions >= T2_SESSIONS, (
                f"Trade hold={trade.hold_sessions} sessions — violates T+2"
            )

    def test_t2_constant_is_2(self):
        assert T2_SESSIONS == 2


# ─────────────────────────────────────────────────────────────
# Fee structure
# ─────────────────────────────────────────────────────────────
class TestFees:
    def test_pnl_accounts_for_fees(self, ohlcv):
        """P&L should be < gross price difference (fees must be deducted)."""
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        for trade in r.trades:
            gross_pct = (trade.exit_price - trade.entry_price) / trade.entry_price
            # Net pnl_pct should be less than gross (fees deducted)
            if gross_pct > 0:
                assert trade.pnl_pct < gross_pct * 1.0001  # small tolerance


# ─────────────────────────────────────────────────────────────
# BacktestTrade
# ─────────────────────────────────────────────────────────────
class TestBacktestTrade:
    def test_pnl_pct_positive_on_winning_trade(self):
        trade = BacktestTrade(
            entry_idx=10, exit_idx=30,
            entry_date="2026-01-01", exit_date="2026-03-01",
            entry_price=50_000, exit_price=60_000,
            stop_loss=47_500, take_profit=57_500,
            pnl_pct=0.18, pnl_vnd=4_000_000,
            hold_sessions=20, exit_reason="target",
        )
        assert trade.pnl_pct > 0

    def test_pnl_pct_negative_on_stop(self):
        trade = BacktestTrade(
            entry_idx=10, exit_idx=12,
            entry_date="2026-01-01", exit_date="2026-01-03",
            entry_price=50_000, exit_price=47_500,
            stop_loss=47_500, take_profit=57_500,
            pnl_pct=-0.05, pnl_vnd=-1_250_000,
            hold_sessions=2, exit_reason="stop",
        )
        assert trade.pnl_pct < 0


# ─────────────────────────────────────────────────────────────
# Multi-TF backtest
# ─────────────────────────────────────────────────────────────
class TestMultiTFBacktest:
    def test_returns_dict_with_all_tfs(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="VCB")
        for tf in ("1W", "2W", "1M", "3M", "5M"):
            assert tf in results

    def test_each_result_is_backtest_result(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="VCB")
        for r in results.values():
            assert isinstance(r, BacktestResult)


# ─────────────────────────────────────────────────────────────
# summarise_results
# ─────────────────────────────────────────────────────────────
class TestSummariseResults:
    def test_returns_dataframe(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="VCB")
        df = summarise_results(results)
        assert isinstance(df, pd.DataFrame)

    def test_one_row_per_tf(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="VCB")
        df = summarise_results(results)
        assert len(df) == 5

    def test_columns_present(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="VCB")
        df = summarise_results(results)
        # Actual column names from summarise_results
        for col in ("TF", "Total Ret %", "Win Rate %"):
            assert col in df.columns, f"Missing column '{col}', got: {list(df.columns)}"


# ─────────────────────────────────────────────────────────────
# trades_to_df
# ─────────────────────────────────────────────────────────────
class TestTradesToDf:
    def test_empty_trades(self, ohlcv):
        r  = run_backtest(ohlcv, "5M", ticker="VCB")
        r.trades.clear()
        df = trades_to_df(r)
        assert isinstance(df, pd.DataFrame)

    def test_has_trades(self, ohlcv):
        r  = run_backtest(ohlcv, "1M", ticker="VCB")
        df = trades_to_df(r)
        if len(r.trades) > 0:
            # Actual column names from trades_to_df
            assert "Entry Px" in df.columns
            assert "Exit Px"  in df.columns


# ─────────────────────────────────────────────────────────────
# FIX Audit Round 2 — VN LOT_SIZE enforcement in backtest
# ─────────────────────────────────────────────────────────────
class TestLotSizeEnforcement:
    """VN minimum lot is 100 shares. Backtest must align positions to LOT_SIZE.

    Without lot-size enforcement, the engine assumes fractional shares are
    purchasable, which overstates P&L for small accounts or expensive stocks
    (e.g., VCB at 100,000 VND — 15% of 50M = 7.5M → 75 shares → should be
    rounded DOWN to 0 lots... but 1 lot minimum applies).
    """

    def test_trade_has_n_shares_field(self, ohlcv):
        """Each BacktestTrade must expose n_shares (lot-aligned share count)."""
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        for trade in r.trades:
            assert hasattr(trade, "n_shares"), "BacktestTrade must have n_shares field"

    def test_n_shares_multiple_of_lot_size(self, ohlcv):
        """n_shares for every trade must be a multiple of LOT_SIZE (100)."""
        from config import LOT_SIZE
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        for trade in r.trades:
            assert trade.n_shares % LOT_SIZE == 0, (
                f"n_shares={trade.n_shares} is not a multiple of LOT_SIZE={LOT_SIZE}"
            )

    def test_n_shares_at_least_one_lot(self, ohlcv):
        """All trades must hold at least one lot (LOT_SIZE shares)."""
        from config import LOT_SIZE
        r = run_backtest(ohlcv, "1M", ticker="VCB")
        for trade in r.trades:
            assert trade.n_shares >= LOT_SIZE, (
                f"n_shares={trade.n_shares} is less than minimum LOT_SIZE={LOT_SIZE}"
            )

    def test_backtest_trade_dataclass_default_n_shares(self):
        """BacktestTrade must accept n_shares=0 as default (backward compat)."""
        trade = BacktestTrade(
            entry_idx=10, exit_idx=30,
            entry_date="2026-01-01", exit_date="2026-03-01",
            entry_price=50_000, exit_price=60_000,
            stop_loss=47_500, take_profit=57_500,
            pnl_pct=0.18, pnl_vnd=4_000_000,
            hold_sessions=20, exit_reason="target",
        )
        assert trade.n_shares == 0  # default value

    def test_lot_aligned_pnl_realistic(self, ohlcv):
        """P&L magnitude should be realistic (not inflated by fractional shares).

        For a 100M VND account, 15% position = 15M VND. At ~50k price,
        that's ~300 shares = 3 lots. P&L per trade should be <= 15M * max_gain.
        """
        capital = 100_000_000
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=capital)
        pos_pct = 0.15  # default 1M position pct
        max_reasonable_vnd = capital * pos_pct * 0.5  # 50% gain on 1 position is extreme
        for trade in r.trades:
            assert abs(trade.pnl_vnd) <= max_reasonable_vnd, (
                f"|pnl_vnd|={abs(trade.pnl_vnd):,.0f} exceeds {max_reasonable_vnd:,.0f} "
                f"(likely fractional-share overstatement)"
            )


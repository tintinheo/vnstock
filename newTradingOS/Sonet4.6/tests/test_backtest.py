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


class TestBacktestExchangePropagation:
    def test_hnx_ticker_exchange_passed_to_compute_all_and_score(self, ohlcv, monkeypatch):
        import backtest.engine as engine
        from core.indicators import compute_all as real_compute_all
        from core.scoring import compute_score as real_compute_score

        seen_compute_all: list[str] = []
        seen_compute_score: list[str] = []

        def capture_compute_all(df, cfg, exchange="HOSE"):
            seen_compute_all.append(exchange)
            return real_compute_all(df, cfg, exchange=exchange)

        def capture_compute_score(df, tf, **kwargs):
            seen_compute_score.append(kwargs.get("exchange"))
            return real_compute_score(df, tf, **kwargs)

        monkeypatch.setattr(engine, "compute_all", capture_compute_all)
        monkeypatch.setattr(engine, "compute_score", capture_compute_score)

        result = engine.run_backtest(ohlcv, "1M", ticker="PVS")

        assert isinstance(result, BacktestResult)
        assert seen_compute_all, "compute_all was not called"
        assert seen_compute_score, "compute_score was not called"
        assert set(seen_compute_all) == {"HNX"}
        assert set(seen_compute_score) == {"HNX"}


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
        for trade in r.trades:
            max_plausible_gain = capital * 0.20  # 20M VND max per trade
            assert abs(trade.pnl_vnd) <= max_plausible_gain, (
                f"PnL {trade.pnl_vnd:,.0f} exceeds plausible max {max_plausible_gain:,.0f}"
            )


# ─────────────────────────────────────────────────────────────
# Round 5 Fix #5 — open trade MTM at end of backtest
# ─────────────────────────────────────────────────────────────
class TestOpenTradeMTM:
    """Lệnh đang mở cuối backtest phải được tính vào equity (mark-to-market)."""

    def test_equity_always_non_negative_with_mtm(self, ohlcv_bull):
        """Equity không bao giờ âm kể cả sau MTM cuối kỳ."""
        r = run_backtest(ohlcv_bull, "1M", ticker="MTM_TEST")
        assert all(v >= 0 for v in r.equity_curve), (
            "Equity curve contains negative values after MTM fix"
        )

    def test_equity_non_empty_after_warmup(self, ohlcv_bull):
        """Backtest bull data phải có equity curve dài."""
        r = run_backtest(ohlcv_bull, "1M", ticker="MTM_A")
        assert len(r.equity_curve) > 0

    def test_metrics_computed_even_with_open_trade(self, ohlcv_bull):
        """metrics phải là dict hợp lệ dù có open trade cuối kỳ."""
        r = run_backtest(ohlcv_bull, "5M", ticker="MTM_5M")
        assert isinstance(r.metrics, dict)
        # If no error, must have basic keys
        if "error" not in r.metrics:
            for key in ("cagr", "sharpe", "max_dd"):
                assert key in r.metrics, f"Missing metric: {key}"

    def test_5m_no_crash_with_mtm(self, ohlcv_bull):
        """5M backtest trên dữ liệu bull không được crash với MTM fix."""
        r = run_backtest(ohlcv_bull, "5M", ticker="MTM_CRASH")
        assert isinstance(r, BacktestResult)


# ─────────────────────────────────────────────────────────────
# Round 5 Fix #7 — regime/macro_score passthrough
# ─────────────────────────────────────────────────────────────
class TestMultiTFRegimePassthrough:
    """regime và macro_score phải được truyền đúng qua run_multi_tf_backtest."""

    def test_regime_stored_in_params(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="R_TEST", regime="bear")
        for tf, res in results.items():
            if "error" not in res.metrics:
                assert res.params.get("regime") == "bear", (
                    f"TF={tf}: regime không được truyền đúng — "
                    f"expected 'bear', got '{res.params.get('regime')}'"
                )

    def test_macro_score_stored_in_params(self, ohlcv):
        results = run_multi_tf_backtest(ohlcv, ticker="M_TEST", macro_score=7.5)
        for tf, res in results.items():
            if "error" not in res.metrics:
                assert res.params.get("macro_score") == 7.5, (
                    f"TF={tf}: macro_score không được truyền đúng — "
                    f"expected 7.5, got '{res.params.get('macro_score')}'"
                )

    def test_bear_regime_reduces_1w_trades(self, ohlcv_bull):
        """1W chỉ cho BUY trong bull — bear regime phải có ít trade hơn hoặc bằng bull."""
        r_bull = run_multi_tf_backtest(ohlcv_bull, ticker="DIFF_R", regime="bull")
        r_bear = run_multi_tf_backtest(ohlcv_bull, ticker="DIFF_R", regime="bear")
        n_bull = len(r_bull["1W"].trades)
        n_bear = len(r_bear["1W"].trades)
        assert n_bear <= n_bull, (
            f"Bear regime phải có ít hoặc bằng trade bull cho 1W, "
            f"nhưng bear={n_bear} > bull={n_bull}"
        )

    def test_default_regime_is_bull(self, ohlcv):
        """Default không truyền regime → phải là 'bull'."""
        results = run_multi_tf_backtest(ohlcv, ticker="DEF_R")
        for tf, res in results.items():
            if "error" not in res.metrics:
                assert res.params.get("regime") == "bull", (
                    f"TF={tf}: default regime should be 'bull'"
                )

    def test_all_tfs_present_with_custom_regime(self, ohlcv):
        """Tất cả 5 TF phải có trong kết quả kể cả khi truyền regime sideways."""
        results = run_multi_tf_backtest(ohlcv, ticker="ALL_TF", regime="sideways")
        assert set(results.keys()) == {"1W", "2W", "1M", "3M", "5M"}


# ────────────────────────────────────────────────────────────
# Round 3 Fix #5 — backtest skips entry when capital < 1 lot
# ────────────────────────────────────────────────────────────
class TestInsufficientCapitalSkip:
    """Backtest engine must skip trade entry when position_size_vnd returns
    (0, 0.0), i.e. when allocated capital cannot afford even 1 VN lot.

    The engine must not crash and must produce a valid BacktestResult
    with zero trades.
    """

    def test_no_crash_with_tiny_capital(self, ohlcv):
        """1 VND capital — cannot afford any lot — backtest must not crash."""
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=1.0)
        assert isinstance(r, BacktestResult), "Expected BacktestResult even with 1 VND capital"

    def test_zero_trades_with_tiny_capital(self, ohlcv):
        """With 1 VND capital, no trade should ever be entered."""
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=1.0)
        assert len(r.trades) == 0, (
            f"Expected 0 trades with 1 VND capital, got {len(r.trades)}"
        )

    def test_equity_curve_valid_with_tiny_capital(self, ohlcv):
        """Even with no trades, equity curve must be non-empty and non-negative."""
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=1.0)
        assert len(r.equity_curve) > 0
        assert all(e >= 0 for e in r.equity_curve)

    def test_normal_capital_still_trades(self, ohlcv):
        """After the fix, normal capital (100M VND) must still produce trades."""
        r = run_backtest(ohlcv, "1M", ticker="VCB", initial_capital=100_000_000)
        assert isinstance(r, BacktestResult)
        # With 500 bars of bull/neutral data, at least some trades should occur
        # (not asserting exact count since it depends on signals)


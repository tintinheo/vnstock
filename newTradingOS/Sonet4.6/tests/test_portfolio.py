"""
tests/test_portfolio.py — NewTradingOS v14.0
Tests for portfolio/sizing.py and portfolio/tracker.py
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from portfolio.sizing import (
    kelly_fraction, position_size_vnd,
    allocate_budget, compute_portfolio_metrics,
    TradeStats,
)
from portfolio.tracker import Portfolio, Position
from config import LOT_SIZE, INITIAL_CAPITAL


# ─────────────────────────────────────────────────────────────
# Kelly Criterion
# ─────────────────────────────────────────────────────────────
class TestKellyFraction:
    def test_positive_edge(self):
        """High win rate + good RR should give positive fraction."""
        f = kelly_fraction(0.60, 0.10, 0.05)
        assert f > 0

    def test_max_cap(self):
        """Should never exceed max_fraction."""
        f = kelly_fraction(0.99, 0.50, 0.01, max_fraction=0.25)
        assert f <= 0.25

    def test_min_floor(self):
        """Should never go below min_fraction."""
        f = kelly_fraction(0.01, 0.01, 0.50, min_fraction=0.03)
        assert f >= 0.03

    def test_zero_win_rate(self):
        f = kelly_fraction(0.0, 0.10, 0.05)
        assert f >= 0.03   # should return min_fraction

    def test_zero_avg_loss(self):
        f = kelly_fraction(0.55, 0.10, 0.0)
        assert f >= 0.03


# ─────────────────────────────────────────────────────────────
# Position Size
# ─────────────────────────────────────────────────────────────
class TestPositionSize:
    def test_multiple_of_lot(self):
        n_shares, _ = position_size_vnd(100_000_000, 0.10, 50_000)
        assert n_shares % LOT_SIZE == 0

    def test_positive_shares(self):
        n_shares, vnd = position_size_vnd(100_000_000, 0.10, 50_000)
        assert n_shares > 0
        assert vnd > 0

    def test_vnd_within_capital(self):
        capital = 50_000_000
        _, vnd = position_size_vnd(capital, 0.10, 30_000)
        # VND should be close to 10% of capital (within one lot tolerance)
        assert vnd <= capital * 0.15


# ─────────────────────────────────────────────────────────────
# Allocate Budget
# ─────────────────────────────────────────────────────────────
class TestAllocateBudget:
    def test_all_timeframes_present(self):
        budget = allocate_budget(100_000_000, "balanced")
        from config import TIMEFRAME_CONFIG
        for tf in TIMEFRAME_CONFIG:
            assert tf in budget

    def test_sum_le_capital(self):
        capital = 100_000_000
        budget  = allocate_budget(capital, "balanced")
        assert sum(budget.values()) <= capital * 1.01  # allow tiny float error

    def test_profiles(self):
        for profile in ("aggressive", "balanced", "conservative"):
            budget = allocate_budget(100_000_000, profile)
            assert len(budget) > 0


# ─────────────────────────────────────────────────────────────
# TradeStats
# ─────────────────────────────────────────────────────────────
class TestTradeStats:
    def test_update_win(self):
        ts = TradeStats()
        ts.update(0.05)
        assert ts.n_wins == 1
        assert ts.n_trades == 1
        assert abs(ts.avg_win_pct - 0.05) < 1e-9

    def test_update_loss(self):
        ts = TradeStats()
        ts.update(-0.03)
        assert ts.n_losses == 1
        assert abs(ts.avg_loss_pct - 0.03) < 1e-9

    def test_win_rate(self):
        ts = TradeStats()
        for _ in range(6):
            ts.update(0.05)
        for _ in range(4):
            ts.update(-0.03)
        assert abs(ts.win_rate - 0.60) < 1e-9

    def test_kelly_property(self):
        ts = TradeStats()
        ts.n_trades = 10; ts.n_wins = 6; ts.n_losses = 4
        ts.avg_win_pct = 0.08; ts.avg_loss_pct = 0.04
        k = ts.kelly
        assert 0 < k <= 0.25


# ─────────────────────────────────────────────────────────────
# Portfolio tracker
# ─────────────────────────────────────────────────────────────
class TestPortfolio:
    def _make_position(self, ticker="VCB", entry=50_000, shares=500):
        cost = entry * shares * 1.002
        return Position(
            ticker=ticker, timeframe="1M",
            entry_date="2026-01-01", entry_price=entry,
            n_shares=shares, stop_loss=entry * 0.95,
            take_profit=entry * 1.15, cost_vnd=cost,
        )

    def test_open_position(self):
        pf  = Portfolio(capital=INITIAL_CAPITAL)
        pos = self._make_position()
        ok  = pf.open_position(pos)
        assert ok
        assert len(pf.open_positions) == 1

    def test_insufficient_cash(self):
        pf  = Portfolio(capital=1_000)   # very small capital
        pos = self._make_position(entry=50_000, shares=500)
        ok  = pf.open_position(pos)
        assert not ok

    def test_cash_decreases_after_open(self):
        pf      = Portfolio(capital=INITIAL_CAPITAL)
        pos     = self._make_position()
        cash_before = pf.cash
        pf.open_position(pos)
        assert pf.cash < cash_before

    def test_close_position(self):
        pf  = Portfolio(capital=INITIAL_CAPITAL)
        pos = self._make_position(entry=50_000)
        pf.open_position(pos)
        closed = pf.close_position("VCB", 55_000, "2026-02-01", "target")
        assert closed is not None
        assert closed.pnl_pct is not None
        assert len(pf.open_positions) == 0
        assert len(pf.trades) == 1

    def test_close_nonexistent_ticker(self):
        pf     = Portfolio(capital=INITIAL_CAPITAL)
        result = pf.close_position("NONE", 50_000)
        assert result is None

    def test_realised_pnl_positive_on_profit(self):
        pf = Portfolio(capital=INITIAL_CAPITAL)
        pf.open_position(self._make_position(entry=50_000))
        pf.close_position("VCB", 60_000, "2026-02-01", "target")
        assert pf.realised_pnl > 0

    def test_save_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        try:
            pf = Portfolio(capital=200_000_000)
            pf.open_position(self._make_position())
            pf.save(tmp_path)
            pf2 = Portfolio.load(tmp_path)
            assert abs(pf2.capital - pf.capital) < 1e-3
            assert len(pf2.open_positions) == 1
        finally:
            os.unlink(tmp_path)

    def test_positions_df(self):
        pf = Portfolio(capital=INITIAL_CAPITAL)
        pf.open_position(self._make_position("VCB"))
        pf.open_position(self._make_position("TCB"))
        df = pf.positions_df()
        assert len(df) == 2

    def test_trades_df(self):
        pf = Portfolio(capital=INITIAL_CAPITAL)
        pf.open_position(self._make_position())
        pf.close_position("VCB", 55_000)
        df = pf.trades_df()
        assert len(df) == 1


# ─────────────────────────────────────────────────────────────
# Portfolio metrics
# ─────────────────────────────────────────────────────────────
class TestPortfolioMetrics:
    def test_growing_equity(self):
        eq     = [100, 102, 105, 108, 112, 115]
        trades = [{"pnl_pct": 0.05}] * 5
        m      = compute_portfolio_metrics(eq, trades)
        assert m["total_return"] > 0
        assert m["cagr"]  > 0
        assert m["max_dd"] <= 0

    def test_drawdown_negative(self):
        eq = [100, 120, 90, 80, 110]
        m  = compute_portfolio_metrics(eq, [])
        assert m["max_dd"] < 0

    def test_sharpe_positive_on_profits(self):
        eq = [100 * (1.001 ** i) for i in range(200)]
        m  = compute_portfolio_metrics(eq, [{"pnl_pct": 0.001}] * 100)
        assert m["sharpe"] > 0

    def test_empty_curve(self):
        m = compute_portfolio_metrics([100], [])
        assert m == {}


# ────────────────────────────────────────────────────────────
# Round 3 Fix #5 — position_size_vnd insufficient-capital guard
# ────────────────────────────────────────────────────────────
class TestPositionSizeInsufficientCapital:
    """position_size_vnd must return (0, 0.0) when capital cannot
    afford even a single VN lot (100 shares).

    Previous behaviour (max(1, n_lots)) forced 1 lot regardless,
    silently investing 4× the intended allocation on small accounts.
    Example: capital=50M, fraction=5%, price=100,000 VND:
      budget = 2.5M  <  1 lot = 10M  → must return (0, 0.0)
    """

    def test_returns_zero_when_budget_below_one_lot(self):
        """50M × 5% = 2.5M; 1 lot at 100,000 VND = 10M — insufficient."""
        n, vnd = position_size_vnd(50_000_000, 0.05, 100_000, lot_size=100)
        assert n == 0, f"Expected n_shares=0 when capital insufficient, got {n}"
        assert vnd == 0.0, f"Expected vnd=0.0 when capital insufficient, got {vnd}"

    def test_returns_zero_on_tiny_capital(self):
        """1,000 VND capital at any price/fraction can't buy 1 lot."""
        n, vnd = position_size_vnd(1_000, 0.99, 1_000, lot_size=100)
        assert n == 0
        assert vnd == 0.0

    def test_returns_positive_when_sufficient(self):
        """100M × 10% = 10M; 1 lot at 50,000 VND = 5M — can buy 2 lots."""
        n, vnd = position_size_vnd(100_000_000, 0.10, 50_000, lot_size=100)
        assert n > 0, f"Expected positive n_shares, got {n}"
        assert n % 100 == 0, "n_shares must be a multiple of lot_size=100"
        assert vnd > 0.0

    def test_exact_boundary_one_lot(self):
        """When budget exactly equals 1 lot cost, must return exactly 1 lot."""
        # budget = capital * fraction = lot_size * price
        # e.g. lot_size=100, price=10,000 → 1 lot = 1,000,000 VND
        # Need capital * fraction = 1,000,000 exactly (before BUY_TOTAL fee)
        # Use big capital with small fraction to avoid fee confusion
        # capital=10M, fraction=0.1 → budget=1M = exactly 1 lot
        n, vnd = position_size_vnd(10_000_000, 0.10, 10_000, lot_size=100)
        assert n >= 100, f"Should be able to afford at least 1 lot, got {n}"

    def test_existing_positive_case_unchanged(self):
        """Original test case: 100M × 10% at 50,000 VND — still works."""
        n, vnd = position_size_vnd(100_000_000, 0.10, 50_000)
        assert n > 0
        assert vnd > 0
        assert n % LOT_SIZE == 0

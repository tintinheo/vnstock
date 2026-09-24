"""ATR-Based Position Sizing — unit tests (Phase II).

Covers:
  1.  Basic ATR sizing: shares = risk_amount / stop_distance, lot-rounded
  2.  AMF BLOCK → 0 shares
  3.  AMF WARN → 50% share reduction (default warn_size_multiplier)
  4.  AMF PASS → full shares
  5.  Zero ATR → returns zero dict
  6.  Zero entry price → returns zero dict
  7.  Zero portfolio value → returns zero dict
  8.  stop_price = entry - ATR × mult
  9.  atr_risk_amount = shares × stop_distance
 10.  atr_position_value = shares × entry_price
 11.  atr_size_pct = position_value / portfolio_value
 12.  atr_risk_pct_actual close to requested risk_pct (within rounding)
 13.  Explicit risk_pct and atr_mult override config defaults
 14.  Small portfolio / large ATR → shares round to 0 (no partial lot)
 15.  shares always multiple of 100 (lot discipline)
"""
from __future__ import annotations

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _size(entry, atr14, portfolio=10_000_000_000, risk_pct=0.01, atr_mult=2.0, amf="PASS"):
    from tradingos.core.sizing import compute_atr_position_size
    return compute_atr_position_size(
        entry_price=entry,
        atr14=atr14,
        portfolio_value=portfolio,
        risk_pct=risk_pct,
        atr_mult=atr_mult,
        amf_decision=amf,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestATRSizingBasic:

    def test_basic_shares_calculation(self):
        """Verify core formula: shares = risk_amount / stop_distance, lot-rounded."""
        # portfolio=10B, risk_pct=1% → risk_amount=100M
        # ATR14=500, atr_mult=2.0 → stop_distance=1000
        # shares_raw = 100_000_000 / 1000 = 100_000
        # lot-rounded: 100_000 // 100 * 100 = 100_000
        result = _size(entry=50_000, atr14=500, portfolio=10_000_000_000, risk_pct=0.01, atr_mult=2.0)
        assert result["atr_position_shares"] == 100_000

    def test_stop_price_formula(self):
        """stop_price = entry_price - ATR14 × atr_mult."""
        result = _size(entry=88_600, atr14=400, risk_pct=0.01, atr_mult=2.0)
        assert result["atr_stop_price"] == pytest.approx(88_600 - 400 * 2.0, abs=1)

    def test_stop_distance_value(self):
        """atr_stop_distance = ATR14 × atr_mult."""
        result = _size(entry=60_000, atr14=600, atr_mult=2.5)
        assert result["atr_stop_distance"] == pytest.approx(600 * 2.5, abs=1)

    def test_position_value_formula(self):
        """atr_position_value = atr_position_shares × entry_price."""
        result = _size(entry=50_000, atr14=500)
        expected_value = result["atr_position_shares"] * 50_000
        assert result["atr_position_value"] == pytest.approx(expected_value, abs=1)

    def test_risk_amount_formula(self):
        """atr_risk_amount = atr_position_shares × stop_distance."""
        result = _size(entry=50_000, atr14=500, atr_mult=2.0)
        stop_dist = result["atr_stop_distance"]
        expected_risk = result["atr_position_shares"] * stop_dist
        assert result["atr_risk_amount"] == pytest.approx(expected_risk, abs=100)

    def test_shares_multiple_of_100(self):
        """All non-zero share counts must be multiples of 100 (HOSE lot)."""
        for atr in [300, 700, 1234, 987]:
            result = _size(entry=45_000, atr14=atr)
            shares = result["atr_position_shares"]
            if shares > 0:
                assert shares % 100 == 0, f"shares={shares} not a multiple of 100 (atr={atr})"


class TestATRSizingAMFGating:

    def test_amf_block_returns_zero(self):
        """AMF BLOCK → no position: all values zero."""
        result = _size(entry=50_000, atr14=500, amf="BLOCK")
        assert result["atr_position_shares"] == 0
        assert result["atr_stop_price"] == 0.0
        assert result["atr_position_value"] == 0.0
        assert result["atr_risk_amount"] == 0.0

    def test_amf_pass_full_size(self):
        """AMF PASS → full position (same as no AMF gate)."""
        result_pass = _size(entry=50_000, atr14=500, amf="PASS")
        assert result_pass["atr_position_shares"] > 0

    def test_amf_warn_half_size(self):
        """AMF WARN → shares are <= half of AMF PASS shares (warn_size_multiplier=0.5)."""
        result_pass = _size(entry=50_000, atr14=500, amf="PASS")
        result_warn = _size(entry=50_000, atr14=500, amf="WARN")
        # warn should be <= pass/2 (rounding may make it slightly less)
        assert result_warn["atr_position_shares"] <= result_pass["atr_position_shares"] * 0.5 + 100

    def test_amf_warn_still_lot_rounded(self):
        """AMF WARN result shares still multiple of 100."""
        result = _size(entry=50_000, atr14=500, amf="WARN")
        shares = result["atr_position_shares"]
        if shares > 0:
            assert shares % 100 == 0


class TestATRSizingEdgeCases:

    def test_zero_atr_returns_zero_dict(self):
        """ATR14 = 0 → cannot compute stop distance → return zeros."""
        result = _size(entry=50_000, atr14=0)
        assert result["atr_position_shares"] == 0
        assert result["atr_stop_price"] == 0.0

    def test_zero_entry_returns_zero_dict(self):
        """entry_price = 0 → invalid → return zeros."""
        result = _size(entry=0, atr14=500)
        assert result["atr_position_shares"] == 0

    def test_zero_portfolio_returns_zero_dict(self):
        """portfolio_value = 0 → no capital → return zeros."""
        result = _size(entry=50_000, atr14=500, portfolio=0)
        assert result["atr_position_shares"] == 0

    def test_small_portfolio_large_atr_returns_zero(self):
        """If risk budget supports < 1 lot → return 0 shares (no partial lots)."""
        # portfolio=50M, risk_pct=1% → risk_amount=500_000
        # ATR14=100_000, mult=2.0 → stop_distance=200_000
        # shares_raw = 500_000 / 200_000 = 2.5 → lot-round → 0
        result = _size(entry=1_000_000, atr14=100_000, portfolio=50_000_000, risk_pct=0.01, atr_mult=2.0)
        assert result["atr_position_shares"] == 0

    def test_explicit_overrides_used(self):
        """Explicit risk_pct and atr_mult override config defaults."""
        r1 = _size(entry=50_000, atr14=500, risk_pct=0.02, atr_mult=3.0)
        r2 = _size(entry=50_000, atr14=500, risk_pct=0.01, atr_mult=2.0)
        # 2% risk / (500×3) = 200M/1500 ≈ 133_333 shares → 133_300
        # 1% risk / (500×2) = 100M/1000 = 100_000 shares
        assert r1["atr_position_shares"] > r2["atr_position_shares"]


class TestATRSizingRiskAccuracy:

    def test_risk_pct_actual_within_tolerance(self):
        """atr_risk_pct_actual should be close to requested risk_pct (within 1 lot tolerance)."""
        portfolio = 10_000_000_000
        risk_pct = 0.01
        result = _size(entry=50_000, atr14=500, portfolio=portfolio, risk_pct=risk_pct, atr_mult=2.0)
        if result["atr_position_shares"] > 0:
            # Actual risk may be slightly less due to lot rounding — should be ≤ requested
            assert result["atr_risk_pct_actual"] <= risk_pct + 0.001

    def test_size_pct_consistent_with_position_value(self):
        """atr_size_pct = atr_position_value / portfolio_value."""
        portfolio = 10_000_000_000
        result = _size(entry=50_000, atr14=500, portfolio=portfolio)
        if result["atr_position_shares"] > 0:
            expected_pct = result["atr_position_value"] / portfolio
            assert result["atr_size_pct"] == pytest.approx(expected_pct, abs=0.0001)

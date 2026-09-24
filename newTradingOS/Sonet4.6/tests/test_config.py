"""
tests/test_config.py — NewTradingOS v14.0
Tests for config.py — universe lists, thresholds, exchange routing.
Covers BUG-03 fix: VN100_LIST must NOT be alphabetically biased.
"""
from __future__ import annotations

import pytest

from config import (
    VN30_LIST, VN100_LIST, HOSE_LIST, HNX_LIST, UPCOM_LIST,
    MARKET_SCAN_LIST, TICKER_EXCHANGE,
    get_price_limit, get_tick_size, round_to_tick,
    score_to_action, TIMEFRAME_CONFIG,
)


# ─────────────────────────────────────────────────────────────
# VN100_LIST — BUG-03 regression suite
# ─────────────────────────────────────────────────────────────
class TestVN100List:
    def test_vn100_includes_all_vn30_tickers(self):
        """Every VN30 constituent must be present in VN100."""
        missing = set(VN30_LIST) - set(VN100_LIST)
        assert not missing, f"VN100 missing VN30 tickers: {sorted(missing)}"

    def test_vn100_size_approx_100(self):
        """VN100 should have between 90 and 120 tickers."""
        n = len(VN100_LIST)
        assert 90 <= n <= 120, f"VN100_LIST has {n} tickers (expected 90-120)"

    def test_vn100_not_alphabetically_biased(self):
        """BUG-03: VN100 must not be dominated by A/B/C tickers.

        The old implementation used `sorted(HOSE_LIST)[:70]` which is alphabetical
        → filled with A/B/C tickers. The fix uses an explicit curated list.
        Assert that A/B/C tickers make up < 25% of the total (they are ~8% of
        the real VN100 index).
        """
        abc_count = sum(1 for t in VN100_LIST if t[0] in "ABC")
        ratio = abc_count / len(VN100_LIST)
        assert ratio < 0.25, (
            f"VN100_LIST is alphabetically biased: {abc_count}/{len(VN100_LIST)} "
            f"({ratio:.0%}) tickers start with A/B/C"
        )

    def test_vn100_includes_mid_alphabet_major_stocks(self):
        """Key mid-alphabet stocks (by market cap/liquidity) must be in VN100."""
        required = ["OCB", "SHB", "TPB", "VND", "VIX", "NT2", "GMD", "TCH"]
        missing = [t for t in required if t not in VN100_LIST]
        assert not missing, (
            f"VN100_LIST missing important mid-alphabet stocks: {missing}"
        )

    def test_vn100_contains_no_duplicates(self):
        """VN100 list must have no duplicate tickers."""
        assert len(VN100_LIST) == len(set(VN100_LIST)), (
            "VN100_LIST contains duplicate tickers"
        )

    def test_vn100_is_sorted(self):
        """VN100 list should be sorted for deterministic order."""
        assert VN100_LIST == sorted(set(VN100_LIST))

    def test_vn100_contains_only_hose_tickers(self):
        """VN100 should only contain HOSE tickers (no HNX/UPCOM).

        HNX/UPCOM tickers are in TICKER_EXCHANGE; VN100 is a HOSE index.
        """
        non_hose = [t for t in VN100_LIST if TICKER_EXCHANGE.get(t) in ("HNX", "UPCOM")]
        assert not non_hose, (
            f"VN100_LIST contains HNX/UPCOM tickers: {non_hose}"
        )

    def test_vn100_subset_of_market_scan_list(self):
        """Every VN100 ticker should be in the broader MARKET_SCAN_LIST universe."""
        outside = set(VN100_LIST) - set(MARKET_SCAN_LIST)
        assert not outside, (
            f"VN100 contains tickers not in MARKET_SCAN_LIST: {sorted(outside)}"
        )

    def test_vn30_subset_of_vn100(self):
        """VN30 is a subset of VN100."""
        assert set(VN30_LIST).issubset(set(VN100_LIST))

    def test_vn100_contains_key_sectors_beyond_banking(self):
        """VN100 must include stocks from multiple sectors, not just A/B/C names."""
        # Energy/Oil
        assert "GAS" in VN100_LIST or "PLX" in VN100_LIST, "No energy stock in VN100"
        # Tech
        assert "FPT" in VN100_LIST, "FPT missing from VN100"
        # Steel
        assert "HPG" in VN100_LIST, "HPG missing from VN100"
        # Real estate
        assert any(t in VN100_LIST for t in ["VIC", "VHM", "NVL", "KDH"]), (
            "No real estate stock in VN100"
        )


# ─────────────────────────────────────────────────────────────
# Exchange routing & price limits
# ─────────────────────────────────────────────────────────────
class TestExchangeRouting:
    def test_default_exchange_is_hose(self):
        assert get_price_limit("VCB") == 0.07
        assert get_price_limit("UNKNOWN") == 0.07

    def test_hnx_limit(self):
        assert get_price_limit("PVS") == 0.10

    def test_upcom_limit(self):
        assert get_price_limit("ACV") == 0.15

    def test_hose_list_excludes_hnx_upcom(self):
        hnx_in_hose = [t for t in HOSE_LIST if TICKER_EXCHANGE.get(t) == "HNX"]
        upcom_in_hose = [t for t in HOSE_LIST if TICKER_EXCHANGE.get(t) == "UPCOM"]
        assert not hnx_in_hose, f"HNX tickers in HOSE_LIST: {hnx_in_hose}"
        assert not upcom_in_hose, f"UPCOM tickers in HOSE_LIST: {upcom_in_hose}"


# ─────────────────────────────────────────────────────────────
# Tick size
# ─────────────────────────────────────────────────────────────
class TestTickSize:
    @pytest.mark.parametrize("price, expected_tick", [
        (5_000,   10),    # HOSE < 10,000
        (9_999,   10),    # HOSE just below 10,000
        (10_000,  50),    # HOSE at 10,000
        (25_000,  50),    # HOSE mid-range
        (49_999,  50),    # HOSE just below 50,000
        (50_000, 100),    # HOSE at 50,000
        (88_000, 100),    # HOSE > 50,000
    ])
    def test_hose_tick_size(self, price, expected_tick):
        assert get_tick_size(price, "HOSE") == expected_tick

    def test_hnx_always_100(self):
        for price in (5_000, 25_000, 88_000):
            assert get_tick_size(price, "HNX") == 100

    def test_upcom_always_100(self):
        for price in (5_000, 25_000, 88_000):
            assert get_tick_size(price, "UPCOM") == 100

    def test_round_to_tick_hose(self):
        # 45,023 → nearest 50 = 45,000
        assert round_to_tick(45_023.0, "HOSE") == 45_000.0
        # 45,026 → nearest 50 = 45_050
        assert round_to_tick(45_026.0, "HOSE") == 45_050.0
        # 120,080 → nearest 100 = 120_100
        assert round_to_tick(120_080.0, "HOSE") == 120_100.0


# ─────────────────────────────────────────────────────────────
# score_to_action thresholds
# ─────────────────────────────────────────────────────────────
class TestScoreToAction:
    @pytest.mark.parametrize("score, expected", [
        (100.0, "STRONG BUY"),
        (80.0,  "STRONG BUY"),
        (79.9,  "BUY"),
        (65.0,  "BUY"),
        (64.9,  "HOLD"),
        (45.0,  "HOLD"),
        (44.9,  "WATCH"),
        (30.0,  "WATCH"),
        (29.9,  "SELL"),
        (0.0,   "SELL"),
    ])
    def test_boundaries(self, score, expected):
        assert score_to_action(score) == expected

    def test_no_overlap_at_80(self):
        """score=80 must map to exactly STRONG BUY, not ambiguous."""
        assert score_to_action(80.0) == "STRONG BUY"

    def test_no_overlap_at_65(self):
        assert score_to_action(65.0) == "BUY"

    def test_no_overlap_at_45(self):
        assert score_to_action(45.0) == "HOLD"

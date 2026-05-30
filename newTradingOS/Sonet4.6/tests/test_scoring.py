"""
tests/test_scoring.py — NewTradingOS v14.0
Tests for core/scoring.py — signal scoring engine.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.scoring import compute_score, batch_score, SignalResult
from config import TIMEFRAME_CONFIG


# ─────────────────────────────────────────────────────────────
# compute_score basics
# ─────────────────────────────────────────────────────────────
class TestComputeScore:
    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_returns_signal_result(self, ohlcv, tf):
        sig = compute_score(ohlcv, tf, ticker="VCB")
        assert isinstance(sig, SignalResult)

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_score_in_range(self, ohlcv, tf):
        sig = compute_score(ohlcv, tf, ticker="VCB")
        assert 0 <= sig.score <= 100

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_action_valid(self, ohlcv, tf):
        sig = compute_score(ohlcv, tf, ticker="VCB")
        assert sig.action in ("STRONG BUY", "BUY", "HOLD", "WATCH", "SELL")

    def test_price_equals_last_close(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        assert abs(sig.price - float(ohlcv["Close"].iloc[-1])) < 1e-3

    def test_stop_loss_below_price(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        if sig.price > 0:
            assert sig.stop_loss < sig.price

    def test_take_profit_above_price(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        if sig.price > 0:
            assert sig.take_profit > sig.price

    def test_rr_ratio_matches_config(self, ohlcv):
        for tf in ("1W", "2W", "1M", "3M", "5M"):
            sig = compute_score(ohlcv, tf)
            assert sig.rr_ratio == TIMEFRAME_CONFIG[tf]["target_rr"]

    def test_insufficient_data_returns_zero_score(self, ohlcv_small):
        sig = compute_score(ohlcv_small, "5M", ticker="X")
        assert sig.score == 0

    def test_breakdown_keys_present(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        for key in ("Trend", "Momentum", "RSI", "Volume", "Macro", "ADX"):
            assert key in sig.breakdown, f"Missing breakdown key: {key}"

    def test_breakdown_sum_close_to_score(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        total = sum(sig.breakdown.values())
        # Allow small floating point divergence
        assert abs(total - sig.score) < 0.5


# ─────────────────────────────────────────────────────────────
# Regime filter
# ─────────────────────────────────────────────────────────────
class TestRegimeFilter:
    def test_1w_bear_regime_downgrades_buy(self, ohlcv_bull):
        """1W requires bull regime — bear should downgrade BUY to WATCH."""
        sig = compute_score(ohlcv_bull, "1W", regime="bear", macro_score=8)
        # Even with a high-scoring series, action should not be BUY in bear
        if sig.score >= TIMEFRAME_CONFIG["1W"]["min_score"]:
            assert sig.action in ("WATCH", "HOLD", "SELL"), \
                "1W should not BUY in bear regime"

    def test_3m_accepts_bear_regime(self, ohlcv):
        """3M includes all regimes in regime_filter."""
        sig = compute_score(ohlcv, "3M", regime="bear", macro_score=3)
        assert sig.regime_ok is True


# ─────────────────────────────────────────────────────────────
# batch_score
# ─────────────────────────────────────────────────────────────
class TestBatchScore:
    def test_returns_list(self, mock_data_dict):
        results = batch_score(mock_data_dict, "1M")
        assert isinstance(results, list)

    def test_sorted_by_score(self, mock_data_dict):
        results = batch_score(mock_data_dict, "1M")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, mock_data_dict):
        results = batch_score(mock_data_dict, "1M", min_score=90)
        assert all(r.score >= 90 for r in results)

    def test_empty_dict_returns_empty(self):
        results = batch_score({}, "1M")
        assert results == []

    def test_skips_empty_df(self):
        data = {"VCB": (pd.DataFrame(), "TEST")}
        results = batch_score(data, "1M")
        assert results == []


# ─────────────────────────────────────────────────────────────
# FIX #4 — exchange param propagation
# ─────────────────────────────────────────────────────────────
class TestComputeScoreExchange:
    def test_exchange_param_accepted(self, ohlcv):
        """compute_score must accept and not crash on exchange kwarg."""
        for ex in ("HOSE", "HNX", "UPCOM"):
            sig = compute_score(ohlcv, "1M", exchange=ex, ticker="TEST")
            assert isinstance(sig, SignalResult)

    def test_default_exchange_hose(self, ohlcv):
        """Score must be identical whether exchange='HOSE' or omitted."""
        sig_default = compute_score(ohlcv, "1M", ticker="VCB")
        sig_hose    = compute_score(ohlcv, "1M", ticker="VCB", exchange="HOSE")
        assert abs(sig_default.score - sig_hose.score) < 1e-3

    def test_batch_score_exchange_map(self, mock_data_dict):
        """batch_score must accept and use exchange_map without crashing."""
        ex_map = {t: "HNX" for t in mock_data_dict}
        results = batch_score(mock_data_dict, "1M", exchange_map=ex_map)
        assert isinstance(results, list)
        assert len(results) > 0


# ─────────────────────────────────────────────────────────────
# FIX #4 — foreign flow 20d
# ─────────────────────────────────────────────────────────────
class TestForeignFlow20d:
    def test_ff20d_higher_score_than_ff1d_on_1m(self, ohlcv):
        """For 1M TF, a strong positive 20d net buy should score >= single-day buy."""
        sig_1d  = compute_score(ohlcv, "1M", foreign_flow_net=5e10,
                                foreign_flow_net_20d=0.0, ticker="VCB")
        sig_20d = compute_score(ohlcv, "1M", foreign_flow_net=5e10,
                                foreign_flow_net_20d=5e10, ticker="VCB")
        # Both positive → same Foreign component (5 pts)
        assert abs(sig_1d.score - sig_20d.score) < 0.1

    def test_ff20d_used_when_nonzero(self, ohlcv):
        """When net_20d != 0, it should override net_today signal."""
        # net_today = 0 (no signal), net_20d = strong buy
        sig_no_20d  = compute_score(ohlcv, "1M", foreign_flow_net=0.0,
                                    foreign_flow_net_20d=0.0, ticker="VCB")
        sig_with_20d = compute_score(ohlcv, "1M", foreign_flow_net=0.0,
                                     foreign_flow_net_20d=5e10, ticker="VCB")
        # strong 20d buy should improve Foreign component from 1 → 5 pts
        assert sig_with_20d.score >= sig_no_20d.score

    def test_ff20d_zero_fallback_to_ff1d(self, ohlcv):
        """When foreign_flow_net_20d == 0, system falls back to foreign_flow_net."""
        sig_via_1d   = compute_score(ohlcv, "1M", foreign_flow_net=5e10,
                                     foreign_flow_net_20d=0.0, ticker="VCB")
        sig_via_both = compute_score(ohlcv, "1M", foreign_flow_net=5e10,
                                     foreign_flow_net_20d=5e10, ticker="VCB")
        # Both resolve to 5e10 → scores identical
        assert abs(sig_via_1d.score - sig_via_both.score) < 0.1

    def test_ff_only_active_on_long_tf(self, ohlcv):
        """Foreign flow must have 0 impact on 1W timeframe."""
        sig_no_ff = compute_score(ohlcv, "1W", foreign_flow_net=0.0,
                                  foreign_flow_net_20d=0.0, ticker="VCB")
        sig_ff    = compute_score(ohlcv, "1W", foreign_flow_net=1e12,
                                  foreign_flow_net_20d=1e12, ticker="VCB")
        # 1W has regime_filter=['bull'] only — but FF component should be 0
        assert sig_no_ff.breakdown.get("Foreign", 0) == 0
        assert sig_ff.breakdown.get("Foreign", 0) == 0


# ─────────────────────────────────────────────────────────────
# FIX Audit Round 2 — 2W Foreign Flow active
# ─────────────────────────────────────────────────────────────
class TestForeignFlow2W:
    """Foreign flow should affect 2W scores (10-session hold is meaningful for FF).

    VN-specific: foreign investors tend to trend for 2+ weeks. A sustained
    foreign buy over 10 sessions signals institutional accumulation and is
    predictive of continued price appreciation.
    """

    def test_ff_active_on_2w_strong_buy(self, ohlcv):
        """A strong 20d foreign buy (>1e10) should give +5 Foreign pts on 2W."""
        sig = compute_score(ohlcv, "2W", foreign_flow_net_20d=2e10, ticker="VCB")
        assert sig.breakdown.get("Foreign", 0) == 5.0, (
            f"Expected Foreign=5 on 2W with strong buy, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_zero_on_2w_gives_1pt(self, ohlcv):
        """Zero foreign flow on 2W should give baseline 1 pt (not 0)."""
        sig = compute_score(ohlcv, "2W", foreign_flow_net=0.0,
                            foreign_flow_net_20d=0.0, ticker="VCB")
        assert sig.breakdown.get("Foreign", -1) == 1.0, (
            f"Expected Foreign=1 for neutral flow on 2W, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_strong_sell_on_2w_gives_0pt(self, ohlcv):
        """A strong sustained foreign sell on 2W should give 0 Foreign pts."""
        sig = compute_score(ohlcv, "2W", foreign_flow_net_20d=-2e10, ticker="VCB")
        assert sig.breakdown.get("Foreign", -1) == 0.0, (
            f"Expected Foreign=0 for strong sell on 2W, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_improves_2w_score_vs_no_ff(self, ohlcv):
        """Strong FF buy on 2W should produce higher score than no FF."""
        sig_no_ff = compute_score(ohlcv, "2W", foreign_flow_net=0.0,
                                  foreign_flow_net_20d=0.0, ticker="VCB")
        sig_ff    = compute_score(ohlcv, "2W", foreign_flow_net=0.0,
                                  foreign_flow_net_20d=2e10, ticker="VCB")
        assert sig_ff.score > sig_no_ff.score, (
            f"2W score with strong FF buy ({sig_ff.score}) should exceed "
            f"no-FF score ({sig_no_ff.score})"
        )

    def test_ff_still_zero_on_1w(self, ohlcv):
        """Adding 2W does NOT change 1W — FF must remain 0 for 1W."""
        sig = compute_score(ohlcv, "1W", foreign_flow_net=1e12,
                            foreign_flow_net_20d=1e12, ticker="VCB")
        assert sig.breakdown.get("Foreign", 0) == 0


# ─────────────────────────────────────────────────────────────
# FIX Audit Round 2 — VN Tick Rounding in scoring output
# ─────────────────────────────────────────────────────────────
class TestScoringTickRounding:
    """Stop-loss and take-profit from compute_score must be at valid VN tick prices."""

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_stop_loss_at_valid_tick_all_tf(self, ohlcv, tf):
        """Stop-loss must be a valid HOSE tick multiple for all timeframes."""
        from config import get_tick_size
        sig  = compute_score(ohlcv, tf, exchange="HOSE", ticker="VCB")
        stop = sig.stop_loss
        tick = get_tick_size(stop, "HOSE")
        assert stop % tick == 0, f"TF={tf}: stop {stop} not multiple of tick {tick}"

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_take_profit_at_valid_tick_all_tf(self, ohlcv, tf):
        """Take-profit must be a valid HOSE tick multiple for all timeframes."""
        from config import get_tick_size
        sig  = compute_score(ohlcv, tf, exchange="HOSE", ticker="VCB")
        tp   = sig.take_profit
        tick = get_tick_size(tp, "HOSE")
        assert tp % tick == 0, f"TF={tf}: take_profit {tp} not multiple of tick {tick}"

    def test_hnx_stop_is_100_tick(self, ohlcv):
        """On HNX exchange, stop_loss must be a multiple of 100."""
        sig  = compute_score(ohlcv, "1M", exchange="HNX", ticker="PVS")
        assert sig.stop_loss % 100 == 0

    def test_upcom_stop_is_100_tick(self, ohlcv):
        """On UPCOM exchange, stop_loss must be a multiple of 100."""
        sig  = compute_score(ohlcv, "1M", exchange="UPCOM", ticker="ACV")
        assert sig.stop_loss % 100 == 0


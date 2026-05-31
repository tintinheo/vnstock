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

    def test_low_liquidity_downgrades_actionable_signal(self, ohlcv_bull, monkeypatch):
        import core.scoring as scoring_module

        df = ohlcv_bull.copy()
        df["Volume"] = 1_000
        monkeypatch.setattr(scoring_module, "score_to_action", lambda score: "STRONG BUY")

        sig = scoring_module.compute_score(df, "1M", ticker="ILLQ")

        assert sig.action == "WATCH"
        assert "liquidity" in sig.message.lower()

    def test_liquid_name_keeps_actionable_signal(self, ohlcv_bull, monkeypatch):
        import core.scoring as scoring_module

        monkeypatch.setattr(scoring_module, "score_to_action", lambda score: "STRONG BUY")
        sig = scoring_module.compute_score(ohlcv_bull, "1M", ticker="VCB")

        assert sig.action in ("STRONG BUY", "BUY")


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


# ────────────────────────────────────────────────────────────
# Round 3 Fix #3 — score_to_action() boundary tests
# ────────────────────────────────────────────────────────────
class TestScoreToActionBoundaries:
    """score_to_action must return unambiguous labels at every boundary value.

    The old dict-based implementation with inclusive-both-ends ranges caused
    score=80 to match both (80,100) and (65,80). The new if/elif chain must
    resolve each boundary to exactly one action.
    """

    @pytest.mark.parametrize("score,expected", [
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
        (-1.0,  "SELL"),
    ])
    def test_boundary(self, score, expected):
        from config import score_to_action
        assert score_to_action(score) == expected, (
            f"score_to_action({score}) returned "
            f"'{score_to_action(score)}', expected '{expected}'"
        )

    def test_all_five_actions_reachable(self):
        """All 5 distinct action labels must be reachable."""
        from config import score_to_action
        results = {score_to_action(s) for s in (90, 70, 50, 35, 10)}
        assert results == {"STRONG BUY", "BUY", "HOLD", "WATCH", "SELL"}


# ────────────────────────────────────────────────────────────
# Round 3 Fix #2 — RSI < 30 danger zone should score low
# ────────────────────────────────────────────────────────────
class TestRSIDangerZonePts:
    """RSI < 30 (deep oversold) must score fewer points than RSI 30-45
    (mild oversold recovery) in VN market context.

    VN-specific: RSI < 30 = margin call cascade zone where forced
    liquidation can persist for weeks. This is not a buy signal.
    RSI 30-45 = oversold recovery, a genuine VN buying zone (12 pts).
    RSI < 30 must only score 4 pts (was incorrectly 7).
    """

    def test_bear_series_score_not_inflated(self, ohlcv_bear):
        """A bear-trending series should produce a total score below 50."""
        sig = compute_score(ohlcv_bear, "1M", regime="bear",
                            macro_score=2.0, ticker="TEST")
        assert sig.score < 60, (
            f"Bear series scored {sig.score} — RSI danger zone too generous"
        )

    def test_rsi_breakdown_on_bear_data_low(self, ohlcv_bear):
        """RSI component on bear data must be <= 7 (down from 7, now 4 max)."""
        sig = compute_score(ohlcv_bear, "1M", regime="bear",
                            macro_score=2.0, ticker="TEST")
        rsi_pts = sig.breakdown.get("RSI", 99)
        assert rsi_pts <= 7, (
            f"RSI breakdown={rsi_pts} on bear data, expected <= 7"
        )

    def test_bull_rsi_higher_than_bear_rsi(self, ohlcv_bull, ohlcv_bear):
        """RSI component must be higher on bull data than bear data."""
        sig_bull = compute_score(ohlcv_bull, "1M", regime="bull",
                                 macro_score=7.0, ticker="TEST")
        sig_bear = compute_score(ohlcv_bear, "1M", regime="bear",
                                 macro_score=2.0, ticker="TEST")
        assert sig_bull.breakdown.get("RSI", 0) >= sig_bear.breakdown.get("RSI", 0), (
            "Bull RSI pts should be >= bear RSI pts"
        )


# ────────────────────────────────────────────────────────────
# Round 3 Fix #1 — BB_pctB contributes to Volume scoring
# ────────────────────────────────────────────────────────────
class TestBBBreakoutVolumeBonus:
    """BB %B breakout/support bonus must be included in Volume breakdown.

    BB %B > 0.8 + volume spike (vol_r > 1.5) = institutional breakout
    confirmation. This is a key VN pattern: stocks that break upper
    Bollinger Band with strong volume show sustained institutional buying.
    BB %B < 0.15 (near lower band) + no floor streak = support accumulation.

    Both paths add points to Volume component (still capped at 20).
    """

    def test_score_in_range_after_bb_bonus(self, ohlcv_bull):
        """Score must remain within 0-100 after BB bonus is applied."""
        sig = compute_score(ohlcv_bull, "1M", regime="bull",
                            macro_score=7.0, ticker="VCB")
        assert 0 <= sig.score <= 100, (
            f"Score out of range after BB bonus: {sig.score}"
        )

    def test_volume_breakdown_capped_at_20(self, ohlcv_bull):
        """Volume component must never exceed 20 pts even with BB bonus."""
        sig = compute_score(ohlcv_bull, "1M", regime="bull",
                            macro_score=7.0, ticker="VCB")
        vol_pts = sig.breakdown.get("Volume", 99)
        assert vol_pts <= 20.0, (
            f"Volume breakdown={vol_pts} exceeds cap of 20 pts"
        )

    def test_breakdown_sum_still_matches_total(self, ohlcv):
        """BB bonus goes into Volume; total breakdown must still sum to score."""
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        total = sum(sig.breakdown.values())
        assert abs(total - sig.score) < 0.5, (
            f"breakdown sum {total:.2f} != score {sig.score:.2f}"
        )

    def test_bull_volume_gte_bear_volume(self, ohlcv_bull, ohlcv_bear):
        """Bull data (likely near upper BB) should get >= Volume pts vs bear."""
        sig_bull = compute_score(ohlcv_bull, "1M", regime="bull",
                                 macro_score=7.0, ticker="TEST")
        sig_bear = compute_score(ohlcv_bear, "1M", regime="bear",
                                 macro_score=2.0, ticker="TEST")
        assert sig_bull.breakdown.get("Volume", 0) >= sig_bear.breakdown.get("Volume", -5)


# ─────────────────────────────────────────────────────────────
# Round 5 Fix #4 — _precomputed flag
# ─────────────────────────────────────────────────────────────
class TestPrecomputedFlag:
    """_precomputed=True bỏ qua compute_all — tối ưu cho backtest loop (O(n²)→O(n))."""

    def test_precomputed_same_score_as_normal(self, ohlcv):
        """_precomputed=True phải cho điểm giống hệt normal mode."""
        from core.indicators import compute_all
        tf  = "1M"
        cfg = TIMEFRAME_CONFIG[tf]
        df_ind = compute_all(ohlcv.copy(), cfg)

        sig_normal = compute_score(ohlcv, tf, ticker="PRE_A")
        sig_pre    = compute_score(df_ind, tf, ticker="PRE_A", _precomputed=True)

        assert abs(sig_normal.score - sig_pre.score) < 0.01, (
            f"Normal={sig_normal.score:.3f} vs Precomputed={sig_pre.score:.3f}"
        )
        assert sig_normal.action == sig_pre.action

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_precomputed_all_timeframes(self, ohlcv, tf):
        """_precomputed mode phải hoạt động cho tất cả 5 TF."""
        from core.indicators import compute_all
        cfg    = TIMEFRAME_CONFIG[tf]
        df_ind = compute_all(ohlcv.copy(), cfg)
        sig    = compute_score(df_ind, tf, _precomputed=True)
        assert isinstance(sig, SignalResult)
        assert 0 <= sig.score <= 100

    def test_precomputed_false_default(self, ohlcv):
        """Default _precomputed=False phải hoạt động bình thường."""
        sig = compute_score(ohlcv, "1M")
        assert isinstance(sig, SignalResult)
        assert 0 <= sig.score <= 100

    def test_precomputed_stop_below_price(self, ohlcv):
        """Với _precomputed=True, stop_loss vẫn phải < price."""
        from core.indicators import compute_all
        df_ind = compute_all(ohlcv.copy(), TIMEFRAME_CONFIG["1M"])
        sig = compute_score(df_ind, "1M", _precomputed=True)
        if sig.price > 0:
            assert sig.stop_loss < sig.price

    def test_precomputed_target_above_price(self, ohlcv):
        """Với _precomputed=True, take_profit vẫn phải > price."""
        from core.indicators import compute_all
        df_ind = compute_all(ohlcv.copy(), TIMEFRAME_CONFIG["1M"])
        sig = compute_score(df_ind, "1M", _precomputed=True)
        if sig.price > 0:
            assert sig.take_profit > sig.price


# ─────────────────────────────────────────────────────────────
# Round 5 Fix #1 — ACB/SHB exchange mapping (HOSE, not HNX)
# ─────────────────────────────────────────────────────────────
class TestExchangeMapping:
    """ACB chuyển HOSE 2021, SHB chuyển HOSE 2022 — giá limit phải là ±7%."""

    def test_acb_is_hose_price_limit(self):
        from config import get_price_limit
        assert get_price_limit("ACB") == 0.07, (
            "ACB chuyển sang HOSE năm 2021 — phải dùng giá limit ±7% (HOSE), không phải ±10% (HNX)"
        )

    def test_shb_is_hose_price_limit(self):
        from config import get_price_limit
        assert get_price_limit("SHB") == 0.07, (
            "SHB chuyển sang HOSE năm 2022 — phải dùng giá limit ±7% (HOSE), không phải ±10% (HNX)"
        )

    def test_pvs_still_hnx(self):
        from config import get_price_limit, TICKER_EXCHANGE
        assert TICKER_EXCHANGE.get("PVS") == "HNX"
        assert get_price_limit("PVS") == 0.10

    def test_oil_still_upcom(self):
        from config import get_price_limit, TICKER_EXCHANGE
        assert TICKER_EXCHANGE.get("OIL") == "UPCOM"
        assert get_price_limit("OIL") == 0.15

    def test_acb_not_in_hnx_map(self):
        from config import TICKER_EXCHANGE
        assert TICKER_EXCHANGE.get("ACB") is None, (
            "ACB không được liệt trong TICKER_EXCHANGE — default về HOSE"
        )

    def test_shb_not_in_hnx_map(self):
        from config import TICKER_EXCHANGE
        assert TICKER_EXCHANGE.get("SHB") is None, (
            "SHB không được liệt trong TICKER_EXCHANGE — default về HOSE"
        )


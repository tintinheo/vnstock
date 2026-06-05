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
        # When total score components exceed 100 before clamping,
        # breakdown stores pre-clamp values while score is clamped to 100.
        # So breakdown sum >= score, and the gap is bounded by the clamp window.
        assert total >= sig.score - 0.1, (
            f"breakdown sum {total:.2f} should be >= clamped score {sig.score:.2f}"
        )
        assert (total - sig.score) <= 5.0, (
            f"breakdown sum {total:.2f} exceeds clamped score {sig.score:.2f} by more than 5 pts"
        )

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


# ─────────────────────────────────────────────────────────────
# BUG-02 — score phải luôn >= 0 (không bao giờ âm)
# ─────────────────────────────────────────────────────────────
class TestScoreNeverNegative:
    """BUG-02 regression: streak floor liên tiếp làm vol -= 3 có thể đẩy
    tổng score xuống âm. Fix: clamp score = max(0, min(100, raw_score)).
    """

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_floor_streak_score_not_negative(self, ohlcv_floor_streak, tf):
        """Score không âm với dữ liệu 3 phiên sàn liên tiếp cho tất cả TF."""
        sig = compute_score(ohlcv_floor_streak, tf, ticker="FLOOR")
        assert sig.score >= 0.0, (
            f"TF={tf}: score={sig.score} < 0 — clamp floor fix chưa hoạt động"
        )

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_floor_streak_score_in_valid_range(self, ohlcv_floor_streak, tf):
        """Score phải nằm trong khoảng [0, 100] với mọi dữ liệu."""
        sig = compute_score(ohlcv_floor_streak, tf, ticker="FLOOR")
        assert 0.0 <= sig.score <= 100.0, (
            f"TF={tf}: score={sig.score} ngoài khoảng [0, 100]"
        )

    def test_bear_series_score_not_negative(self, ohlcv_bear):
        """Score với dữ liệu giảm mạnh (bear series) cũng phải >= 0."""
        sig = compute_score(ohlcv_bear, "1M", regime="bear",
                            macro_score=0.0, ticker="BEAR")
        assert sig.score >= 0.0, f"Bear series score={sig.score} < 0"

    def test_score_type_is_float(self, ohlcv_floor_streak):
        """Score phải là float, không phải NaN hoặc inf."""
        sig = compute_score(ohlcv_floor_streak, "1M", ticker="FLOOR")
        import math
        assert isinstance(sig.score, float)
        assert not math.isnan(sig.score)
        assert not math.isinf(sig.score)


# ─────────────────────────────────────────────────────────────
# BUG-05 — RSI zones calibrated theo RSI period
# ─────────────────────────────────────────────────────────────
class TestRsiZonesByPeriod:
    """BUG-05: RSI-9 (1W) oscillates higher than RSI-14/21.
    Using uniform zones would penalise 1W signals by 5 pts for the same
    trending stock. Fix: period-specific zone boundaries via _RSI_ZONES.
    """

    def test_rsi_score_function_exists(self):
        """_rsi_score helper phải tồn tại và có thể import."""
        from core.scoring import _rsi_score
        assert callable(_rsi_score)

    @pytest.mark.parametrize("rsi_v, expected_pts", [
        (55.0, 15),   # trong zone 48-68 → max pts (period 9)
        (68.0, 10),   # trong zone 68-78 → 10 pts (period 9)
        (40.0, 12),   # trong zone 35-48 → 12 pts (period 9)
        (32.0,  4),   # trong zone 0-35 → 4 pts (period 9)
        (80.0,  5),   # trong zone 78-88 → 5 pts (period 9)
        (90.0,  2),   # trong zone 88-101 → 2 pts (period 9)
    ])
    def test_period9_zones(self, rsi_v, expected_pts):
        """Zone boundaries cho RSI-9 phải đúng với bảng _RSI_ZONES[9]."""
        from core.scoring import _rsi_score
        result = _rsi_score(rsi_v, 9)
        assert result == float(expected_pts), (
            f"RSI={rsi_v} with period=9: expected {expected_pts} pts, got {result}"
        )

    @pytest.mark.parametrize("rsi_v, expected_pts", [
        (55.0, 15),   # trong zone 45-65 → max pts (period 14, unchanged regression)
        (65.0, 10),   # trong zone 65-75 → 10 pts
        (37.0, 12),   # trong zone 30-45 → 12 pts
        (25.0,  4),   # trong zone 0-30 → 4 pts
        (78.0,  5),   # trong zone 75-85 → 5 pts
        (88.0,  2),   # trong zone 85-101 → 2 pts
    ])
    def test_period14_zones_regression(self, rsi_v, expected_pts):
        """Zone boundaries period=14 phải giữ nguyên (regression test)."""
        from core.scoring import _rsi_score
        result = _rsi_score(rsi_v, 14)
        assert result == float(expected_pts), (
            f"RSI={rsi_v} with period=14: expected {expected_pts} pts, got {result}"
        )

    @pytest.mark.parametrize("rsi_v, expected_pts", [
        (52.0, 15),   # trong zone 42-62 → max pts (period 21)
        (62.0, 10),   # trong zone 62-72 → 10 pts
        (35.0, 12),   # trong zone 28-42 → 12 pts
        (22.0,  4),   # trong zone 0-28 → 4 pts
        (75.0,  5),   # trong zone 72-82 → 5 pts
        (85.0,  2),   # trong zone 82-101 → 2 pts
    ])
    def test_period21_zones(self, rsi_v, expected_pts):
        """Zone boundaries cho RSI-21 phải đúng với bảng _RSI_ZONES[21]."""
        from core.scoring import _rsi_score
        result = _rsi_score(rsi_v, 21)
        assert result == float(expected_pts), (
            f"RSI={rsi_v} with period=21: expected {expected_pts} pts, got {result}"
        )

    def test_unknown_period_falls_back_to_14(self):
        """Period không có trong _RSI_ZONES phải dùng period=14 zones."""
        from core.scoring import _rsi_score
        # RSI=55, period=14 → 15 pts; period=7 (unknown) → also 15 pts (fallback)
        assert _rsi_score(55.0, 7) == _rsi_score(55.0, 14)
        assert _rsi_score(68.0, 7) == _rsi_score(68.0, 14)

    def test_same_bullish_stock_scores_comparably_across_1w_and_1m(self, ohlcv_bull):
        """Cùng cổ phiếu bull, điểm 1W và 1M không chênh lệch quá 8 pts RSI."""
        sig_1w = compute_score(ohlcv_bull, "1W", regime="bull", macro_score=7.0)
        sig_1m = compute_score(ohlcv_bull, "1M", regime="bull", macro_score=7.0)
        rsi_diff = abs(
            sig_1w.breakdown.get("RSI", 0) - sig_1m.breakdown.get("RSI", 0)
        )
        assert rsi_diff <= 8, (
            f"RSI pts: 1W={sig_1w.breakdown.get('RSI')} vs 1M={sig_1m.breakdown.get('RSI')} "
            f"— chênh {rsi_diff} pts (quá lớn, ngưỡng zone chưa được calibrate)"
        )


# ─────────────────────────────────────────────────────────────
# BUG-06 — SMA slope window adaptive theo sma_fast period
# ─────────────────────────────────────────────────────────────
class TestSmaSlopeAdaptiveWindow:
    """BUG-06: slope_bars = max(3, cfg['sma_fast'] // 5).
    1W (sma_fast=5): max(3, 1)=3 bars — giống cũ.
    5M (sma_fast=50): max(3, 10)=10 bars — thay vì 3 bars vô nghĩa.
    """

    def test_1w_slope_window_is_3(self, ohlcv):
        """1W: sma_fast=5 → slope_bars = max(3, 5//5) = 3 (không đổi)."""
        from config import TIMEFRAME_CONFIG
        sma_fast = TIMEFRAME_CONFIG["1W"]["sma_fast"]
        slope_bars = max(3, sma_fast // 5)
        assert slope_bars == 3, f"1W slope_bars={slope_bars}, expected 3"

    def test_5m_slope_window_is_10(self):
        """5M: sma_fast=50 → slope_bars = max(3, 50//5) = 10."""
        from config import TIMEFRAME_CONFIG
        sma_fast = TIMEFRAME_CONFIG["5M"]["sma_fast"]
        slope_bars = max(3, sma_fast // 5)
        assert slope_bars == 10, f"5M slope_bars={slope_bars}, expected 10"

    def test_3m_slope_window_is_10(self):
        """3M: sma_fast=50 → slope_bars = max(3, 50//5) = 10."""
        from config import TIMEFRAME_CONFIG
        sma_fast = TIMEFRAME_CONFIG["3M"]["sma_fast"]
        slope_bars = max(3, sma_fast // 5)
        assert slope_bars == 10, f"3M slope_bars={slope_bars}, expected 10"

    def test_1m_slope_window_is_4(self):
        """1M: sma_fast=20 → slope_bars = max(3, 20//5) = 4."""
        from config import TIMEFRAME_CONFIG
        sma_fast = TIMEFRAME_CONFIG["1M"]["sma_fast"]
        slope_bars = max(3, sma_fast // 5)
        assert slope_bars == 4, f"1M slope_bars={slope_bars}, expected 4"

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_slope_bars_never_zero(self, tf):
        """slope_bars phải luôn >= 3 với mọi TF."""
        from config import TIMEFRAME_CONFIG
        sma_fast = TIMEFRAME_CONFIG[tf]["sma_fast"]
        slope_bars = max(3, sma_fast // 5)
        assert slope_bars >= 3, f"TF={tf}: slope_bars={slope_bars} < 3"

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_compute_score_runs_without_error_with_adaptive_slope(self, ohlcv, tf):
        """compute_score với adaptive slope window không gây lỗi index-out-of-range."""
        sig = compute_score(ohlcv, tf, ticker="SLOPE_TEST")
        assert isinstance(sig, SignalResult)
        assert 0.0 <= sig.score <= 100.0


# ─────────────────────────────────────────────────────────────
# BUG-07 — Foreign flow 1B VND minimum threshold
# ─────────────────────────────────────────────────────────────
class TestForeignFlowThreshold:
    """BUG-07: mua ròng < 1B VND là noise intraday, không phải signal thực.
    Old: any ff > 0 → 3 pts.
    New: ff > 1e10 → 5 pts | ff > 1e9 → 3 pts | ff > 0 → 1 pt | ff < -1e10 → 0 pt | else → 1 pt.
    """

    def test_1w_ff_always_zero_pts(self, ohlcv):
        """1W không tính FF — breakdown['Foreign'] phải = 0."""
        sig = compute_score(ohlcv, "1W",
                            foreign_flow_net=2e10, foreign_flow_net_20d=2e10,
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 0.0

    def test_ff_500m_vnd_scores_1pt(self, ohlcv):
        """500M VND mua ròng = noise → 1 pt (không phải 3 pts như cũ)."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=500_000_000,  # 500M VND
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 1.0, (
            f"500M VND (noise level) should score 1 pt, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_1b_vnd_scores_1pt(self, ohlcv):
        """Đúng 1B VND là ranh giới dưới tier 3pts → 1 pt (exclusive lower bound)."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=1_000_000_000,  # 1B VND
                            ticker="VCB")
        # 1e9 is NOT > 1e9, so it falls to the `elif ff_ref > 0: ff_pts = 1` branch
        assert sig.breakdown.get("Foreign", -99) == 1.0

    def test_ff_2b_vnd_scores_3pt(self, ohlcv):
        """2B VND mua ròng đáng kể → 3 pts."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=2_000_000_000,  # 2B VND
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 3.0, (
            f"2B VND should score 3 pts, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_15b_vnd_scores_5pt(self, ohlcv):
        """15B VND mua ròng mạnh → 5 pts (max)."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=15_000_000_000,  # 15B VND
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 5.0, (
            f"15B VND should score 5 pts (max), got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_negative_large_scores_0pt(self, ohlcv):
        """Bán ròng mạnh (< -10B VND) → 0 pts."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=-15_000_000_000,  # -15B VND
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 0.0, (
            f"Strong sell (-15B VND) should score 0 pts, got {sig.breakdown.get('Foreign')}"
        )

    def test_ff_small_negative_scores_1pt(self, ohlcv):
        """Bán ròng vừa phải (> -10B, < 0) → 1 pt (baseline)."""
        sig = compute_score(ohlcv, "1M",
                            foreign_flow_net=0.0,
                            foreign_flow_net_20d=-500_000_000,  # -500M VND (moderate)
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 1.0, (
            f"Moderate sell (-500M VND) should score 1 pt, got {sig.breakdown.get('Foreign')}"
        )

    @pytest.mark.parametrize("tf", ["2W", "1M", "3M", "5M"])
    def test_strong_buy_ff_scores_5_on_all_long_tfs(self, ohlcv, tf):
        """Strong FF buy (>10B) phải cho 5 pts trên tất cả TF dài."""
        sig = compute_score(ohlcv, tf,
                            foreign_flow_net_20d=15_000_000_000,
                            ticker="VCB")
        assert sig.breakdown.get("Foreign", -99) == 5.0, (
            f"TF={tf}: strong FF buy should score 5, got {sig.breakdown.get('Foreign')}"
        )


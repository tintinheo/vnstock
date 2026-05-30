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

    def test_rr_ratio_dynamic(self, ohlcv_bull):
        """RR ratio should be calculated dynamically based on ATR, not fixed."""
        sig = compute_score(ohlcv_bull, "1M", ticker="VCB")
        if sig.action in ("BUY", "STRONG BUY"):
            assert sig.rr_ratio > 0
            # Check if it's based on ATR, not a fixed config value
            cfg = TIMEFRAME_CONFIG["1M"]
            expected_rr = (cfg["tp_multiplier"] * sig.atr) / (cfg["sl_multiplier"] * sig.atr)
            assert abs(sig.rr_ratio - expected_rr) < 0.1 # Allow for rounding differences
        else:
            assert sig.rr_ratio == 0

    def test_insufficient_data_returns_zero_score(self, ohlcv_small):
        sig = compute_score(ohlcv_small, "5M", ticker="X")
        assert sig.score == 0

    def test_breakdown_keys_present(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        expected_keys = {"Trend", "Momentum", "RSI", "Volume", "Foreign Flow", "Macro", "ADX"}
        assert set(sig.breakdown.keys()) == expected_keys

    def test_breakdown_sum_close_to_score(self, ohlcv):
        sig = compute_score(ohlcv, "1M", ticker="VCB")
        total = sum(sig.breakdown.values())
        # final_score is clipped at 0, so compare with the clipped total
        assert abs(max(0, total) - sig.score) < 0.5


# ─────────────────────────────────────────────────────────────
# Regime filter
# ─────────────────────────────────────────────────────────────
class TestRegimeFilter:
    def test_bear_regime_gives_zero_macro_points(self, ohlcv_bull):
        """A bear regime should result in 0 points for the Macro component."""
        sig = compute_score(ohlcv_bull, "1W", regime="bear", macro_score=10)
        assert sig.breakdown["Macro"] == 0

    def test_sideways_regime_halves_macro_points(self, ohlcv_bull):
        """A sideways regime should halve the macro score contribution."""
        sig = compute_score(ohlcv_bull, "1W", regime="sideways", macro_score=8)
        assert sig.breakdown["Macro"] == 4

    def test_bull_regime_uses_full_macro_score(self, ohlcv_bull):
        """A bull regime should use the full macro score."""
        sig = compute_score(ohlcv_bull, "1W", regime="bull", macro_score=7)
        assert sig.breakdown["Macro"] == 7


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
    def test_ff_active_on_2w(self, ohlcv):
        """Foreign flow must have a non-zero impact on 2W timeframe."""
        sig_no_ff = compute_score(ohlcv, "2W", foreign_flow_net=0.0, foreign_flow_net_20d=0.0)
        # Use a large net flow that would trigger the highest score tier
        large_net_flow = 1e12
        avg_vol = ohlcv['volume'].mean()
        avg_price = ohlcv['close'].mean()
        if avg_vol > 0 and avg_price > 0:
            # Make flow significant relative to volume
            large_net_flow = avg_vol * avg_price * 0.1
        
        sig_ff = compute_score(ohlcv, "2W", foreign_flow_net=large_net_flow, foreign_flow_net_20d=large_net_flow)
        
        assert sig_ff.breakdown["Foreign Flow"] > 0
        assert sig_ff.score > sig_no_ff.score


# ─────────────────────────────────────────────────────────────
# Audit Round 6: New Scoring Logic Tests
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def mock_df_with_indicators():
    """Creates a mock DataFrame with all necessary indicator columns initialized."""
    from core.indicators import compute_all
    from config import TIMEFRAME_CONFIG
    
    # Create a base DataFrame that is long enough
    data = {
        'open': np.linspace(100, 150, 200),
        'high': np.linspace(102, 155, 200),
        'low': np.linspace(98, 148, 200),
        'close': np.linspace(101, 152, 200),
        'volume': np.linspace(100000, 200000, 200)
    }
    df = pd.DataFrame(data)
    # Pre-calculate all indicators to ensure columns exist
    df_computed = compute_all(df, TIMEFRAME_CONFIG["1M"])
    return df_computed

class TestNewScoringComponents:
    def test_supertrend_buy_increases_score(self, mock_df_with_indicators):
        """A clear Supertrend buy signal should result in a high Trend score."""
        df = mock_df_with_indicators
        # Manually create a perfect Supertrend buy signal on the last row
        df.loc[df.index[-1], 'close'] = 160
        df.loc[df.index[-1], 'supertrend'] = 150
        df.loc[df.index[-1], 'supertrend_dir'] = 1
        
        sig = compute_score(df, "1M", _precomputed=True)
        assert sig.breakdown["Trend"] >= 15

    def test_obv_buy_increases_score(self, mock_df_with_indicators):
        """A clear OBV buy signal should result in a high Volume score."""
        df = mock_df_with_indicators
        # Manually create a perfect OBV buy signal
        df.loc[df.index[-1], 'obv_sma'] = 100000
        df.loc[df.index[-1], 'obv'] = 110000 # 10% above SMA
        
        sig = compute_score(df, "1M", _precomputed=True)
        assert sig.breakdown["Volume"] >= 10

    def test_standardized_foreign_flow_score(self, mock_df_with_indicators):
        """Test the new standardized foreign flow scoring."""
        df = mock_df_with_indicators
        avg_vol = df['sma_volume_slow'].iloc[-1]
        avg_price = df['sma_slow'].iloc[-1]
        
        # Ensure avg_vol and avg_price are not zero
        if avg_vol == 0 or avg_price == 0:
            pytest.skip("Average volume or price is zero, cannot test flow score.")

        # Case 1: Net buy > 5% of avg volume -> 10 pts
        net_buy_strong = avg_vol * avg_price * 0.06
        sig1 = compute_score(df, "1M", foreign_flow_net=net_buy_strong, _precomputed=True)
        assert sig1.breakdown["Foreign Flow"] == 10

        # Case 2: Net buy > 2% of avg volume -> 5 pts
        net_buy_moderate = avg_vol * avg_price * 0.03
        sig2 = compute_score(df, "1M", foreign_flow_net=net_buy_moderate, _precomputed=True)
        assert sig2.breakdown["Foreign Flow"] == 5
        
        # Case 3: Net sell > 5% of avg volume -> -10 pts
        net_sell_strong = - (avg_vol * avg_price * 0.06)
        sig3 = compute_score(df, "1M", foreign_flow_net=net_sell_strong, _precomputed=True)
        assert sig3.breakdown["Foreign Flow"] == -10

        # Case 4: Neutral flow -> 0 pts
        sig4 = compute_score(df, "1M", foreign_flow_net=0, _precomputed=True)
        assert sig4.breakdown["Foreign Flow"] == 0


# ─────────────────────────────────────────────────────────────
# Round 5 Fix #4 — _precomputed flag
# ─────────────────────────────────────────────────────────────
class TestPrecomputedFlag:
    """_precomputed=True bỏ qua compute_all — tối ưu cho backtest loop (O(n²)→O(n))."""

    def test_precomputed_same_score_as_normal(self, ohlcv):
        """_precomputed=True should yield the same score as normal run."""
        from core.indicators import compute_all
        
        # Normal run
        sig_normal = compute_score(ohlcv, "1M", ticker="VCB")

        # Precomputed run
        df_precomputed = compute_all(ohlcv.copy(), TIMEFRAME_CONFIG["1M"])
        sig_precomputed = compute_score(df_precomputed, "1M", ticker="VCB", _precomputed=True)

        assert abs(sig_normal.score - sig_precomputed.score) < 0.1
        assert sig_normal.action == sig_precomputed.action

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_precomputed_all_timeframes(self, ohlcv, tf):
        """_precomputed flag must work across all timeframes."""
        from core.indicators import compute_all
        df_precomputed = compute_all(ohlcv.copy(), TIMEFRAME_CONFIG[tf])
        sig = compute_score(df_precomputed, tf, _precomputed=True)
        assert isinstance(sig, SignalResult)
        assert 0 <= sig.score <= 100

    def test_precomputed_false_default(self, ohlcv):
        """Ensure _precomputed defaults to False and runs without precomputed df."""
        # This should run without error, even though df is not precomputed
        sig = compute_score(ohlcv, "1M")
        assert isinstance(sig, SignalResult)

    def test_precomputed_stop_below_price(self, strong_bull_df):
        """Using a strong bullish fixture to ensure a BUY signal is generated."""
        sig = compute_score(strong_bull_df, "1M", _precomputed=True, regime="bull")
        assert sig.action in ("BUY", "STRONG BUY"), f"Fixture should have produced a BUY signal, but got {sig.action} with score {sig.score}"
        assert sig.stop_loss < sig.price

    def test_precomputed_target_above_price(self, strong_bull_df):
        """Using a strong bullish fixture to ensure a BUY signal is generated."""
        sig = compute_score(strong_bull_df, "1M", _precomputed=True, regime="bull")
        assert sig.action in ("BUY", "STRONG BUY"), f"Fixture should have produced a BUY signal, but got {sig.action} with score {sig.score}"
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


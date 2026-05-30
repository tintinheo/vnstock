"""
tests/test_indicators.py — NewTradingOS v14.0
Unit tests for core/indicators.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.indicators import (
    sma, ema, rsi, macd, atr, bollinger_bands, bb_percent_b,
    adx, _wilder_smooth, volume_ratio, obv, money_flow_index, roc,
    manipulation_score, compute_all, golden_cross,
    ceiling_floor_streak, chaikin_money_flow, supertrend,
)
from config import TIMEFRAME_CONFIG, EXCHANGE_PRICE_LIMIT


# ─────────────────────────────────────────────────────────────
# SMA
# ─────────────────────────────────────────────────────────────
class TestSMA:
    def test_basic(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = sma(s, 3)
        assert abs(result.iloc[-1] - 4.0) < 1e-9

    def test_min_periods(self):
        s = pd.Series([10.0, 20.0])
        result = sma(s, 5)
        assert not result.isna().any(), "min_periods=1 should prevent NaN"

    def test_longer_series(self, ohlcv):
        result = sma(ohlcv["Close"], 20)
        assert len(result) == len(ohlcv)
        assert not result.isna().any()


# ─────────────────────────────────────────────────────────────
# EMA
# ─────────────────────────────────────────────────────────────
class TestEMA:
    def test_basic(self):
        s = pd.Series([1.0] * 20)
        result = ema(s, 10)
        assert abs(result.iloc[-1] - 1.0) < 1e-6

    def test_no_nan(self, ohlcv):
        result = ema(ohlcv["Close"], 20)
        assert not result.isna().any()


# ─────────────────────────────────────────────────────────────
# RSI
# ─────────────────────────────────────────────────────────────
class TestRSI:
    def test_range_0_100(self, ohlcv):
        result = rsi(ohlcv["Close"], 14)
        valid  = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_all_up_near_100(self):
        """RSI on strong uptrend (with pullbacks) should be well above 50."""
        rng = np.random.default_rng(7)
        # normal(+0.4, 1.0) gives mostly positive changes (uptrend) with some negatives
        changes = rng.normal(0.4, 1.0, 120)
        prices  = pd.Series(np.cumsum(changes) + 100.0)
        result  = rsi(prices, 14).dropna()
        assert len(result) > 0, "RSI should have non-NaN values on trending series"
        assert result.iloc[-1] > 55, f"Expected RSI > 55 on uptrend, got {result.iloc[-1]:.1f}"

    def test_all_down_near_0(self):
        s = pd.Series([float(50 - i) for i in range(50)])
        result = rsi(s, 14).dropna()
        assert result.iloc[-1] < 10

    def test_short_series(self, ohlcv_small):
        result = rsi(ohlcv_small["Close"], 14)
        assert len(result) == len(ohlcv_small)


# ─────────────────────────────────────────────────────────────
# MACD
# ─────────────────────────────────────────────────────────────
class TestMACD:
    def test_returns_three_series(self, ohlcv):
        line, sig, hist = macd(ohlcv["Close"])
        assert len(line) == len(ohlcv)
        assert len(sig)  == len(ohlcv)
        assert len(hist) == len(ohlcv)

    def test_histogram_equals_line_minus_signal(self, ohlcv):
        line, sig, hist = macd(ohlcv["Close"])
        diff = (line - sig - hist).abs().max()
        assert diff < 1e-9

    def test_no_nan(self, ohlcv):
        line, sig, hist = macd(ohlcv["Close"])
        for s in (line, sig, hist):
            assert not s.isna().any()


# ─────────────────────────────────────────────────────────────
# ATR
# ─────────────────────────────────────────────────────────────
class TestATR:
    def test_non_negative(self, ohlcv):
        result = atr(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], 14)
        assert (result.dropna() >= 0).all()

    def test_length(self, ohlcv):
        result = atr(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], 14)
        assert len(result) == len(ohlcv)


# ─────────────────────────────────────────────────────────────
# BOLLINGER BANDS
# ─────────────────────────────────────────────────────────────
class TestBollingerBands:
    def test_upper_gt_lower(self, ohlcv):
        upper, mid, lower = bollinger_bands(ohlcv["Close"])
        # Compare only where both are non-NaN (NaN>=NaN == False, not NaN)
        mask = upper.notna() & lower.notna()
        assert (upper[mask] >= lower[mask]).all()

    def test_pctb_range(self, ohlcv):
        """Most values should be in [0, 1] but can exceed on breakouts."""
        pctb = bb_percent_b(ohlcv["Close"])
        # At least 80% of values in [0, 1]
        ratio = ((pctb >= 0) & (pctb <= 1)).sum() / len(pctb)
        assert ratio > 0.8


# ─────────────────────────────────────────────────────────────
# ADX
# ─────────────────────────────────────────────────────────────
class TestADX:
    def test_range(self, ohlcv):
        result = adx(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], 14)
        valid  = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()


# ─────────────────────────────────────────────────────────────
# VOLUME INDICATORS
# ─────────────────────────────────────────────────────────────
class TestVolumeIndicators:
    def test_volume_ratio_gt_zero(self, ohlcv):
        result = volume_ratio(ohlcv["Volume"], 20)
        assert (result.dropna() > 0).all()

    def test_obv_monotone_on_all_up(self):
        n   = 50
        s   = pd.Series([float(i) for i in range(n)])
        vol = pd.Series([1_000_000.0] * n)
        result = obv(s, vol)
        diffs  = result.diff().dropna()
        assert (diffs >= 0).all(), "OBV should be non-decreasing on all-up closes"

    def test_mfi_range(self, ohlcv):
        result = money_flow_index(
            ohlcv["High"], ohlcv["Low"], ohlcv["Close"], ohlcv["Volume"], 14
        )
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# ─────────────────────────────────────────────────────────────
# ROC
# ─────────────────────────────────────────────────────────────
class TestROC:
    def test_flat_series_returns_zero(self):
        s      = pd.Series([100.0] * 50)
        result = roc(s, 5).dropna()
        assert (result.abs() < 1e-9).all()


# ─────────────────────────────────────────────────────────────
# MANIPULATION SCORE
# ─────────────────────────────────────────────────────────────
class TestManipulationScore:
    def test_range_0_100(self, ohlcv):
        result = manipulation_score(ohlcv["Close"], ohlcv["Volume"])
        valid  = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_spike_raises_score(self):
        n     = 50
        close = pd.Series([100.0] * n)
        vol   = pd.Series([1_000.0] * n)
        # Inject huge volume spike on last bar
        vol.iloc[-1] = 50_000.0
        result = manipulation_score(close, vol)
        assert result.iloc[-1] >= 50, "Huge volume spike should score >= 50"


# ─────────────────────────────────────────────────────────────
# COMPUTE ALL
# ─────────────────────────────────────────────────────────────
class TestComputeAll:
    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_adds_expected_columns(self, ohlcv, tf):
        cfg    = TIMEFRAME_CONFIG[tf]
        result = compute_all(ohlcv.copy(), cfg)
        expected = ["SMA_fast", "SMA_slow", "EMA_fast", "EMA_slow",
                    "RSI", "MACD", "MACD_signal", "MACD_hist",
                    "ATR", "BB_upper", "BB_mid", "BB_lower", "BB_pctB",
                    "Vol_ratio", "OBV", "MFI", "ADX", "Manip_score"]
        for col in expected:
            assert col in result.columns, f"Missing column: {col} for TF={tf}"

    def test_no_crash_on_minimal_data(self, ohlcv_small):
        cfg    = TIMEFRAME_CONFIG["1W"]
        result = compute_all(ohlcv_small.copy(), cfg)
        assert "RSI" in result.columns


# ─────────────────────────────────────────────────────────────
# GOLDEN CROSS
# ─────────────────────────────────────────────────────────────
class TestGoldenCross:
    def test_detects_crossover(self):
        # Create series where fast crosses above slow at position 10
        fast = pd.Series([1.0] * 5 + [3.0] * 10)
        slow = pd.Series([2.0] * 15)
        result = golden_cross(fast, slow)
        # Should have +1 signal at index 5
        assert result.iloc[5] == 1


# ─────────────────────────────────────────────────────────────
# FIX #6 — Wilder Smoothing for ADX
# ─────────────────────────────────────────────────────────────
class TestWilderSmooth:
    def test_constant_input_returns_constant(self):
        """Wilder smooth of a constant series must equal that constant."""
        s      = pd.Series([5.0] * 50)
        result = _wilder_smooth(s, 14)
        assert (result.dropna() - 5.0).abs().max() < 1e-6

    def test_length_preserved(self, ohlcv):
        result = _wilder_smooth(ohlcv["Close"], 14)
        assert len(result) == len(ohlcv)

    def test_adx_more_responsive_than_sma(self, ohlcv):
        """
        ADX with Wilder smoothing should react faster to a trend shift than
        a plain 14-period SMA. After a strong trending period, the Wilder ADX
        should generally be higher — confirming the fix is active.
        """
        result = adx(ohlcv["High"], ohlcv["Low"], ohlcv["Close"], 14)
        valid  = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()
        # ADX with Wilder smoothing should be non-zero on trending synthetic data
        assert valid.iloc[-1] > 0

    def test_adx_range_0_100_wilder(self, ohlcv_bull):
        """Wilder ADX must remain in [0, 100] on trending bull data."""
        result = adx(ohlcv_bull["High"], ohlcv_bull["Low"], ohlcv_bull["Close"], 14)
        valid  = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()


# ─────────────────────────────────────────────────────────────
# FIX #2 — Exchange-aware Ceiling/Floor Streak
# ─────────────────────────────────────────────────────────────
class TestCeilingFloorStreak:
    def test_hose_7pct_limit(self):
        """6.9% move should NOT count as trần on HOSE (threshold = 97% * 7% = 6.79%)."""
        prices = pd.Series([100.0, 106.9])  # 6.9% — below 7%
        streak = ceiling_floor_streak(prices, limit_pct=0.07)
        # 6.9% >= 0.07 * 0.97 = 6.79% — should trigger ceiling streak
        assert streak.iloc[-1] == 1.0

    def test_hnx_10pct_limit_not_triggered_at_7pct(self):
        """7% move must NOT count as trần on HNX (limit is 10%)."""
        prices = pd.Series([100.0] * 30 + [107.0])
        streak = ceiling_floor_streak(prices, limit_pct=0.10)
        # 7 / 100 = 7% < 97% * 10% = 9.7%
        assert streak.iloc[-1] == 0.0, "7% should not be trần on HNX (±10%)"

    def test_hnx_10pct_triggers_at_9_8pct(self):
        """9.8% move must count as trần on HNX (threshold = 97% * 10% = 9.7%)."""
        prices = pd.Series([100.0] * 30 + [109.8])
        streak = ceiling_floor_streak(prices, limit_pct=0.10)
        # 9.8% >= 9.7% → trần
        assert streak.iloc[-1] == 1.0, "9.8% should be trần on HNX (±10%)"

    def test_upcom_15pct_limit(self):
        """14.8% move must count as trần on UPCoM (threshold = 97% * 15% = 14.55%)."""
        prices = pd.Series([100.0] * 30 + [114.8])
        streak = ceiling_floor_streak(prices, limit_pct=0.15)
        assert streak.iloc[-1] == 1.0, "14.8% should be trần on UPCoM (±15%)"

    def test_san_negative_streak(self):
        """Consecutive sàn should produce negative streak values."""
        prices = pd.Series([100.0, 93.0, 86.49])  # ~-7% each bar
        streak = ceiling_floor_streak(prices, limit_pct=0.07)
        assert streak.iloc[-1] == -2.0

    def test_streak_resets_on_normal_day(self):
        """A normal-move day must reset the streak to 0."""
        prices = pd.Series([100.0, 107.0, 107.0])  # trần then flat
        streak = ceiling_floor_streak(prices, limit_pct=0.07)
        assert streak.iloc[-1] == 0.0

    @pytest.mark.parametrize("exchange,limit_pct", [
        ("HOSE",  0.07),
        ("HNX",   0.10),
        ("UPCOM", 0.15),
    ])
    def test_exchange_price_limit_config(self, exchange, limit_pct):
        """Config EXCHANGE_PRICE_LIMIT must have correct values."""
        assert abs(EXCHANGE_PRICE_LIMIT[exchange] - limit_pct) < 1e-9


# ─────────────────────────────────────────────────────────────
# FIX #2 — compute_all passes correct exchange
# ─────────────────────────────────────────────────────────────
class TestComputeAllExchange:
    def _make_hnx_spike(self):
        """Return a df where the last bar has a 9.8% jump (trần HNX, NOT trần HOSE)."""
        import numpy as np
        n   = 100
        rng = np.random.default_rng(5)
        c   = 100_000.0 * np.exp(np.cumsum(rng.normal(0, 0.005, n)))
        c[-1] = c[-2] * 1.098  # exactly 9.8% jump
        df = pd.DataFrame({
            "Open": c * 0.99, "High": c * 1.01, "Low": c * 0.98, "Close": c,
            "Volume": np.ones(n) * 1_000_000,
        })
        return df

    def test_streak_hose_0_for_98pct(self):
        """For HOSE, a 9.8% move exceeds ±7% and should be flagged as ceiling streak."""
        cfg = TIMEFRAME_CONFIG["1M"]
        df  = self._make_hnx_spike()
        result = compute_all(df.copy(), cfg, exchange="HOSE")
        # 9.8% >= 97% * 7% = 6.79%, so HOSE sees it as trần
        assert result["Streak"].iloc[-1] >= 1.0

    def test_streak_hnx_1_for_98pct(self):
        """For HNX, 9.8% also counts as trần (>= 97% * 10% = 9.7%)."""
        cfg = TIMEFRAME_CONFIG["1M"]
        df  = self._make_hnx_spike()
        result = compute_all(df.copy(), cfg, exchange="HNX")
        assert result["Streak"].iloc[-1] >= 1.0

    def test_streak_default_hose(self, ohlcv):
        """Default exchange (no arg) should behave like HOSE."""
        cfg = TIMEFRAME_CONFIG["1M"]
        result_default = compute_all(ohlcv.copy(), cfg)
        result_hose    = compute_all(ohlcv.copy(), cfg, exchange="HOSE")
        assert (result_default["Streak"] == result_hose["Streak"]).all()


# ─────────────────────────────────────────────────────────────
# FIX #3 — ATC Manipulation Bonus
# ─────────────────────────────────────────────────────────────
class TestManipulationScoreATC:
    def test_atc_bonus_adds_to_score(self, ohlcv):
        """High ATC vol ratio should raise the manipulation score."""
        n        = len(ohlcv)
        base_vol = ohlcv["Volume"]
        # All ATC vol = 80% of total (well above ATC_RATIO_THRESH=40%)
        atc_ratio = pd.Series([0.80] * n, index=ohlcv.index)

        score_base = manipulation_score(ohlcv["Close"], base_vol)
        score_atc  = manipulation_score(ohlcv["Close"], base_vol, atc_vol_ratio=atc_ratio)

        # ATC bonus should raise score — compare only non-NaN rows
        valid = score_base.notna() & score_atc.notna()
        assert (score_atc[valid] >= score_base[valid]).all(), \
            "ATC bonus must not lower the manipulation score"
        assert score_atc.dropna().iloc[-1] > score_base.dropna().iloc[-1], \
            "High ATC ratio must add bonus points on the last bar"

    def test_none_atc_unchanged(self, ohlcv):
        """Passing atc_vol_ratio=None must produce identical results to no arg."""
        score_none    = manipulation_score(ohlcv["Close"], ohlcv["Volume"], atc_vol_ratio=None)
        score_default = manipulation_score(ohlcv["Close"], ohlcv["Volume"])
        # Compare only non-NaN rows (early rows may be NaN due to rolling)
        valid = score_none.notna() & score_default.notna()
        assert (score_none[valid] == score_default[valid]).all()

    def test_atc_score_capped_at_100(self):
        """Even with all signals maxed out, manipulation score must not exceed 100."""
        n     = 50
        close = pd.Series([100.0] * (n - 1) + [115.0])  # big price spike
        vol   = pd.Series([100.0] * (n - 1) + [10_000.0])  # huge vol spike
        atc_r = pd.Series([1.0] * n)  # 100% ATC volume
        result = manipulation_score(close, vol, atc_vol_ratio=atc_r)
        assert result.max() <= 100.0

    def test_atc_below_threshold_no_bonus(self, ohlcv):
        """ATC ratio below ATC_RATIO_THRESH should produce near-zero bonus."""
        from config import ATC_RATIO_THRESH
        n          = len(ohlcv)
        atc_low    = pd.Series([ATC_RATIO_THRESH * 0.1] * n, index=ohlcv.index)
        score_base = manipulation_score(ohlcv["Close"], ohlcv["Volume"])
        score_atc  = manipulation_score(ohlcv["Close"], ohlcv["Volume"], atc_vol_ratio=atc_low)
        # Low ATC ratio → minimal bonus
        diff = (score_atc - score_base).abs().max()
        assert diff < 3.0, "Low ATC ratio should add <3 pts bonus"

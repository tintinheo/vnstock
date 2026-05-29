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
    adx, volume_ratio, obv, money_flow_index, roc,
    manipulation_score, compute_all, golden_cross,
)
from config import TIMEFRAME_CONFIG


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

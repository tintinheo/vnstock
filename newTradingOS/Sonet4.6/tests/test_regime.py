"""
tests/test_regime.py — NewTradingOS v14.0
Tests for core/regime.py — HMM and rule-based regime detection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.regime import (
    detect_regime, _detect_rule, regime_color, regime_emoji,
    regime_label_vi, RegimeResult,
)


# ─────────────────────────────────────────────────────────────
# RegimeResult namedtuple
# ─────────────────────────────────────────────────────────────
class TestRegimeResult:
    def test_fields(self):
        r = RegimeResult("bull", 0.8, ["bull"], "hmm", {"bull": 0.001})
        assert r.regime == "bull"
        assert r.probability == 0.8

    def test_valid_regime_values(self):
        for regime in ("bull", "bear", "sideways"):
            r = detect_regime(pd.Series([100.0] * 60), use_hmm=False)
            assert r.regime in ("bull", "bear", "sideways")


# ─────────────────────────────────────────────────────────────
# Rule-based detection
# ─────────────────────────────────────────────────────────────
class TestRuleDetection:
    def test_bull_trending_up(self):
        n = 200
        prices = pd.Series([100.0 * (1.005 ** i) for i in range(n)])
        r = _detect_rule(prices)
        assert r.regime == "bull"

    def test_bear_trending_down(self):
        n = 200
        prices = pd.Series([100.0 * (0.995 ** i) for i in range(n)])
        r = _detect_rule(prices)
        assert r.regime == "bear"

    def test_sideways_flat(self):
        prices = pd.Series([100.0] * 100)
        r = _detect_rule(prices)
        assert r.regime == "sideways"

    def test_probability_between_0_1(self, ohlcv_prices):
        r = _detect_rule(ohlcv_prices)
        assert 0.0 <= r.probability <= 1.0

    def test_history_length(self, ohlcv_prices):
        r = _detect_rule(ohlcv_prices)
        assert len(r.history) == len(ohlcv_prices)

    def test_method_label(self, ohlcv_prices):
        r = _detect_rule(ohlcv_prices)
        assert r.method == "rule"


# ─────────────────────────────────────────────────────────────
# detect_regime public API
# ─────────────────────────────────────────────────────────────
class TestDetectRegime:
    def test_empty_series(self):
        r = detect_regime(pd.Series([], dtype=float))
        assert r.regime == "sideways"
        assert r.probability == 0.5

    def test_none_series(self):
        r = detect_regime(None)
        assert r.regime == "sideways"

    def test_short_series_fallback(self):
        prices = pd.Series([100.0, 101.0, 99.0, 102.0, 98.0])
        r = detect_regime(prices, use_hmm=False)
        assert r.regime in ("bull", "bear", "sideways")

    def test_long_series_rule(self, ohlcv_prices):
        r = detect_regime(ohlcv_prices, use_hmm=False)
        assert r.regime in ("bull", "bear", "sideways")
        assert r.method == "rule"


# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────
class TestHelpers:
    def test_regime_color(self):
        assert regime_color("bull")     == "#00cc66"
        assert regime_color("bear")     == "#ff4444"
        assert regime_color("sideways") == "#ffaa33"
        assert regime_color("unknown")  == "#aaaaaa"

    def test_regime_emoji(self):
        assert regime_emoji("bull") == "🟢"
        assert regime_emoji("bear") == "🔴"

    def test_label_vi(self):
        assert regime_label_vi("bull")     == "Tăng"
        assert regime_label_vi("bear")     == "Giảm"
        assert regime_label_vi("sideways") == "Đi ngang"

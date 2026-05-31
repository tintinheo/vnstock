# -*- coding: utf-8 -*-
"""
tests/test_regime.py â€” NewTradingOS v14.0
Tests for core/regime.py â€” HMM and rule-based regime detection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.regime import (
    detect_regime, detect_market_regime, detect_regime_history, _detect_rule,
    regime_color, regime_emoji, regime_label_vi, RegimeResult,
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RegimeResult namedtuple
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class TestRegimeResult:
    def test_fields(self):
        r = RegimeResult("bull", 0.8, ["bull"], "hmm", {"bull": 0.001})
        assert r.regime == "bull"
        assert r.probability == 0.8

    def test_valid_regime_values(self):
        for regime in ("bull", "bear", "sideways"):
            r = detect_regime(pd.Series([100.0] * 60), use_hmm=False)
            assert r.regime in ("bull", "bear", "sideways")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Rule-based detection
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    def test_detect_regime_history_preserves_index(self):
        idx = pd.bdate_range("2026-01-05", periods=8)
        prices = pd.Series(np.linspace(1_200.0, 1_230.0, len(idx)), index=idx)

        history = detect_regime_history(prices)

        assert list(history.index) == list(idx)
        assert len(history) == len(prices)
        assert set(history.unique()).issubset({"bull", "bear", "sideways"})


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# detect_regime public API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helper functions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# ─────────────────────────────────────────────────────────────
# FIX #1 — detect_regime enforced for VN-Index use only
# ─────────────────────────────────────────────────────────────
class TestDetectRegimeVNIndex:
    def test_detect_market_regime_is_alias(self, ohlcv_prices):
        """detect_market_regime must be an alias for detect_regime."""
        r1 = detect_regime(ohlcv_prices, use_hmm=False)
        r2 = detect_market_regime(ohlcv_prices, use_hmm=False)
        assert r1.regime == r2.regime
        assert r1.method == r2.method
        assert r1.probability == r2.probability

    def test_vni_uptrend_gives_bull(self):
        """Synthetic VNI-style 500-day uptrend must produce bull regime."""
        n      = 300
        prices = pd.Series([1000.0 * (1.0015 ** i) for i in range(n)])
        r = detect_regime(prices, use_hmm=False)
        assert r.regime == "bull", f"Expected bull, got {r.regime}"

    def test_vni_downtrend_gives_bear(self):
        """Synthetic VNI-style downtrend must produce bear regime."""
        n      = 300
        prices = pd.Series([1400.0 * (0.9985 ** i) for i in range(n)])
        r = detect_regime(prices, use_hmm=False)
        assert r.regime == "bear", f"Expected bear, got {r.regime}"

    def test_result_has_history_same_length_as_prices(self, ohlcv_prices):
        r = detect_regime(ohlcv_prices, use_hmm=False)
        assert len(r.history) == len(ohlcv_prices)

    def test_history_only_valid_labels(self, ohlcv_prices):
        r = detect_regime(ohlcv_prices, use_hmm=False)
        assert all(h in ("bull", "bear", "sideways") for h in r.history)

    def test_probability_reflects_consistency(self):
        """Strongly trending price should yield high probability."""
        n = 200
        prices = pd.Series([1000.0 * (1.002 ** i) for i in range(n)])
        r = detect_regime(prices, use_hmm=False)
        # Consistent uptrend → last 20 sessions should mostly be 'bull'
        assert r.probability >= 0.7, f"Expected prob>=0.7 for consistent trend, got {r.probability}"

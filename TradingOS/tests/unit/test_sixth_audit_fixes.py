"""
Sixth-Pass Audit Regression Tests — BUG-24 through BUG-29

Run focused:
    pytest tests/unit/test_sixth_audit_fixes.py -v --tb=short

Coverage:
    BUG-24  macro.py         _regime_from_score reads thresholds from config (was ±30, now ±15)
    BUG-25  macro.py         macro_sizing_multiplier reads multipliers from config (was 0.75/0.40)
    BUG-26  macro.py         _staleness_penalty reads grace/pts/cap from config
    BUG-27  t_plus_engine    truthiness → is not None on rsi/adx/di_plus/di_minus
    BUG-28  patterns.py      second_mouse_gate: iloc[i-1] at i=0 no longer wraps to last bar
    BUG-29  horizon_forecast  long-horizon macro gate uses config ±15 not hardcoded ±20
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 60, base: float = 30_000.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = base + np.cumsum(rng.normal(0, base * 0.004, n))
    close = np.clip(close, base * 0.5, base * 2)
    atr = close * 0.012
    df = pd.DataFrame({
        "open":   close * (1 - rng.uniform(0, 0.002, n)),
        "high":   close + rng.uniform(0, atr, n),
        "low":    close - rng.uniform(0, atr, n),
        "close":  close,
        "volume": rng.integers(200_000, 900_000, n).astype(float),
    })
    df.index = pd.date_range("2024-01-02", periods=n, freq="B")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# BUG-24: _regime_from_score reads thresholds from config (accommodative_min=15,
#          restrictive_max=-15) instead of hardcoded ±30
# ─────────────────────────────────────────────────────────────────────────────

class TestBug24RegimeThresholds:
    """Score of ±20 should switch regime with config ±15 but NOT with old hardcoded ±30."""

    def _regime(self, score: float, prev: str = "NEUTRAL") -> str:
        from tradingos.core.macro import _regime_from_score
        return _regime_from_score(score, prev)

    def test_score_20_is_accommodative_not_neutral(self):
        """score=20 > config accommodative_min=15 → ACCOMMODATIVE (old code would be NEUTRAL)."""
        assert self._regime(20.0) == "ACCOMMODATIVE"

    def test_score_negative_16_is_restrictive_not_neutral(self):
        """score=-16 < config restrictive_max=-15 → RESTRICTIVE (old code would be NEUTRAL)."""
        assert self._regime(-16.0) == "RESTRICTIVE"

    def test_score_0_is_neutral(self):
        """score=0 is well within bounds → NEUTRAL regardless of threshold."""
        assert self._regime(0.0) == "NEUTRAL"

    def test_score_50_is_accommodative(self):
        """score=50 > any threshold → ACCOMMODATIVE."""
        assert self._regime(50.0) == "ACCOMMODATIVE"

    def test_hysteresis_restrictive_exits_via_hyst(self):
        """prev=RESTRICTIVE, score=-3: -3 > rest_thr+hyst=-15+10=-5 → early return NEUTRAL."""
        # The hysteresis early-return fires when score is on the correct side of (rest_thr+hyst)
        assert self._regime(-3.0, prev="RESTRICTIVE") == "NEUTRAL"

    def test_hysteresis_accommodative_crosses_to_neutral_at_4(self):
        """prev=ACCOMMODATIVE, score=4 < 15-10=5 → switches to NEUTRAL (early return)."""
        assert self._regime(4.0, prev="ACCOMMODATIVE") == "NEUTRAL"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-25: macro_sizing_multiplier reads multipliers from config
#          config: sizing_neutral=0.65, sizing_restrictive=0.32
#          old hardcode: NEUTRAL=0.75, RESTRICTIVE=0.40
# ─────────────────────────────────────────────────────────────────────────────

class TestBug25SizingMultipliers:
    def _mult(self, regime: str, confidence: str = "HIGH") -> float:
        from tradingos.core.macro import MacroResult, macro_sizing_multiplier
        mr = MacroResult(
            macro_score=0.0,
            macro_regime=regime,
            macro_confidence=confidence,
            macro_staleness_days=0,
        )
        return macro_sizing_multiplier(mr)

    def test_neutral_high_uses_config_065(self):
        """NEUTRAL/HIGH should return 0.65 (config sizing_neutral), not old 0.75."""
        result = self._mult("NEUTRAL", "HIGH")
        assert abs(result - 0.65) < 1e-9, f"Expected 0.65, got {result}"

    def test_restrictive_high_uses_config_032(self):
        """RESTRICTIVE/HIGH should return 0.32 (config sizing_restrictive), not old 0.40."""
        result = self._mult("RESTRICTIVE", "HIGH")
        assert abs(result - 0.32) < 1e-9, f"Expected 0.32, got {result}"

    def test_accommodative_high_is_100(self):
        """ACCOMMODATIVE/HIGH → 1.00 (unchanged in config)."""
        result = self._mult("ACCOMMODATIVE", "HIGH")
        assert abs(result - 1.00) < 1e-9

    def test_neutral_medium_haircut(self):
        """NEUTRAL/MEDIUM → 0.65 * 0.90 = 0.585."""
        result = self._mult("NEUTRAL", "MEDIUM")
        assert abs(result - 0.65 * 0.90) < 1e-6

    def test_restrictive_low_haircut(self):
        """RESTRICTIVE/LOW → 0.32 * 0.80 = 0.256."""
        result = self._mult("RESTRICTIVE", "LOW")
        assert abs(result - 0.32 * 0.80) < 1e-6

    def test_none_macro_result_returns_100(self):
        """None input → 1.0 (no macro data = no constraint)."""
        from tradingos.core.macro import macro_sizing_multiplier
        assert macro_sizing_multiplier(None) == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# BUG-26: _staleness_penalty reads constants from config
#          config: grace_days=3, pts_per_day=5, cap_pts=40
# ─────────────────────────────────────────────────────────────────────────────

class TestBug26StalenessPenalty:
    def _pen(self, days: int) -> float:
        from tradingos.core.macro import _staleness_penalty
        return _staleness_penalty(days)

    def test_within_grace_period_zero_penalty(self):
        """3 days stale (= grace) → 0 penalty."""
        assert self._pen(3) == 0.0

    def test_day_5_gives_10pts(self):
        """(5-3) * 5 = 10 pts penalty."""
        assert abs(self._pen(5) - 10.0) < 1e-9

    def test_day_11_hits_cap_at_40(self):
        """(11-3) * 5 = 40 → capped at 40."""
        assert self._pen(11) == 40.0

    def test_beyond_cap_still_40(self):
        """100 days stale → still capped at 40."""
        assert self._pen(100) == 40.0


# ─────────────────────────────────────────────────────────────────────────────
# BUG-27: t_plus_engine truthiness → is not None guards
# ─────────────────────────────────────────────────────────────────────────────

class TestBug27Truthiness:
    """Verify _score_range_break handles None and 0.0 ADX without exception."""

    def _make_t_plus_df(self, adx_val: float | None) -> pd.DataFrame:
        """Minimal df for _score_range_break."""
        n = 30
        rng = np.random.default_rng(99)
        close = 50_000 + np.cumsum(rng.normal(0, 200, n))
        df = pd.DataFrame({
            "open": close * 0.999, "high": close * 1.005,
            "low": close * 0.995, "close": close,
            "volume": rng.integers(100_000, 500_000, n).astype(float),
            "BB_upper": close * 1.01, "BB_lower": close * 0.99,
            "BB_mid": close,
            # ADX: fill array, last value is adx_val
            "ADX": ([10.0] * (n - 1) + [adx_val if adx_val is not None else float("nan")]),
            "DI_plus": [12.0] * n,
            "DI_minus": [8.0] * n,
        })
        return df

    def test_none_adx_no_exception(self):
        """_score_range_break(df with ADX=None/NaN) must not raise."""
        from tradingos.core.t_plus_engine import _score_range_break
        df = self._make_t_plus_df(None)
        score, reasons = _score_range_break(df)
        assert isinstance(score, float)

    def test_zero_adx_no_exception(self):
        """_score_range_break(df with ADX=0.0) must not raise — is not None guard works."""
        from tradingos.core.t_plus_engine import _score_range_break
        df = self._make_t_plus_df(0.0)
        score, reasons = _score_range_break(df)
        assert isinstance(score, float)
        # ADX=0 < 25 AND array shows rising (last 10→0, but adx_arr built from column)
        # No "ADX rất mạnh" or "ADX mạnh" reason expected since adx=0 doesn't meet > 25/30
        adx_strong_reasons = [r for r in reasons if "ADX rất mạnh" in r or "ADX mạnh" in r]
        assert adx_strong_reasons == []

    def test_valid_rsi_range_scores_correctly(self):
        """RSI in healthy range (55–72) still scores via is-not-None guard."""
        from tradingos.core.t_plus_engine import _score_momentum_cont
        n = 30
        rng = np.random.default_rng(42)
        close = 50_000 + np.cumsum(rng.normal(0, 200, n))
        df = pd.DataFrame({
            "close": close, "open": close, "high": close, "low": close,
            "volume": rng.integers(100_000, 500_000, n).astype(float),
            "SMA20": close, "SMA50": close * 0.95, "SMA200": close * 0.90,
            "ADX": [30.0] * n, "DI_plus": [20.0] * n, "DI_minus": [10.0] * n,
            "RSI14": [60.0] * n, "OBV": np.cumsum(rng.integers(0, 100_000, n)).astype(float),
            "MACD_hist": [0.05] * n,
        })
        score, reasons = _score_momentum_cont(df)
        rsi_reasons = [r for r in reasons if "RSI" in r and "momentum" in r]
        assert len(rsi_reasons) >= 1, "RSI=60 should trigger 'RSI vùng momentum' reason"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-28: patterns.py second_mouse_gate — iloc[i-1] at i=0 wraps to last bar
# ─────────────────────────────────────────────────────────────────────────────

class TestBug28SecondMouseGate:
    """
    Off-by-one fix: loop now starts at i=1 so iloc[i-1] is always the true
    prior bar, not the last bar of the lookback window.
    """

    def _make_breakout_df(self, n_history: int = 20,
                          lookback: int = 5,
                          breakout_level: float = 100.0) -> tuple[pd.DataFrame, float]:
        """
        Construct df where:
        - Bars (oldest→newest): only bar[0] of the lookback has close > level
        - All other bars (1-4) have close < level
        - bar[4] (newest/last in lookback) has low < level
        Old code (i starts at 0): at i=0, iloc[-1] = bar[4].low < level → false trigger
        New code (i starts at 1): bars 1-4 all have close < level → no trigger
        """
        total = n_history + lookback
        # History bars all below level
        rng = np.random.default_rng(123)
        history_close = breakout_level * 0.90 + rng.uniform(0, 5, n_history)
        # Lookback bars: bar[0]=breakout, bar[1..4] decline below level
        lookback_close = np.array([breakout_level * 1.10,  # bar[0]: above level
                                   breakout_level * 0.95,  # bar[1]
                                   breakout_level * 0.93,  # bar[2]
                                   breakout_level * 0.92,  # bar[3]
                                   breakout_level * 0.91]) # bar[4]: newest, below level
        close = np.concatenate([history_close, lookback_close])
        low   = close * 0.95   # all lows below close
        high  = close * 1.03
        df = pd.DataFrame({
            "open": close * 0.998, "high": high, "low": low, "close": close,
            "volume": np.full(total, 500_000.0),
        })
        df.index = pd.date_range("2024-01-02", periods=total, freq="B")
        return df, breakout_level

    def test_no_false_trigger_at_i0(self):
        """
        With fix: bars 1-4 of lookback all have close < level → no breakout found.
        Expect reason = 'No recent breakout or breakout is too new'.
        """
        from tradingos.core.patterns import second_mouse_gate
        df, level = self._make_breakout_df()
        result = second_mouse_gate(df, breakout_level=level, lookback=5)
        assert result["confirmed"] is False
        assert "No recent breakout" in result.get("reason", "")

    def test_valid_breakout_still_detected(self):
        """
        With a proper retest setup (breakout at i=1, pullback holds above level),
        second_mouse_gate should detect it correctly after the fix.
        """
        from tradingos.core.patterns import second_mouse_gate
        level = 100.0
        # Build bars: bar[0].low < level (came from below), bar[1].close > level (breakout),
        # bars[2-4]: pullback that holds above level, lower volume, last recovers
        n_hist = 10
        history = np.full(n_hist, level * 0.92)
        lookback_close = np.array([level * 0.95,   # bar[0]: came from below
                                   level * 1.06,   # bar[1]: breakout
                                   level * 1.02,   # bar[2]: pullback, holds above
                                   level * 1.01,   # bar[3]: still above
                                   level * 1.04])  # bar[4]: recovery
        lookback_low   = np.array([level * 0.92,   # bar[0]: below level (valid prior bar)
                                   level * 1.03,   # bar[1]: above level
                                   level * 1.01,   # bar[2]: above level ✓
                                   level * 1.005,  # bar[3]: above level ✓
                                   level * 1.02])  # bar[4]: above level
        lookback_high  = lookback_close * 1.02
        lookback_vol   = np.array([400_000.0, 900_000.0, 250_000.0, 260_000.0, 800_000.0])
        close = np.concatenate([history, lookback_close])
        low   = np.concatenate([history * 0.97, lookback_low])
        high  = np.concatenate([history * 1.03, lookback_high])
        vol   = np.concatenate([np.full(n_hist, 400_000.0), lookback_vol])
        df = pd.DataFrame({
            "open": close * 0.999, "high": high, "low": low, "close": close,
            "volume": vol,
        })
        df.index = pd.date_range("2024-01-02", periods=len(df), freq="B")
        result = second_mouse_gate(df, breakout_level=level, lookback=5)
        # The retest holds, so confirmed should be True
        assert result["confirmed"]  # np.True_ or True both acceptable


# ─────────────────────────────────────────────────────────────────────────────
# BUG-29: horizon_forecast long-horizon macro gate ±20 → config ±15
# ─────────────────────────────────────────────────────────────────────────────

class TestBug29HorizonMacroGate:
    """
    macro_score=17 (between old ±20 and config ±15):
    Old code: 17 < 20 → no bull boost
    New code: 17 > 15 (config) → bull += 2.0
    """

    def _forecast_long_bull_score(self, macro_score: float) -> float:
        """Call _forecast_long with given macro_score and return total bull score."""
        from tradingos.core.horizon_forecast import _forecast_long
        n = 60
        close = 50_000 + np.linspace(0, 2000, n)  # rising trend for SMA200
        df = pd.DataFrame({
            "open": close, "high": close * 1.005, "low": close * 0.995,
            "close": close,
            "volume": np.full(n, 500_000.0),
            "SMA200": close,   # flat SMA200 slope → no SMA200 score
            "OBV": np.cumsum(np.full(n, 10_000.0)),
            "Hurst": np.full(n, 0.5),
        })
        ctx = {
            "macro_regime": "NEUTRAL",
            "macro_score": macro_score,
            "fundamental_score": None,
        }
        vote, conf, reasons = _forecast_long(df, ctx)
        # Extract bull score by checking macro-related reasons
        macro_bull = sum(2.0 for r in reasons if "Kinh tế vĩ mô thuận" in r)
        macro_bear = sum(2.0 for r in reasons if "Kinh tế vĩ mô bất lợi" in r)
        return macro_bull - macro_bear

    def test_macro_score_17_gives_bull_boost(self):
        """score=17 > config accommodative_min=15 → macro bull +2.0."""
        delta = self._forecast_long_bull_score(17.0)
        assert delta == 2.0, f"Expected +2.0 macro bull for score=17, got {delta}"

    def test_macro_score_negative_17_gives_bear_boost(self):
        """score=-17 < config restrictive_max=-15 → macro bear +2.0."""
        delta = self._forecast_long_bull_score(-17.0)
        assert delta == -2.0, f"Expected -2.0 macro bear for score=-17, got {delta}"

    def test_macro_score_10_is_neutral(self):
        """score=10 between -15 and +15 → no macro contribution."""
        delta = self._forecast_long_bull_score(10.0)
        assert delta == 0.0

    def test_macro_score_25_still_gives_boost(self):
        """score=25 > 15 → still +2.0 (not doubled)."""
        delta = self._forecast_long_bull_score(25.0)
        assert delta == 2.0

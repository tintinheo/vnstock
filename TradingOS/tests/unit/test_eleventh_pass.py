"""Eleventh pass — Gap Analysis, VWAP, T+2.5 entry score tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ── OHLCV factory ─────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120, trend: float = 0.001, gap_pct: float = 0.0) -> pd.DataFrame:
    rng    = np.random.default_rng(42)
    dates  = pd.bdate_range("2024-01-02", periods=n)
    close  = 25_000 * np.cumprod(1 + rng.normal(trend, 0.01, n))
    volume = rng.integers(500_000, 2_000_000, n).astype(float)
    high   = close * 1.01
    low    = close * 0.99
    open_  = np.concatenate([close[:-1] * 0.995, [close[-2] * (1 + gap_pct / 100)]])

    if gap_pct != 0.0:
        high[-1] = max(open_[-1], close[-1]) * 1.005
        low[-1]  = min(open_[-1], close[-1]) * 0.995

    return pd.DataFrame({
        "date":   dates,
        "open":   open_,
        "high":   high,
        "low":    low,
        "close":  close,
        "volume": volume,
    })


def _make_with_indicators(n: int = 120, trend: float = 0.001, gap_pct: float = 0.0) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n=n, trend=trend, gap_pct=gap_pct))


# ═══════════════════════════════════════════════════════════════════════════════
# New indicator columns in compute_all()
# ═══════════════════════════════════════════════════════════════════════════════

class TestNewIndicatorColumns:
    """Verify compute_all() now produces the extended indicator columns."""

    def test_macd_hist_column_exists(self):
        df = _make_with_indicators()
        assert "MACD_hist" in df.columns

    def test_macd_line_and_signal_exist(self):
        df = _make_with_indicators()
        assert "MACD_line" in df.columns and "MACD_signal" in df.columns

    def test_stoch_k_d_columns_exist(self):
        df = _make_with_indicators()
        assert "STOCH_K" in df.columns and "STOCH_D" in df.columns

    def test_williams_r_column_exists(self):
        df = _make_with_indicators()
        assert "WILLIAMS_R" in df.columns

    def test_cci_column_exists(self):
        df = _make_with_indicators()
        assert "CCI" in df.columns

    def test_adx_di_columns_exist(self):
        df = _make_with_indicators()
        assert all(c in df.columns for c in ("ADX", "DI_plus", "DI_minus"))

    def test_williams_r_range_minus100_to_0(self):
        df = _make_with_indicators()
        valid = df["WILLIAMS_R"].dropna()
        assert len(valid) > 0
        assert (valid >= -100).all() and (valid <= 0.01).all()

    def test_stoch_k_range_0_to_100(self):
        df = _make_with_indicators()
        valid = df["STOCH_K"].dropna()
        assert len(valid) > 0
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_adx_nonnegative(self):
        df = _make_with_indicators()
        valid = df["ADX"].dropna()
        assert len(valid) > 0
        assert (valid >= 0).all()

    def test_existing_columns_still_present(self):
        df = _make_with_indicators()
        for col in ("RSI14", "ATR14", "SMA20", "SMA50", "SMA200",
                    "EMA9", "EMA21", "OBV", "BB_upper", "BB_mid", "BB_lower"):
            assert col in df.columns, f"Missing column: {col}"

    def test_macd_hist_equals_line_minus_signal(self):
        df = _make_with_indicators()
        diff = (df["MACD_line"] - df["MACD_signal"] - df["MACD_hist"]).dropna().abs()
        assert diff.max() < 1e-6


# ═══════════════════════════════════════════════════════════════════════════════
# detect_gaps
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectGaps:
    def _call(self, **kw):
        from tradingos.core.gap_vwap import detect_gaps
        return detect_gaps(_make_ohlcv(**kw))

    def test_returns_dict_with_required_keys(self):
        r = self._call()
        assert all(k in r for k in ("gap_pct", "gap_type", "avg_gap_pct", "gap_fill_pct"))

    def test_gap_up_detected(self):
        r = self._call(gap_pct=1.5)
        assert r["gap_type"] == "GAP_UP"
        assert r["gap_pct"] > 0.5

    def test_gap_down_detected(self):
        r = self._call(gap_pct=-1.5)
        assert r["gap_type"] == "GAP_DOWN"
        assert r["gap_pct"] < -0.5

    def test_small_gap_is_no_gap(self):
        r = self._call(gap_pct=0.3)
        assert r["gap_type"] == "NO_GAP"

    def test_no_gap_flat(self):
        r = self._call(gap_pct=0.0)
        assert r["gap_type"] == "NO_GAP"

    def test_empty_df_returns_safe_defaults(self):
        from tradingos.core.gap_vwap import detect_gaps
        r = detect_gaps(pd.DataFrame())
        assert r["gap_type"] == "NO_GAP"
        assert r["gap_pct"] == 0.0

    def test_short_df_returns_safe_defaults(self):
        from tradingos.core.gap_vwap import detect_gaps
        r = detect_gaps(_make_ohlcv(n=2))
        assert r["gap_type"] == "NO_GAP"

    def test_gap_pct_within_reasonable_range(self):
        r = self._call(gap_pct=0.8)
        assert -10 <= r["gap_pct"] <= 10

    def test_avg_gap_pct_nonnegative(self):
        r = self._call()
        assert r["avg_gap_pct"] >= 0.0

    def test_gap_fill_pct_0_to_100(self):
        r = self._call()
        assert 0 <= r["gap_fill_pct"] <= 100

    def test_gap_up_pct_positive(self):
        r = self._call(gap_pct=2.0)
        assert r["gap_pct"] > 0

    def test_gap_down_pct_negative(self):
        r = self._call(gap_pct=-2.0)
        assert r["gap_pct"] < 0


# ═══════════════════════════════════════════════════════════════════════════════
# compute_vwap_result (daily)
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeVwapResult:
    def _call(self, **kw):
        from tradingos.core.gap_vwap import compute_vwap_result
        df = _make_with_indicators(**kw)
        return compute_vwap_result(df)

    def test_returns_required_keys(self):
        r = self._call()
        assert all(k in r for k in ("vwap", "price_vs_vwap_pct", "vwap_dev"))

    def test_vwap_is_positive(self):
        r = self._call()
        assert r["vwap"] is not None and r["vwap"] > 0

    def test_vwap_dev_valid_values(self):
        r = self._call()
        assert r["vwap_dev"] in ("ABOVE", "BELOW", "AT")

    def test_strong_uptrend_price_tends_above_vwap(self):
        r = self._call(trend=0.008)
        assert r["price_vs_vwap_pct"] > 0

    def test_strong_downtrend_price_tends_below_vwap(self):
        r = self._call(trend=-0.008)
        assert r["price_vs_vwap_pct"] < 0

    def test_short_df_returns_none_vwap(self):
        from tradingos.core.gap_vwap import compute_vwap_result
        r = compute_vwap_result(_make_ohlcv(n=5))
        assert r["vwap"] is None

    def test_uses_precomputed_vwap_daily_column(self):
        from tradingos.core.gap_vwap import compute_vwap_result
        df = _make_with_indicators()
        df["VWAP_daily"] = 99_999.0
        r = compute_vwap_result(df)
        assert r["vwap"] == 99_999

    def test_vwap_dev_above_when_price_much_higher(self):
        from tradingos.core.gap_vwap import compute_vwap_result
        df = _make_with_indicators()
        df["VWAP_daily"] = df["close"].iloc[-1] * 0.95   # price ~5% above VWAP
        r = compute_vwap_result(df)
        assert r["vwap_dev"] == "ABOVE"

    def test_vwap_dev_below_when_price_much_lower(self):
        from tradingos.core.gap_vwap import compute_vwap_result
        df = _make_with_indicators()
        df["VWAP_daily"] = df["close"].iloc[-1] * 1.05   # price ~4.8% below VWAP
        r = compute_vwap_result(df)
        assert r["vwap_dev"] == "BELOW"


# ═══════════════════════════════════════════════════════════════════════════════
# compute_monthly_pivots
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeMonthlyPivots:
    def test_returns_five_pivot_levels(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        r = compute_monthly_pivots(_make_ohlcv())
        assert all(k in r for k in ("monthly_pp", "monthly_r1", "monthly_r2", "monthly_s1", "monthly_s2"))

    def test_r1_above_pp_above_s1(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        r = compute_monthly_pivots(_make_ohlcv())
        assert r["monthly_r1"] > r["monthly_pp"] > r["monthly_s1"]

    def test_r2_above_r1(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        r = compute_monthly_pivots(_make_ohlcv())
        assert r["monthly_r2"] > r["monthly_r1"]

    def test_s2_below_s1(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        r = compute_monthly_pivots(_make_ohlcv())
        assert r["monthly_s2"] < r["monthly_s1"]

    def test_short_df_returns_empty(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        assert compute_monthly_pivots(_make_ohlcv(n=5)) == {}

    def test_all_values_positive(self):
        from tradingos.core.gap_vwap import compute_monthly_pivots
        r = compute_monthly_pivots(_make_ohlcv())
        assert all(v > 0 for v in r.values())


# ═══════════════════════════════════════════════════════════════════════════════
# compute_fibonacci_levels
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeFibonacciLevels:
    def test_returns_five_levels(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        r = compute_fibonacci_levels(_make_ohlcv())
        assert all(k in r for k in ("fib_618", "fib_500", "fib_382", "fib_swing_high", "fib_swing_low"))

    def test_fib_618_between_swing_low_and_high(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        r = compute_fibonacci_levels(_make_ohlcv())
        assert r["fib_swing_low"] < r["fib_618"] < r["fib_swing_high"]

    def test_fib_382_above_618(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        r = compute_fibonacci_levels(_make_ohlcv())
        assert r["fib_382"] > r["fib_618"]

    def test_fib_500_between_382_and_618(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        r = compute_fibonacci_levels(_make_ohlcv())
        assert r["fib_618"] < r["fib_500"] < r["fib_382"]

    def test_short_df_returns_empty(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        assert compute_fibonacci_levels(_make_ohlcv(n=5)) == {}

    def test_all_values_positive(self):
        from tradingos.core.gap_vwap import compute_fibonacci_levels
        r = compute_fibonacci_levels(_make_ohlcv())
        assert all(v > 0 for v in r.values())


# ═══════════════════════════════════════════════════════════════════════════════
# compute_t25_entry_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeT25EntryScore:
    def _call(self, **kw):
        from tradingos.core.t25_engine import compute_t25_entry_score
        return compute_t25_entry_score(_make_with_indicators(**kw))

    def test_returns_required_keys(self):
        r = self._call()
        assert all(k in r for k in (
            "t25_score", "t25_signal", "t25_momo_score",
            "t25_struct_score", "t25_conf_score", "t25_confirms", "t25_regime",
        ))

    def test_score_in_0_to_100_range(self):
        r = self._call()
        assert 0 <= r["t25_score"] <= 100

    def test_signal_valid_values(self):
        r = self._call()
        assert r["t25_signal"] in ("T25_BUY", "T25_WATCH", "T25_NEUTRAL", "T25_AVOID")

    def test_regime_valid_values(self):
        r = self._call()
        assert r["t25_regime"] in ("BULL_TREND", "SIDEWAYS", "BEAR_TREND")

    def test_strong_uptrend_scores_higher_than_downtrend(self):
        up   = self._call(trend=+0.006, n=150)
        down = self._call(trend=-0.006, n=150)
        assert up["t25_score"] >= down["t25_score"]

    def test_confirms_is_list_of_strings(self):
        r = self._call()
        assert isinstance(r["t25_confirms"], list)
        assert all(isinstance(s, str) for s in r["t25_confirms"])

    def test_momo_score_nonnegative_and_max_20(self):
        r = self._call()
        assert 0 <= r["t25_momo_score"] <= 20

    def test_struct_score_nonnegative_and_max_20(self):
        r = self._call()
        assert 0 <= r["t25_struct_score"] <= 20

    def test_conf_score_nonnegative_and_max_10(self):
        r = self._call()
        assert 0 <= r["t25_conf_score"] <= 10

    def test_buy_signal_implies_score_above_threshold(self):
        r = self._call()
        if r["t25_signal"] == "T25_BUY":
            threshold = 74.8 if r["t25_regime"] == "BEAR_TREND" else 68.0
            assert r["t25_score"] >= threshold

    def test_avoid_signal_implies_score_below_32(self):
        r = self._call()
        if r["t25_signal"] == "T25_AVOID":
            assert r["t25_score"] <= 32.0

    def test_with_candle_pts_increases_conf_score(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators()
        r_base   = compute_t25_entry_score(df, pattern_result={})
        r_candle = compute_t25_entry_score(df, pattern_result={"candle_pts": 3})
        assert r_candle["t25_conf_score"] >= r_base["t25_conf_score"]

    def test_with_rsi_div_pts_increases_conf_score(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators()
        r_base = compute_t25_entry_score(df, pattern_result={})
        r_div  = compute_t25_entry_score(df, pattern_result={"rsi_div_pts": 4})
        assert r_div["t25_conf_score"] >= r_base["t25_conf_score"]

    def test_conf_score_capped_at_10_with_large_bonus(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators()
        r = compute_t25_entry_score(df, pattern_result={"candle_pts": 10, "rsi_div_pts": 10})
        assert r["t25_conf_score"] <= 10.0

    def test_short_df_does_not_crash(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators(n=30)
        r = compute_t25_entry_score(df)
        assert isinstance(r["t25_score"], float)
        assert 0 <= r["t25_score"] <= 100

    def test_none_pattern_result_does_not_crash(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators()
        r = compute_t25_entry_score(df, pattern_result=None)
        assert isinstance(r["t25_score"], float)

    def test_empty_pattern_result_does_not_crash(self):
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_with_indicators()
        r = compute_t25_entry_score(df, pattern_result={})
        assert isinstance(r["t25_score"], float)

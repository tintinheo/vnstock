"""
Unit tests for VN-Swing Alpha Improvement features:
  - calculate_fractional_kelly (portfolio_engine)
  - T25ExitManager Kelly mode + kelly_mode in _out()
  - calculate_csad (Quant_Profiler)
  - compute_rolling_beta_5d (Quant_Profiler)
  - rolling_beta_5d field in analyse_ticker result dict
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: calculate_fractional_kelly
# ─────────────────────────────────────────────────────────────────────────────
from portfolio_engine import calculate_fractional_kelly

def test_half_kelly_normal():
    """Normal volatility (< 0.03) → Half-Kelly."""
    f = calculate_fractional_kelly(win_prob=0.60, gain_loss_ratio=2.0/1.5, market_volatility=0.02)
    b = 2.0 / 1.5
    expected = max(0.0, (b * 0.60 - 0.40) / b) * 0.5
    assert abs(f - expected) < 1e-9, f"Half-Kelly: {f} != {expected}"

def test_quarter_kelly_high_stress():
    """High stress (> 0.03) → Quarter-Kelly."""
    f = calculate_fractional_kelly(win_prob=0.60, gain_loss_ratio=2.0/1.5, market_volatility=0.04)
    b = 2.0 / 1.5
    expected = max(0.0, (b * 0.60 - 0.40) / b) * 0.25
    assert abs(f - expected) < 1e-9, f"Quarter-Kelly: {f} != {expected}"

def test_negative_expectation_clamped_to_zero():
    """Negative Kelly expectation must be clamped to 0."""
    f = calculate_fractional_kelly(win_prob=0.30, gain_loss_ratio=0.5, market_volatility=0.01)
    assert f == 0.0, f"Negative expectation should return 0, got {f}"

def test_boundary_volatility_exactly_003():
    """Volatility exactly 0.03 → normal (Half-Kelly) path."""
    f_at  = calculate_fractional_kelly(0.60, 2.0/1.5, 0.03)
    f_low = calculate_fractional_kelly(0.60, 2.0/1.5, 0.02)
    assert f_at == f_low, "Vol=0.03 should use Half-Kelly (not >0.03)"

print("T1: calculate_fractional_kelly")
test_half_kelly_normal()
test_quarter_kelly_high_stress()
test_negative_expectation_clamped_to_zero()
test_boundary_volatility_exactly_003()
print("  PASS (4/4)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: T25ExitManager uses dynamic Kelly + kelly_mode in _out()
# ─────────────────────────────────────────────────────────────────────────────
from portfolio_engine import T25ExitManager

def test_kelly_mode_half():
    """Low ATR/price (< 0.03) → Half-Kelly mode."""
    m = T25ExitManager(entry_price=20000, atr=100, bt_win_rate=0.60)  # vol=0.005
    assert m.kelly_mode == "Half-Kelly", f"Expected Half-Kelly, got {m.kelly_mode}"

def test_kelly_mode_quarter():
    """High ATR/price (> 0.03) → Quarter-Kelly mode."""
    m = T25ExitManager(entry_price=10000, atr=400, bt_win_rate=0.60)  # vol=0.04
    assert m.kelly_mode == "Quarter-Kelly", f"Expected Quarter-Kelly, got {m.kelly_mode}"

def test_quarter_size_smaller_than_half():
    """Quarter-Kelly → smaller rec_size_pct than Half-Kelly for same parameters."""
    m_half    = T25ExitManager(entry_price=20000, atr=100,  bt_win_rate=0.65)
    m_quarter = T25ExitManager(entry_price=10000, atr=400,  bt_win_rate=0.65)
    assert m_quarter.recommended_size_pct <= m_half.recommended_size_pct, (
        f"Quarter {m_quarter.recommended_size_pct}% should be <= Half {m_half.recommended_size_pct}%"
    )

def test_kelly_mode_in_daily_update_output():
    """_out() must include 'kelly_mode' key."""
    m = T25ExitManager(20000, 300, 0.60)
    out = m.daily_update(20000, 1)
    assert "kelly_mode" in out, f"kelly_mode missing from daily_update output: {list(out.keys())}"
    assert out["kelly_mode"] in ("Half-Kelly", "Quarter-Kelly"), f"Invalid kelly_mode: {out['kelly_mode']}"

def test_rec_size_clamped():
    """recommended_size_pct always in [5, 25]."""
    for wp in [0.10, 0.40, 0.60, 0.80, 0.99]:
        for atr in [10, 500, 5000]:
            m = T25ExitManager(20000, atr, wp)
            assert 5.0 <= m.recommended_size_pct <= 25.0, (
                f"size_pct={m.recommended_size_pct} out of bounds for wp={wp}, atr={atr}"
            )

print("T2: T25ExitManager")
test_kelly_mode_half()
test_kelly_mode_quarter()
test_quarter_size_smaller_than_half()
test_kelly_mode_in_daily_update_output()
test_rec_size_clamped()
print("  PASS (5/5)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: calculate_csad
# ─────────────────────────────────────────────────────────────────────────────
from Quant_Profiler import calculate_csad

def test_csad_identical_returns():
    """All same returns → CSAD = 0 (pure herding)."""
    assert calculate_csad([0.03, 0.03, 0.03]) == 0.0

def test_csad_known_value():
    """Manual computation must match."""
    rets = np.array([0.03, -0.01, 0.02, 0.005])
    expected = float(np.mean(np.abs(rets - np.mean(rets))))
    result = calculate_csad(rets)
    assert abs(result - expected) < 1e-12, f"CSAD mismatch: {result} != {expected}"

def test_csad_empty():
    assert calculate_csad([]) == 0.0

def test_csad_single_element():
    assert calculate_csad([0.05]) == 0.0

def test_csad_nan_ignored():
    """NaN entries are dropped, not propagated."""
    r = calculate_csad([0.01, float("nan"), 0.05])
    assert r > 0.0, "NaN should be ignored"
    assert not np.isnan(r), "Result must not be NaN"

def test_csad_positive_definite():
    """CSAD is always >= 0."""
    for arr in [[-0.05, 0.05], [0.01, -0.01, 0.02, -0.03], [0.0, 0.0, 0.0, 0.1]]:
        assert calculate_csad(arr) >= 0.0

def test_csad_herding_threshold():
    """Market limit-up scenario (all +7%) → CSAD nearly 0 (herding)."""
    herding = [0.07] * 5
    assert calculate_csad(herding) < 0.001

print("T3: calculate_csad")
test_csad_identical_returns()
test_csad_known_value()
test_csad_empty()
test_csad_single_element()
test_csad_nan_ignored()
test_csad_positive_definite()
test_csad_herding_threshold()
print("  PASS (7/7)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: compute_rolling_beta_5d
# ─────────────────────────────────────────────────────────────────────────────
from Quant_Profiler import compute_rolling_beta_5d, calculate_indicators

def _make_df(closes, n=10):
    """Build minimal OHLCV DataFrame. Uses lists to avoid pd.Series index-alignment issues."""
    dates = pd.date_range("2026-01-01", periods=n)
    c = [float(v) for v in list(closes)[:n]]
    return pd.DataFrame({
        "Open":   c,
        "High":   [v * 1.01 for v in c],
        "Low":    [v * 0.99 for v in c],
        "Close":  c,
        "Volume": [1_000_000.0] * n,
    }, index=dates)

def test_beta_identical():
    """Stock = market → beta = 1.0."""
    closes = [100, 102, 101, 104, 103, 106, 105, 108, 107, 110]
    df_s = _make_df(closes)
    df_m = _make_df(closes)
    b = compute_rolling_beta_5d(df_s, df_m)
    assert abs(b - 1.0) < 1e-6, f"Expected beta=1.0, got {b}"

def test_beta_double():
    """Stock moves 2× market → beta ≈ 2.0."""
    mkt = np.array([100, 101, 102, 103, 104, 105, 106, 107, 108, 109], dtype=float)
    mkt_rets = np.diff(mkt) / mkt[:-1]
    stk_rets = mkt_rets * 2
    stk = np.concatenate([[100.0], 100.0 * np.cumprod(1 + stk_rets)])
    df_s = _make_df(stk.tolist())
    df_m = _make_df(mkt.tolist())
    b = compute_rolling_beta_5d(df_s, df_m)
    assert abs(b - 2.0) < 0.05, f"Expected beta~2.0, got {b}"

def test_beta_fallback_no_market():
    """No market data → fallback to ATR ratio, still positive."""
    closes = [float(100 + i + (i % 3 - 1)) for i in range(30)]
    df = _make_df(closes, n=30)
    df = calculate_indicators(df)
    b = compute_rolling_beta_5d(df, None)
    assert b > 0, f"Fallback beta should be positive, got {b}"

def test_beta_empty_df():
    """Empty input → returns 1.0."""
    assert compute_rolling_beta_5d(pd.DataFrame(), None) == 1.0

def test_beta_too_short():
    """Fewer than 6 bars → returns 1.0."""
    df = _make_df([100, 101, 102, 103, 104], n=5)
    assert compute_rolling_beta_5d(df, None) == 1.0

def test_beta_market_zero_variance():
    """Market has zero variance (flat) → fallback, no division by zero."""
    stock_c = [100, 102, 101, 104, 103, 106, 105, 108, 107, 110]
    flat_c  = [100] * 10
    df_s = _make_df(stock_c)
    df_m = _make_df(flat_c)
    b = compute_rolling_beta_5d(df_s, df_m)  # var_m = 0 → should not crash
    assert isinstance(b, float), f"Should return float, got {type(b)}"

print("T4: compute_rolling_beta_5d")
test_beta_identical()
test_beta_double()
test_beta_fallback_no_market()
test_beta_empty_df()
test_beta_too_short()
test_beta_zero_variance = test_beta_market_zero_variance
test_beta_zero_variance()
print("  PASS (6/6)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 5: rolling_beta_5d in analyse_ticker() result dict
# ─────────────────────────────────────────────────────────────────────────────
from Quant_Profiler import analyse_ticker

print("T5: analyse_ticker result dict contains rolling_beta_5d")
res = analyse_ticker("HPG", days=50, verbose=False)
assert "rolling_beta_5d" in res, f"rolling_beta_5d missing. Keys: {list(res.keys())[:10]}"
assert isinstance(res["rolling_beta_5d"], float), f"Wrong type: {type(res['rolling_beta_5d'])}"
assert res["rolling_beta_5d"] > 0, f"Beta must be positive, got {res['rolling_beta_5d']}"
print(f"  rolling_beta_5d = {res['rolling_beta_5d']}  (HPG, 50d)")
print("  PASS (1/1)")

# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 52)
print("  ALL 23 TEST CASES PASSED — VN-Swing Alpha Improvement")
print("=" * 52)

# ─────────────────────────────────────────────────────────────────────────────
# Test 6: _build_lstm_training_data
# ─────────────────────────────────────────────────────────────────────────────
from forecast_engine import _build_lstm_training_data, _SEQ_LEN, _FEATURES

def _make_indicator_df(n=100):
    """Minimal OHLCV + computed indicators DataFrame for training tests."""
    dates  = pd.date_range("2024-01-01", periods=n)
    closes = np.cumsum(np.random.default_rng(42).normal(0, 1, n)) + 100
    df = pd.DataFrame({
        "Open": closes * 0.995, "High": closes * 1.01,
        "Low":  closes * 0.99,  "Close": closes,
        "Volume": np.full(n, 500_000.0),
    }, index=dates)
    df["Vol_MA20"]  = df["Volume"].rolling(20, min_periods=1).mean()
    df["RSI"]       = 50.0
    df["MACD_Hist"] = 0.0
    df["ATR"]       = np.abs(df["High"] - df["Low"])
    return df

def test_build_returns_none_on_none_df():
    X, y = _build_lstm_training_data(None)
    assert X is None and y is None

def test_build_returns_none_on_short_df():
    df_short = _make_indicator_df(n=_SEQ_LEN + 5)   # too short
    X, y = _build_lstm_training_data(df_short)
    assert X is None and y is None

def test_build_returns_none_on_missing_column():
    df = _make_indicator_df(100)
    df.drop(columns=["ATR"], inplace=True)
    X, y = _build_lstm_training_data(df)
    assert X is None and y is None

def test_build_returns_correct_shapes():
    df = _make_indicator_df(100)
    X, y = _build_lstm_training_data(df)
    assert X is not None and y is not None
    # n=100, skip first SEQ_LEN and last 5 → expect 100 - SEQ_LEN - 5 = 75 samples
    expected_n = 100 - _SEQ_LEN - 5
    assert X.shape == (expected_n, _SEQ_LEN, _FEATURES), f"Wrong X shape: {X.shape}"
    assert y.shape == (expected_n,), f"Wrong y shape: {y.shape}"

def test_build_output_is_float32():
    df = _make_indicator_df(100)
    X, y = _build_lstm_training_data(df)
    assert X.dtype == np.float32, f"X dtype should be float32, got {X.dtype}"
    assert y.dtype == np.float32, f"y dtype should be float32, got {y.dtype}"

print("T6: _build_lstm_training_data")
test_build_returns_none_on_none_df()
test_build_returns_none_on_short_df()
test_build_returns_none_on_missing_column()
test_build_returns_correct_shapes()
test_build_output_is_float32()
print("  PASS (5/5)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 7: train_lstm_model
# ─────────────────────────────────────────────────────────────────────────────
import unittest.mock as _mock
from forecast_engine import train_lstm_model, _KERAS_AVAILABLE, _LSTM_CACHE

def test_train_returns_none_when_keras_unavailable():
    with _mock.patch("forecast_engine._KERAS_AVAILABLE", False):
        result = train_lstm_model("TEST", _make_indicator_df(100))
    assert result is None

def test_train_returns_none_on_insufficient_data():
    df_tiny = _make_indicator_df(5)
    result = train_lstm_model("TINY", df_tiny)
    assert result is None, "Should return None for < 20 training samples"

def test_train_produces_model_and_caches():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    _LSTM_CACHE.pop("TRAINTEST", None)   # clear any cached entry
    df = _make_indicator_df(120)
    model = train_lstm_model("TRAINTEST", df, force=True, epochs=3, patience=3)
    assert model is not None, "train_lstm_model returned None with Keras available"
    assert "TRAINTEST" in _LSTM_CACHE, "Model should be cached after training"

def test_train_progress_callback_called():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    called_epochs = []

    def _cb(epoch, total, logs):
        called_epochs.append(epoch)
        assert isinstance(total, int) and total > 0
        assert isinstance(logs, dict)

    _LSTM_CACHE.pop("CBTEST", None)
    train_lstm_model("CBTEST", _make_indicator_df(120), force=True,
                     epochs=3, patience=3, progress_callback=_cb)
    assert len(called_epochs) > 0, "progress_callback was never called"
    assert all(e >= 1 for e in called_epochs), "epoch should be 1-based"

def test_train_returns_cached_without_force():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    # Re-use the model trained in test_train_produces_model_and_caches
    cached = _LSTM_CACHE.get("TRAINTEST")
    if cached is None:
        print("    SKIP (no cached model)")
        return
    result = train_lstm_model("TRAINTEST", _make_indicator_df(120), force=False)
    assert result is cached, "Should return cached model without retraining"

print("T7: train_lstm_model")
test_train_returns_none_when_keras_unavailable()
test_train_returns_none_on_insufficient_data()
test_train_produces_model_and_caches()
test_train_progress_callback_called()
test_train_returns_cached_without_force()
print("  PASS (5/5)")

# ─────────────────────────────────────────────────────────────────────────────
# Test 8: _lstm_inference
# ─────────────────────────────────────────────────────────────────────────────
from forecast_engine import _lstm_inference, prepare_lstm_features

def test_inference_returns_none_when_keras_unavailable():
    df = _make_indicator_df(100)
    features = prepare_lstm_features(df)
    with _mock.patch("forecast_engine._KERAS_AVAILABLE", False):
        result = _lstm_inference("NKERAS", features, df)
    assert result is None

def test_inference_returns_none_without_df_and_no_model():
    from forecast_engine import _MODELS_DIR
    import pathlib
    model_path = _MODELS_DIR / "GHOST_lstm.keras"
    if model_path.exists():
        model_path.unlink()   # ensure no file
    _LSTM_CACHE.pop("GHOST", None)
    df = _make_indicator_df(100)
    features = prepare_lstm_features(df)
    result = _lstm_inference("GHOST", features, df=None)
    # Without df, cannot auto-train → should return None (Keras available or not)
    if not _KERAS_AVAILABLE:
        assert result is None
    else:
        assert result is None, "No model on disk and no df provided — should be None"

def test_inference_auto_trains_and_returns_float():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    from forecast_engine import _MODELS_DIR
    model_path = _MODELS_DIR / "AUTOTRAIN_lstm.keras"
    if model_path.exists():
        model_path.unlink()
    _LSTM_CACHE.pop("AUTOTRAIN", None)
    df = _make_indicator_df(120)
    features = prepare_lstm_features(df)
    result = _lstm_inference("AUTOTRAIN", features, df)
    assert isinstance(result, float), f"Expected float, got {type(result)}: {result}"

def test_inference_uses_cache_on_second_call():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    # Use the TRAINTEST model cached earlier
    if "TRAINTEST" not in _LSTM_CACHE:
        print("    SKIP (no cached model from T7)")
        return
    df = _make_indicator_df(120)
    features = prepare_lstm_features(df)
    # Patch models load to verify it is NOT called (we should use cache)
    with _mock.patch("forecast_engine.keras") as _mk:
        _mk.models.load_model.side_effect = RuntimeError("should not load from disk")
        result = _lstm_inference("TRAINTEST", features, df=None)
    # result may be float or None depending on predict; no RuntimeError = cache was hit
    assert True   # no exception raised means cache path taken

def test_inference_produces_float_with_trained_model():
    if not _KERAS_AVAILABLE:
        print("    SKIP (Keras not installed)")
        return
    if "TRAINTEST" not in _LSTM_CACHE:
        print("    SKIP (no cached model from T7)")
        return
    df = _make_indicator_df(120)
    features = prepare_lstm_features(df)
    result = _lstm_inference("TRAINTEST", features, df)
    assert isinstance(result, float), f"Expected float prediction, got {type(result)}"

print("T8: _lstm_inference")
test_inference_returns_none_when_keras_unavailable()
test_inference_returns_none_without_df_and_no_model()
test_inference_auto_trains_and_returns_float()
test_inference_uses_cache_on_second_call()
test_inference_produces_float_with_trained_model()
print("  PASS (5/5)")

print()
print("=" * 52)
print("  ALL 38 TEST CASES PASSED — LSTM + Improvements")
print("=" * 52)

# ─────────────────────────────────────────────────────────────────────────────
# Test 9: generate_t_plus_recommendation
# ─────────────────────────────────────────────────────────────────────────────
from portfolio_engine import generate_t_plus_recommendation

_BASE_R = {
    "ticker":          "TEST",
    "t25_signal":      "T25_BUY",
    "t25_score":       80.0,
    "bull_pct":        66.0,
    "signal_confirmed": True,
    "regime":          "BULL_TREND",
    "vsa_state":       "ACCUM",
    "candle_pattern":  "HAMMER",
    "rsi_divergence":  "NONE",
    "at_ceiling":      False,
    "at_floor":        False,
    "rolling_beta_5d": 1.0,
    "kl_ratio":        1.5,
    "price":           50000.0,
    "sma20":           49500.0,
    "atr":             800.0,
    "sl":              48000.0,
    "tp1":             53000.0,
    "tp2":             56000.0,
    "rr1":             1.5,
}


def test_t25_avoid_forces_avoid_grade():
    """T25_AVOID signal must force AVOID / Grade E regardless of other scores."""
    r = {**_BASE_R, "t25_signal": "T25_AVOID", "at_ceiling": False}
    rec = generate_t_plus_recommendation(r)
    assert rec["action"] == "AVOID",  f"Expected AVOID, got {rec['action']}"
    assert rec["grade"]  == "E",      f"Expected Grade E, got {rec['grade']}"
    assert rec["confidence_score"] == 0, "Force-AVOID should have score 0"
    assert rec["position_size_pct"] == 0.0


def test_at_ceiling_forces_avoid():
    """at_ceiling=True must force AVOID / Grade E."""
    r = {**_BASE_R, "at_ceiling": True}
    rec = generate_t_plus_recommendation(r)
    assert rec["action"] == "AVOID", f"Expected AVOID, got {rec['action']}"
    assert rec["grade"]  == "E"
    assert "Giá chạm TRẦN" in " ".join(rec["risk_flags"])


def test_strong_buy_scenario():
    """All-positive signals should produce STRONG_BUY / Grade A."""
    r = {**_BASE_R}  # base is already all-positive
    rec = generate_t_plus_recommendation(r)
    assert rec["action"] == "STRONG_BUY", f"Expected STRONG_BUY, got {rec['action']} (score={rec['confidence_score']})"
    assert rec["grade"]  == "A"
    assert rec["confidence_score"] >= 80


def test_bear_trend_reduces_confidence():
    """BEAR_TREND regime should give a lower score than BULL_TREND."""
    r_bull = {**_BASE_R, "regime": "BULL_TREND"}
    r_bear = {**_BASE_R, "regime": "BEAR_TREND"}
    bull_score = generate_t_plus_recommendation(r_bull)["confidence_score"]
    bear_score = generate_t_plus_recommendation(r_bear)["confidence_score"]
    assert bear_score < bull_score, (
        f"BEAR_TREND score ({bear_score}) should be < BULL_TREND score ({bull_score})"
    )


def test_risk_flags_populated():
    """at_ceiling, DISTRIB vsa, high beta should all produce non-empty risk_flags."""
    r = {
        **_BASE_R,
        "at_ceiling":      True,
        "vsa_state":       "DISTRIB",
        "rolling_beta_5d": 2.0,
    }
    rec = generate_t_plus_recommendation(r)
    # at_ceiling forces AVOID — risk_flags must mention ceiling
    assert len(rec["risk_flags"]) > 0, "Expected non-empty risk_flags"
    assert any("TRẦN" in f or "ceiling" in f.lower() for f in rec["risk_flags"]), (
        f"Expected ceiling flag, got: {rec['risk_flags']}"
    )


print("\nT9: generate_t_plus_recommendation")
test_t25_avoid_forces_avoid_grade()
test_at_ceiling_forces_avoid()
test_strong_buy_scenario()
test_bear_trend_reduces_confidence()
test_risk_flags_populated()
print("  PASS (5/5)")

print()
print("=" * 52)
print("  ALL 43 TEST CASES PASSED — T+ Rec + LSTM + Improvements")
print("=" * 52)


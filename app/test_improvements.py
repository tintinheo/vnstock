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

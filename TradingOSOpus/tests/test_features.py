"""tests/test_features.py – Test all technical indicators."""
import numpy as np, pandas as pd
from features.technical import sma, ema, rsi, macd, bollinger_bands, atr, obv, build_all_indicators

def test_sma_basic():
    s = pd.Series([1,2,3,4,5], dtype=float)
    assert abs(sma(s, 3).iloc[-1] - 4.0) < 1e-10

def test_rsi_bounded():
    s = pd.Series(np.random.randn(100).cumsum() + 100)
    valid = rsi(s).dropna()
    assert valid.min() >= 0 and valid.max() <= 100

def test_macd_columns():
    result = macd(pd.Series(np.random.randn(50).cumsum() + 100))
    assert set(result.columns) == {"macd_line", "signal_line", "macd_histogram"}

def test_bollinger_upper_gte_lower():
    bb = bollinger_bands(pd.Series(np.random.randn(50).cumsum() + 100))
    valid = bb.dropna()
    assert (valid["bb_upper"] >= valid["bb_lower"]).all()

def test_build_all_indicators(sample_ohlcv):
    result = build_all_indicators(sample_ohlcv)
    assert result.shape[1] > 30 and "rsi" in result.columns

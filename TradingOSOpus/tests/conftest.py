"""tests/conftest.py – Shared pytest fixtures."""
import numpy as np, pandas as pd, pytest

@pytest.fixture
def sample_ohlcv():
    np.random.seed(42); n = 500
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=n)
    close = 50_000 * np.exp(np.cumsum(np.random.normal(0.0003, 0.018, n)))
    high = close * (1 + np.abs(np.random.normal(0, 0.008, n)))
    low  = close * (1 - np.abs(np.random.normal(0, 0.008, n)))
    opn  = low + (high - low) * np.random.uniform(0.2, 0.8, n)
    return pd.DataFrame({"date": dates, "open": opn, "high": high, "low": low, "close": close, "volume": np.random.lognormal(13,1,n).astype(int)})

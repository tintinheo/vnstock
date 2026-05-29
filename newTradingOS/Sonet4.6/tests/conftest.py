"""
tests/conftest.py — NewTradingOS v14.0
Shared pytest fixtures for all test modules.
Uses synthetic data — no live API calls in tests.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

# ─── Make project root importable ────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ─────────────────────────────────────────────────────────────
# DATA FIXTURES
# ─────────────────────────────────────────────────────────────
def _make_ohlcv(
    n: int = 500,
    start_price: float = 50_000,
    mu: float = 0.0005,
    sigma: float = 0.015,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data (GBM)."""
    rng    = np.random.default_rng(seed)
    rets   = rng.normal(mu, sigma, n)
    closes = start_price * np.exp(np.cumsum(rets))
    spreads = np.abs(rng.normal(0, sigma * 0.5, n)) * closes

    dates  = pd.bdate_range(end="2026-05-29", periods=n)
    df = pd.DataFrame({
        "Open":   closes - spreads * 0.4,
        "High":   closes + spreads * 0.6,
        "Low":    closes - spreads * 0.6,
        "Close":  closes,
        "Volume": np.abs(rng.normal(5_000_000, 1_500_000, n)).astype(int),
    }, index=dates)
    df.index.name = "Date"
    return df


def _make_ohlcv_bull(n: int = 500) -> pd.DataFrame:
    """Trending-up data."""
    return _make_ohlcv(n=n, mu=0.001, sigma=0.01, seed=1)


def _make_ohlcv_bear(n: int = 500) -> pd.DataFrame:
    """Trending-down data."""
    return _make_ohlcv(n=n, mu=-0.0008, sigma=0.015, seed=2)


def _make_ohlcv_small(n: int = 30) -> pd.DataFrame:
    """Very short data — for edge-case tests."""
    return _make_ohlcv(n=n, seed=99)


@pytest.fixture
def ohlcv():
    return _make_ohlcv()


@pytest.fixture
def ohlcv_bull():
    return _make_ohlcv_bull()


@pytest.fixture
def ohlcv_bear():
    return _make_ohlcv_bear()


@pytest.fixture
def ohlcv_small():
    return _make_ohlcv_small()


@pytest.fixture
def ohlcv_prices(ohlcv):
    """Just the Close series from synthetic data."""
    return ohlcv["Close"]


@pytest.fixture
def mock_data_dict(ohlcv):
    """Dict of {ticker: (df, source)} for scanner/batch tests."""
    tickers = ["VCB", "TCB", "MBB", "FPT", "HPG", "VHM"]
    return {
        t: (_make_ohlcv(seed=i), "TEST")
        for i, t in enumerate(tickers)
    }

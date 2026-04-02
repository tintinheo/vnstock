"""Technical indicator engine (SRS §2, Module 2).

Indicators: SMA/EMA/RSI/ATR/OBV/VWAP/Hurst/Z_vol/OFI/Bollinger
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ── Moving Averages ───────────────────────────────────────────────────────────

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ── RSI ───────────────────────────────────────────────────────────────────────

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, 1e-9)
    return 100 - 100 / (1 + rs)


# ── ATR ───────────────────────────────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


# ── OBV ───────────────────────────────────────────────────────────────────────

def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum()


# ── VWAP ──────────────────────────────────────────────────────────────────────

def vwap_daily(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """
    Rolling volume-weighted average price (true VWAP for daily bars).

    Uses a `window`-bar rolling sum so each day's value reflects the
    volume-weighted price over the recent window — a meaningful reference
    for detecting price manipulation vs. actual traded value.
    For the first `window-1` bars, falls back to the typical price to
    avoid NaN propagation.
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3
    rolling_tpvol = (tp * df["volume"]).rolling(window, min_periods=1).sum()
    rolling_vol   = df["volume"].rolling(window, min_periods=1).sum().replace(0, 1)
    return rolling_tpvol / rolling_vol


def vwap_intraday(df_5m: pd.DataFrame) -> pd.Series:
    """Cumulative intraday VWAP from 5-minute bars."""
    tp = (df_5m["high"] + df_5m["low"] + df_5m["close"]) / 3
    cum_vol = df_5m["volume"].cumsum()
    cum_tpvol = (tp * df_5m["volume"]).cumsum()
    return cum_tpvol / cum_vol.replace(0, 1)


# ── Bollinger Bands ───────────────────────────────────────────────────────────

def bollinger(series: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower)."""
    mid = sma(series, period)
    std = series.rolling(period).std()
    return mid + num_std * std, mid, mid - num_std * std


# ── Hurst Exponent ────────────────────────────────────────────────────────────

def hurst_exponent(series: pd.Series, max_lag: int = 40) -> float:
    """
    Approximate Hurst exponent via R/S analysis.
    Requires at least max_lag*2 samples for a statistically reliable estimate.
    Increased default max_lag from 20→40 (needs ≥80 bars) to reduce estimation
    noise, and minimum series length requirement now enforces this.
    """
    if len(series) < max_lag * 2:
        return 0.5
    lags = range(2, max_lag)
    rs_values = []
    for lag in lags:
        chunks = [series.values[i:i+lag] for i in range(0, len(series) - lag, lag)]
        if not chunks:
            continue
        rs_list = []
        for chunk in chunks:
            if len(chunk) < 2:
                continue
            mean = np.mean(chunk)
            deviation = np.cumsum(chunk - mean)
            r = deviation.max() - deviation.min()
            s = np.std(chunk, ddof=1)
            if s > 0:
                rs_list.append(r / s)
        if rs_list:
            rs_values.append(np.mean(rs_list))
    if len(rs_values) < 2:
        return 0.5
    try:
        h, _ = np.polyfit(np.log(list(lags)[:len(rs_values)]), np.log(rs_values), 1)
        return float(np.clip(h, 0.0, 1.0))
    except Exception:
        return 0.5


# ── Z-Score Volume (volume anomaly) ──────────────────────────────────────────

def z_vol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    mu = df["volume"].rolling(period).mean()
    sigma = df["volume"].rolling(period).std().replace(0, 1)
    return (df["volume"] - mu) / sigma


# ── OFI (Order Flow Imbalance proxy) ─────────────────────────────────────────

def ofi(df: pd.DataFrame) -> pd.Series:
    """
    OFI proxy from OHLCV: positive = buy pressure, negative = sell pressure.
    Based on: if close > prev_close → buy side; else sell side.
    """
    delta_close = df["close"].diff()
    buy_vol = df["volume"].where(delta_close > 0, 0)
    sell_vol = df["volume"].where(delta_close < 0, 0)
    return (buy_vol - sell_vol).cumsum()


# ── Compute All Indicators ────────────────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all indicators to OHLCV DataFrame in-place.
    Input: df with columns [date, open, high, low, close, volume]
    Output: same df with additional indicator columns.
    """
    df = df.copy()
    # Support both date-column and DatetimeIndex styles
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    else:
        # DatetimeIndex — normalise index but keep it
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

    df["SMA20"]  = sma(df["close"], 20)
    df["SMA50"]  = sma(df["close"], 50)
    df["SMA200"] = sma(df["close"], 200)
    df["EMA9"]   = ema(df["close"], 9)
    df["EMA21"]  = ema(df["close"], 21)

    df["RSI14"]  = rsi(df["close"], 14)
    df["ATR14"]  = atr(df, 14)
    df["OBV"]    = obv(df)
    df["Z_vol"]  = z_vol(df, 20)
    df["OFI"]    = ofi(df)

    bb_upper, bb_mid, bb_lower = bollinger(df["close"], 20)
    df["BB_upper"] = bb_upper
    df["BB_mid"]   = bb_mid
    df["BB_lower"] = bb_lower

    df["VWAP_daily"] = vwap_daily(df)

    # Hurst — compute on last 200 bars for reliable R/S statistics (needs ≥80)
    if len(df) >= 80:
        h = hurst_exponent(df["close"].tail(200))
        df["Hurst"] = h  # scalar broadcast
    else:
        df["Hurst"] = 0.5

    # Volume-price correlation proxy
    df["VP_corr"] = df["close"].rolling(20).corr(df["volume"])

    return df

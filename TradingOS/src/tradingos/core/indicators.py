"""Technical indicator engine (SRS §2, Module 2).

Indicators: SMA/EMA/RSI/ATR/OBV/VWAP/Hurst/Z_vol/OFI/Bollinger
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ── PSO-optimized RSI threshold cache ────────────────────────────────────────
# Loaded once at module import from config/rsi_thresholds.yaml (if present).
# Falls back to hardcoded _RSI_BASE + _RSI_SECTOR_ADJ tables silently.

_RSI_YAML_CACHE: dict[str, Any] | None = None
_RSI_YAML_LOADED = False   # sentinel — load attempted exactly once


def _load_rsi_yaml() -> dict[str, Any] | None:
    global _RSI_YAML_CACHE, _RSI_YAML_LOADED
    if _RSI_YAML_LOADED:
        return _RSI_YAML_CACHE
    _RSI_YAML_LOADED = True
    # config/rsi_thresholds.yaml is two levels up from this file:
    # indicators.py → core/ → tradingos/ → src/ → TradingOS/ → config/
    config_path = Path(__file__).resolve().parents[3] / "config" / "rsi_thresholds.yaml"
    if not config_path.exists():
        return None
    try:
        import yaml  # PyYAML — already a transitive dep
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _RSI_YAML_CACHE = data.get("rsi_thresholds") if data else None
        return _RSI_YAML_CACHE
    except Exception:
        return None


# ── Moving Averages ───────────────────────────────────────────────────────────

def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def sma_with_confidence(
    series: pd.Series,
    period: int = 200,
) -> tuple[float | None, str]:
    """
    Compute a single SMA value for the last bar with a data-quality confidence tier.

    Returns (value, confidence) where confidence is one of:
      'HIGH'   — >= period clean bars available  (full SMA)
      'MEDIUM' — 80–99% of period available      (partial SMA, labelled ~SMA{period})
      'LOW'    — 50–79% of period available      (EMA proxy)
      'NONE'   — < 50% of period available       (not computed; value=None)

    Uses EMA as a proxy when insufficient history exists so downstream code
    always has a numeric fallback rather than NaN.
    """
    clean = series.dropna()
    n = len(clean)

    if n >= period:
        value = float(clean.iloc[-period:].mean())
        return value, "HIGH"
    elif n >= int(period * 0.8):
        value = float(clean.mean())
        return value, "MEDIUM"
    elif n >= int(period * 0.5):
        # EMA is a reasonable proxy when we have at least half the required history
        value = float(clean.ewm(span=period, adjust=False).mean().iloc[-1])
        return value, "LOW"
    else:
        return None, "NONE"


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
    rs_values: list[float] = []
    valid_lags: list[int] = []   # [BUG-30 FIX] track actual lags that produced R/S values
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
            valid_lags.append(lag)   # [BUG-30 FIX] record the lag that succeeded
    if len(rs_values) < 2:
        return 0.5
    try:
        # [BUG-30 FIX] Use valid_lags (actual lag values that produced R/S estimates)
        # instead of list(lags)[:len(rs_values)].  The old approach assumed all lags
        # produced values sequentially, but some lags can be skipped when chunks are
        # too small or std=0, biasing the regression slope (Hurst estimate).
        h, _ = np.polyfit(np.log(valid_lags), np.log(rs_values), 1)
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


# ── MACD components ───────────────────────────────────────────────────────────

def macd_components(
    series: pd.Series, fast: int = 12, slow: int = 26, signal_p: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_p)
    return macd_line, signal_line, macd_line - signal_line


# ── Adaptive RSI Thresholds ───────────────────────────────────────────────────

# Base thresholds per market regime
_RSI_BASE: dict[str, dict[str, float]] = {
    "BULL_TREND":      {"overbought": 80.0, "warning": 75.0, "oversold": 45.0},
    "BEAR_TREND":      {"overbought": 65.0, "warning": 60.0, "oversold": 30.0},
    "SIDEWAYS":        {"overbought": 70.0, "warning": 65.0, "oversold": 35.0},
    "HIGH_VOLATILITY": {"overbought": 75.0, "warning": 68.0, "oversold": 30.0},
    "TRANSITIONAL":    {"overbought": 72.0, "warning": 67.0, "oversold": 32.0},
    "STEADY_BULL":     {"overbought": 80.0, "warning": 75.0, "oversold": 45.0},
    "STEADY_BEAR":     {"overbought": 65.0, "warning": 60.0, "oversold": 30.0},
}

# VN-specific sector adjustments (additive delta on overbought / oversold)
_RSI_SECTOR_ADJ: dict[str, dict[str, float]] = {
    "BANKING":        {"overbought": +3.0, "oversold": +3.0},
    "REAL_ESTATE":    {"overbought": +5.0, "oversold": -5.0},
    "STEEL_MATERIAL": {"overbought": -3.0, "oversold": -3.0},
    "SECURITIES":     {"overbought": +2.0, "oversold": +2.0},
    "INFRASTRUCTURE": {"overbought":  0.0, "oversold":  0.0},
    "GENERAL":        {"overbought":  0.0, "oversold":  0.0},
}


def get_adaptive_rsi_thresholds(
    regime: str = "SIDEWAYS",
    sector: str = "GENERAL",
) -> dict[str, float]:
    """
    Return RSI thresholds (overbought / warning / oversold) adapted to the
    current market regime and VN-specific sector characteristics.

    Priority:
      1. PSO-optimized values from config/rsi_thresholds.yaml (if present)
      2. Hardcoded _RSI_BASE + _RSI_SECTOR_ADJ tables (fallback)

    regime : one of BULL_TREND | BEAR_TREND | SIDEWAYS | HIGH_VOLATILITY |
             TRANSITIONAL | STEADY_BULL | STEADY_BEAR  (from gmo.py)
    sector : one of BANKING | REAL_ESTATE | STEEL_MATERIAL | SECURITIES |
             INFRASTRUCTURE | GENERAL

    Returns dict with keys: overbought, warning, oversold
    """
    # Try PSO-optimized thresholds first
    yaml_data = _load_rsi_yaml()
    if yaml_data is not None:
        regime_data = yaml_data.get(regime) or yaml_data.get("TRANSITIONAL", {})
        combo = regime_data.get(sector) or regime_data.get("GENERAL")
        if combo and all(k in combo for k in ("overbought", "warning", "oversold")):
            return {
                "overbought": float(combo["overbought"]),
                "warning":    float(combo["warning"]),
                "oversold":   float(combo["oversold"]),
            }

    # Fallback: hardcoded tables
    base = _RSI_BASE.get(regime, _RSI_BASE["SIDEWAYS"]).copy()
    adj  = _RSI_SECTOR_ADJ.get(sector, _RSI_SECTOR_ADJ["GENERAL"])
    base["overbought"] = min(95.0, base["overbought"] + adj["overbought"])
    base["oversold"]   = max(10.0, base["oversold"]   + adj["oversold"])
    return base


def evaluate_rsi_signal(
    rsi_value: float,
    regime: str = "SIDEWAYS",
    sector: str = "GENERAL",
) -> dict:
    """
    Classify an RSI reading relative to regime-adaptive thresholds.

    Returns dict with keys: label, action_hint, overbought, warning, oversold
      label       : OVERBOUGHT | ELEVATED | HEALTHY | NEUTRAL | OVERSOLD
      action_hint : WAIT_PULLBACK | MONITOR_CLOSELY | FAVORABLE | NO_SIGNAL | WATCH_REVERSAL
    """
    th = get_adaptive_rsi_thresholds(regime, sector)

    if rsi_value >= th["overbought"]:
        label  = "OVERBOUGHT"
        action = "WAIT_PULLBACK"
    elif rsi_value >= th["warning"]:
        label  = "ELEVATED"
        action = "MONITOR_CLOSELY"
    elif rsi_value <= th["oversold"]:
        label  = "OVERSOLD"
        action = "WATCH_REVERSAL"
    elif rsi_value >= 45.0:
        label  = "HEALTHY"
        action = "FAVORABLE"
    else:
        label  = "NEUTRAL"
        action = "NO_SIGNAL"

    return {
        "label":       label,
        "action_hint": action,
        "overbought":  th["overbought"],
        "warning":     th["warning"],
        "oversold":    th["oversold"],
    }


# ── Stochastic Oscillator ─────────────────────────────────────────────────────

def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    """Returns (%K, %D)."""
    low_min  = df["low"].rolling(k_period).min()
    high_max = df["high"].rolling(k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, 1e-9)
    return k, k.rolling(d_period).mean()


# ── Williams %R ───────────────────────────────────────────────────────────────

def williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Williams %R oscillator (−100 to 0)."""
    high_max = df["high"].rolling(period).max()
    low_min  = df["low"].rolling(period).min()
    return -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, 1e-9)


# ── CCI ───────────────────────────────────────────────────────────────────────

def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Commodity Channel Index."""
    tp = (df["high"] + df["low"] + df["close"]) / 3
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - tp.rolling(period).mean()) / (0.015 * mad.replace(0, 1e-9))


# ── ADX / DI ──────────────────────────────────────────────────────────────────

def adx_di(df: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (ADX, DI_plus, DI_minus)."""
    high, low, close = df["high"], df["low"], df["close"]
    plus_dm  = (high - high.shift()).clip(lower=0)
    minus_dm = (low.shift() - low).clip(lower=0)
    # Directional: only the dominant side contributes
    plus_dm  = plus_dm.where(plus_dm >= minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    a = 1.0 / period
    atr_s    = tr.ewm(alpha=a, adjust=False).mean()
    di_plus  = 100 * plus_dm.ewm(alpha=a, adjust=False).mean()  / atr_s.replace(0, 1e-9)
    di_minus = 100 * minus_dm.ewm(alpha=a, adjust=False).mean() / atr_s.replace(0, 1e-9)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus).replace(0, 1e-9)
    return dx.ewm(alpha=a, adjust=False).mean(), di_plus, di_minus


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

    df["SMA3"]   = sma(df["close"], 3)
    df["SMA5"]   = sma(df["close"], 5)
    df["SMA7"]   = sma(df["close"], 7)
    df["SMA10"]  = sma(df["close"], 10)
    df["SMA20"]  = sma(df["close"], 20)
    df["SMA50"]  = sma(df["close"], 50)
    df["SMA200"] = sma(df["close"], 200)
    df["EMA9"]   = ema(df["close"], 9)
    df["EMA21"]  = ema(df["close"], 21)
    df["EMA50"]  = ema(df["close"], 50)
    df["EMA200"] = ema(df["close"], 200)

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

    # ── Extended indicators (T+2.5, Gap, VWAP support) ───────────────────
    _ml, _ms, _mh = macd_components(df["close"])
    df["MACD_line"]   = _ml
    df["MACD_signal"] = _ms
    df["MACD_hist"]   = _mh

    df["STOCH_K"], df["STOCH_D"] = stochastic(df)
    df["WILLIAMS_R"]             = williams_r(df)
    df["CCI"]                    = cci(df)
    df["ADX"], df["DI_plus"], df["DI_minus"] = adx_di(df)

    return df

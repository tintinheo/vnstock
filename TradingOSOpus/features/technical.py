"""features/technical.py – 17 technical indicators with real formulas."""
import pandas as pd, numpy as np

def sma(series, n=20):
    return series.rolling(window=n, min_periods=1).mean()

def ema(series, n=20):
    return series.ewm(span=n, adjust=False).mean()

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast); ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    return pd.DataFrame({"macd_line": macd_line, "signal_line": signal_line,
                          "macd_histogram": macd_line - signal_line})

def rsi(series, n=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(n).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def bollinger_bands(series, n=20, num_std=2):
    mid = sma(series, n); std = series.rolling(n).std()
    return pd.DataFrame({"bb_middle": mid, "bb_upper": mid + num_std * std,
                          "bb_lower": mid - num_std * std, "bb_width": (2 * num_std * std) / mid})

def atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def obv(df):
    sign = np.sign(df["close"].diff()).fillna(0)
    return (sign * df["volume"]).cumsum()

def vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / df["volume"].cumsum()

def adx(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    plus_dm = (h - h.shift(1)).clip(lower=0)
    minus_dm = (l.shift(1) - l).clip(lower=0)
    atr_val = atr(df, n).replace(0, np.nan)
    plus_di = 100 * (plus_dm.rolling(n).mean() / atr_val)
    minus_di = 100 * (minus_dm.rolling(n).mean() / atr_val)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return pd.DataFrame({"adx": dx.rolling(n).mean(), "plus_di": plus_di, "minus_di": minus_di})

def stochastic(df, n=14, smooth_k=3, smooth_d=3):
    low_n = df["low"].rolling(n).min(); high_n = df["high"].rolling(n).max()
    k = 100 * (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan)
    k_smooth = k.rolling(smooth_k).mean(); d_smooth = k_smooth.rolling(smooth_d).mean()
    return pd.DataFrame({"stoch_k": k_smooth, "stoch_d": d_smooth})

def williams_r(df, n=14):
    high_n = df["high"].rolling(n).max(); low_n = df["low"].rolling(n).min()
    return -100 * (high_n - df["close"]) / (high_n - low_n).replace(0, np.nan)

def cci(df, n=20):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(n).mean()
    mad = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - sma_tp) / (0.015 * mad).replace(0, np.nan)

def mfi(df, n=14):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    rmf = tp * df["volume"]
    delta = tp.diff()
    pos_flow = rmf.where(delta > 0, 0).rolling(n).sum()
    neg_flow = rmf.where(delta <= 0, 0).rolling(n).sum()
    ratio = pos_flow / neg_flow.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))

def volume_ratio(df, n=20):
    return df["volume"] / df["volume"].rolling(n).mean().replace(0, np.nan)

def price_change(series, n=1):
    return series.pct_change(n)

def distance_from_high_low(df, n=52):
    high_n = df["high"].rolling(n * 5).max()
    low_n = df["low"].rolling(n * 5).min()
    rng = (high_n - low_n).replace(0, np.nan)
    return pd.DataFrame({"dist_high": (high_n - df["close"]) / rng,
                          "dist_low": (df["close"] - low_n) / rng})

def build_all_indicators(df):
    """Build all 30+ indicator columns onto a copy of df."""
    out = df.copy()
    for n in [5, 10, 20, 50, 100, 200]:
        out[f"sma_{n}"] = sma(out["close"], n)
        out[f"ema_{n}"] = ema(out["close"], n)
    m = macd(out["close"]); out = pd.concat([out, m], axis=1)
    out["rsi"] = rsi(out["close"])
    bb = bollinger_bands(out["close"]); out = pd.concat([out, bb], axis=1)
    out["atr"] = atr(out)
    out["obv"] = obv(out)
    out["vwap"] = vwap(out)
    adx_df = adx(out); out = pd.concat([out, adx_df], axis=1)
    stoch = stochastic(out); out = pd.concat([out, stoch], axis=1)
    out["williams_r"] = williams_r(out)
    out["cci"] = cci(out)
    out["mfi"] = mfi(out)
    out["volume_ratio"] = volume_ratio(out)
    for n in [1, 5, 10, 20]:
        out[f"return_{n}d"] = price_change(out["close"], n)
    dhl = distance_from_high_low(out); out = pd.concat([out, dhl], axis=1)
    return out
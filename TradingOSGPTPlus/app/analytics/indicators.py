import numpy as np
import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.sort_values("date").copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"].replace(0, np.nan)

    out["return_1d"] = close.pct_change()
    out["sma_10"] = close.rolling(10, min_periods=10).mean()
    out["sma_20"] = close.rolling(20, min_periods=20).mean()
    out["sma_50"] = close.rolling(50, min_periods=50).mean()
    out["ema_12"] = close.ewm(span=12, adjust=False).mean()
    out["ema_26"] = close.ewm(span=26, adjust=False).mean()
    out["macd"] = out["ema_12"] - out["ema_26"]
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["rsi_14"] = rsi(close)
    out["atr_14"] = atr(high, low, close)
    out["bb_mid"] = out["sma_20"]
    out["bb_std"] = close.rolling(20, min_periods=20).std()
    out["bb_upper"] = out["bb_mid"] + 2 * out["bb_std"]
    out["bb_lower"] = out["bb_mid"] - 2 * out["bb_std"]
    out["volume_sma_20"] = volume.rolling(20, min_periods=20).mean()
    out["volume_ratio"] = volume / out["volume_sma_20"]
    out["highest_20"] = high.rolling(20, min_periods=20).max()
    out["lowest_20"] = low.rolling(20, min_periods=20).min()
    out["highest_60"] = high.rolling(60, min_periods=60).max()
    out["lowest_60"] = low.rolling(60, min_periods=60).min()
    out["drawdown_60"] = close / close.rolling(60, min_periods=20).max() - 1
    out["volatility_20"] = out["return_1d"].rolling(20, min_periods=20).std() * np.sqrt(252)
    out["adx_14"] = adx(high, low, close)
    return out


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr = atr(high, low, close, period=1)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr.ewm(alpha=1 / period, adjust=False).mean()
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / tr.ewm(alpha=1 / period, adjust=False).mean()
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


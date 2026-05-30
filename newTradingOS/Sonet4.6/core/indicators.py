"""
core/indicators.py — NewTradingOS v14.0
Pure technical indicator functions — no side effects, fully testable.
All functions accept pd.Series or pd.DataFrame and return pd.Series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────
# TREND
# ─────────────────────────────────────────────────────────────
def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def golden_cross(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Returns +1 at golden cross, -1 at death cross, 0 otherwise."""
    prev_fast_below = fast.shift(1) < slow.shift(1)
    now_fast_above  = fast >= slow
    gc = (prev_fast_below & now_fast_above).astype(int)
    prev_fast_above = fast.shift(1) >= slow.shift(1)
    now_fast_below  = fast < slow
    dc = (prev_fast_above & now_fast_below).astype(int)
    return gc - dc


# ─────────────────────────────────────────────────────────────
# MOMENTUM
# ─────────────────────────────────────────────────────────────
def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period, min_periods=1).mean()
    loss  = (-delta.clip(upper=0)).rolling(period, min_periods=1).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series,
         fast: int = 12, slow: int = 26, signal: int = 9,
         ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    ema_f = ema(close, fast)
    ema_s = ema(close, slow)
    line  = ema_f - ema_s
    sig   = ema(line, signal)
    hist  = line - sig
    return line, sig, hist


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
               k_period: int = 14, d_period: int = 3,
               ) -> tuple[pd.Series, pd.Series]:
    """Returns (%K, %D)."""
    lowest  = low.rolling(k_period, min_periods=1).min()
    highest = high.rolling(k_period, min_periods=1).max()
    denom   = (highest - lowest).replace(0, np.nan)
    pct_k   = 100 * (close - lowest) / denom
    pct_d   = pct_k.rolling(d_period, min_periods=1).mean()
    return pct_k, pct_d


def roc(close: pd.Series, period: int = 10) -> pd.Series:
    """Rate of Change (%)."""
    return ((close - close.shift(period)) / close.shift(period)) * 100


# ─────────────────────────────────────────────────────────────
# VOLATILITY
# ─────────────────────────────────────────────────────────────
def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """Average True Range."""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def bollinger_bands(close: pd.Series,
                    period: int = 20, std_dev: float = 2.0,
                    ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower)."""
    mid   = sma(close, period)
    sigma = close.rolling(period, min_periods=1).std()
    upper = mid + std_dev * sigma
    lower = mid - std_dev * sigma
    return upper, mid, lower


def bb_percent_b(close: pd.Series,
                 period: int = 20, std_dev: float = 2.0) -> pd.Series:
    """Bollinger %B: 0=lower band, 0.5=mid, 1=upper."""
    upper, mid, lower = bollinger_bands(close, period, std_dev)
    denom = (upper - lower).replace(0, np.nan)
    return (close - lower) / denom


def keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series,
                     ema_period: int = 20, atr_period: int = 10,
                     mult: float = 2.0,
                     ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, mid, lower)."""
    mid   = ema(close, ema_period)
    atr_v = atr(high, low, close, atr_period)
    return mid + mult * atr_v, mid, mid - mult * atr_v


# ─────────────────────────────────────────────────────────────
# TREND STRENGTH
# ─────────────────────────────────────────────────────────────
def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """Average Directional Index — trend strength (0–100)."""
    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr_v      = atr(high, low, close, period)
    tr_v_rep  = tr_v.replace(0, np.nan)

    plus_di   = 100 * pd.Series(plus_dm,  index=close.index).rolling(period).mean() / tr_v_rep
    minus_di  = 100 * pd.Series(minus_dm, index=close.index).rolling(period).mean() / tr_v_rep

    dx_denom  = (plus_di + minus_di).replace(0, np.nan)
    dx        = 100 * (plus_di - minus_di).abs() / dx_denom
    return dx.rolling(period, min_periods=1).mean()


# ─────────────────────────────────────────────────────────────
# VOLUME
# ─────────────────────────────────────────────────────────────
def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume / SMA(volume, period)."""
    vol_ma = volume.rolling(period, min_periods=1).mean()
    return volume / vol_ma.replace(0, np.nan)


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff().fillna(0))
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series,
         volume: pd.Series) -> pd.Series:
    """Volume Weighted Average Price (running)."""
    typical = (high + low + close) / 3
    cum_tpv = (typical * volume).cumsum()
    cum_vol = volume.cumsum().replace(0, np.nan)
    return cum_tpv / cum_vol


def money_flow_index(high: pd.Series, low: pd.Series, close: pd.Series,
                     volume: pd.Series, period: int = 14) -> pd.Series:
    """Money Flow Index (0–100)."""
    typical   = (high + low + close) / 3
    raw_money = typical * volume
    pos_flow  = raw_money.where(typical > typical.shift(1), 0)
    neg_flow  = raw_money.where(typical < typical.shift(1), 0)
    pos_sum   = pos_flow.rolling(period, min_periods=1).sum()
    neg_sum   = neg_flow.rolling(period, min_periods=1).sum()
    mfr       = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def chaikin_money_flow(high: pd.Series, low: pd.Series, close: pd.Series,
                       volume: pd.Series, period: int = 14) -> pd.Series:
    """
    Chaikin Money Flow (-1 to +1).

    Uses close position within the day's H-L range, then smooths by volume.
    Superior to OBV for VN market because it handles overnight gaps correctly —
    a stock that gaps up but closes near its low scores negatively (distribution),
    while OBV would score it positively (just price direction).
    """
    hl_range        = (high - low).replace(0, np.nan)
    money_flow_mult = ((close - low) - (high - close)) / hl_range
    money_flow_vol  = money_flow_mult * volume
    cmf = (money_flow_vol.rolling(period, min_periods=1).sum() /
           volume.rolling(period, min_periods=1).sum().replace(0, np.nan))
    return cmf


def supertrend(high: pd.Series, low: pd.Series, close: pd.Series,
               atr_period: int = 10, multiplier: float = 3.0,
               ) -> tuple[pd.Series, pd.Series]:
    """
    SuperTrend indicator. Returns (line, direction).

    direction: +1 = bullish (price above line), -1 = bearish (price below line).
    Very popular in Southeast Asian markets. The line acts as a dynamic ATR-based
    support (bullish) or resistance (bearish) that adapts to current volatility.
    """
    atr_v = atr(high, low, close, atr_period)
    hl2   = (high + low) / 2.0
    upper = hl2 + multiplier * atr_v
    lower = hl2 - multiplier * atr_v

    n    = len(close)
    st   = np.full(n, np.nan)
    dire = np.zeros(n, dtype=float)

    for i in range(n):
        if i == 0:
            st[i]   = upper.iloc[0]
            dire[i] = -1.0
            continue

        ub        = upper.iloc[i]
        lb        = lower.iloc[i]
        prev_ub   = upper.iloc[i - 1]
        prev_lb   = lower.iloc[i - 1]
        prev_cl   = close.iloc[i - 1]
        curr_cl   = close.iloc[i]

        # Ratchet bands — never widen against the trend
        final_ub = ub if (ub < prev_ub or prev_cl > prev_ub) else prev_ub
        final_lb = lb if (lb > prev_lb or prev_cl < prev_lb) else prev_lb

        if dire[i - 1] == -1.0:          # previous bar was bearish
            if curr_cl > st[i - 1]:
                dire[i] = 1.0
                st[i]   = final_lb
            else:
                dire[i] = -1.0
                st[i]   = final_ub
        else:                             # previous bar was bullish
            if curr_cl < st[i - 1]:
                dire[i] = -1.0
                st[i]   = final_ub
            else:
                dire[i] = 1.0
                st[i]   = final_lb

    idx = close.index
    return pd.Series(st, index=idx), pd.Series(dire, index=idx)


def ceiling_floor_streak(close: pd.Series,
                         limit_pct: float = 0.07) -> pd.Series:
    """
    Consecutive ceiling / floor hit counter (VN-specific).

    Returns:
      +N  — N consecutive days the stock hit the upper price limit (trần)
      -N  — N consecutive days the stock hit the lower price limit (sàn)
       0  — no streak

    Uses 97% of limit_pct as threshold to account for small rounding differences
    in displayed vs calculated percentage.

    VN limits: HoSE ±7%, HNX ±10%, UPCoM ±15%.
    Default 7% covers HoSE (the primary market for VN30/VN100).
    """
    pct_chg   = close.pct_change()
    threshold = limit_pct * 0.97
    n         = len(close)
    streak    = np.zeros(n, dtype=float)

    for i in range(1, n):
        ch = pct_chg.iloc[i]
        if pd.isna(ch):
            streak[i] = 0.0
        elif ch >= threshold:
            streak[i] = max(streak[i - 1] + 1.0, 1.0)
        elif ch <= -threshold:
            streak[i] = min(streak[i - 1] - 1.0, -1.0)
        else:
            streak[i] = 0.0

    return pd.Series(streak, index=close.index)


# ─────────────────────────────────────────────────────────────
# MARKET MANIPULATION DETECTION
# ─────────────────────────────────────────────────────────────
def manipulation_score(
    close: pd.Series,
    volume: pd.Series,
    vol_ma_period: int = 20,
    price_move_days: int = 5,
    pump_vol_threshold: float = 3.0,
    pump_price_threshold: float = 0.15,
) -> pd.Series:
    """
    Score 0–100: higher = more likely manipulated.

    Components:
    - Volume spike (vs SMA20)
    - Price move (5-day %)
    - Small market cap proxy (high volatility)
    """
    vol_ma     = volume.rolling(vol_ma_period, min_periods=1).mean()
    v_ratio    = volume / vol_ma.replace(0, np.nan)
    price_move = close.pct_change(price_move_days).abs()

    v_score = (v_ratio / pump_vol_threshold).clip(0, 1) * 50
    p_score = (price_move / pump_price_threshold).clip(0, 1) * 50
    return (v_score + p_score).clip(0, 100)


# ─────────────────────────────────────────────────────────────
# HELPER — COMPUTE ALL INDICATORS AT ONCE
# ─────────────────────────────────────────────────────────────
def compute_all(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """
    Compute all indicators specified in a TIMEFRAME_CONFIG entry.
    Mutates df in-place, returns it.
    """
    close  = df["Close"]
    high   = df.get("High",   close)
    low    = df.get("Low",    close)
    volume = df.get("Volume", pd.Series(0, index=close.index))

    # Trend
    df["SMA_fast"]  = sma(close, cfg["sma_fast"])
    df["SMA_slow"]  = sma(close, cfg["sma_slow"])
    df["EMA_fast"]  = ema(close, cfg["ema_fast"])
    df["EMA_slow"]  = ema(close, cfg["ema_slow"])

    # Momentum
    df["RSI"]       = rsi(close, cfg["rsi_period"])
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = macd(
        close, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"])
    df["ROC"]       = roc(close, cfg["sma_fast"])

    # Volatility
    df["ATR"]       = atr(high, low, close, cfg["atr_period"])
    df["BB_upper"], df["BB_mid"], df["BB_lower"] = bollinger_bands(
        close, cfg["bb_period"], cfg["bb_std"])

    # Volume — compute vol_ma once, reuse for Vol_ratio (avoids recomputing in scoring)
    _vol_ma         = volume.rolling(cfg["volume_ma"], min_periods=1).mean()
    df["Vol_MA"]    = _vol_ma
    df["Vol_ratio"] = volume / _vol_ma.replace(0, np.nan)
    df["OBV"]       = obv(close, volume)
    df["MFI"]       = money_flow_index(high, low, close, volume)

    # Trend strength
    df["ADX"]         = adx(high, low, close, cfg["adx_period"])

    # Manipulation
    df["Manip_score"] = manipulation_score(close, volume)

    # BB %B — inline using already-stored BB columns (avoids double bollinger_bands call)
    _bb_denom     = (df["BB_upper"] - df["BB_lower"]).replace(0, np.nan)
    df["BB_pctB"] = (close - df["BB_lower"]) / _bb_denom

    # ── VN-SPECIFIC INDICATORS ──────────────────────────────
    # Chaikin Money Flow: gap-adjusted smart-money inflow indicator
    df["CMF"] = chaikin_money_flow(high, low, close, volume, cfg["volume_ma"])

    # SuperTrend: ATR-based dynamic support/resistance, popular in SEA markets
    df["ST"], df["ST_dir"] = supertrend(high, low, close, cfg["atr_period"])

    # Ceiling/Floor streak: consecutive price-limit hits (VN ±7% HoSE rule)
    df["Streak"] = ceiling_floor_streak(close)

    return df

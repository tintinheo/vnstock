"""
core/indicators.py — NewTradingOS v14.0
Pure technical indicator functions — no side effects, fully testable.
All functions accept pd.Series or pd.DataFrame and return pd.Series.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional


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
    """RSI using Wilder's original EWM smoothing (alpha=1/period).

    Wilder (1978) specified exponential smoothing, not SMA, for both the
    average gain and average loss. Using EWM ensures RSI responds correctly
    to momentum shifts — important for VN stocks that can sustain extreme
    RSI levels (>80 in strong runs) due to the daily price-limit mechanism.
    """
    delta = close.diff()
    gain  = _wilder_smooth(delta.clip(lower=0), period)
    loss  = _wilder_smooth((-delta).clip(lower=0), period)
    rs    = gain / loss.replace(0, np.nan)
    rsi_v = 100 - (100 / (1 + rs))
    # When loss==0 and gain>0: RS → ∞ → RSI should be 100 (not NaN)
    rsi_v = rsi_v.where(~((loss == 0) & (gain > 0)), 100.0)
    return rsi_v


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
    """Average True Range using Wilder's EWM smoothing (alpha=1/period).

    Wilder (1978) used his own exponential smoothing method for ATR as well
    as ADX. Using EWM (vs plain SMA) makes ATR more responsive to sudden
    volatility expansions — critical for VN market where T-floor/ceiling
    streaks can compress then violently expand volatility overnight.
    Consistent with the ADX implementation which also uses Wilder EWM.
    """
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return _wilder_smooth(tr, period)


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
def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing method — EWM with alpha = 1/period (not SMA).

    Used by ADX to replicate J. Welles Wilder's original specification.
    Produces a more responsive indicator than plain SMA rolling.
    """
    return series.ewm(alpha=1.0 / period, adjust=False, min_periods=1).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """Average Directional Index using proper Wilder smoothing (0–100).

    Fixed from original SMA implementation to use Wilder EWM smoothing
    (alpha = 1/period) on True Range, +DM, and -DM independently, and
    a final Wilder smooth of DX — matching the original Wilder (1978) spec.
    This produces a more responsive signal especially on VN breakout stocks.
    """
    # Raw True Range (computed fresh — not the pre-averaged ATR)
    tr_raw = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=close.index,
    )
    minus_dm  = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=close.index,
    )

    # Wilder-smooth TR, +DM, -DM independently
    atr_w    = _wilder_smooth(tr_raw, period)
    plus_w   = _wilder_smooth(plus_dm, period)
    minus_w  = _wilder_smooth(minus_dm, period)

    safe_atr = atr_w.replace(0, np.nan)
    plus_di  = 100 * plus_w  / safe_atr
    minus_di = 100 * minus_w / safe_atr

    dx_denom = (plus_di + minus_di).replace(0, np.nan)
    dx       = 100 * (plus_di - minus_di).abs() / dx_denom
    return _wilder_smooth(dx.fillna(0), period)


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
    atc_vol_ratio: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Score 0–100: higher = more likely manipulated.

    Components:
    - Volume spike vs SMA20 (0–50 pts)
    - 5-day price move (0–50 pts)
    - ATC volume concentration (optional bonus up to +25 pts, capped at 100)

    Parameters
    ----------
    atc_vol_ratio : optional pd.Series
        Ratio of ATC (closing auction) volume to total day volume, range [0, 1].
        Requires intraday data. When provided, high ATC concentration (>40%)
        adds up to 25 bonus points to the manipulation score.
        See config.ATC_RATIO_THRESH. Pass None (default) when only daily OHLCV
        is available — existing behaviour is fully preserved.
    """
    from config import ATC_RATIO_THRESH  # 0.40

    vol_ma     = volume.rolling(vol_ma_period, min_periods=1).mean()
    v_ratio    = volume / vol_ma.replace(0, np.nan)
    price_move = close.pct_change(price_move_days).abs()

    v_score = (v_ratio / pump_vol_threshold).clip(0, 1) * 50
    p_score = (price_move / pump_price_threshold).clip(0, 1) * 50
    base    = (v_score + p_score).clip(0, 100)

    if atc_vol_ratio is not None:
        # Align to close index in case caller passes a raw Series
        atc_s     = atc_vol_ratio.reindex(close.index).fillna(0.0)
        atc_bonus = (atc_s / ATC_RATIO_THRESH).clip(0, 1) * 25
        return (base + atc_bonus).clip(0, 100)

    return base


# ─────────────────────────────────────────────────────────────
# HELPER — COMPUTE ALL INDICATORS AT ONCE
# ─────────────────────────────────────────────────────────────
def compute_all(df: pd.DataFrame, cfg: dict, exchange: str = "HOSE") -> pd.DataFrame:
    """
    Compute all indicators specified in a TIMEFRAME_CONFIG entry.
    Mutates df in-place, returns it.

    Parameters
    ----------
    exchange : str
        The exchange the ticker belongs to: 'HOSE' (±7%), 'HNX' (±10%), or
        'UPCOM' (±15%). Used to set the correct price-limit threshold for the
        ceiling/floor streak indicator. Defaults to 'HOSE'.
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

    # Ceiling/Floor streak: exchange-specific price limits
    #   HOSE ±7%, HNX ±10%, UPCoM ±15%  (fixed: was always 7% before)
    from config import EXCHANGE_PRICE_LIMIT
    limit_pct = EXCHANGE_PRICE_LIMIT.get(exchange.upper(), 0.07)
    df["Streak"] = ceiling_floor_streak(close, limit_pct=limit_pct)

    # Money Flow Index: period now follows cfg["volume_ma"] to match CMF (VN-03 fix).
    # Previously hardcoded to period=14 for all timeframes — inconsistent with CMF
    # which already used cfg["volume_ma"] (5 for 1W, 20 for 1M/3M/5M).
    # MFI-5 for 1W is more responsive to short-term volume surges (correct for 5-session hold);
    # MFI-20 for longer TFs is stabler and avoids noise-driven false signals.
    df["MFI"] = money_flow_index(high, low, close, volume, cfg["volume_ma"])

    return df

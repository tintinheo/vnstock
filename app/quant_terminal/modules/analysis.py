"""
Technical analysis — indicators, signal scoring, support/resistance, VaR.
All input DataFrames have prices in thousands-VND.
"""
import logging
from typing import Union

import numpy as np
import pandas as pd

_log = logging.getLogger("analysis")


# ── INDICATORS ────────────────────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicator columns to a copy of df.
    Expected input columns: open, high, low, close, volume.
    All prices in thousands-VND.
    """
    if df is None or df.empty or "close" not in df.columns:
        return df

    c = pd.to_numeric(df["close"], errors="coerce").ffill()

    # ── EMAs ─────────────────────────────────────────────────────────────────
    df["ema20"]  = c.ewm(span=20, adjust=False).mean()
    df["ema50"]  = c.ewm(span=50, adjust=False).mean()
    df["ema200"] = c.ewm(span=200, adjust=False).mean()

    # ── RSI (14) ──────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs        = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    # ── MACD (12, 26, 9) ──────────────────────────────────────────────────────
    ema12             = c.ewm(span=12, adjust=False).mean()
    ema26             = c.ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd"] - df["macd_signal"]

    # ── ATR (14) ──────────────────────────────────────────────────────────────
    if "high" in df.columns and "low" in df.columns:
        h = pd.to_numeric(df["high"], errors="coerce")
        l = pd.to_numeric(df["low"],  errors="coerce")
        prev_c  = c.shift(1)
        tr      = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        df["atr14"] = tr.ewm(com=13, adjust=False).mean()
    else:
        df["atr14"] = c.rolling(14).std().fillna(c.std())

    # ── Bollinger (20, 2σ) ────────────────────────────────────────────────────
    bb_mid       = c.rolling(20).mean()
    bb_std       = c.rolling(20).std()
    df["bb_mid"] = bb_mid
    df["bb_up"]  = bb_mid + 2 * bb_std
    df["bb_low"] = bb_mid - 2 * bb_std

    # ── Volume MA ─────────────────────────────────────────────────────────────
    if "volume" in df.columns:
        vol = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["vol_ma20"] = vol.rolling(20).mean()

    return df


# ── SIGNAL SCORE ─────────────────────────────────────────────────────────────

def compute_signal_score(hist: pd.DataFrame) -> dict:
    """
    Compute a composite signal score (-100 to +100) from multiple indicators.
    Returns dict: {score, label, color, rsi, macd_hist, signals}.
    signals: {indicator_name: (label_str, direction_int, detail_str)}
    """
    EMPTY = {"score": 0, "label": "N/A", "color": "#6B7280",
             "rsi": 50.0, "macd_hist": 0.0, "signals": {}}
    if hist is None or hist.empty or len(hist) < 26:
        return EMPTY

    df = compute_indicators(hist.copy())
    if df.empty:
        return EMPTY

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    close = float(last.get("close", 0))
    if close <= 0:
        return EMPTY

    signals = {}
    score   = 0

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi = float(last.get("rsi", 50))
    if rsi < 30:
        signals["RSI"] = ("Oversold", +1, f"RSI {rsi:.1f} < 30")
        score += 20
    elif rsi < 45:
        signals["RSI"] = ("Yếu", 0, f"RSI {rsi:.1f}")
        score -= 5
    elif rsi > 70:
        signals["RSI"] = ("Overbought", -1, f"RSI {rsi:.1f} > 70")
        score -= 15
    elif rsi > 55:
        signals["RSI"] = ("Mạnh", +1, f"RSI {rsi:.1f}")
        score += 10

    # ── MACD ──────────────────────────────────────────────────────────────────
    macd_h  = float(last.get("macd_hist", 0))
    macd_ph = float(prev.get("macd_hist", 0))
    macd_line = float(last.get("macd", 0))
    if macd_h > 0 and macd_h > macd_ph:
        signals["MACD"] = ("Bullish tăng tốc", +1, f"Hist={macd_h:+.3f}")
        score += 20
    elif macd_h > 0:
        signals["MACD"] = ("Bullish", +1, f"Hist={macd_h:+.3f}")
        score += 10
    elif macd_h < 0 and macd_h < macd_ph:
        signals["MACD"] = ("Bearish tăng tốc", -1, f"Hist={macd_h:+.3f}")
        score -= 20
    elif macd_h < 0:
        signals["MACD"] = ("Bearish", -1, f"Hist={macd_h:+.3f}")
        score -= 10

    # ── EMA Trend ─────────────────────────────────────────────────────────────
    ema20  = float(last.get("ema20",  close))
    ema50  = float(last.get("ema50",  close))
    ema200 = float(last.get("ema200", close))

    if close > ema20 > ema50 > ema200:
        signals["EMA Trend"] = ("Strong Uptrend", +1, "C>E20>E50>E200")
        score += 25
    elif close > ema20 > ema50:
        signals["EMA Trend"] = ("Uptrend", +1, "C>E20>E50")
        score += 15
    elif close > ema20:
        signals["EMA Trend"] = ("Above EMA20", +1, "C>E20")
        score += 8
    elif close < ema20 < ema50 < ema200:
        signals["EMA Trend"] = ("Strong Downtrend", -1, "C<E20<E50<E200")
        score -= 25
    elif close < ema20 < ema50:
        signals["EMA Trend"] = ("Downtrend", -1, "C<E20<E50")
        score -= 15
    else:
        signals["EMA Trend"] = ("Giằng co", 0, "mixed")

    # ── Bollinger ─────────────────────────────────────────────────────────────
    bb_up  = float(last.get("bb_up",  close * 1.05))
    bb_low = float(last.get("bb_low", close * 0.95))
    bb_mid = float(last.get("bb_mid", close))
    if close > bb_up:
        signals["Bollinger"] = ("Breakout trên", -1, f"Trên BB trên {bb_up:.2f}")
        score -= 10
    elif close < bb_low:
        signals["Bollinger"] = ("Breakout dưới", +1, f"Dưới BB dưới {bb_low:.2f}")
        score += 10
    elif close > bb_mid:
        signals["Bollinger"] = ("Trên giữa", +1, "Nửa trên BB")
        score += 5
    else:
        signals["Bollinger"] = ("Dưới giữa", -1, "Nửa dưới BB")
        score -= 5

    # ── Volume confirmation ───────────────────────────────────────────────────
    if "volume" in df.columns and "vol_ma20" in df.columns:
        vol    = float(last.get("volume",  0))
        vol_ma = float(last.get("vol_ma20", 1))
        if vol_ma > 0 and vol > vol_ma * 1.5 and macd_h > 0:
            signals["Volume"] = ("Tăng mạnh + KL cao", +1, f"Vol={vol/1e6:.1f}M")
            score += 10
        elif vol_ma > 0 and vol > vol_ma * 1.5 and macd_h < 0:
            signals["Volume"] = ("Giảm + KL cao", -1, f"Vol={vol/1e6:.1f}M")
            score -= 10

    # ── Normalize ─────────────────────────────────────────────────────────────
    score = max(-100, min(100, score))

    if score >= 40:
        label = "Tích lũy"; color = "#16A34A"
    elif score >= 20:
        label = "Bullish";   color = "#86EFAC"
    elif score >= -10:
        label = "Trung tính"; color = "#6B7280"
    elif score >= -30:
        label = "Yếu";       color = "#FCA5A5"
    else:
        label = "Bearish";   color = "#DC2626"

    return {
        "score":     int(score),
        "label":     label,
        "color":     color,
        "rsi":       rsi,
        "macd_hist": macd_h,
        "signals":   signals,
    }


# ── BETA ─────────────────────────────────────────────────────────────────────

def compute_beta(
    stock_hist: pd.DataFrame,
    index_hist: pd.DataFrame,
    symbol: str = "",
) -> Union[float, str]:
    """Compute beta of stock vs index using 120-session rolling window."""
    if symbol.upper() == "VNINDEX":
        return "—"
    if stock_hist is None or index_hist is None:
        return "N/A"
    if stock_hist.empty or index_hist.empty:
        return "N/A"
    if "close" not in stock_hist.columns or "close" not in index_hist.columns:
        return "N/A"

    try:
        s_ret = pd.to_numeric(stock_hist["close"], errors="coerce").pct_change().dropna()
        i_ret = pd.to_numeric(index_hist["close"], errors="coerce").pct_change().dropna()
        # Align on index
        common = s_ret.index.intersection(i_ret.index)
        if len(common) < 20:
            return "N/A"
        s_ret = s_ret.loc[common].tail(120)
        i_ret = i_ret.loc[common].tail(120)
        cov  = float(s_ret.cov(i_ret))
        var  = float(i_ret.var())
        if var == 0:
            return "N/A"
        return round(cov / var, 2)
    except Exception as e:
        _log.warning("compute_beta: %s", e)
        return "N/A"


# ── SUPPORT / RESISTANCE ──────────────────────────────────────────────────────

def find_support_resistance(
    hist: pd.DataFrame, window: int = 10, n_levels: int = 3
) -> dict:
    """
    Detect price support and resistance levels using pivot highs/lows.
    Returns {resistance: [prices ...], support: [prices ...]} in thousands-VND.
    """
    empty = {"resistance": [], "support": []}
    if hist is None or hist.empty or len(hist) < window * 2:
        return empty
    if "high" not in hist.columns or "low" not in hist.columns:
        return empty

    h = pd.to_numeric(hist["high"],  errors="coerce").fillna(0).values
    l = pd.to_numeric(hist["low"],   errors="coerce").fillna(0).values
    c = pd.to_numeric(hist["close"], errors="coerce").fillna(0).values
    n = len(c)
    current_price = float(c[-1]) if n > 0 else 0

    resistances = []
    supports    = []

    for i in range(window, n - window):
        # Pivot high
        if h[i] == max(h[i - window:i + window + 1]):
            if h[i] > current_price:
                resistances.append(round(float(h[i]), 2))
        # Pivot low
        if l[i] == min(l[i - window:i + window + 1]):
            if l[i] < current_price:
                supports.append(round(float(l[i]), 2))

    def _deduplicate(levels: list, tol: float = 0.015) -> list:
        """Merge levels within tol % of each other."""
        if not levels:
            return []
        levels = sorted(set(levels))
        merged = [levels[0]]
        for lvl in levels[1:]:
            if abs(lvl - merged[-1]) / (merged[-1] + 1e-9) > tol:
                merged.append(lvl)
        return merged

    resistances = sorted(_deduplicate(resistances))[:n_levels]
    supports    = sorted(_deduplicate(supports), reverse=True)[:n_levels]

    return {"resistance": resistances, "support": supports}


# ── VALUE AT RISK ─────────────────────────────────────────────────────────────

def compute_var(returns: pd.Series, confidence: float = 0.95) -> dict:
    """
    Historical VaR and CVaR at given confidence level.
    Input: daily returns series (fractional).
    Returns: {var_pct, cvar_pct} — both negative numbers (losses).
    """
    empty = {"var_pct": 0.0, "cvar_pct": 0.0}
    if returns is None or len(returns) < 20:
        return empty
    try:
        clean = pd.to_numeric(returns, errors="coerce").dropna()
        if len(clean) < 20:
            return empty
        q        = 1 - confidence
        var_pct  = float(clean.quantile(q) * 100)
        cvar_pct = float(clean[clean <= clean.quantile(q)].mean() * 100)
        return {
            "var_pct":  round(var_pct,  3),
            "cvar_pct": round(cvar_pct, 3),
        }
    except Exception as e:
        _log.warning("compute_var: %s", e)
        return empty

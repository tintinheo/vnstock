"""
Technical analysis engine — computes RSI, MACD, Bollinger, EMA, volume signals
and aggregates them into a composite signal score.
"""
import pandas as pd
import numpy as np

try:
    import pandas_ta as ta
    HAS_TA = True
except ImportError:
    HAS_TA = False


# ─── INDICATOR COMPUTATION ───────────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given OHLCV DataFrame, add indicator columns.
    Returns augmented DataFrame.
    """
    if df is None or df.empty or len(df) < 30:
        return df

    df = df.copy()
    c = df["close"]
    v = df.get("volume", pd.Series(1, index=df.index))

    # ── RSI ──────────────────────────────────────────────────────────────────
    if HAS_TA:
        rsi = ta.rsi(c, length=14)
    else:
        delta = c.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
    df["rsi"] = rsi

    # ── MACD ─────────────────────────────────────────────────────────────────
    if HAS_TA:
        macd_df = ta.macd(c, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            # pandas_ta order: MACD_12_26_9, MACDh_12_26_9 (hist), MACDs_12_26_9 (signal)
            df["macd"]        = macd_df.iloc[:, 0]
            df["macd_hist"]   = macd_df.iloc[:, 1]
            df["macd_signal"] = macd_df.iloc[:, 2]
    else:
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df["macd"]        = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"]   = df["macd"] - df["macd_signal"]

    # ── BOLLINGER BANDS ──────────────────────────────────────────────────────
    if HAS_TA:
        bb = ta.bbands(c, length=20, std=2)
        if bb is not None and not bb.empty:
            # pandas_ta order: BBL_20_2.0 (lower), BBM_20_2.0 (mid), BBU_20_2.0 (upper)
            df["bb_lower"] = bb.iloc[:, 0]
            df["bb_mid"]   = bb.iloc[:, 1]
            df["bb_upper"] = bb.iloc[:, 2]
    else:
        mid = c.rolling(20).mean()
        std = c.rolling(20).std()
        df["bb_upper"] = mid + 2 * std
        df["bb_mid"]   = mid
        df["bb_lower"] = mid - 2 * std

    # ── EMA ──────────────────────────────────────────────────────────────────
    for span in [20, 50, 200]:
        df[f"ema{span}"] = c.ewm(span=span, adjust=False).mean()

    # ── VOLUME ───────────────────────────────────────────────────────────────
    df["vol_sma20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_sma20"].replace(0, np.nan)

    # ── ATR ──────────────────────────────────────────────────────────────────
    h = df.get("high", c)
    l = df.get("low",  c)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    return df


# ─── SIGNAL SCORING ──────────────────────────────────────────────────────────

def compute_signal_score(df: pd.DataFrame) -> dict:
    """
    Aggregate technical signals into a composite score.
    Returns {score, label, signals, details}
    score: -100 (strong sell) to +100 (strong buy)
    """
    if df is None or df.empty or len(df) < 30:
        return _empty_signal()

    df = compute_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    signals = {}
    scores  = {}

    # ── RSI ──────────────────────────────────────────────────────────────────
    rsi = last.get("rsi", 50)
    if not pd.isna(rsi):
        if rsi > 70:
            signals["RSI"] = ("Bán — quá mua", -1, f"RSI {rsi:.1f} > 70")
            scores["RSI"] = -20
        elif rsi < 30:
            signals["RSI"] = ("Mua — quá bán", +1, f"RSI {rsi:.1f} < 30")
            scores["RSI"] = +20
        elif rsi > 55:
            signals["RSI"] = ("Tích cực", +0.5, f"RSI {rsi:.1f}")
            scores["RSI"] = +10
        elif rsi < 45:
            signals["RSI"] = ("Tiêu cực", -0.5, f"RSI {rsi:.1f}")
            scores["RSI"] = -10
        else:
            signals["RSI"] = ("Trung tính", 0, f"RSI {rsi:.1f}")
            scores["RSI"] = 0

    # ── MACD ─────────────────────────────────────────────────────────────────
    macd      = last.get("macd", 0)
    macd_sig  = last.get("macd_signal", 0)
    macd_hist = last.get("macd_hist", 0)
    prev_hist = prev.get("macd_hist", 0)
    if not any(pd.isna(x) for x in [macd, macd_sig, macd_hist]):
        if macd > macd_sig and macd_hist > 0 and macd_hist > prev_hist:
            signals["MACD"] = ("Mua mạnh", +1, f"MACD crossover dương, hist tăng {macd_hist:.0f}")
            scores["MACD"] = +25
        elif macd > macd_sig:
            signals["MACD"] = ("Tích cực", +0.5, f"MACD > Signal, hist {macd_hist:.0f}")
            scores["MACD"] = +10
        elif macd < macd_sig and macd_hist < 0 and macd_hist < prev_hist:
            signals["MACD"] = ("Bán mạnh", -1, f"MACD crossover âm, hist {macd_hist:.0f}")
            scores["MACD"] = -25
        else:
            signals["MACD"] = ("Tiêu cực", -0.5, "MACD < Signal")
            scores["MACD"] = -10

    # ── BOLLINGER ─────────────────────────────────────────────────────────────
    close   = last.get("close", 0)
    bb_up   = last.get("bb_upper", np.nan)
    bb_low  = last.get("bb_lower", np.nan)
    bb_mid  = last.get("bb_mid", np.nan)
    if not any(pd.isna(x) for x in [bb_up, bb_low, bb_mid, close]) and bb_up != bb_low:
        bb_pct = (close - bb_low) / (bb_up - bb_low)
        if bb_pct > 0.95:
            signals["Bollinger"] = ("Bán — chạm dải trên", -1, f"BB%: {bb_pct:.0%}")
            scores["Bollinger"] = -15
        elif bb_pct < 0.05:
            signals["Bollinger"] = ("Mua — chạm dải dưới", +1, f"BB%: {bb_pct:.0%}")
            scores["Bollinger"] = +15
        elif bb_pct > 0.6:
            signals["Bollinger"] = ("Tích cực", +0.5, f"BB%: {bb_pct:.0%}")
            scores["Bollinger"] = +5
        else:
            signals["Bollinger"] = ("Tiêu cực", -0.5, f"BB%: {bb_pct:.0%}")
            scores["Bollinger"] = -5

    # ── EMA TREND ─────────────────────────────────────────────────────────────
    ema20  = last.get("ema20", np.nan)
    ema50  = last.get("ema50", np.nan)
    ema200 = last.get("ema200", np.nan)
    if not any(pd.isna(x) for x in [close, ema20, ema50]):
        if close > ema20 > ema50:
            signals["EMA Trend"] = ("Uptrend rõ ràng", +1, "Giá > EMA20 > EMA50")
            scores["EMA Trend"] = +20
        elif close < ema20 < ema50:
            signals["EMA Trend"] = ("Downtrend rõ ràng", -1, "Giá < EMA20 < EMA50")
            scores["EMA Trend"] = -20
        elif close > ema20:
            signals["EMA Trend"] = ("Tích cực ngắn hạn", +0.5, "Giá > EMA20")
            scores["EMA Trend"] = +10
        else:
            signals["EMA Trend"] = ("Tiêu cực ngắn hạn", -0.5, "Giá < EMA20")
            scores["EMA Trend"] = -10

    # ── VOLUME ────────────────────────────────────────────────────────────────
    vol_ratio = last.get("vol_ratio", 1)
    if not pd.isna(vol_ratio):
        if vol_ratio > 2.0 and close > prev.get("close", close):
            signals["Volume"] = ("Mua — volume đột biến tích cực", +1, f"Vol ratio: {vol_ratio:.1f}x")
            scores["Volume"] = +15
        elif vol_ratio > 2.0 and close < prev.get("close", close):
            signals["Volume"] = ("Bán — volume đột biến tiêu cực", -1, f"Vol ratio: {vol_ratio:.1f}x")
            scores["Volume"] = -15
        elif vol_ratio > 1.3:
            signals["Volume"] = ("Volume cao hơn TB", +0.3, f"Vol ratio: {vol_ratio:.1f}x")
            scores["Volume"] = +5
        else:
            signals["Volume"] = ("Volume thấp — thiếu conviction", 0, f"Vol ratio: {vol_ratio:.1f}x")
            scores["Volume"] = 0

    total_score = sum(scores.values())
    total_score = max(-100, min(100, total_score))

    if total_score >= 50:
        label, color = "Mua mạnh", "#16A34A"
    elif total_score >= 20:
        label, color = "Mua", "#4ADE80"
    elif total_score >= -20:
        label, color = "Trung tính", "#F59E0B"
    elif total_score >= -50:
        label, color = "Bán", "#F87171"
    else:
        label, color = "Bán mạnh", "#DC2626"

    return {
        "score": total_score,
        "label": label,
        "color": color,
        "signals": signals,
        "scores":  scores,
        "rsi":     rsi if not pd.isna(rsi) else 50,
        "macd":    macd,
        "macd_hist": macd_hist,
        "atr14":   last.get("atr14", 0),
        "close":   close,
        "ema20":   ema20,
        "ema50":   ema50,
        "ema200":  ema200,
    }


def _empty_signal() -> dict:
    return {
        "score": 0, "label": "Không đủ dữ liệu", "color": "#6B7280",
        "signals": {}, "scores": {}, "rsi": 50, "macd": 0,
        "macd_hist": 0, "atr14": 0, "close": 0,
        "ema20": None, "ema50": None, "ema200": None,
    }


# ─── BETA CALCULATION ────────────────────────────────────────────────────────

def compute_beta(stock_df: pd.DataFrame, index_df: pd.DataFrame, window: int = 60) -> float:
    """Compute rolling beta of stock vs index over last `window` days."""
    if stock_df is None or index_df is None or len(stock_df) < 10:
        return 1.0
    try:
        s_ret = stock_df["close"].pct_change().dropna()
        i_ret = index_df["close"].pct_change().dropna()
        common = s_ret.index.intersection(i_ret.index)
        if len(common) < 10:
            return 1.0
        s = s_ret.loc[common].tail(window)
        i = i_ret.loc[common].tail(window)
        cov = np.cov(s, i)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 1.0
        return round(float(beta), 2)
    except:
        return 1.0


# ─── SUPPORT / RESISTANCE ────────────────────────────────────────────────────

def find_support_resistance(df: pd.DataFrame, n_levels: int = 3) -> dict:
    """Find key support and resistance levels from recent price action."""
    if df is None or df.empty or len(df) < 20:
        return {"support": [], "resistance": []}
    c = df["close"].values
    h = df.get("high", df["close"]).values
    l = df.get("low",  df["close"]).values

    # Simple: rolling local min/max
    from scipy.signal import argrelextrema
    try:
        order = max(3, len(c) // 20)
        resist_idx = argrelextrema(h, np.greater, order=order)[0]
        support_idx = argrelextrema(l, np.less, order=order)[0]
        resistance = sorted(set(h[resist_idx].round(2)), reverse=True)[:n_levels]
        support    = sorted(set(l[support_idx].round(2)), reverse=True)[:n_levels]
    except Exception:
        # Fallback: percentile-based
        resistance = [np.percentile(h, 75), np.percentile(h, 85), np.percentile(h, 95)]
        support    = [np.percentile(l, 25), np.percentile(l, 15), np.percentile(l, 5)]
        resistance = [round(r, 2) for r in resistance]
        support    = [round(s, 2) for s in support]

    return {"support": support, "resistance": resistance}


def compute_var(returns: pd.Series, confidence: float = 0.95) -> dict:
    """
    Historical Value-at-Risk (VaR) and Conditional VaR (CVaR / Expected Shortfall).

    Parameters
    ----------
    returns    : pd.Series of daily simple returns (decimal, e.g. 0.015 for +1.5%)
    confidence : VaR confidence level  (default 0.95 → 95th percentile tail)

    Returns
    -------
    dict: {var_pct, cvar_pct}  — both as %, negative = loss
          e.g. {"var_pct": -2.1, "cvar_pct": -3.4}
    """
    r = returns.dropna()
    if len(r) < 20:
        return {"var_pct": 0.0, "cvar_pct": 0.0}
    q    = float(np.percentile(r, (1 - confidence) * 100))   # e.g. -0.021
    tail = r[r <= q]
    cvar = float(tail.mean()) if len(tail) > 0 else q
    return {"var_pct": round(q * 100, 2), "cvar_pct": round(cvar * 100, 2)}

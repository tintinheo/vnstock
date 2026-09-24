#!/usr/bin/env python3
"""
forecast_engine.py  —  PROMETHEE II MCDA, Monte Carlo, Multi-horizon Voting,
                        LSTM inference (with sklearn fallback)
═══════════════════════════════════════════════════════════════════════════════
Standalone — no Streamlit import.  Imported by Quant_Profiler_ui.py.

Exposed API:
    promethee_ii_ranking(ticker_results)  → pd.DataFrame
    monte_carlo_projection(price, atr, days, sims)  → dict
    multi_horizon_forecast(r, df)  → dict
    prepare_lstm_features(df)  → np.ndarray | None
"""

import os
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

_DIR        = Path(__file__).parent
_MODELS_DIR = _DIR / "data" / "models"
_MODELS_DIR.mkdir(parents=True, exist_ok=True)   # auto-create on first import

# In-memory LSTM model cache — avoids reloading .keras from disk on every Streamlit rerun.
# Capped at _LSTM_CACHE_MAX entries (LRU via OrderedDict) to prevent unbounded growth.
# Each Keras model ≈ 1–5 MB; 15 entries ≈ 15–75 MB ceiling.
from collections import OrderedDict as _OrderedDict
_LSTM_CACHE_MAX: int = 15
_LSTM_CACHE: _OrderedDict = _OrderedDict()


def _lstm_cache_put(key: str, model) -> None:
    """Insert into LRU cache, evicting the oldest entry when at capacity."""
    _LSTM_CACHE.pop(key, None)         # remove if already present (refresh position)
    _LSTM_CACHE[key] = model
    while len(_LSTM_CACHE) > _LSTM_CACHE_MAX:
        evicted, _ = _LSTM_CACHE.popitem(last=False)
        import logging as _lg
        _lg.getLogger(__name__).debug("LSTM cache evicted: %s (capacity=%d)", evicted, _LSTM_CACHE_MAX)

# ─── Optional heavy deps with graceful fallback ───────────────────────────────
try:
    import keras                         # type: ignore
    _KERAS_AVAILABLE = True
    _KERAS_BACKEND   = "keras"
except ImportError:
    try:
        from tensorflow import keras     # type: ignore  # TF 2.x bundled Keras
        _KERAS_AVAILABLE = True
        _KERAS_BACKEND   = "tf.keras"
    except ImportError:
        _KERAS_AVAILABLE = False
        _KERAS_BACKEND   = None

try:
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  A. PROMETHEE II  (Multiple Criteria Decision Analysis)
# ═══════════════════════════════════════════════════════════════════════════════

# Criteria weights — academic consensus for emerging markets (normalised to sum to 1)
_CRITERIA = {
    "score":      {"weight": 0.50, "direction": "max"},   # composite bull score
    "liquidity":  {"weight": 0.30, "direction": "max"},   # vol/MA20 turnover ratio
    "volatility": {"weight": 0.20, "direction": "min"},   # ATR% — lower = better
}

# Linear preference thresholds (p = strict preference, q = indifference)
_THRESHOLDS = {
    "score":      {"p": 15.0, "q": 3.0},
    "liquidity":  {"p": 1.0,  "q": 0.1},
    "volatility": {"p": 3.0,  "q": 0.3},
}


def _extract_criteria_values(r: dict) -> dict:
    """Extract raw criterion values from an analyse_ticker result dict."""
    price = r.get("price") or 1.0
    atr   = r.get("atr")   or 0.0
    kl    = r.get("kl_ratio") or 0.0
    # score: bull_pct already on 0-100 scale
    score = r.get("bull_pct") or 50.0
    # liquidity: vol/MA20 ratio; cap at 5× to prevent outlier dominance
    liq   = min(float(kl), 5.0)
    # volatility: ATR as % of price — daily average range
    vol   = float(atr) / float(price) * 100 if price > 0 else 0.0
    return {"score": score, "liquidity": liq, "volatility": vol}


def _linear_preference(diff: float, p: float, q: float) -> float:
    """
    Linear preference function: P(a,b) given criterion diff (a - b).
    P = 0 if diff ≤ q, P = 1 if diff ≥ p, linear in between.
    """
    if diff <= q:
        return 0.0
    if diff >= p:
        return 1.0
    return (diff - q) / (p - q)


def promethee_ii_ranking(ticker_results: list[dict]) -> pd.DataFrame:
    """
    PROMETHEE II ranking of tickers.

    Algorithm:
    1. For each criterion, extract values for all tickers.
    2. For each ordered pair (a, b), compute pairwise preference P(a,b) using
       linear preference function.
    3. Aggregate into unicriterion preference π(a,b) = Σ w_k × P_k(a,b).
    4. Compute positive flow φ⁺(a) and negative flow φ⁻(a).
    5. Net flow φ(a) = φ⁺(a) − φ⁻(a) → rank descending.

    Returns DataFrame[ticker, phi_pos, phi_neg, net_flow, rank,
                       score_val, liq_val, vol_val, signal].
    """
    if not ticker_results:
        return pd.DataFrame()

    # Filter out error results
    valid = [r for r in ticker_results if "error" not in r and r.get("price")]
    if len(valid) < 2:
        # Single ticker — assign rank=1
        if valid:
            r = valid[0]
            cv = _extract_criteria_values(r)
            return pd.DataFrame([{
                "ticker":    r["ticker"],
                "phi_pos":   0.0,
                "phi_neg":   0.0,
                "net_flow":  0.0,
                "rank":      1,
                "score_val": cv["score"],
                "liq_val":   cv["liquidity"],
                "vol_val":   cv["volatility"],
                "signal":    r.get("signal", ""),
            }])
        return pd.DataFrame()

    n       = len(valid)
    tickers = [r["ticker"] for r in valid]
    crit_vals = {r["ticker"]: _extract_criteria_values(r) for r in valid}

    # Build π matrix (n × n)
    pi = np.zeros((n, n))
    for i, ti in enumerate(tickers):
        for j, tj in enumerate(tickers):
            if i == j:
                continue
            agg = 0.0
            for cname, cfg in _CRITERIA.items():
                vi = crit_vals[ti][cname]
                vj = crit_vals[tj][cname]
                diff = (vi - vj) if cfg["direction"] == "max" else (vj - vi)
                th   = _THRESHOLDS[cname]
                pref = _linear_preference(diff, th["p"], th["q"])
                agg += cfg["weight"] * pref
            pi[i, j] = agg

    phi_pos = pi.sum(axis=1) / (n - 1)
    phi_neg = pi.sum(axis=0) / (n - 1)
    net     = phi_pos - phi_neg

    ranks = np.argsort(-net) + 1   # descending rank
    order = np.argsort(-net)

    rows = []
    for idx in order:
        ti = tickers[idx]
        cv = crit_vals[ti]
        r  = valid[idx]
        rows.append({
            "ticker":    ti,
            "phi_pos":   round(float(phi_pos[idx]), 4),
            "phi_neg":   round(float(phi_neg[idx]), 4),
            "net_flow":  round(float(net[idx]),     4),
            "rank":      int(np.where(order == idx)[0][0]) + 1,
            "score_val": round(cv["score"],      1),
            "liq_val":   round(cv["liquidity"],  2),
            "vol_val":   round(cv["volatility"], 2),
            "signal":    r.get("signal", ""),
            "price":     r.get("price", 0),
            "pct_change":r.get("pct_change", 0),
            "rr1":       r.get("rr1"),
            "atr":       r.get("atr"),
        })

    df = pd.DataFrame(rows)
    df["rank"] = df["net_flow"].rank(ascending=False, method="min").astype(int)
    return df.sort_values("rank").reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  B. MONTE CARLO RISK PROJECTION
# ═══════════════════════════════════════════════════════════════════════════════

def monte_carlo_projection(
    current_price: float,
    atr: float,
    days: int = 5,
    sims: int = 10_000,
    seed: Optional[int] = 42,
) -> dict:
    """
    Generate `sims` probabilistic price paths for the next `days` trading days.

    Volatility proxy: daily_vol = atr / current_price  (ATR% as daily σ).
    Model: Geometric Brownian Motion (daily log-return ~ N(0, vol)).

    Returns:
        expected_price  — mean final price across all paths
        p5_downside     — 5th percentile final price (95% confidence floor)
        p95_upside      — 95th percentile final price (upside target)
        max_drawdown_p5 — worst-case drawdown at p5 (as negative %)
        all_paths       — (sims × days) array for fan-chart rendering (optional, 200 sampled paths)
        percentile_paths — dict {p5: array, p50: array, p95: array} over days
    """
    if current_price <= 0 or atr is None or atr <= 0:
        return {
            "expected_price": current_price,
            "p5_downside":    current_price,
            "p95_upside":     current_price,
            "max_drawdown_p5": 0.0,
            "percentile_paths": {},
        }

    rng     = np.random.default_rng(seed)
    vol     = float(atr) / float(current_price)    # daily volatility proxy
    # Drift term: 0 (neutral assumption; no directional bias in risk model)
    drift   = 0.0

    # Simulate returns: (sims × days)
    daily_ret = rng.normal(drift, vol, (sims, days))
    # Cumulative price paths via cumprod
    cum = np.cumprod(1 + daily_ret, axis=1)
    price_paths = current_price * cum     # (sims × days)

    final_prices = price_paths[:, -1]
    expected     = float(np.mean(final_prices))
    p5           = float(np.percentile(final_prices, 5))
    p95          = float(np.percentile(final_prices, 95))
    mdd_p5       = float((p5 - current_price) / current_price * 100)

    # Per-day percentile paths for fan chart
    pct_paths = {
        "p5":  [float(np.percentile(price_paths[:, d], 5))  for d in range(days)],
        "p50": [float(np.percentile(price_paths[:, d], 50)) for d in range(days)],
        "p95": [float(np.percentile(price_paths[:, d], 95)) for d in range(days)],
    }

    return {
        "expected_price":   round(expected, 0),
        "p5_downside":      round(p5,       0),
        "p95_upside":       round(p95,      0),
        "max_drawdown_p5":  round(mdd_p5,   2),
        "percentile_paths": pct_paths,
        "vol_used":         round(vol * 100, 3),
        "days":             days,
        "sims":             sims,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  C. MULTI-HORIZON VOTING FORECAST
# ═══════════════════════════════════════════════════════════════════════════════

def _calc_monthly_pivots(df: pd.DataFrame) -> dict:
    """Monthly pivot points from last 20 bars (proxy for ~1 month of data)."""
    if df is None or len(df) < 20:
        return {}
    last20 = df.iloc[-20:]
    H  = float(last20["High"].max())
    L  = float(last20["Low"].min())
    C  = float(df["Close"].iloc[-1])
    PP = (H + L + C) / 3
    R1 = 2 * PP - L
    S1 = 2 * PP - H
    R2 = PP + (H - L)
    S2 = PP - (H - L)
    return {"pp": round(PP, 0), "r1": round(R1, 0), "r2": round(R2, 0),
            "s1": round(S1, 0), "s2": round(S2, 0)}


def _calc_fibonacci(df: pd.DataFrame, lookback: int = 20) -> dict:
    """Fibonacci 50% / 61.8% retracement levels from last `lookback` bars."""
    if df is None or len(df) < lookback:
        return {}
    window = df.iloc[-lookback:]
    swing_high = float(window["High"].max())
    swing_low  = float(window["Low"].min())
    rng = swing_high - swing_low
    if rng <= 0:
        return {}
    return {
        "swing_high": round(swing_high, 0),
        "swing_low":  round(swing_low,  0),
        "fib_500":    round(swing_high - 0.500 * rng, 0),
        "fib_618":    round(swing_high - 0.618 * rng, 0),
        "fib_382":    round(swing_high - 0.382 * rng, 0),
    }


def _short_term_signals(r: dict, df: pd.DataFrame) -> tuple[int, int, list[str]]:
    """
    Short-term (3-5 day) voting signals.
    Returns (bull_votes, total_votes, reasons).
    RSI dynamic threshold: buy if RSI < 35 AND price > SMA5.
    """
    bull = 0
    total = 0
    reasons = []

    price = r.get("price") or 0
    rsi   = r.get("rsi")
    macd  = r.get("macd")
    macd_sig = r.get("macd_signal")
    atr   = r.get("atr") or 0

    # Compute SMA5 from df if available
    sma5 = None
    if df is not None and "Close" in df.columns and len(df) >= 5:
        sma5 = float(df["Close"].rolling(5).mean().iloc[-1])

    # Vote 1: RSI < 35 + price above SMA5
    total += 1
    if rsi is not None and rsi < 35 and sma5 and price > sma5:
        bull += 1
        reasons.append(f"RSI={rsi:.0f}<35 & Giá>SMA5 → MUA")
    elif rsi is not None and rsi > 65:
        reasons.append(f"RSI={rsi:.0f}>65 → QUÁ MUA")
    else:
        reasons.append(f"RSI={rsi:.0f} → Trung lập" if rsi else "RSI: N/A")

    # Vote 2: MACD crossover
    total += 1
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            bull += 1
            reasons.append("MACD > Signal → Động lượng dương")
        else:
            reasons.append("MACD < Signal → Động lượng âm")
    else:
        reasons.append("MACD: N/A")

    # Vote 3: Price > SMA20 (short-term trend)
    total += 1
    sma20 = r.get("sma20")
    if sma20 and price > sma20:
        bull += 1
        reasons.append(f"Giá>{sma20:,.0f} (SMA20) → Ngắn hạn tăng")
    elif sma20:
        reasons.append(f"Giá<{sma20:,.0f} (SMA20) → Ngắn hạn giảm")
    else:
        reasons.append("SMA20: N/A")

    # Vote 4: ATR-momentum (Stoch)
    total += 1
    stoch = r.get("stoch_k")
    if stoch is not None:
        if stoch < 20:
            bull += 1
            reasons.append(f"Stoch={stoch:.0f}<20 → Quá bán")
        elif stoch > 80:
            reasons.append(f"Stoch={stoch:.0f}>80 → Quá mua")
        else:
            reasons.append(f"Stoch={stoch:.0f} → Trung lập")
    else:
        reasons.append("Stoch: N/A")

    return bull, total, reasons


def _mid_term_signals(r: dict, pivots: dict, fib: dict) -> tuple[int, int, list[str]]:
    """Mid-term (monthly) voting signals using pivot + Fibonacci."""
    bull = 0
    total = 0
    reasons = []
    price = r.get("price") or 0

    # Vote 1: Above monthly S1 (support zone)
    total += 1
    s1 = pivots.get("s1")
    if s1 and price > s1:
        bull += 1
        reasons.append(f"Giá>{s1:,.0f} (S1 tháng) → Trên vùng hỗ trợ")
    elif s1:
        reasons.append(f"Giá<{s1:,.0f} (S1 tháng) → Dưới vùng hỗ trợ")
    else:
        reasons.append("Pivot S1: N/A")

    # Vote 2: Fibonacci 61.8% support
    total += 1
    fib618 = fib.get("fib_618")
    if fib618 and price > fib618:
        bull += 1
        reasons.append(f"Giá>{fib618:,.0f} (Fib 61.8%) → Hỗ trợ Fibonacci")
    elif fib618:
        reasons.append(f"Giá<{fib618:,.0f} (Fib 61.8%) → Dưới Fib 61.8%")
    else:
        reasons.append("Fibonacci: N/A")

    # Vote 3: Above SMA50
    total += 1
    sma50 = r.get("sma50")
    if sma50 and price > sma50:
        bull += 1
        reasons.append(f"Giá>SMA50 ({sma50:,.0f}) → Trung hạn tăng")
    elif sma50:
        reasons.append(f"Giá<SMA50 ({sma50:,.0f}) → Trung hạn giảm")

    return bull, total, reasons


def _long_term_signals(r: dict) -> tuple[int, int, list[str]]:
    """Long-term (3-6 month) factor scores."""
    bull = 0
    total = 0
    reasons = []

    # Vote 1: Above SMA200 (primary trend)
    total += 1
    sma200 = r.get("sma200")
    price  = r.get("price") or 0
    if sma200 and price > sma200:
        bull += 1
        d200 = (price - sma200) / sma200 * 100
        reasons.append(f"Giá>SMA200 (+{d200:.1f}%) → Dài hạn tăng")
    elif sma200:
        d200 = (price - sma200) / sma200 * 100
        reasons.append(f"Giá<SMA200 ({d200:.1f}%) → Dài hạn giảm")
    else:
        reasons.append("SMA200: N/A")

    # Vote 2: SMA200 slope (regime)
    total += 1
    slope = r.get("sma200_slope") or 0
    if slope > 0.3:
        bull += 1
        reasons.append(f"SMA200 slope +{slope:.2f}%/20d → Xu hướng tăng bền vững")
    elif slope < -0.3:
        reasons.append(f"SMA200 slope {slope:.2f}%/20d → Xu hướng giảm")
    else:
        reasons.append(f"SMA200 slope {slope:+.2f}%/20d → Đi ngang")

    # Vote 3: ADX trending + DI direction
    total += 1
    adx = r.get("adx") or 0
    pdi = r.get("pdi") or 0
    ndi = r.get("ndi") or 0
    if adx > 25 and pdi > ndi:
        bull += 1
        reasons.append(f"ADX={adx:.0f}>25 & +DI({pdi:.0f})>-DI({ndi:.0f}) → Xu hướng tăng mạnh")
    elif adx > 25:
        reasons.append(f"ADX={adx:.0f}>25 & -DI({ndi:.0f})>+DI({pdi:.0f}) → Xu hướng giảm mạnh")
    else:
        reasons.append(f"ADX={adx:.0f}<25 → Đi ngang dài hạn")

    # Vote 4: OBV confirmation
    total += 1
    obv    = r.get("obv")
    obv_ma = r.get("obv_ma")
    if obv and obv_ma and obv > obv_ma:
        bull += 1
        reasons.append("OBV>OBV_MA20 → Tích lũy thể hiệu dài hạn")
    elif obv and obv_ma:
        reasons.append("OBV<OBV_MA20 → Phân phối dài hạn")
    else:
        reasons.append("OBV: N/A")

    return bull, total, reasons


def _vote_to_label(bull: int, total: int) -> tuple[str, float]:
    """Convert vote count to (label_vi, confidence_pct)."""
    if total == 0:
        return "Không đủ dữ liệu", 0.0
    conf = bull / total * 100
    if conf >= 75:
        return "MUA 🟢", conf
    if conf >= 55:
        return "THEO DÕI–TĂNG 🔵", conf
    if conf <= 25:
        return "BÁN / TRÁNH 🔴", conf
    if conf <= 45:
        return "THEO DÕI–GIẢM 🟠", conf
    return "TRUNG LẬP ⚪", conf


# ─── LSTM / Ridge ─────────────────────────────────────────────────────────────

_SEQ_LEN   = 20    # lookback window for LSTM
_FEATURES  = 5     # close_scaled, vol_scaled, rsi_norm, macd_hist_norm, atr_pct


def prepare_lstm_features(df: pd.DataFrame) -> Optional[np.ndarray]:
    """
    Build a (1, SEQ_LEN, FEATURES) input array for LSTM inference.
    Features per bar: [close_ret%, vol_ratio, rsi/100, macd_hist_norm, atr_pct]
    Returns None if insufficient data or columns missing.
    """
    needed = ("Close", "Volume", "RSI", "MACD_Hist", "ATR", "Vol_MA20")
    if df is None or len(df) < _SEQ_LEN + 1:
        return None
    for col in needed:
        if col not in df.columns:
            return None
    try:
        tail = df.iloc[-(_SEQ_LEN + 1):]
        close   = tail["Close"].values.astype(float)
        vol     = tail["Volume"].values.astype(float)
        rsi     = tail["RSI"].values.astype(float)
        mh      = tail["MACD_Hist"].values.astype(float)
        atr_arr = tail["ATR"].values.astype(float)
        vol_ma  = tail["Vol_MA20"].values.astype(float)

        # Returns (% change relative to prior bar)
        close_ret  = np.diff(close) / (close[:-1] + 1e-9) * 100      # (SEQ_LEN,)
        vol_ratio  = vol[1:] / (vol_ma[1:] + 1e-9)                   # (SEQ_LEN,)
        rsi_n      = np.clip(rsi[1:] / 100.0, 0, 1)                  # (SEQ_LEN,)
        mh_n       = np.clip(mh[1:] / (close[1:] + 1e-9) * 100, -5, 5)
        atr_pct    = atr_arr[1:] / (close[1:] + 1e-9) * 100          # (SEQ_LEN,)

        seq = np.stack([close_ret, vol_ratio, rsi_n, mh_n, atr_pct], axis=1)  # (SEQ_LEN, 5)
        seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
        return seq.reshape(1, _SEQ_LEN, _FEATURES)
    except Exception:
        return None


import logging as _log_mod
_fe_log = _log_mod.getLogger("quant_profiler")


def _build_lstm_training_data(
    df: pd.DataFrame,
) -> "tuple[Optional[np.ndarray], Optional[np.ndarray]]":
    """
    Build (X, y) training arrays from a full OHLCV+indicator DataFrame.

    X: (n_samples, SEQ_LEN, FEATURES)  float32 — sliding windows
    y: (n_samples,)                    float32 — 5-day forward return in %

    Returns (None, None) if df is None, too short, missing columns, or < 20 samples.
    """
    needed = ("Close", "Volume", "RSI", "MACD_Hist", "ATR", "Vol_MA20")
    if df is None or len(df) < _SEQ_LEN + 10:
        return None, None
    for col in needed:
        if col not in df.columns:
            return None, None
    try:
        close   = df["Close"].values.astype(float)
        vol     = df["Volume"].values.astype(float)
        rsi     = df["RSI"].values.astype(float)
        mh      = df["MACD_Hist"].values.astype(float)
        atr_arr = df["ATR"].values.astype(float)
        vol_ma  = df["Vol_MA20"].values.astype(float)

        # Per-bar features — same definition as prepare_lstm_features()
        close_ret = np.concatenate([[0.0], np.diff(close) / (close[:-1] + 1e-9) * 100])
        vol_ratio = vol / (vol_ma + 1e-9)
        rsi_n     = np.clip(rsi / 100.0, 0, 1)
        mh_n      = np.clip(mh / (close + 1e-9) * 100, -5, 5)
        atr_pct   = atr_arr / (close + 1e-9) * 100

        feat_mat = np.stack([close_ret, vol_ratio, rsi_n, mh_n, atr_pct], axis=1)  # (N, 5)
        feat_mat = np.nan_to_num(feat_mat, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

        n = len(close)
        X_list, y_list = [], []
        for i in range(_SEQ_LEN, n - 5):
            X_list.append(feat_mat[i - _SEQ_LEN : i])
            fwd = (close[i + 5] - close[i]) / (close[i] + 1e-9) * 100
            y_list.append(float(fwd))

        if len(X_list) < 20:
            return None, None

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)
    except Exception:
        return None, None


def train_lstm_model(
    ticker:            str,
    df:                pd.DataFrame,
    force:             bool  = False,
    epochs:            int   = 60,
    patience:          int   = 8,
    progress_callback = None,
) -> "Optional[object]":
    """
    Train (or retrain) an LSTM model for *ticker* and persist to data/models/.

    Args:
        force:             re-train even if a saved model already exists.
        epochs:            max training epochs (EarlyStopping usually cuts short).
        patience:          EarlyStopping patience.
        progress_callback: callable(epoch: int, total: int, logs: dict) called each
                           epoch — use this for live UI progress bars.

    Returns trained Keras model, or None if Keras unavailable / training failed.
    """
    if not _KERAS_AVAILABLE:
        return None

    cache_key  = ticker.upper()
    model_path = _MODELS_DIR / f"{cache_key}_lstm.keras"

    # Return cached in-memory model when not forcing a retrain
    if not force and cache_key in _LSTM_CACHE:
        return _LSTM_CACHE[cache_key]

    X, y = _build_lstm_training_data(df)
    if X is None or len(X) < 20:
        _fe_log.warning("train_lstm_model %s: insufficient training data (%s rows)", ticker,
                        len(df) if df is not None else 0)
        return None

    _fe_log.info("train_lstm_model %s: %d samples — starting", ticker, len(X))
    try:
        # Build inline progress callback class if caller wants epoch-level updates
        callbacks_list = []

        es = keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=0,
        )
        callbacks_list.append(es)

        if progress_callback is not None:
            _req_epochs = epochs   # capture for closure

            class _PBar(keras.callbacks.Callback):   # type: ignore[misc]
                def on_epoch_end(self, epoch, logs=None):   # noqa: ANN001
                    progress_callback(epoch + 1, _req_epochs, logs or {})

            callbacks_list.append(_PBar())

        # Time-ordered 85/15 split — no shuffle, preserves temporal structure
        split   = max(10, int(len(X) * 0.85))
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        model = keras.Sequential([
            keras.layers.Input(shape=(_SEQ_LEN, _FEATURES)),
            keras.layers.LSTM(64, return_sequences=True),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(32),
            keras.layers.Dropout(0.1),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(1),
        ])
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss="mse",
            metrics=["mae"],
        )

        history = model.fit(
            X_tr, y_tr,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=max(8, min(32, len(X_tr) // 4)),
            callbacks=callbacks_list,
            verbose=0,
        )

        stopped_epoch = len(history.history["loss"])
        val_mae       = history.history.get("val_mae", [None])[-1]
        _fe_log.info(
            "train_lstm_model %s: done in %d epochs, val_mae=%.4f",
            ticker, stopped_epoch, val_mae or 0,
        )

        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))
        _lstm_cache_put(cache_key, model)

        # Attach training metadata as lightweight attributes for UI display
        model._train_epochs   = stopped_epoch   # type: ignore[attr-defined]
        model._train_val_mae  = val_mae          # type: ignore[attr-defined]
        model._train_samples  = len(X_tr)        # type: ignore[attr-defined]
        return model

    except Exception as exc:
        _fe_log.warning("train_lstm_model %s failed: %s", ticker, exc)
        return None


def _lstm_inference(
    ticker:   str,
    features: np.ndarray,
    df:       pd.DataFrame = None,   # provided for silent auto-train on first use
) -> Optional[float]:
    """
    Predict 5-day forward return (%) using the saved LSTM model for *ticker*.

    Resolution order:
      1. In-memory _LSTM_CACHE (fastest — no disk I/O)
      2. Load from data/models/{TICKER}_lstm.keras
      3. Auto-train on first use if df is provided (silent, no progress callback)

    Falls through to None if Keras is unavailable or no model can be obtained.
    """
    if not _KERAS_AVAILABLE:
        return None

    cache_key  = ticker.upper()
    model_path = _MODELS_DIR / f"{cache_key}_lstm.keras"

    # 1. In-memory cache
    model = _LSTM_CACHE.get(cache_key)

    # 2. Load from disk
    if model is None and model_path.exists():
        try:
            model = keras.models.load_model(str(model_path), compile=False)
            _lstm_cache_put(cache_key, model)
        except Exception:
            pass

    # 3. Silent auto-train on first analysis
    if model is None and df is not None:
        model = train_lstm_model(ticker, df)

    if model is None:
        return None
    try:
        pred = float(model.predict(features, verbose=0)[0][0])
        return round(pred, 2)
    except Exception:
        return None


def _ridge_inference(df: pd.DataFrame) -> Optional[float]:
    """Fallback: Ridge regression on 5-day forward returns + RSI/MACD features."""
    if not _SKLEARN_AVAILABLE or df is None or len(df) < 30:
        return None
    try:
        close = df["Close"].values.astype(float)
        rsi   = df["RSI"].values.astype(float) if "RSI" in df.columns else np.full(len(close), 50.0)
        mh    = df["MACD_Hist"].values.astype(float) if "MACD_Hist" in df.columns else np.zeros(len(close))

        # Labels: 5-day forward return
        fwd   = np.full(len(close), np.nan)
        for i in range(len(close) - 5):
            if close[i] > 0:
                fwd[i] = (close[i + 5] - close[i]) / close[i] * 100
        valid = ~np.isnan(fwd) & ~np.isnan(rsi) & ~np.isnan(mh)
        if valid.sum() < 20:
            return None

        X = np.column_stack([rsi[valid], mh[valid]])
        y = fwd[valid]
        scaler = StandardScaler()
        X_s    = scaler.fit_transform(X)
        model  = Ridge(alpha=10.0)
        model.fit(X_s[:-5], y[:-5])   # hold last 5 out-of-sample

        # Predict from latest feature
        latest = np.array([[rsi[-1], mh[-1]]])
        latest_s = scaler.transform(latest)
        pred = float(model.predict(latest_s)[0])
        return round(pred, 2)
    except Exception:
        return None


def multi_horizon_forecast(
    r: dict,
    df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Multi-horizon voting classifier. Returns:
        {
            short_vote, short_conf, short_reasons,
            mid_vote, mid_conf, mid_reasons,   mid_pivots, mid_fib,
            long_vote, long_conf, long_reasons,
            overall_vote, overall_conf,
            lstm_pred_pct,   # predicted 5-day return %, or None
            lstm_source,     # 'lstm' | 'ridge' | 'n/a'
        }
    """
    # Reuse pivot/fib already computed in analyse_ticker result dict (avoids recomputation)
    _pp = r.get("monthly_pp")
    if _pp:
        pivots = {
            "pp": _pp,
            "r1": r.get("monthly_r1", 0), "r2": r.get("monthly_r2", 0),
            "s1": r.get("monthly_s1", 0), "s2": r.get("monthly_s2", 0),
        }
    else:
        pivots = _calc_monthly_pivots(df) if df is not None else {}
    _fib618 = r.get("fib_618")
    if _fib618:
        fib = {
            "fib_618": _fib618,
            "fib_500": r.get("fib_500", 0), "fib_382": r.get("fib_382", 0),
            "swing_high": r.get("fib_swing_high", 0), "swing_low": r.get("fib_swing_low", 0),
        }
    else:
        fib = _calc_fibonacci(df) if df is not None else {}

    # Short-term
    sb, st, sr = _short_term_signals(r, df)
    short_vote, short_conf = _vote_to_label(sb, st)

    # Mid-term
    mb, mt, mr = _mid_term_signals(r, pivots, fib)
    mid_vote, mid_conf  = _vote_to_label(mb, mt)

    # Long-term
    lb, lt, lr = _long_term_signals(r)
    long_vote, long_conf = _vote_to_label(lb, lt)

    # Overall voting (weighted: short=2, mid=1, long=2)
    ov_bull  = sb * 2 + mb * 1 + lb * 2
    ov_total = st * 2 + mt * 1 + lt * 2
    overall_vote, overall_conf = _vote_to_label(ov_bull, ov_total)

    # LSTM / Ridge prediction
    features   = prepare_lstm_features(df) if df is not None else None
    lstm_pred  = None
    lstm_src   = "n/a"
    if features is not None:
        ticker     = r.get("ticker", "")
        lstm_pred  = _lstm_inference(ticker, features, df)   # pass df for silent auto-train
        if lstm_pred is not None:
            lstm_src = "lstm"
        else:
            lstm_pred = _ridge_inference(df)
            lstm_src  = "ridge" if lstm_pred is not None else "n/a"

    return {
        "short_vote":    short_vote,
        "short_conf":    round(short_conf,  1),
        "short_reasons": sr,
        "mid_vote":      mid_vote,
        "mid_conf":      round(mid_conf,    1),
        "mid_reasons":   mr,
        "mid_pivots":    pivots,
        "mid_fib":       fib,
        "long_vote":     long_vote,
        "long_conf":     round(long_conf,   1),
        "long_reasons":  lr,
        "overall_vote":  overall_vote,
        "overall_conf":  round(overall_conf, 1),
        "lstm_pred_pct": lstm_pred,
        "lstm_source":   lstm_src,
    }


# ─── Smoke test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick Monte Carlo check
    mc = monte_carlo_projection(20_000, 500, days=5, sims=10_000)
    assert mc["p5_downside"] < mc["expected_price"] < mc["p95_upside"], "MC order check failed"
    print("Monte Carlo OK:", mc)

    # PROMETHEE with mock data
    mock_results = [
        {"ticker": "A", "price": 20000, "bull_pct": 70, "kl_ratio": 2.0, "atr": 400, "signal": "MUA"},
        {"ticker": "B", "price": 15000, "bull_pct": 45, "kl_ratio": 0.8, "atr": 600, "signal": "TRUNG LẬP"},
        {"ticker": "C", "price": 30000, "bull_pct": 60, "kl_ratio": 1.5, "atr": 300, "signal": "THEO DÕI–TĂNG"},
    ]
    rank_df = promethee_ii_ranking(mock_results)
    print("\nPROMETHEE II ranking:\n", rank_df[["ticker", "net_flow", "rank"]])
    assert rank_df.iloc[0]["ticker"] == "A", "A should rank #1 (highest bull + liquidity)"
    print("\nAll smoke tests passed.")

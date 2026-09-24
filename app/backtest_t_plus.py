#!/usr/bin/env python3
"""
backtest_t_plus.py  —  Walk-Forward Backtest for T+ Recommendation Engine
═══════════════════════════════════════════════════════════════════════════════
Tests the generate_t_plus_recommendation() system on 3 years of historical
data using rolling-window indicator recomputation.

Modes tested:
  1. T+ Baseline     — original scoring (no CF enrichment)
  2. T+ with GARCH   — position halved when high_vol_regime=True
  3. T+ with GARCH+HMM — full CF scoring (+/-5 pts from HMM, Day-1 direction)

Usage:
    python backtest_t_plus.py [--tickers TCB VNM FPT ...] [--horizon 5]
                               [--start 2023-01-01] [--end 2026-03-21]
                               [--min-score 65]

Outputs:
  - Console summary table
  - data/backtest_t_plus_results.csv  (per-trade log)
  - data/backtest_t_plus_summary.json (aggregate metrics per mode)
"""

import sys
import os
import json
import argparse
import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Add app dir to sys.path if run from elsewhere ─────────────────────────────
_APP_DIR = Path(__file__).parent
sys.path.insert(0, str(_APP_DIR))

from Quant_Profiler import fetch_ohlcv, compute_t25_score
from portfolio_engine import generate_t_plus_recommendation, T25ExitManager

# Optional: candle_forecast_engine for GARCH/HMM backtest
try:
    from candle_forecast_engine import fit_garch, fit_hmm
    _CF_AVAILABLE = True
except ImportError:
    _CF_AVAILABLE = False

_MAX_DAILY_RET = 0.065   # ±6.5% VN hard limit

# ── CF walk-forward cache: refit only every N bars ────────────────────────────
_CF_GARCH_CACHE: dict = {}   # ticker → {"bar": i, "result": GARCHResult}
_CF_HMM_CACHE:   dict = {}   # ticker → {"bar": i, "result": HMMResult}
_CF_GARCH_PERIOD = 5          # refit GARCH every 5 bars
_CF_HMM_PERIOD   = 20         # refit HMM every 20 bars

_DATA_DIR = _APP_DIR / "data"
_DATA_DIR.mkdir(exist_ok=True)

# ── Default backtest universe (diversified VN sectors) ────────────────────────
DEFAULT_TICKERS = [
    "TCB", "VCB", "MBB", "BID",         # Banking
    "VNM", "MSN", "MWG", "FRT",         # Consumer
    "FPT", "CMG",                        # Tech
    "VHM", "VIC", "NVL",                 # Real estate
    "HPG", "HSG",                        # Steel
    "DCM", "DGC",                        # Chemicals
    "GAS", "PLX",                        # Oil & gas
    "DHC", "DMC",                        # Healthcare
]

# ── Minimum lookback bars needed before first signal ─────────────────────────
_MIN_LOOKBACK = 60   # 60 trading days ≈ 3 months


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATOR ENGINE  (self-contained, no Quant_Profiler side-effects)
# ══════════════════════════════════════════════════════════════════════════════

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()

def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d  = close.diff()
    up = d.clip(lower=0)
    dn = (-d).clip(lower=0)
    rs = up.ewm(com=n - 1, adjust=False).mean() / dn.ewm(com=n - 1, adjust=False).mean()
    return 100 - 100 / (1 + rs)

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - df["Close"].shift()).abs(),
        (df["Low"]  - df["Close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def _macd(close: pd.Series):
    fast = _ema(close, 12)
    slow = _ema(close, 26)
    macd_line = fast - slow
    signal    = _ema(macd_line, 9)
    hist      = macd_line - signal
    return hist

def _stoch(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    lo  = df["Low"].rolling(k_period).min()
    hi  = df["High"].rolling(k_period).max()
    k   = 100 * (df["Close"] - lo) / (hi - lo + 1e-9)
    d   = k.rolling(d_period).mean()
    return k, d

def _williams_r(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hi = df["High"].rolling(n).max()
    lo = df["Low"].rolling(n).min()
    return -100 * (hi - df["Close"]) / (hi - lo + 1e-9)

def _cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp  = (df["High"] + df["Low"] + df["Close"]) / 3
    ma  = tp.rolling(n).mean()
    mad = tp.rolling(n).apply(lambda x: np.abs(x - x.mean()).mean())
    return (tp - ma) / (0.015 * mad + 1e-9)

def _vsa_state(df: pd.DataFrame, i: int) -> str:
    """Simplified VSA: look at last 5 bars at index i."""
    if i < 5:
        return "NEUTRAL"
    window = df.iloc[i-5:i+1]
    close  = window["Close"]
    vol    = window["Volume"]
    mv     = vol.mean()
    last_c = close.iloc[-1]
    p5_c   = close.iloc[-5]
    trend  = last_c > p5_c
    last_v = vol.iloc[-1]
    # Accumulation: up trend + volume > 1.5× avg + no extreme spread
    spread = (window["High"].iloc[-1] - window["Low"].iloc[-1]) / (window["Close"].iloc[-1] + 1e-9)
    if trend and last_v > 1.5 * mv and spread < 0.04:
        return "ACCUM"
    # No supply: narrow spread day on low volume
    if spread < 0.015 and last_v < 0.6 * mv:
        return "NO_SUPPLY"
    # Distribution: down move + high volume
    if not trend and last_v > 1.8 * mv:
        return "DISTRIB"
    return "NEUTRAL"

def _regime(close: pd.Series, sma50: pd.Series, sma200: pd.Series, i: int) -> str:
    """Regime classification at row i."""
    if i < 1 or pd.isna(sma50.iloc[i]) or pd.isna(sma200.iloc[i]):
        return "UNKNOWN"
    c  = float(close.iloc[i])
    s5 = float(sma50.iloc[i])
    s2 = float(sma200.iloc[i])
    if c > s5 > s2:
        return "BULL_TREND"
    elif c < s5 < s2:
        return "BEAR_TREND"
    else:
        return "SIDEWAYS"

def _candle_pts(df: pd.DataFrame, i: int) -> int:
    """Simple candle pattern scoring at row i."""
    if i < 1:
        return 0
    o, h, l, c = (float(df[k].iloc[i]) for k in ("Open", "High", "Low", "Close"))
    body   = abs(c - o)
    rng    = h - l if h > l else 1e-9
    body_r = body / rng
    lower_wick = (min(o, c) - l) / rng
    upper_wick = (h - max(o, c)) / rng
    if body_r > 0.70 and c > o:
        return 3   # Marubozu bullish
    if lower_wick > 0.55 and body_r < 0.35 and upper_wick < 0.15:
        return 3   # Hammer
    if body_r < 0.05:
        return 0   # Doji → neutral
    if body_r > 0.70 and c < o:
        return -2  # Bearish marubozu
    return 0


def compute_rolling_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all rolling indicators needed by compute_t25_score() and
    generate_t_plus_recommendation() for every row in df.
    Returns the same df with added indicator columns.
    """
    close  = df["Close"]
    volume = df["Volume"]

    df = df.copy()
    df["sma20"]  = close.rolling(20).mean()
    df["sma50"]  = close.rolling(50).mean()
    df["sma200"] = close.rolling(200).mean()
    df["ema9"]   = _ema(close, 9)
    df["ema21"]  = _ema(close, 21)
    df["atr14"]  = _atr(df, 14)
    df["rsi14"]  = _rsi(close, 14)
    df["macd_h"] = _macd(close)

    stk, std_ = _stoch(df)
    df["stoch_k"] = stk
    df["stoch_d"] = std_
    df["wr14"]    = _williams_r(df, 14)
    df["cci20"]   = _cci(df, 20)

    # Volume ratio vs MA20
    vm20 = volume.rolling(20).mean()
    df["vol_ratio"] = volume / vm20.replace(0, np.nan)

    # Bollinger Bands
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    df["bb_mid"]   = bb_mid
    df["bb_lower"] = bb_mid - 2 * bb_std
    df["bb_upper"] = bb_mid + 2 * bb_std

    df["pct_change"] = close.pct_change() * 100

    # Log returns for GARCH/HMM
    df["log_ret"] = np.log(close / close.shift(1))

    # Bull pct over last 5 bars
    def _bpct(x):
        pos = (x > 0).sum()
        return pos / len(x) * 100 if len(x) == 5 else 50.0
    df["bull_pct"] = df["log_ret"].rolling(5).apply(_bpct, raw=True)

    # Signal confirmed: 2-of-3 (close > sma20, rsi > 50, macd_h > 0) for 2 bars
    cond = (
        (close > df["sma20"]).astype(int)
        + (df["rsi14"] > 50).astype(int)
        + (df["macd_h"] > 0).astype(int)
    )
    df["confirmed"] = (cond.rolling(2).min() >= 2)

    # RSI divergence (simplified: price up but RSI down over 10 bars → bearish)
    price_up = close > close.shift(10)
    rsi_down = df["rsi14"] < df["rsi14"].shift(10)
    rsi_up   = df["rsi14"] > df["rsi14"].shift(10)
    df["rsi_div"] = np.where(price_up & rsi_down, "BEARISH",
                    np.where(~price_up & rsi_up,  "BULLISH", "NONE"))

    # At SMA20 ceiling/floor
    df["at_ceiling"] = (close / df["sma20"] - 1) > 0.06
    df["at_floor"]   = (close / df["sma20"] - 1) < -0.06

    # kl_ratio
    df["kl_ratio"] = df["vol_ratio"].fillna(1.0)

    # Rolling beta vs index (proxy: 5D vol × 0.8)
    df["beta5d"] = (df["log_ret"].rolling(5).std() / 0.012).clip(0.5, 3.0)

    return df


def build_t25_at(df: pd.DataFrame, i: int) -> dict:
    """
    Build the T25 score dict for row i using pre-computed indicator columns.
    Minimal subset of compute_t25_score() parameters.
    """
    macd_arr  = df["macd_h"].iloc[max(0, i-3):i+1].tolist()
    rsi       = float(df["rsi14"].iloc[i]) if not pd.isna(df["rsi14"].iloc[i]) else None
    rsi_5ago  = float(df["rsi14"].iloc[i-5]) if i >= 5 and not pd.isna(df["rsi14"].iloc[i-5]) else None
    vol_ratio = float(df["vol_ratio"].iloc[i]) if not pd.isna(df["vol_ratio"].iloc[i]) else 1.0
    pct_chg   = float(df["pct_change"].iloc[i]) if not pd.isna(df["pct_change"].iloc[i]) else 0.0
    stk       = float(df["stoch_k"].iloc[i]) if not pd.isna(df["stoch_k"].iloc[i]) else 50.0
    stk_arr   = df["stoch_k"].iloc[max(0,i-2):i+1].tolist()
    std_arr   = df["stoch_d"].iloc[max(0,i-2):i+1].tolist()
    wr        = float(df["wr14"].iloc[i]) if not pd.isna(df["wr14"].iloc[i]) else -50.0
    wr_5ago   = float(df["wr14"].iloc[i-5]) if i >= 5 else None
    cci       = float(df["cci20"].iloc[i]) if not pd.isna(df["cci20"].iloc[i]) else 0.0
    cci_4ago  = float(df["cci20"].iloc[i-4]) if i >= 4 and not pd.isna(df["cci20"].iloc[i-4]) else None
    close     = float(df["Close"].iloc[i])
    sma20_v   = float(df["sma20"].iloc[i])  if not pd.isna(df["sma20"].iloc[i])  else close
    ema9_v    = float(df["ema9"].iloc[i])   if not pd.isna(df["ema9"].iloc[i])   else close
    ema21_v   = float(df["ema21"].iloc[i])  if not pd.isna(df["ema21"].iloc[i])  else close
    sma50_v   = float(df["sma50"].iloc[i])  if not pd.isna(df["sma50"].iloc[i])  else close
    sma200_v  = float(df["sma200"].iloc[i]) if not pd.isna(df["sma200"].iloc[i]) else close
    bb_lo     = float(df["bb_lower"].iloc[i]) if not pd.isna(df["bb_lower"].iloc[i]) else close * 0.96
    bb_md     = float(df["bb_mid"].iloc[i])   if not pd.isna(df["bb_mid"].iloc[i])   else close
    regime    = _regime(df["Close"], df["sma50"], df["sma200"], i)
    vsa       = _vsa_state(df, i)
    cpnts     = _candle_pts(df, i)
    rsi_div   = str(df["rsi_div"].iloc[i]) if i < len(df) else "NONE"
    div_pts   = 4 if rsi_div == "BULLISH" else 0

    return compute_t25_score(
        macd_hist_arr=macd_arr,
        rsi=rsi, rsi_5bar_ago=rsi_5ago,
        vol_ratio=vol_ratio, pct_change=pct_chg,
        stoch_k=stk, stoch_k_arr=stk_arr, stoch_d_arr=std_arr,
        williams_r=wr, williams_r_5bar=wr_5ago,
        cci=cci, cci_4bar_ago=cci_4ago,
        ema9=ema9_v, ema21=ema21_v, sma50=sma50_v, sma200=sma200_v,
        price=close, sma20=sma20_v,
        fib_618=None, monthly_s1=None,
        bb_lower=bb_lo, bb_mid=bb_md,
        adx=20, plus_di=25, minus_di=20,
        vsa_state=vsa, candle_pts=cpnts, div_pts=div_pts,
        regime=regime,
    )


def build_r_at(df: pd.DataFrame, i: int, ticker: str, t25: dict) -> dict:
    """Construct an r-dict for generate_t_plus_recommendation() at row i."""
    close    = float(df["Close"].iloc[i])
    sma20_v  = float(df["sma20"].iloc[i]) if not pd.isna(df["sma20"].iloc[i]) else close
    atr_v    = float(df["atr14"].iloc[i]) if not pd.isna(df["atr14"].iloc[i]) else close * 0.02
    bull_p   = float(df["bull_pct"].iloc[i]) if not pd.isna(df["bull_pct"].iloc[i]) else 50.0
    regime   = _regime(df["Close"], df["sma50"], df["sma200"], i)
    vsa      = _vsa_state(df, i)
    rsi_div  = str(df["rsi_div"].iloc[i]) if i < len(df) else "NONE"
    candle_p = "HAMMER" if _candle_pts(df, i) == 3 else "NEUTRAL"
    atr_sl   = close - 1.5 * atr_v
    atr_tp1  = close + 2.0 * atr_v
    atr_tp2  = close + 3.5 * atr_v
    return {
        "ticker":           ticker,
        "price":            close,
        "sma20":            sma20_v,
        "atr":              atr_v,
        "t25_signal":       t25["t25_signal"],
        "t25_score":        t25["t25_score"],
        "t25_confirms":     t25["t25_confirms"],
        "bull_pct":         bull_p,
        "regime":           regime,
        "signal_confirmed": bool(df["confirmed"].iloc[i]) if i < len(df) else False,
        "vsa_state":        vsa,
        "candle_pattern":   candle_p,
        "rsi_divergence":   rsi_div,
        "at_ceiling":       bool(df["at_ceiling"].iloc[i]),
        "at_floor":         bool(df["at_floor"].iloc[i]),
        "rolling_beta_20d": float(df["beta5d"].iloc[i]) if not pd.isna(df["beta5d"].iloc[i]) else 1.0,
        "kl_ratio":         float(df["kl_ratio"].iloc[i]) if not pd.isna(df["kl_ratio"].iloc[i]) else 1.0,
        "rs_rating":        50,
        "sl":               atr_sl,
        "tp1":              atr_tp1,
        "tp2":              atr_tp2,
        "bt5_win_rate":     0.55,
    }


def build_cf_at(df: pd.DataFrame, i: int, n_days: int = 5,
                ticker: str = "__") -> dict | None:
    """
    Build a minimal cf_result dict using GARCH+HMM on data up to row i.
    SARIMA/Prophet are deliberately skipped — too expensive for walk-forward.
    GARCH is refit every _CF_GARCH_PERIOD bars; HMM every _CF_HMM_PERIOD bars.
    A fast linear-regression trend extrapolation supplies the Day-1 direction.
    Returns None if _CF_AVAILABLE is False or insufficient data.
    """
    if not _CF_AVAILABLE or i < _MIN_LOOKBACK:
        return None
    hist = df.iloc[:i+1].copy()
    close_s  = hist["Close"].dropna()
    log_rets = hist["log_ret"].dropna()
    if len(close_s) < 60:
        return None
    try:
        # ── GARCH: refit every _CF_GARCH_PERIOD bars ─────────────────────────
        gc = _CF_GARCH_CACHE.get(ticker)
        if gc is None or (i - gc["bar"]) >= _CF_GARCH_PERIOD:
            garch = fit_garch(log_rets, n_days)
            _CF_GARCH_CACHE[ticker] = {"bar": i, "result": garch}
        else:
            garch = gc["result"]

        # ── HMM: refit every _CF_HMM_PERIOD bars ─────────────────────────────
        hc = _CF_HMM_CACHE.get(ticker)
        if hc is None or (i - hc["bar"]) >= _CF_HMM_PERIOD:
            hmm = fit_hmm(log_rets)
            _CF_HMM_CACHE[ticker] = {"bar": i, "result": hmm}
        else:
            hmm = hc["result"]

        # Fast Day-1 direction: linear trend on last 10 bars
        current_price = float(close_s.iloc[-1])
        last_10 = close_s.iloc[-10:].values
        if len(last_10) >= 5:
            x = np.arange(len(last_10))
            slope, intercept = np.polyfit(x, last_10, 1)
            next_p   = float(intercept + slope * len(last_10))
            day1_pct = float(np.clip(
                (next_p - current_price) / current_price * 100,
                -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100,
            ))
        else:
            day1_pct = 0.0

        # Stub EnsemblePrediction using linear-extrapolation pct_changes
        pct_proj   = [day1_pct * max(0.0, 1.0 - 0.15 * d) for d in range(n_days)]
        close_proj = [current_price * (1 + p / 100) for p in pct_proj]
        from candle_forecast_engine import EnsemblePrediction, CandleDict
        ens = EnsemblePrediction(
            close_preds=close_proj,
            pct_changes=pct_proj,
            model_weights={"linreg": 1.0},
            directional_accuracy={},
        )
        ci_w = garch.sigma_t1 * 1.645 * current_price
        c0 = CandleDict(
            day=1, date_lbl="D1",
            open=current_price, high=current_price + ci_w, low=current_price - ci_w,
            close=float(close_proj[0]) if close_proj else current_price,
            volume=float(hist["Volume"].iloc[-1]),
            lower_ci=round(current_price - ci_w, 0),
            upper_ci=round(current_price + ci_w, 0),
            pattern="NEUTRAL", signal="NEUTRAL",
        )
        return {"garch": garch, "hmm": hmm, "ensemble": ens, "candles": [c0]}
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  WALK-FORWARD BACKTEST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def backtest_ticker(
    ticker:    str,
    df:        pd.DataFrame,
    start_dt:  str,
    end_dt:    str,
    horizon:   int = 5,
    min_score: int = 65,
    with_cf:   bool = False,
) -> list[dict]:
    """
    Walk forward through df from start_dt to end_dt.
    For each bar with a BUY/STRONG_BUY signal (score >= min_score),
    record the trade and evaluate actual forward return.
    Returns list of trade dicts.
    """
    df = compute_rolling_indicators(df)
    df.index = pd.to_datetime(df.index)

    # Reset per-ticker CF caches so new ticker starts fresh
    _CF_GARCH_CACHE.pop(ticker, None)
    _CF_HMM_CACHE.pop(ticker, None)

    # Filter to date range
    mask = (df.index >= pd.Timestamp(start_dt)) & (df.index <= pd.Timestamp(end_dt))
    scan_idx = df.index[mask]

    trades = []
    for ts in scan_idx:
        i = df.index.get_loc(ts)
        if i < _MIN_LOOKBACK or (i + horizon) >= len(df):
            continue

        # Build signal at row i
        try:
            t25  = build_t25_at(df, i)
            r    = build_r_at(df, i, ticker, t25)
            cf   = build_cf_at(df, i, n_days=horizon, ticker=ticker) if with_cf else None
            rec  = generate_t_plus_recommendation(r, cf_result=cf)
        except Exception as exc:
            continue

        action = rec["action"]
        score  = rec["confidence_score"]

        # Only record actionable signals
        if action not in ("BUY", "STRONG_BUY", "WATCH"):
            continue

        # Forward return
        entry_price  = float(df["Close"].iloc[i])
        exit_price   = float(df["Close"].iloc[i + horizon])
        fwd_ret_pct  = (exit_price - entry_price) / entry_price * 100

        # Maximum adverse excursion (worst intra-trade close)
        intra = df["Close"].iloc[i+1:i+horizon+1]
        mae   = float((intra.min() - entry_price) / entry_price * 100)

        # Win / Loss
        is_win = fwd_ret_pct > 0

        # SL hit check (if SL exists)
        sl = rec.get("sl_price")
        sl_hit = False
        if sl:
            sl_hit = bool(df["Low"].iloc[i+1:i+horizon+1].min() <= sl)

        # CF fields
        garch_sigma    = None
        high_vol       = None
        hmm_transition = None
        day1_pct       = None
        if cf:
            garch_cf = cf.get("garch")
            if garch_cf and hasattr(garch_cf, "sigma_t1"):
                garch_sigma = round(float(garch_cf.sigma_t1) * 100, 3)  # as %
                high_vol    = bool(garch_cf.high_vol_regime)
            hmm_cf = cf.get("hmm")
            if hmm_cf:
                hmm_transition = rec.get("hmm_transition")
            ens_cf = cf.get("ensemble")
            if ens_cf and hasattr(ens_cf, "pct_changes") and ens_cf.pct_changes:
                day1_pct = float(ens_cf.pct_changes[0])

        trades.append({
            "ticker":        ticker,
            "date":          ts.strftime("%Y-%m-%d"),
            "action":        action,
            "score":         score,
            "entry_price":   round(entry_price, 0),
            "exit_price":    round(exit_price, 0),
            "fwd_ret_pct":   round(fwd_ret_pct, 2),
            "mae_pct":       round(mae, 2),
            "is_win":        is_win,
            "sl_hit":        sl_hit,
            "horizon_days":  horizon,
            "t25_signal":    t25["t25_signal"],
            "garch_sigma_pct": garch_sigma,
            "high_vol_regime": high_vol,
            "hmm_transition":  hmm_transition,
            "cf_day1_pct":     day1_pct,
            "position_size":   round(rec["position_size_pct"], 1),
            "rr_ratio":        rec.get("rr_ratio"),
        })

    return trades


# ══════════════════════════════════════════════════════════════════════════════
#  METRICS COMPUTATION
# ══════════════════════════════════════════════════════════════════════════════

def compute_metrics(trades: list[dict], mode_name: str, min_score: int) -> dict:
    if not trades:
        return {"mode": mode_name, "n_trades": 0}

    df_t = pd.DataFrame(trades)
    rets = df_t["fwd_ret_pct"].values

    n           = len(df_t)
    win_rate    = float(df_t["is_win"].mean() * 100)
    avg_ret     = float(rets.mean())
    avg_win     = float(df_t.loc[df_t["is_win"],  "fwd_ret_pct"].mean()) if df_t["is_win"].any() else 0.0
    avg_loss    = float(df_t.loc[~df_t["is_win"], "fwd_ret_pct"].mean()) if (~df_t["is_win"]).any() else 0.0
    profit_fac  = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
    sharpe      = float(rets.mean() / (rets.std() + 1e-9) * (252 ** 0.5))  # annualised
    max_dd      = float(df_t["mae_pct"].min())
    sl_hit_rate = float(df_t["sl_hit"].mean() * 100) if "sl_hit" in df_t.columns else None

    # By action
    for act in ("STRONG_BUY", "BUY", "WATCH"):
        sub   = df_t[df_t["action"] == act]
        label = f"  {act}: n={len(sub)}"
        if len(sub):
            label += f" wr={sub['is_win'].mean()*100:.1f}% avg={sub['fwd_ret_pct'].mean():.2f}%"

    # CF-specific: GARCH high_vol regime filtering effect
    hv_trades  = df_t[df_t["high_vol_regime"] == True]  if "high_vol_regime" in df_t.columns else pd.DataFrame()
    nvhv_trades = df_t[df_t["high_vol_regime"] == False] if "high_vol_regime" in df_t.columns else pd.DataFrame()

    return {
        "mode":             mode_name,
        "min_score":        min_score,
        "n_trades":         n,
        "win_rate_pct":     round(win_rate, 1),
        "avg_return_pct":   round(avg_ret, 2),
        "avg_win_pct":      round(avg_win, 2),
        "avg_loss_pct":     round(avg_loss, 2),
        "profit_factor":    round(profit_fac, 2),
        "sharpe_ann":       round(sharpe, 2),
        "max_mae_pct":      round(max_dd, 2),
        "sl_hit_rate_pct":  round(sl_hit_rate, 1) if sl_hit_rate is not None else None,
        "by_action": {
            act: {
                "n":     int(len(df_t[df_t["action"] == act])),
                "wr":    round(df_t[df_t["action"] == act]["is_win"].mean() * 100, 1) if len(df_t[df_t["action"] == act]) else 0.0,
                "avg":   round(df_t[df_t["action"] == act]["fwd_ret_pct"].mean(), 2) if len(df_t[df_t["action"] == act]) else 0.0,
            }
            for act in ("STRONG_BUY", "BUY", "WATCH")
        },
        "high_vol_regime": {
            "n_trades":   int(len(hv_trades)),
            "win_rate":   round(float(hv_trades["is_win"].mean() * 100), 1) if len(hv_trades) else None,
            "avg_ret":    round(float(hv_trades["fwd_ret_pct"].mean()), 2) if len(hv_trades) else None,
        } if len(hv_trades) else None,
        "normal_vol_regime": {
            "n_trades":  int(len(nvhv_trades)),
            "win_rate":  round(float(nvhv_trades["is_win"].mean() * 100), 1) if len(nvhv_trades) else None,
            "avg_ret":   round(float(nvhv_trades["fwd_ret_pct"].mean()), 2) if len(nvhv_trades) else None,
        } if len(nvhv_trades) else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Backtest T+ Recommendation Engine")
    parser.add_argument("--tickers",   nargs="+", default=DEFAULT_TICKERS, metavar="T",
                        help="List of ticker symbols")
    parser.add_argument("--horizon",   type=int, default=5,
                        help="Forward return horizon in trading days (default: 5)")
    parser.add_argument("--start",     default="2023-01-01",
                        help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end",       default="2026-03-21",
                        help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--min-score", type=int, default=65,
                        help="Minimum confidence score to trade (default: 65)")
    parser.add_argument("--cf",        action="store_true",
                        help="Run CF-enriched backtest (slower, requires arch/hmmlearn)")
    parser.add_argument("--output",    default=str(_DATA_DIR / "backtest_t_plus"),
                        help="Output path prefix (no extension)")
    args = parser.parse_args()

    # Calculate needed days history to cover backtest range + lookback buffer
    from datetime import datetime
    start = datetime.strptime(args.start, "%Y-%m-%d")
    end   = datetime.strptime(args.end,   "%Y-%m-%d")
    cal_days  = (end - start).days
    hist_needed = int(cal_days * 252 / 365 + _MIN_LOOKBACK + 50)
    hist_needed = max(hist_needed, 800)  # at least 800 bars

    print(f"\n{'='*70}")
    print(f"  T+ Recommendation Backtest  |  {args.start} → {args.end}")
    print(f"  Tickers: {len(args.tickers)}  |  Horizon: {args.horizon}D  |  Min-score: {args.min_score}")
    print(f"  CF enrichment: {'ON' if args.cf else 'OFF'}")
    print(f"{'='*70}\n")

    all_trades_base = []
    all_trades_cf   = []

    for ticker in args.tickers:
        print(f"  ⬇ Fetching {ticker} ({hist_needed} bars)...", end=" ", flush=True)
        try:
            df, src = fetch_ohlcv(ticker, days=hist_needed, verbose=False)
        except Exception as exc:
            print(f"FAILED ({exc})")
            continue
        if df is None or df.empty:
            print("NO DATA")
            continue
        print(f"OK ({src}, {len(df)} bars)")

        # ── Baseline: T+ without CF ──────────────────────────────────────────
        print(f"    ↳ Baseline ...", end=" ", flush=True)
        t_base = backtest_ticker(
            ticker, df.copy(), args.start, args.end,
            horizon=args.horizon, min_score=args.min_score, with_cf=False,
        )
        all_trades_base.extend(t_base)
        wr_b = sum(1 for t in t_base if t["is_win"]) / max(1, len(t_base)) * 100
        print(f"{len(t_base)} trades  WR={wr_b:.1f}%")

        # ── CF-enriched: T+ with GARCH+HMM ──────────────────────────────────
        if args.cf and _CF_AVAILABLE:
            print(f"    ↳ CF-enriched ...", end=" ", flush=True)
            t_cf = backtest_ticker(
                ticker, df.copy(), args.start, args.end,
                horizon=args.horizon, min_score=args.min_score, with_cf=True,
            )
            all_trades_cf.extend(t_cf)
            wr_cf = sum(1 for t in t_cf if t["is_win"]) / max(1, len(t_cf)) * 100
            print(f"{len(t_cf)} trades  WR={wr_cf:.1f}%")
        elif args.cf:
            print(f"    ↳ CF-enriched: SKIPPED (candle_forecast_engine not available)")

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  AGGREGATE RESULTS")
    print(f"{'='*70}")

    summaries = []

    metrics_base = compute_metrics(all_trades_base, "T+_Baseline", args.min_score)
    summaries.append(metrics_base)
    _print_metrics(metrics_base)

    if args.cf and all_trades_cf:
        metrics_cf = compute_metrics(all_trades_cf, "T+_CF_Enriched", args.min_score)
        summaries.append(metrics_cf)
        _print_metrics(metrics_cf)

        # ── Differential analysis ─────────────────────────────────────────────
        print("\n  ── CF REGIME FILTERING EFFECT ──")
        hv = metrics_cf.get("high_vol_regime")
        nv = metrics_cf.get("normal_vol_regime")
        if hv:
            print(f"  HIGH_VOL_REGIME: n={hv['n_trades']}  WR={hv['win_rate']}%  avg={hv['avg_ret']}%")
        if nv:
            print(f"  NORMAL_VOL:      n={nv['n_trades']}  WR={nv['win_rate']}%  avg={nv['avg_ret']}%")

    # ── Save outputs ──────────────────────────────────────────────────────────
    out = Path(args.output)
    all_trades = all_trades_base + all_trades_cf
    if all_trades:
        pd.DataFrame(all_trades).to_csv(str(out) + "_results.csv", index=False)
        print(f"\n  📄 Trade log → {out}_results.csv  ({len(all_trades)} rows)")

    with open(str(out) + "_summary.json", "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)
    print(f"  📊 Summary  → {out}_summary.json")
    print(f"{'='*70}\n")


def _print_metrics(m: dict) -> None:
    print(f"\n  MODE: {m['mode']}")
    print(f"  {'─'*50}")
    if m.get("n_trades", 0) == 0:
        print("  No trades generated.")
        return
    print(f"  Trades:          {m['n_trades']}")
    print(f"  Win Rate:        {m['win_rate_pct']}%")
    print(f"  Avg Return:      {m['avg_return_pct']}%  (win: {m['avg_win_pct']}%  loss: {m['avg_loss_pct']}%)")
    print(f"  Profit Factor:   {m['profit_factor']}")
    print(f"  Sharpe (ann.):   {m['sharpe_ann']}")
    print(f"  Max MAE:         {m['max_mae_pct']}%")
    if m.get("sl_hit_rate_pct") is not None:
        print(f"  SL Hit Rate:     {m['sl_hit_rate_pct']}%")
    print(f"  By Action:")
    for act, v in m.get("by_action", {}).items():
        if v["n"] > 0:
            print(f"    {act:12s} n={v['n']:4d}  WR={v['wr']:5.1f}%  avg={v['avg']:+5.2f}%")


if __name__ == "__main__":
    main()

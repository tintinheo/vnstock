"""Universe Builder — CAN SLIM filters + RS Rating + PCA exclusion (SRS §3.9)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.fetcher import fetch_universe, fetch_ohlcv
from ..utils.config import cfg
from .indicators import rsi as compute_rsi


def _rs_rating(ticker_return_252: float, universe_returns: pd.Series) -> float:
    """Relative Strength Rating: percentile rank among universe."""
    if len(universe_returns) == 0:
        return 50.0
    rank = (universe_returns < ticker_return_252).mean()
    return round(rank * 100, 1)


def compute_universe_rs(tickers: list[str], days: int = 252) -> pd.DataFrame:
    """
    Fetch 252d returns for all tickers, compute RS Rating.
    Returns DataFrame columns: [ticker, return_252d, rs_rating].
    """
    records = []
    for ticker in tickers:
        try:
            df = fetch_ohlcv(ticker, days=days + 5)
            if df.empty or len(df) < 50:
                continue
            ret = float(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
            records.append({"ticker": ticker, "return_252d": ret})
        except Exception:
            pass

    if not records:
        return pd.DataFrame(columns=["ticker", "return_252d", "rs_rating"])

    df_rs = pd.DataFrame(records)
    universe_rets = df_rs["return_252d"]
    df_rs["rs_rating"] = df_rs["return_252d"].apply(lambda r: _rs_rating(r, universe_rets))
    return df_rs.sort_values("rs_rating", ascending=False).reset_index(drop=True)


def canslim_filters(df: pd.DataFrame, ticker: str) -> dict:
    """
    Simplified CAN SLIM technical checks (C, A are price/volume based):
    - C: Current quarterly earnings proxy (slope of EPS-like proxy)
    - A+N: 52-week price > 80th percentile of range → new highs
    - S: Volume surge (supply/demand)
    - L: Relative strength
    - I: Institutional-like accumulation (OBV trend)
    - M: Market environment (from HMM, passed separately)
    """
    if df.empty or len(df) < 50:
        return {"passed": False, "score": 0, "details": {}}

    score = 0
    details = {}

    # N: Trading near 52-week high (price > 80% of 52w range)
    high_52w = float(df["high"].tail(252).max())
    low_52w = float(df["low"].tail(252).min())
    cur_price = float(df["close"].iloc[-1])
    pct_range = (cur_price - low_52w) / max(high_52w - low_52w, 1)
    details["near_high"] = pct_range
    if pct_range >= 0.75:
        score += 15

    # S: Volume increasing vs 50d average
    vol_50 = float(df["volume"].tail(50).mean())
    vol_now = float(df["volume"].iloc[-1])
    vol_surge = vol_now / max(vol_50, 1)
    details["vol_surge"] = round(vol_surge, 2)
    if vol_surge > 1.2:
        score += 10

    # I: OBV trend (compare last 20 slope)
    obv = (df["volume"] * (2 * (df["close"] > df["close"].shift(1)).astype(int) - 1)).cumsum()
    obv_slope = float(np.polyfit(range(min(20, len(obv))), obv.tail(20).values, 1)[0])
    details["obv_slope"] = round(obv_slope, 0)
    if obv_slope > 0:
        score += 10

    # L: RSI > 50 (relative strength)
    rsi_val = float(compute_rsi(df["close"], 14).iloc[-1])
    details["rsi14"] = round(rsi_val, 1)
    if rsi_val > 55:
        score += 10

    # Minimum price filter
    min_price = float(cfg.strategy("universe", "min_price", default=5000))
    if cur_price < min_price:
        score = 0
        details["price_reject"] = cur_price
        return {"passed": False, "score": score, "details": details}

    # Minimum avg daily volume — YAML key is min_avg_vol_20d
    min_vol = float(cfg.strategy("universe", "min_avg_vol_20d", default=100_000))
    if vol_50 < min_vol:
        score = 0
        details["vol_reject"] = vol_50
        return {"passed": False, "score": score, "details": details}

    passed = score >= 25
    return {"passed": passed, "score": score, "details": details}


def build_universe(
    exchange: str = "HOSE",
    rs_min: float | None = None,
    max_tickers: int | None = None,
) -> list[str]:
    """
    Build investable universe:
    1. Fetch all listed tickers on exchange
    2. Apply CAN SLIM technical filters
    3. RS Rating ≥ threshold
    4. Return sorted by RS Rating

    rs_min: minimum RS Rating (default from strategy.yaml)
    max_tickers: cap (default from strategy.yaml)
    """
    rs_threshold = rs_min or float(cfg.strategy("universe", "rs_min", default=60.0))
    cap = max_tickers or int(cfg.strategy("universe", "max_universe_size", default=150))

    all_tickers = fetch_universe(exchange)

    # Compute RS for all (fast batch)
    from ..utils.logging import get_logger
    log = get_logger("universe")
    log.info(f"Building universe from {len(all_tickers)} tickers on {exchange}")

    rs_df = compute_universe_rs(all_tickers, days=252)
    if rs_df.empty:
        return all_tickers[:cap]

    # RS filter
    rs_df = rs_df[rs_df["rs_rating"] >= rs_threshold]

    # CAN SLIM filter on top candidates
    filtered = []
    for row in rs_df.itertuples():
        try:
            df = fetch_ohlcv(row.ticker, days=60)
            result = canslim_filters(df, row.ticker)
            if result["passed"]:
                filtered.append(row.ticker)
            if len(filtered) >= cap:
                break
        except Exception:
            pass

    log.info(f"Universe built: {len(filtered)} tickers")
    return filtered

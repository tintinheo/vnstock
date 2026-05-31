"""
core/data_fetcher.py — NewTradingOS v14.0
Price data pipeline: DNSE (primary) → SSI (fallback)
All VN-native sources; covers HOSE, HNX, UPCOM.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd
import requests

from config import (
    DNSE_URL, SSI_URL,
    API_TIMEOUT, TICKER_EXCHANGE,
)

logger = logging.getLogger("TradingOS.fetcher")

# ─────────────────────────────────────────────────────────────
# Separate HTTP sessions per source to avoid header conflicts
# (DNSE rejects requests that carry SSI's Referer header)
# ─────────────────────────────────────────────────────────────
_DNSE_SESSION = requests.Session()
_DNSE_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124",
    "Accept":     "application/json,*/*;q=0.9",
})

_SSI_SESSION = requests.Session()
_SSI_SESSION.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124",
    "Accept":          "application/json,*/*;q=0.9",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer":         "https://iboard.ssi.com.vn/",
})


def _unix(dt: datetime) -> int:
    return int(dt.timestamp())


# ─────────────────────────────────────────────────────────────
# PARSER HELPERS
# ─────────────────────────────────────────────────────────────
def _parse_udf(raw: dict) -> pd.DataFrame:
    """Parse TradingView UDF format {t, o, h, l, c, v}."""
    if not raw or raw.get("s") == "no_data":
        return pd.DataFrame()
    t_arr = raw.get("t", [])
    c_arr = raw.get("c", [])
    if not t_arr or not c_arr or len(t_arr) < 5:
        return pd.DataFrame()
    try:
        df = pd.DataFrame({
            "Open":   pd.to_numeric(raw.get("o", c_arr), errors="coerce"),
            "High":   pd.to_numeric(raw.get("h", c_arr), errors="coerce"),
            "Low":    pd.to_numeric(raw.get("l", c_arr), errors="coerce"),
            "Close":  pd.to_numeric(c_arr, errors="coerce"),
            "Volume": pd.to_numeric(raw.get("v", [0] * len(t_arr)), errors="coerce"),
        }, index=pd.to_datetime(t_arr, unit="s").normalize())
        df.index.name = "Date"
        df = df.dropna(subset=["Close"]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        _normalize_price_scale(df)
        return df
    except Exception as exc:
        logger.debug("_parse_udf: %s", exc)
        return pd.DataFrame()


def _normalize_price_scale(df: pd.DataFrame) -> None:
    """In-place: some APIs return x1000 VND (e.g. 25.6 instead of 25,600)."""
    if df.empty:
        return
    med = df["Close"].dropna().median()
    if 0 < med < 500:
        for col in ("Open", "High", "Low", "Close"):
            if col in df.columns:
                df[col] = df[col] * 1000


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Standardise OHLCV; remove outliers; ensure positive close."""
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in df.columns:
            df[col] = np.nan
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=["Close"])
    df = df[df["Close"] > 0]
    med = df["Close"].median()
    if med > 0:
        df = df[df["Close"].between(med * 0.05, med * 20)]
    df["Volume"] = df["Volume"].fillna(0).clip(lower=0)
    return df.sort_index()


# ─────────────────────────────────────────────────────────────
# P1: DNSE Entrade
# ─────────────────────────────────────────────────────────────
def _fetch_dnse(symbol: str, days: int = 730) -> pd.DataFrame:
    """
    DNSE Entrade UDF — fastest, covers HOSE/HNX/UPCOM.
    Uses resolution=1D (API changed from 'D').
    """
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (f"{DNSE_URL}?symbol={symbol}&resolution=1D"
           f"&from={from_ts}&to={to_ts}")
    try:
        r = _DNSE_SESSION.get(url, timeout=API_TIMEOUT)
        r.raise_for_status()
        return _parse_udf(r.json())
    except Exception as exc:
        logger.debug("DNSE %s: %s", symbol, exc)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# P2: SSI iBoard
# ─────────────────────────────────────────────────────────────
def _fetch_ssi(symbol: str, days: int = 730) -> pd.DataFrame:
    """SSI iBoard UDF — uses resolution=1D."""
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (f"{SSI_URL}?symbol={symbol}&resolution=1D"
           f"&from={from_ts}&to={to_ts}")
    try:
        r = _SSI_SESSION.get(url, timeout=API_TIMEOUT)
        r.raise_for_status()
        return _parse_udf(r.json())
    except Exception as exc:
        logger.debug("SSI %s: %s", symbol, exc)
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────
def download_data(
    symbol: str,
    days: int = 730,
    min_rows: int = 40,
) -> tuple[pd.DataFrame, str]:
    """
    Download OHLCV via pipeline: DNSE (1D) → SSI.

    Each source tried once. Returns the first result with >= min_rows.
    If none hits min_rows but at least one has data, returns the best
    partial result. Only returns empty when every source returns nothing.
    """
    symbol = symbol.strip().upper()

    fetchers = [
        (_fetch_dnse, "DNSE"),
        (_fetch_ssi,  "SSI"),
    ]

    best_df:  pd.DataFrame = pd.DataFrame()
    best_src: str          = "NONE"

    for fn, src_name in fetchers:
        try:
            df = fn(symbol, days)
        except Exception as exc:
            logger.debug("%s %s unexpected: %s", src_name, symbol, exc)
            df = pd.DataFrame()

        cleaned = _clean_df(df)

        if len(cleaned) > len(best_df):
            best_df, best_src = cleaned, src_name

        if len(cleaned) >= min_rows:
            logger.info("OK %s %s: %d rows", src_name, symbol, len(cleaned))
            return cleaned, src_name

        logger.debug("skip %s %s: %d rows (need %d)",
                     src_name, symbol, len(cleaned), min_rows)

    # Return best partial result rather than empty
    if not best_df.empty:
        logger.warning("partial %s: only %d rows from %s",
                       symbol, len(best_df), best_src)
        return best_df, best_src

    logger.error("No data for %s (exchange=%s)", symbol,
                 TICKER_EXCHANGE.get(symbol, "HOSE"))
    return pd.DataFrame(), "NONE"


def batch_download(
    symbols: list[str],
    days: int = 730,
    max_workers: int = 8,
    delay: float = 0.05,
    chunk_size: int = 120,
    on_progress=None,   # callable(done: int, total: int, sym: str) | None
) -> dict[str, tuple[pd.DataFrame, str]]:
    """
    Download multiple tickers concurrently.
    Returns dict[symbol -> (df, source)].

    on_progress is called in the calling thread after each ticker completes,
    making it safe to call Streamlit UI functions from the callback.
    """
    results: dict[str, tuple[pd.DataFrame, str]] = {}

    def _worker(sym: str) -> tuple[str, pd.DataFrame, str]:
        time.sleep(delay)
        df, src = download_data(sym, days)
        return sym, df, src

    total = len(symbols)
    if total == 0:
        return results

    normalized_chunk_size = max(1, int(chunk_size or total))
    chunks = [
        symbols[index:index + normalized_chunk_size]
        for index in range(0, total, normalized_chunk_size)
    ]

    for chunk_index, chunk in enumerate(chunks, start=1):
        worker_count = min(max_workers, len(chunk))
        logger.info(
            "batch_download chunk %d/%d: %d symbols with %d workers",
            chunk_index, len(chunks), len(chunk), worker_count,
        )
        with ThreadPoolExecutor(max_workers=max(1, worker_count)) as pool:
            futures = {pool.submit(_worker, s): s for s in chunk}
            for fut in as_completed(futures):
                sym, df, src = fut.result()
                results[sym] = (df, src)
                if on_progress is not None:
                    try:
                        on_progress(len(results), total, sym)
                    except Exception:
                        pass  # never let UI errors block data fetching

    return results


def get_latest_price(symbol: str) -> Optional[float]:
    """Fetch latest close price. Returns None on failure."""
    df, _ = download_data(symbol, days=10, min_rows=1)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])

"""
core/macro_data.py — NewTradingOS v14.0
World markets, VN-Index breadth, foreign flow, NHNN rates.
All data from free public APIs.
"""
from __future__ import annotations

import contextlib
import io
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

from config import WORLD_SYMBOLS, API_TIMEOUT, TICKER_EXCHANGE, EXCHANGE_PRICE_LIMIT

logger = logging.getLogger("TradingOS.macro")

_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept":     "application/json",
}
_VNI_CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "vnstock" / "vni_history_cache.csv"
_BREADTH_HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "breadth_history.csv"


def _tag_vni_source(df: pd.DataFrame, source_mode: str, source_name: str) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    df.attrs["source_mode"] = source_mode
    df.attrs["source_name"] = source_name
    return df


# ─────────────────────────────────────────────────────────────
# WORLD MARKETS
# ─────────────────────────────────────────────────────────────
def _yahoo_price(yf_symbol: str, period: str = "3mo") -> Optional[dict]:
    """
    Fetch closing price history from Yahoo Finance chart API.
    Returns dict with 'prices' (list), 'timestamps' (list), 'current', 'pct_5d'.
    """
    url = _YAHOO_CHART.format(symbol=yf_symbol)
    params = {"range": period, "interval": "1d", "includePrePost": False}
    try:
        r = requests.get(url, headers=_YAHOO_HEADERS, params=params,
                         timeout=API_TIMEOUT)
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        closes = result["indicators"]["quote"][0].get("close", [])
        timestamps = result.get("timestamp", [])
        closes  = [c for c in closes if c is not None]
        if not closes:
            return None
        current = closes[-1]
        pct_1d  = ((closes[-1] / closes[-2]) - 1) * 100 if len(closes) >= 2 else 0
        pct_5d  = ((closes[-1] / closes[-6]) - 1) * 100 if len(closes) >= 6 else 0
        pct_20d = ((closes[-1] / closes[-21]) - 1) * 100 if len(closes) >= 21 else 0
        return {
            "current":   current,
            "pct_1d":    round(pct_1d, 2),
            "pct_5d":    round(pct_5d, 2),
            "pct_20d":   round(pct_20d, 2),
            "prices":    closes,
            "timestamps": timestamps,
        }
    except Exception as exc:
        logger.debug("Yahoo %s: %s", yf_symbol, exc)
        return None


def fetch_world_markets() -> dict[str, Optional[dict]]:
    """
    Fetch all world market indicators in parallel.

    Returns
    -------
    dict[name → {current, pct_1d, pct_5d, pct_20d, prices, timestamps}]
    """
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(8, len(WORLD_SYMBOLS))) as pool:
        futures = {
            name: pool.submit(_yahoo_price, yf_sym)
            for name, yf_sym in WORLD_SYMBOLS.items()
        }
        return {name: fut.result() for name, fut in futures.items()}


# ─────────────────────────────────────────────────────────────
# VN-INDEX & MARKET BREADTH
# ─────────────────────────────────────────────────────────────
def _fetch_vni_data_vnstock(days: int = 365) -> pd.DataFrame:
    """Fallback VNINDEX history via vnstock when public chart APIs fail."""
    try:
        quiet = io.StringIO()
        with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
            from vnstock import Vnstock

            start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end = datetime.now().strftime("%Y-%m-%d")
            raw = Vnstock().stock(symbol="VNINDEX", source="VCI").quote.history(
                start=start,
                end=end,
            )
        if raw is None or raw.empty:
            return pd.DataFrame()

        df = raw.rename(columns={
            "time": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }).copy()
        if "Date" not in df.columns or "Close" not in df.columns:
            return pd.DataFrame()

        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
        df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
        for col in ("Open", "High", "Low", "Close", "Volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["Close"])
        df = df[~df.index.duplicated(keep="last")]
        if days > 0:
            min_date = (datetime.now() - timedelta(days=days)).date()
            df = df[df.index.date >= min_date]
        return df
    except Exception as exc:
        logger.debug("vnstock VNINDEX: %s", exc)
        return pd.DataFrame()


def _save_cached_vni_data(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return

    cached = df.copy()
    if not isinstance(cached.index, pd.DatetimeIndex):
        if "Date" not in cached.columns:
            return
        cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce").dt.normalize()
        cached = cached.dropna(subset=["Date"]).set_index("Date")

    cached.index = pd.to_datetime(cached.index, errors="coerce")
    cached = cached[~cached.index.isna()]
    if cached.empty or "Close" not in cached.columns:
        return

    cached.index = cached.index.normalize()
    cached = cached.sort_index()
    cached = cached[~cached.index.duplicated(keep="last")]
    cached = cached.reset_index().rename(columns={cached.index.name or "index": "Date"})
    _VNI_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cached.to_csv(_VNI_CACHE_PATH, index=False)


def _load_cached_vni_data(days: int = 365) -> pd.DataFrame:
    if not _VNI_CACHE_PATH.exists():
        return pd.DataFrame()
    try:
        cached = pd.read_csv(_VNI_CACHE_PATH)
    except Exception as exc:
        logger.debug("load cached VNINDEX: %s", exc)
        return pd.DataFrame()

    if "Date" not in cached.columns or "Close" not in cached.columns:
        return pd.DataFrame()

    cached["Date"] = pd.to_datetime(cached["Date"], errors="coerce").dt.normalize()
    cached = cached.dropna(subset=["Date"]).set_index("Date").sort_index()
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in cached.columns:
            cached[col] = pd.to_numeric(cached[col], errors="coerce")
    cached = cached.dropna(subset=["Close"])
    cached = cached[~cached.index.duplicated(keep="last")]
    if days > 0:
        min_date = (datetime.now() - timedelta(days=days)).date()
        cached = cached[cached.index.date >= min_date]
    return _tag_vni_source(cached, "cache", "VNINDEX cache")


def fetch_vni_data(days: int = 365) -> pd.DataFrame:
    """
    Fetch VN-Index (VNINDEX) daily OHLCV from DNSE Entrade.
    Returns empty DataFrame on failure.
    """
    from core.data_fetcher import _fetch_dnse
    df = _fetch_dnse("VNINDEX", days=days)
    if not df.empty:
        _save_cached_vni_data(df)
        return _tag_vni_source(df, "live", "DNSE")

    # fallback: Yahoo Finance — ^VNINDEX is the correct symbol for VN-Index
    data = _yahoo_price("^VNINDEX", "2y")
    if data and data["prices"]:
        timestamps = data.get("timestamps") or []
        if len(timestamps) == len(data["prices"]):
            index = pd.to_datetime(timestamps, unit="s", errors="coerce")
            df = pd.DataFrame({"Close": data["prices"]}, index=index)
            df.index.name = "Date"
            df = df[~df.index.isna()]
            df.index = df.index.normalize()
            df = df[~df.index.duplicated(keep="last")]
        else:
            df = pd.DataFrame({"Close": data["prices"]})
        if not df.empty:
            _save_cached_vni_data(df)
            return _tag_vni_source(df, "live", "Yahoo")

    df = _fetch_vni_data_vnstock(days=days)
    if not df.empty:
        _save_cached_vni_data(df)
        return _tag_vni_source(df, "live", "vnstock")

    cached = _load_cached_vni_data(days=days)
    if cached.empty:
        return cached
    return _tag_vni_source(cached, "cache", "VNINDEX cache")


# ─────────────────────────────────────────────────────────────
# KBS IIS API — single endpoint for breadth + foreign flow
# Replaces deprecated SSI iboard-query v2 (gone 2025) and TCBS analysis
# API (deprecated Dec 2024). KBS endpoint covers HOSE/HNX/UPCOM ~370 stocks.
# ─────────────────────────────────────────────────────────────
_KBS_FF_URL  = "https://kbbuddywts.kbsec.com.vn/iis-server/investment/rtranking/foreignTotal"
_KBS_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
# Simple TTL cache: (_data, _timestamp)
_kbs_snapshot_cache: tuple[list, datetime | None] = ([], None)
_KBS_CACHE_TTL = timedelta(minutes=5)
_CAFEF_TICKER_LIVE_REFRESH_LIMIT = 120


def _fetch_kbs_market_snapshot() -> list:
    """
    Fetch real-time market snapshot from KBS IIS API.
    Returns list of dicts: SB=ticker, EX=exchange,
    RE=reference_price, CP=current_price,
    FB=foreign_buy_vol, FS=foreign_sell_vol (in shares).
    Result is cached for 5 minutes to avoid duplicate calls.
    """
    global _kbs_snapshot_cache
    data, ts = _kbs_snapshot_cache
    if ts and (datetime.now() - ts) < _KBS_CACHE_TTL and data:
        return data
    try:
        r = requests.get(
            _KBS_FF_URL,
            params={"top": 500},
            headers=_KBS_HEADERS,
            timeout=API_TIMEOUT,
        )
        r.raise_for_status()
        fresh = r.json()
        if isinstance(fresh, list) and fresh:
            _kbs_snapshot_cache = (fresh, datetime.now())
            return fresh
    except Exception as exc:
        logger.debug("KBS snapshot: %s", exc)
    return []


def _normalize_exchange(exchange: str | None) -> str:
    value = str(exchange or "").strip().upper()
    alias = {
        "HSX": "HOSE",
        "HOSE": "HOSE",
        "HNX": "HNX",
        "UPCOM": "UPCOM",
        "UPCO": "UPCOM",
    }
    return alias.get(value, "HOSE")


def _price_limit_for_exchange(exchange: str) -> float:
    normalized = _normalize_exchange(exchange)
    return float(EXCHANGE_PRICE_LIMIT.get(normalized, EXCHANGE_PRICE_LIMIT.get("HOSE", 0.07)))


def _update_breadth_history(breadth: dict) -> None:
    if not breadth or not breadth.get("fetch_ok"):
        return

    advance = int(breadth.get("advance", 0) or 0)
    decline = int(breadth.get("decline", 0) or 0)
    unchanged = int(breadth.get("unchanged", 0) or 0)
    total = advance + decline + unchanged
    if total <= 0:
        return

    today = datetime.now().date().isoformat()
    ad_ratio = (advance / (advance + decline)) if (advance + decline) > 0 else 0.5
    row = {
        "date": today,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "advance": advance,
        "decline": decline,
        "unchanged": unchanged,
        "ceiling": int(breadth.get("ceiling", 0) or 0),
        "floor": int(breadth.get("floor", 0) or 0),
        "near_ceiling": int(breadth.get("near_ceiling", 0) or 0),
        "near_floor": int(breadth.get("near_floor", 0) or 0),
        "ad_ratio": round(float(ad_ratio), 4),
        "total": total,
    }

    _BREADTH_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _BREADTH_HISTORY_PATH.exists():
        try:
            history = pd.read_csv(_BREADTH_HISTORY_PATH)
        except Exception:
            history = pd.DataFrame()
    else:
        history = pd.DataFrame()

    if history.empty:
        updated = pd.DataFrame([row])
    else:
        history["date"] = history.get("date", pd.Series(dtype=str)).astype(str)
        history = history[history["date"] != today]
        updated = pd.concat([history, pd.DataFrame([row])], ignore_index=True)

    updated = updated.sort_values("date")
    updated.to_csv(_BREADTH_HISTORY_PATH, index=False)


def load_breadth_history(sessions: int = 10) -> pd.DataFrame:
    if not _BREADTH_HISTORY_PATH.exists():
        return pd.DataFrame()

    try:
        history = pd.read_csv(_BREADTH_HISTORY_PATH)
    except Exception as exc:
        logger.debug("load breadth history: %s", exc)
        return pd.DataFrame()

    if history.empty or "date" not in history.columns:
        return pd.DataFrame()

    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history = history.dropna(subset=["date"]).sort_values("date")
    numeric_cols = [
        "advance", "decline", "unchanged", "ceiling", "floor",
        "near_ceiling", "near_floor", "ad_ratio", "total",
    ]
    for col in numeric_cols:
        if col in history.columns:
            history[col] = pd.to_numeric(history[col], errors="coerce").fillna(0)

    if sessions > 0:
        history = history.tail(int(sessions))
    return history.reset_index(drop=True)


def _breadth_history_metrics(history: pd.DataFrame) -> dict:
    if history is None or history.empty:
        return {
            "history": [],
            "momentum": "neutral",
            "ad_line_5": 0,
            "ad_line_10": 0,
        }

    working = history.copy()
    if "advance" not in working.columns or "decline" not in working.columns:
        return {
            "history": [],
            "momentum": "neutral",
            "ad_line_5": 0,
            "ad_line_10": 0,
        }

    working["ad_diff"] = working["advance"] - working["decline"]
    working["ad_line"] = working["ad_diff"].cumsum()

    ad_line_5 = int(working["ad_diff"].tail(5).sum())
    ad_line_10 = int(working["ad_diff"].tail(10).sum())

    ad_ratios = pd.to_numeric(working.get("ad_ratio", pd.Series(dtype=float)), errors="coerce").dropna()
    momentum = "neutral"
    if len(ad_ratios) >= 10:
        recent = float(ad_ratios.tail(5).mean())
        prev = float(ad_ratios.iloc[-10:-5].mean())
        delta = recent - prev
        if delta > 0.03:
            momentum = "expanding"
        elif delta < -0.03:
            momentum = "contracting"
    elif len(ad_ratios) >= 5:
        recent = float(ad_ratios.tail(3).mean())
        prev = float(ad_ratios.head(2).mean())
        delta = recent - prev
        if delta > 0.04:
            momentum = "expanding"
        elif delta < -0.04:
            momentum = "contracting"

    history_payload = [
        {
            "date": row["date"].date().isoformat(),
            "advance": int(row.get("advance", 0) or 0),
            "decline": int(row.get("decline", 0) or 0),
            "unchanged": int(row.get("unchanged", 0) or 0),
            "ceiling": int(row.get("ceiling", 0) or 0),
            "floor": int(row.get("floor", 0) or 0),
            "ad_ratio": round(float(row.get("ad_ratio", 0.5) or 0.5), 4),
            "ad_line": int(row.get("ad_line", 0) or 0),
        }
        for _, row in working.tail(10).iterrows()
    ]

    return {
        "history": history_payload,
        "momentum": momentum,
        "ad_line_5": ad_line_5,
        "ad_line_10": ad_line_10,
    }


def fetch_market_breadth() -> dict:
    """
    Compute advance/decline from KBS IIS real-time snapshot.
    Counts stocks with CP > RE (advance), CP < RE (decline), CP == RE (unchanged).
    """
    data = _fetch_kbs_market_snapshot()
    if not data:
        return {
            "advance": 0,
            "decline": 0,
            "unchanged": 0,
            "ceiling": 0,
            "near_ceiling": 0,
            "floor": 0,
            "near_floor": 0,
            "movement": {
                "up_strong": 0,
                "up": 0,
                "flat": 0,
                "down": 0,
                "down_strong": 0,
            },
            "by_exchange": {},
            "fetch_ok": False,
        }

    advance = decline = unchanged = 0
    ceiling = near_ceiling = floor = near_floor = 0
    movement = {
        "up_strong": 0,
        "up": 0,
        "flat": 0,
        "down": 0,
        "down_strong": 0,
    }
    by_exchange: dict[str, dict[str, int]] = {}

    for item in data:
        cp = float(item.get("CP", 0) or 0)
        re = float(item.get("RE", 0) or 0)
        if re <= 0:
            continue

        exchange = _normalize_exchange(item.get("EX"))
        exchange_limit = _price_limit_for_exchange(exchange)
        pct_move = (cp - re) / re
        abs_move = abs(pct_move)
        near_cutoff = exchange_limit * 0.70
        hard_cutoff = exchange_limit * 0.97

        bucket = by_exchange.setdefault(
            exchange,
            {
                "advance": 0,
                "decline": 0,
                "unchanged": 0,
                "ceiling": 0,
                "floor": 0,
                "up_strong": 0,
                "up": 0,
                "flat": 0,
                "down": 0,
                "down_strong": 0,
            },
        )

        if pct_move > 0:
            advance += 1
            bucket["advance"] += 1
        elif pct_move < 0:
            decline += 1
            bucket["decline"] += 1
        else:
            unchanged += 1
            bucket["unchanged"] += 1

        if pct_move >= hard_cutoff:
            ceiling += 1
            bucket["ceiling"] += 1
        elif pct_move >= near_cutoff:
            near_ceiling += 1

        if pct_move <= -hard_cutoff:
            floor += 1
            bucket["floor"] += 1
        elif pct_move <= -near_cutoff:
            near_floor += 1

        if pct_move >= near_cutoff:
            movement["up_strong"] += 1
            bucket["up_strong"] += 1
        elif pct_move > 0:
            movement["up"] += 1
            bucket["up"] += 1
        elif pct_move <= -near_cutoff:
            movement["down_strong"] += 1
            bucket["down_strong"] += 1
        elif pct_move < 0:
            movement["down"] += 1
            bucket["down"] += 1
        else:
            movement["flat"] += 1
            bucket["flat"] += 1

    result = {
        "advance": advance,
        "decline": decline,
        "unchanged": unchanged,
        "ceiling": ceiling,
        "near_ceiling": near_ceiling,
        "floor": floor,
        "near_floor": near_floor,
        "movement": movement,
        "by_exchange": by_exchange,
        "fetch_ok": True,
    }
    _update_breadth_history(result)
    return result


# ─────────────────────────────────────────────────────────────
# FOREIGN FLOW
# ─────────────────────────────────────────────────────────────
def _empty_foreign_flow() -> dict:
    return {
        "net_buy_value": 0,
        "buy_value": 0,
        "sell_value": 0,
        "net_20d": 0,
        "trend_20d": "neutral",
        "session_net_proxy": 0,
        "session_trend": "neutral",
        "history_sessions": 0,
        "is_20d_proxy": False,
        "basis": "not_available",
    }


def _foreign_flow_from_snapshot_item(item: dict | None) -> dict:
    if not item:
        return _empty_foreign_flow()

    cp  = float(item.get("CP", 0) or 0)
    fb  = float(item.get("FB", 0) or 0)
    fs  = float(item.get("FS", 0) or 0)
    net = (fb - fs) * cp
    buy = fb * cp
    sel = fs * cp
    if net > 5e10:
        session_trend = "accumulate"
    elif net < -5e10:
        session_trend = "distribute"
    else:
        session_trend = "neutral"
    return {
        "net_buy_value": net,
        "buy_value":     buy,
        "sell_value":    sel,
        # Intraday snapshot has no verified 20-session continuity.
        # Keep the 20d fields neutral/unavailable and expose the session signal
        # separately so callers cannot mistake one snapshot for real 20d history.
        "net_20d":   0,
        "trend_20d": "neutral",
        "session_net_proxy": net,
        "session_trend": session_trend,
        "history_sessions": 1,
        "is_20d_proxy": True,
        "basis": "KBS snapshot | session net only",
    }


def _cached_foreign_flow_summaries(symbols: list[str], sessions: int = 20) -> dict[str, dict]:
    if not symbols:
        return {}
    try:
        from core.foreign_flow_crawler import load_cached_foreign_flow, summarize_foreign_flow_history

        cached = load_cached_foreign_flow()
    except Exception as exc:
        logger.debug("load cached foreign flow: %s", exc)
        return {}

    if cached is None or cached.empty or "ticker" not in cached.columns:
        return {}

    working = cached.copy()
    working["ticker"] = working["ticker"].astype(str).str.strip().str.upper()
    wanted = set(symbols)
    working = working[working["ticker"].isin(wanted)]
    if working.empty:
        return {}

    summaries = summarize_foreign_flow_history(working, sessions=sessions)
    return {
        symbol: summaries[symbol]
        for symbol in symbols
        if symbol in summaries
    }


def fetch_foreign_flow_tickers(
    symbols: list[str],
    *,
    sessions: int = 20,
    live_refresh_limit: int = _CAFEF_TICKER_LIVE_REFRESH_LIMIT,
    exchange_map: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Fetch foreign-flow data, preferring verified CafeF history over KBS snapshot."""
    if not symbols:
        return {}

    normalized = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    unique_symbols = list(dict.fromkeys(normalized))
    incoming_exchange_map = {
        str(symbol).strip().upper(): str(exchange).strip().upper()
        for symbol, exchange in (exchange_map or {}).items()
        if str(symbol).strip()
    }
    resolved_exchange_map = {
        symbol: incoming_exchange_map.get(symbol, TICKER_EXCHANGE.get(symbol, "HOSE"))
        for symbol in unique_symbols
    }

    history_results: dict[str, dict] = {}
    live_refresh_limit = max(0, int(live_refresh_limit or 0))
    if len(unique_symbols) > live_refresh_limit:
        history_results = _cached_foreign_flow_summaries(unique_symbols, sessions=sessions)
        logger.info(
            "Foreign-flow batch bounded for %d tickers: using %d cached CafeF summaries and snapshot fallback",
            len(unique_symbols),
            len(history_results),
        )
    else:
        try:
            from core.foreign_flow_crawler import fetch_cafef_foreign_flow_tickers

            history_results = fetch_cafef_foreign_flow_tickers(
                unique_symbols,
                exchange_map=resolved_exchange_map,
                sessions=sessions,
            )
        except Exception as exc:
            logger.debug("CafeF foreign batch: %s", exc)

    missing = [symbol for symbol in unique_symbols if symbol not in history_results]
    lookup: dict[str, dict] = {}
    if missing:
        data = _fetch_kbs_market_snapshot()
        lookup = {
            (item.get("SB", "") or "").upper(): item
            for item in data
        }
    results: dict[str, dict] = {}
    for symbol in symbols:
        symbol_upper = str(symbol).strip().upper()
        if symbol_upper in history_results:
            results[symbol] = history_results[symbol_upper]
        else:
            results[symbol] = _foreign_flow_from_snapshot_item(lookup.get(symbol_upper))
    return results


def fetch_foreign_flow_ticker(
    symbol: str,
    *,
    exchange: str | None = None,
    exchange_map: dict[str, str] | None = None,
) -> dict:
    """
    Fetch foreign buy/sell for a specific ticker.

    Returns
    -------
    dict with keys: net_buy_value, buy_value, sell_value, net_20d, trend_20d,
    session_net_proxy, session_trend, history_sessions, is_20d_proxy, basis.
    All monetary values in VND (shares × price).
    Prefers verified CafeF multi-session history and falls back to KBS intraday
    snapshot when history cannot be retrieved.
    """
    symbol = symbol.strip().upper()
    incoming_exchange_map = {
        str(item_symbol).strip().upper(): str(item_exchange).strip().upper()
        for item_symbol, item_exchange in (exchange_map or {}).items()
        if str(item_symbol).strip()
    }
    exchange = (
        incoming_exchange_map.get(symbol)
        or (str(exchange).strip().upper() if exchange else "")
        or TICKER_EXCHANGE.get(symbol, "HOSE")
    )

    try:
        from core.foreign_flow_crawler import fetch_cafef_foreign_flow_ticker

        history_result = fetch_cafef_foreign_flow_ticker(
            symbol,
            exchange=exchange,
            sessions=20,
        )
        if int(history_result.get("history_sessions", 0) or 0) > 0:
            return history_result
    except Exception as exc:
        logger.debug("CafeF foreign ticker %s: %s", symbol, exc)

    data = _fetch_kbs_market_snapshot()
    for item in data:
        if (item.get("SB", "") or "").upper() == symbol:
            return _foreign_flow_from_snapshot_item(item)
    # Ticker not found in snapshot (may be halted or not in top 500)
    return _empty_foreign_flow()


def fetch_market_foreign_flow(days: int = 20) -> dict:
    """
    Compute aggregate market foreign flow.

    Prefers cached/backfilled CafeF market history for multi-session context and
    falls back to KBS IIS snapshot when history is unavailable.
    """
    try:
        from core.foreign_flow_crawler import fetch_cafef_market_foreign_flow

        history_result = fetch_cafef_market_foreign_flow(sessions=days)
        if history_result.get("fetch_ok", False):
            return history_result
    except Exception as exc:
        logger.debug("CafeF market foreign flow: %s", exc)

    data = _fetch_kbs_market_snapshot()
    if not data:
        return {
            "net_buy": 0,
            "buy": 0,
            "sell": 0,
            "trend": "N/A",
            "fetch_ok": False,
            "net_buy_20d": 0,
            "trend_20d": "neutral",
            "history_sessions": 0,
            "signal_net_buy": 0,
            "basis": "not_available",
            "history": [],
            "history_as_of": None,
        }
    net_buy = buy = sell = 0.0
    for item in data:
        cp = float(item.get("CP", 0) or 0)
        fb = float(item.get("FB", 0) or 0)
        fs = float(item.get("FS", 0) or 0)
        net_buy += (fb - fs) * cp
        buy     += fb * cp
        sell    += fs * cp
    return {
        "net_buy":  net_buy,
        "buy":      buy,
        "sell":     sell,
        "trend":    "Mua r\u00f2ng" if net_buy > 0 else "B\u00e1n r\u00f2ng" if net_buy < 0 else "Trung t\u00ednh",
        "fetch_ok": True,
        "net_buy_20d": 0,
        "trend_20d": "neutral",
        "history_sessions": 1,
        "signal_net_buy": net_buy,
        "basis": "KBS snapshot | session net only",
        "history": [],
        "history_as_of": None,
    }


# ─────────────────────────────────────────────────────────────
# MACRO INDICATORS
# ─────────────────────────────────────────────────────────────
def fetch_macro_indicators() -> dict:
    """
    Compile macro dashboard data.

    Returns
    -------
    dict with world_markets, breadth, foreign_flow, vni_info, stale_fields.
    stale_fields: list[str] of data names that could not be fetched —
    callers should warn the user when this list is non-empty so they know
    macro_score is degraded (e.g. defaulting to neutral for missing components).
    """
    world   = fetch_world_markets()
    breadth = fetch_market_breadth()
    ff      = fetch_market_foreign_flow()
    # ── Detect stale/missing data fields ─────────────────────────────────
    # Use fetch_ok sentinel to distinguish API failure from valid zero values
    # (e.g. non-trading day breadth of 0/0 is not a stale condition).
    stale_fields: list[str] = []
    critical_symbols = ["DXY (USD Index)", "VIX", "S&P 500"]
    for sym in critical_symbols:
        if not world.get(sym):
            stale_fields.append(sym)
    if not breadth.get("fetch_ok", True):
        stale_fields.append("market_breadth")
    if not ff.get("fetch_ok", True):
        stale_fields.append("foreign_flow")
    dxy_info   = world.get("DXY (USD Index)")
    dxy_trend  = "neutral"
    if dxy_info:
        if dxy_info["pct_5d"] > 0.5:
            dxy_trend = "strong_up"
        elif dxy_info["pct_5d"] > 0.1:
            dxy_trend = "up"
        elif dxy_info["pct_5d"] < -0.5:
            dxy_trend = "strong_down"
        elif dxy_info["pct_5d"] < -0.1:
            dxy_trend = "down"

    # Derive VIX risk signal
    vix_info  = world.get("VIX")
    vix_level = "normal"
    if vix_info and vix_info["current"]:
        if vix_info["current"] > 30:
            vix_level = "fear"
        elif vix_info["current"] > 20:
            vix_level = "elevated"

    # Advance/Decline ratio
    total   = breadth["advance"] + breadth["decline"]
    ad_ratio = (breadth["advance"] / total) if total > 0 else 0.5
    breadth_history = load_breadth_history(sessions=10)
    breadth_metrics = _breadth_history_metrics(breadth_history)

    return {
        "world":        world,
        "breadth":      breadth,
        "ad_ratio":     round(ad_ratio, 3),
        "breadth_history": breadth_metrics["history"],
        "breadth_momentum": breadth_metrics["momentum"],
        "breadth_ad_line_5": breadth_metrics["ad_line_5"],
        "breadth_ad_line_10": breadth_metrics["ad_line_10"],
        "foreign_flow": ff,
        "dxy_trend":    dxy_trend,
        "vix_level":    vix_level,
        "stale_fields": stale_fields,
        "fetched_at":   datetime.now().isoformat(),
    }


def get_macro_score(macro: dict) -> tuple[float, str, list[str]]:
    """
    Convert macro dict to a 0-10 score, label, and list of stale fields.

    Returns
    -------
    (score, label, stale_fields)
      score       : float 0-10
      label       : 'bull' | 'neutral' | 'bear'
      stale_fields: list of data names that were missing/default —
                    pass these to the UI to show a warning.
    """
    score = 5.0  # neutral baseline
    stale_fields: list[str] = list(macro.get("stale_fields", []))

    # DXY: down = good for EM
    dxy_trend = macro.get("dxy_trend", "neutral")
    if dxy_trend == "strong_down":  score += 1.5
    elif dxy_trend == "down":       score += 0.75
    elif dxy_trend == "up":         score -= 0.75
    elif dxy_trend == "strong_up":  score -= 1.5

    # VIX: low = good
    vix_level = macro.get("vix_level", "normal")
    if vix_level == "fear":      score -= 2.0
    elif vix_level == "elevated": score -= 0.75

    # Foreign flow
    ff_payload = macro.get("foreign_flow", {})
    ff_net = ff_payload.get("signal_net_buy", ff_payload.get("net_buy", 0))
    if ff_net > 1e10:    score += 1.5   # Strong foreign buy (>10B VND)
    elif ff_net > 0:     score += 0.5
    elif ff_net < -1e10: score -= 1.5
    elif ff_net < 0:     score -= 0.5

    # Market breadth (0-3 score contribution within the same 0-10 macro scale)
    ad_ratio = float(macro.get("ad_ratio", 0.5) or 0.5)
    breadth = macro.get("breadth", {}) or {}
    ceiling = int(breadth.get("ceiling", 0) or 0)
    floor = int(breadth.get("floor", 0) or 0)
    breadth_momentum = str(macro.get("breadth_momentum", "neutral") or "neutral").lower()

    breadth_score = 0.0
    if ad_ratio >= 0.65:
        breadth_score += 2.0
    elif ad_ratio >= 0.55:
        breadth_score += 1.0
    elif ad_ratio <= 0.35:
        breadth_score -= 2.0
    elif ad_ratio <= 0.45:
        breadth_score -= 1.0

    if ceiling > floor:
        breadth_score += 1.0
    elif floor > ceiling:
        breadth_score -= 1.0

    if breadth_momentum == "expanding":
        breadth_score += 0.5
    elif breadth_momentum == "contracting":
        breadth_score -= 0.5

    score += max(-3.0, min(3.0, breadth_score))

    # ── S&P 500 — global risk-on/risk-off signal ──────────────────────────
    # S&P 500 and VN-Index show moderate positive correlation (~0.4-0.6).
    # A sustained S&P rally signals global risk appetite and drives EM inflows.
    # A S&P crash (>-2% in 5d) triggers foreign outflows from VN within 1-3 days.
    sp500 = macro.get("world", {}).get("S&P 500")
    if sp500:
        sp5_pct = sp500.get("pct_5d", 0) or 0
        if sp5_pct > 2.0:    score += 0.50   # global risk-on
        elif sp5_pct > 0.5:  score += 0.25
        elif sp5_pct < -2.0: score -= 0.75   # risk-off: faster VN reaction
        elif sp5_pct < -0.5: score -= 0.25

    # ── CSI 300 — China's market, major driver for VN sectors ────────────
    # CSI 300 has the HIGHEST regional correlation with VN-Index (~0.55-0.70).
    # Key channels: commodity pricing (steel/HPG, coal, chemicals), FDI from
    # Chinese firms, and VN export demand from Chinese buyers.
    csi300 = macro.get("world", {}).get("CSI 300 (CN)")
    if csi300:
        csi_pct = csi300.get("pct_5d", 0) or 0
        if csi_pct > 2.0:    score += 0.50   # China rally → positive for VN
        elif csi_pct > 0.5:  score += 0.25
        elif csi_pct < -2.0: score -= 0.50   # China selloff → VN sells
        elif csi_pct < -0.5: score -= 0.25

    score = max(0.0, min(10.0, score))

    if score >= 7.5:    label = "bull"
    elif score >= 4.5:  label = "neutral"
    else:               label = "bear"

    return round(score, 2), label, stale_fields

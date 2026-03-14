"""
Data fetcher — SSI iBoard direct client with caching.
All market data calls go through this module. SSI is the sole data source.
"""
import time
import json
import hashlib
import logging
import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

_log = logging.getLogger("data_fetcher")

try:
    from vnstock import Vnstock
    VNSTOCK_AVAILABLE = True
except ImportError:
    VNSTOCK_AVAILABLE = False

try:
    from modules import ssi_fetcher
    SSI_AVAILABLE = True
except ImportError:
    SSI_AVAILABLE = False

from config import CACHE_DIR, PRICE_REFRESH_SECONDS


# ─── CACHE ────────────────────────────────────────────────────────────────────

def _cache_key(fn_name: str, *args) -> Path:
    key = hashlib.md5(f"{fn_name}:{'|'.join(str(a) for a in args)}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{fn_name}_{key}.json"


def _read_cache(path: Path, ttl_seconds: int) -> Optional[dict]:
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl_seconds:
        return None
    with open(path) as f:
        return json.load(f)


def _write_cache(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, default=str)


# ─── MAIN DATA CLASS ─────────────────────────────────────────────────────────

class MarketData:
    """Single entry point for all market data in the app."""

    def __init__(self):
        pass

    # ── REAL-TIME QUOTE ───────────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> dict:
        """Return latest quote dict: {symbol, price, change, pct_change, volume, ...}"""
        if not symbol:
            return self._empty_quote("")
        cache_path = _cache_key("quote", symbol)
        cached = _read_cache(cache_path, ttl_seconds=PRICE_REFRESH_SECONDS)
        if cached:
            return cached

        result = self._fetch_quote(symbol)
        if result:
            _write_cache(cache_path, result)
        return result or self._empty_quote(symbol)

    def get_quotes_batch(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple symbols. Returns {symbol: quote_dict}"""
        if SSI_AVAILABLE and symbols:
            sym_set = {s.upper() for s in symbols}
            if sym_set.issubset(ssi_fetcher._VN30_SYMBOLS):
                try:
                    batch = ssi_fetcher.fetch_vn30_batch()
                    if batch and len(batch) >= 5:
                        results = {s: batch.get(s.upper(), self._empty_quote(s)) for s in symbols}
                        # Cache individual quotes
                        for sym, q in results.items():
                            cp = _cache_key("quote", sym)
                            _write_cache(cp, q)
                        return results
                except Exception as e:
                    _log.warning("[quotes_batch] VN30 batch failed: %s", e)
        results = {}
        for sym in symbols:
            results[sym] = self.get_quote(sym)
        return results

    def _fetch_quote(self, symbol: str) -> Optional[dict]:
        if SSI_AVAILABLE:
            try:
                q = ssi_fetcher.fetch_quote(symbol)
                if q and q.get("price", 0) > 0:
                    return q
            except Exception as e:
                _log.warning("[quote] SSI iBoard %s: %s", symbol, e)
        return self._empty_quote(symbol)

    def _empty_quote(self, symbol: str) -> dict:
        return {
            "symbol": symbol, "price": 0, "open": 0, "high": 0, "low": 0,
            "volume": 0, "change": 0, "pct_change": 0, "time": "N/A",
        }

    # ── HISTORICAL OHLCV ─────────────────────────────────────────────────────

    def get_history(self, symbol: str, days: int = 252) -> pd.DataFrame:
        """Return OHLCV DataFrame, index = date."""
        if not symbol:
            return pd.DataFrame()
        cache_path = _cache_key("history", symbol, days)
        cached = _read_cache(cache_path, ttl_seconds=3600)  # 1hr cache for history
        if cached:
            try:
                records = cached.get("records")
                if records:
                    df = pd.DataFrame(records)
                    idx_col = cached.get("index_col", "time")
                    if idx_col in df.columns:
                        df[idx_col] = pd.to_datetime(df[idx_col])
                        df = df.set_index(idx_col)
                    if not df.empty:
                        return df
            except Exception:
                pass  # corrupt cache — refetch

        df = self._fetch_history(symbol, days)
        if df is not None and not df.empty:
            # Serialize as records to avoid DatetimeIndex → JSON TypeError
            cache_records = df.reset_index()
            idx_col = df.index.name or "time"
            _write_cache(cache_path, {
                "records":   cache_records.to_dict(orient="records"),
                "index_col": idx_col,
            })
        return df if df is not None else pd.DataFrame()

    def _fetch_history(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        if SSI_AVAILABLE:
            try:
                df = ssi_fetcher.fetch_history(symbol, days)
                if df is not None and not df.empty and len(df) >= 5:
                    return df
            except Exception as e:
                _log.warning("[history] SSI iBoard %s: %s", symbol, e)
        return pd.DataFrame()

    # ── FINANCIAL RATIOS ─────────────────────────────────────────────────────

    def get_financials(self, symbol: str) -> dict:
        """Return basic financial ratios: P/E, P/B, ROE, debt/equity, etc."""
        if not symbol:
            return {}
        cache_path = _cache_key("financials", symbol)
        cached = _read_cache(cache_path, ttl_seconds=86400)  # 24hr cache
        if cached:
            return cached

        result = self._fetch_financials(symbol)
        if result:
            _write_cache(cache_path, result)
        return result or {}

    def _fetch_financials(self, symbol: str) -> dict:
        if SSI_AVAILABLE:
            try:
                result = ssi_fetcher.fetch_financials(symbol)
                if result and result.get("pe", 0) + result.get("pb", 0) + result.get("roe", 0) > 0:
                    return result
            except Exception as e:
                _log.warning("[financials] SSI iBoard %s: %s", symbol, e)
        return {}

    # ── ANALYST TARGET ────────────────────────────────────────────────────────

    def get_analyst_target(self, symbol: str) -> dict:
        """Return analyst consensus: {target_price, upside_pct, rating}"""
        # This data is hard to get programmatically for VN stocks.
        # In production, scrape from SSI Research or VCSC.
        # For now, return empty — user can manually set in UI.
        return {"target_price": None, "upside_pct": None, "rating": "N/A"}

    # ── INTRADAY OHLCV ─────────────────────────────────────────────

    def get_history_intraday(
        self, symbol: str, resolution: str = "15", days: int = 5
    ) -> pd.DataFrame:
        """
        Return intraday OHLCV DataFrame.
        resolution: '15' = 15-min bars, '60' = 1-hour bars.
        TTL: 60 s (very fresh for live trading).
        """
        if not symbol:
            return pd.DataFrame()
        cache_path = _cache_key("intraday", symbol, resolution, days)
        cached = _read_cache(cache_path, ttl_seconds=60)
        if cached:
            try:
                records = cached.get("records")
                if records:
                    df = pd.DataFrame(records)
                    idx_col = cached.get("index_col", "time")
                    if idx_col in df.columns:
                        df[idx_col] = pd.to_datetime(df[idx_col])
                        df = df.set_index(idx_col)
                    if not df.empty:
                        return df
            except Exception:
                pass

        if SSI_AVAILABLE:
            try:
                df = ssi_fetcher.fetch_intraday(symbol, resolution, days)
                if df is not None and not df.empty:
                    cache_records = df.reset_index()
                    idx_col = df.index.name or "time"
                    _write_cache(cache_path, {
                        "records":   cache_records.to_dict(orient="records"),
                        "index_col": idx_col,
                    })
                    return df
            except Exception as e:
                _log.warning("[intraday] SSI iBoard %s: %s", symbol, e)

        return pd.DataFrame()

    # ── VNINDEX ───────────────────────────────────────────────────────────────

    def get_index(self, index: str = "VNINDEX") -> dict:
        return self.get_quote(index)

    def get_index_history(self, index: str = "VNINDEX", days: int = 252) -> pd.DataFrame:
        return self.get_history(index, days)


# Singleton
_md = MarketData()


def get_quote(symbol: str) -> dict:
    return _md.get_quote(symbol)

def get_quotes_batch(symbols: list) -> dict:
    return _md.get_quotes_batch(symbols)

def get_history(symbol: str, days: int = 252) -> pd.DataFrame:
    return _md.get_history(symbol, days)

def get_financials(symbol: str) -> dict:
    return _md.get_financials(symbol)

def get_index_history(index: str = "VNINDEX", days: int = 252) -> pd.DataFrame:
    return _md.get_index_history(index, days)

def get_history_intraday(symbol: str, resolution: str = "15", days: int = 5) -> pd.DataFrame:
    return _md.get_history_intraday(symbol, resolution, days)

def get_catalyst_calendar(symbol: str) -> list:
    """Return catalyst events for symbol from config.CATALYST_CALENDAR (static)."""
    from config import CATALYST_CALENDAR
    return CATALYST_CALENDAR.get(symbol.upper(), [])

def get_foreign_flow(symbol: str) -> dict:
    """Fetch foreign buy/sell for one symbol via SSI; empty dict on failure."""
    if SSI_AVAILABLE:
        try:
            return ssi_fetcher.fetch_foreign_flow(symbol)
        except Exception as e:
            _log.error("[foreign_flow] %s: %s", symbol, e)
    return {}

def get_foreign_flow_batch(symbols: list) -> list:
    """Fetch foreign flow for a list of symbols; returns list of non-empty dicts."""
    results = []
    for sym in symbols:
        flow = get_foreign_flow(sym)
        if flow:
            results.append(flow)
    return results


def get_corporate_actions(symbol: str, months: int = 12) -> list:
    """Return upcoming corporate actions (dividends, AGM, rights) for symbol. 4h TTL cache."""
    if not symbol:
        return []
    cache_path = _cache_key("corporate_actions", symbol, months)
    cached = _read_cache(cache_path, ttl_seconds=4 * 3600)
    if cached and isinstance(cached.get("items"), list):
        return cached["items"]
    if SSI_AVAILABLE:
        try:
            result = ssi_fetcher.fetch_corporate_actions(symbol, look_ahead_months=months)
            _write_cache(cache_path, {"items": result})
            return result
        except Exception as e:
            _log.error("[corporate_actions] %s: %s", symbol, e)
    return []


def get_company_news(symbol: str, days: int = 30) -> list:
    """Return recent company news for symbol. 15-min TTL cache."""
    if not symbol:
        return []
    cache_path = _cache_key("company_news", symbol, days)
    cached = _read_cache(cache_path, ttl_seconds=900)
    if cached and isinstance(cached.get("items"), list):
        return cached["items"]
    if SSI_AVAILABLE:
        try:
            result = ssi_fetcher.fetch_company_news(symbol, days=days)
            _write_cache(cache_path, {"items": result})
            return result
        except Exception as e:
            _log.error("[company_news] %s: %s", symbol, e)
    return []


def get_company_profile(symbol: str) -> dict:
    """Return company profile for symbol. 24h TTL cache."""
    if not symbol:
        return {}
    cache_path = _cache_key("company_profile", symbol)
    cached = _read_cache(cache_path, ttl_seconds=86400)
    if cached and cached.get("name"):
        return cached
    if SSI_AVAILABLE:
        try:
            result = ssi_fetcher.fetch_company_profile(symbol)
            if result:
                _write_cache(cache_path, result)
            return result
        except Exception as e:
            _log.error("[company_profile] %s: %s", symbol, e)
    return {}

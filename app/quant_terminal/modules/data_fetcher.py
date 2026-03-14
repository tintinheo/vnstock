"""
Data fetcher — wraps vnstock (SSI source) with caching and fallback.
All market data calls go through this module.
"""
import time
import json
import hashlib
import datetime as dt
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

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

from config import DATA_SOURCE, CACHE_DIR, PRICE_REFRESH_SECONDS


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

    def __init__(self, source: str = DATA_SOURCE):
        self.source = source
        self._stock = None

    def _get_stock(self, symbol: str, source: str = None):
        if VNSTOCK_AVAILABLE:
            return Vnstock().stock(symbol=symbol, source=source or self.source)
        return None

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
        results = {}
        for sym in symbols:
            results[sym] = self.get_quote(sym)
        return results

    def _fetch_quote(self, symbol: str) -> Optional[dict]:
        # ── Primary: SSI iBoard direct ────────────────────────────────────────
        if SSI_AVAILABLE:
            try:
                q = ssi_fetcher.fetch_quote(symbol)
                if q and q.get("price", 0) > 0:
                    return q
            except Exception as e:
                print(f"[MarketData] SSI quote {symbol}: {e}")

        if not VNSTOCK_AVAILABLE:
            return self._empty_quote(symbol)
        # ── Fallback: vnstock source waterfall ────────────────────────────────
        # SSI is NOT a valid vnstock source
        _fallbacks = ["VCI", "TCBS", "KBS", "MSN"]
        sources = list(dict.fromkeys([self.source] + _fallbacks))
        for source in sources:
            try:
                stk = self._get_stock(symbol, source)
                df  = stk.quote.history(
                    start=(dt.date.today() - dt.timedelta(days=7)).strftime("%Y-%m-%d"),
                    end=dt.date.today().strftime("%Y-%m-%d"),
                    interval="1D"
                )
                if df is None or df.empty:
                    continue
                df.columns = [c.lower() for c in df.columns]
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                # Normalize: SSI may return raw VND (e.g. 26950); VCI returns thousands (26.95)
                if "close" in df.columns and df["close"].median() > 1000:
                    for col in ["open", "high", "low", "close"]:
                        if col in df.columns:
                            df[col] = df[col] / 1000.0
                if "time" in df.columns:
                    df = df.sort_values("time")
                else:
                    df = df.sort_index()
                last = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else last
                price      = float(last.get("close", 0))
                prev_close = float(prev.get("close", price))
                change     = price - prev_close
                pct        = change / prev_close * 100 if prev_close else 0
                return {
                    "symbol":     symbol,
                    "price":      price,
                    "open":       float(last.get("open",   price)),
                    "high":       float(last.get("high",   price)),
                    "low":        float(last.get("low",    price)),
                    "volume":     float(last.get("volume", 0)),
                    "change":     change,
                    "pct_change": pct,
                    "time":       str(last.name) if hasattr(last, "name") else str(dt.datetime.now()),
                    "source":     source,
                }
            except Exception as e:
                print(f"[MarketData] quote {symbol} source={source}: {e}")
                continue
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
        # ── Primary: SSI iBoard direct ────────────────────────────────────────
        if SSI_AVAILABLE:
            try:
                df = ssi_fetcher.fetch_history(symbol, days)
                if df is not None and not df.empty and len(df) >= 5:
                    return df
            except Exception as e:
                print(f"[MarketData] SSI history {symbol}: {e}")

        if not VNSTOCK_AVAILABLE:
            return self._generate_mock_history(symbol, days)
        # ── Fallback: vnstock source waterfall ────────────────────────────────
        end   = dt.date.today()
        start = end - dt.timedelta(days=days + 30)  # extra buffer for weekends
        # Build deduplicated source list — SSI is NOT a valid vnstock source
        _fallbacks = ["VCI", "TCBS", "KBS", "MSN"]
        sources = list(dict.fromkeys([self.source] + _fallbacks))
        for source in sources:
            try:
                stk = self._get_stock(symbol, source)
                df  = stk.quote.history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    interval="1D"
                )
                if df is None or df.empty:
                    continue
                df.columns = [c.lower() for c in df.columns]
                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                # Normalize: VCI returns 15.10 (thousands), SSI may return 15100 (raw VND)
                if "close" in df.columns and df["close"].median() > 1000:
                    for col in ["open", "high", "low", "close"]:
                        if col in df.columns:
                            df[col] = df[col] / 1000.0
                # Set time column as DatetimeIndex
                if "time" in df.columns:
                    df = df.sort_values("time").set_index("time")
                df.index = pd.to_datetime(df.index)
                return df.tail(days)
            except Exception as e:
                print(f"[MarketData] history {symbol} source={source}: {e}")
                continue
        return self._generate_mock_history(symbol, days)

    def _generate_mock_history(self, symbol: str, days: int) -> pd.DataFrame:
        """Generate plausible mock data for demo/offline mode."""
        seed = sum(ord(c) for c in symbol)
        np.random.seed(seed)
        end = dt.date.today()
        dates = pd.bdate_range(end=end, periods=days)
        base = 15000 + seed % 50000
        returns = np.random.normal(0.0003, 0.015, len(dates))
        closes = base * np.cumprod(1 + returns)
        opens  = closes * (1 + np.random.normal(0, 0.005, len(dates)))
        highs  = np.maximum(closes, opens) * (1 + np.abs(np.random.normal(0, 0.008, len(dates))))
        lows   = np.minimum(closes, opens) * (1 - np.abs(np.random.normal(0, 0.008, len(dates))))
        vols   = np.random.randint(500_000, 5_000_000, len(dates)).astype(float)
        df = pd.DataFrame({
            "open": opens, "high": highs, "low": lows, "close": closes, "volume": vols
        }, index=dates)
        return df

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
        if not VNSTOCK_AVAILABLE:
            return {}
        try:
            stk = self._get_stock(symbol)
            ratios = stk.finance.ratio(period="year", lang="en", dropna=True)
            if ratios is None or ratios.empty:
                return {}
            last = ratios.iloc[-1]
            return {
                "pe":         float(last.get("priceToEarning", 0) or 0),
                "pb":         float(last.get("priceToBook", 0) or 0),
                "roe":        float(last.get("roe", 0) or 0),
                "roa":        float(last.get("roa", 0) or 0),
                "debt_equity": float(last.get("debtOnEquity", 0) or 0),
                "ev_ebitda":  float(last.get("ev_ebitda", 0) or 0),
                "period":     str(last.name) if hasattr(last, "name") else "",
            }
        except Exception as e:
            print(f"[MarketData] financials error {symbol}: {e}")
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
                print(f"[MarketData] SSI intraday {symbol}: {e}")

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

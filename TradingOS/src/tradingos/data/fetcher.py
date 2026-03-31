"""Data fetcher: SSI iboard-api (primary) + DNSE fallback.

No vnstock dependency. Endpoints from SSI_HARrequestLogs.txt:
  OHLCV daily  : GET {ssi_base}/statistics/charts/history?resolution=1D&symbol=X&from=TS&to=TS
  OHLCV 5m     : GET {ssi_base}/statistics/charts/history?resolution=5&symbol=X&from=TS&to=TS
  Quote        : GET https://iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN
  Universe     : GET https://iboard-query.ssi.com.vn/stock/group/{HOSE|HNX}
  FOL stats    : GET {ssi_base}/statistics/company/ssmi/stock-info?symbol=X&fromDate=MM/DD/YYYY&...
DNSE fallback:
  OHLCV daily  : GET {dnse_base}/ohlcs/stock?symbol=X&from=TS&to=TS&resolution=D
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import requests

from ..utils.config import cfg
from ..utils.logging import log
from .cache import cache
from .normalizer import clean_ohlcv

_SSI_QUERY = "https://iboard-query.ssi.com.vn"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingOS/1.1",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://iboard.ssi.com.vn",
    "Referer": "https://iboard.ssi.com.vn/",
}


def _make_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update(_HEADERS)
    return sess


_session = _make_session()


def _get(url: str, params: dict | None = None, timeout: int = 15, retries: int = 3) -> dict | list:
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 400:
                log.debug(f"SSI 400 for {url}")
                return {}
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning(f"Request timeout ({timeout}s): {url}")
            return {}
        except Exception as e:
            if attempt == retries - 1:
                log.debug(f"Request failed: {url} -- {e}")
                return {}
            time.sleep(1.5 ** attempt)
    return {}


def _to_ts(d: date) -> int:
    """Convert a date to UTC midnight Unix timestamp."""
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def _bars_from_payload(payload: dict) -> pd.DataFrame:
    """Convert SSI/DNSE {t,o,h,l,c,v} payload to clean OHLCV DataFrame."""
    t = payload.get("t")
    if not t:
        return pd.DataFrame()
    df = pd.DataFrame({
        "date":   pd.to_datetime(t, unit="s", utc=True).dt.tz_convert("Asia/Ho_Chi_Minh").dt.date,
        "open":   pd.to_numeric(payload.get("o", []), errors="coerce"),
        "high":   pd.to_numeric(payload.get("h", []), errors="coerce"),
        "low":    pd.to_numeric(payload.get("l", []), errors="coerce"),
        "close":  pd.to_numeric(payload.get("c", []), errors="coerce"),
        "volume": pd.to_numeric(payload.get("v", []), errors="coerce"),
    })
    return clean_ohlcv(df.dropna(subset=["close"]).reset_index(drop=True))


# ── SSI primary OHLCV ─────────────────────────────────────────────────────────

def _fetch_ohlcv_ssi(ticker: str, start: date, end: date) -> pd.DataFrame:
    url = f"{cfg.ssi_base}/statistics/charts/history"
    params = {
        "resolution": "1D",
        "symbol": ticker,
        "from": _to_ts(start),
        "to": _to_ts(end) + 86400,
    }
    try:
        raw = _get(url, params, timeout=20)
        if not raw:
            return pd.DataFrame()
        # Response may be {"data": {t,o,h,l,c,v}} or flat {t,o,h,l,c,v}
        payload = raw.get("data", raw) if isinstance(raw, dict) else {}
        return _bars_from_payload(payload)
    except Exception as e:
        log.warning(f"SSI OHLCV failed for {ticker}: {e}")
        return pd.DataFrame()


# ── DNSE fallback OHLCV ───────────────────────────────────────────────────────

def _fetch_ohlcv_dnse(ticker: str, start: date, end: date) -> pd.DataFrame:
    try:
        url = f"{cfg.dnse_base}/ohlcs/stock"
        params = {
            "symbol": ticker,
            "from": _to_ts(start),
            "to": _to_ts(end) + 86400,
            "resolution": "D",
        }
        raw = _get(url, params, timeout=20)
        payload = raw.get("data", raw) if isinstance(raw, dict) else raw
        if isinstance(payload, dict):
            return _bars_from_payload(payload)
        return pd.DataFrame()
    except Exception as e:
        log.warning(f"DNSE OHLCV failed for {ticker}: {e}")
        return pd.DataFrame()


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_ohlcv(
    ticker: str,
    days: int | None = None,
    start: date | None = None,
    end: date | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Fetch OHLCV for a ticker. Uses cache first, then SSI, then DNSE.

    Returns DataFrame with columns: date, open, high, low, close, volume
    """
    ticker = ticker.strip().upper()
    end = end or date.today()
    if start is None:
        history_days = days or int(cfg.get("data", "history_days", default=400))
        start = end - timedelta(days=int(history_days * 1.4))

    if use_cache:
        cached = cache.get_ohlcv(ticker, start, end)
        if not cached.empty and len(cached) > 50:
            return cached

    df = _fetch_ohlcv_ssi(ticker, start, end)
    if df.empty:
        log.debug(f"SSI empty for {ticker} -- trying DNSE")
        df = _fetch_ohlcv_dnse(ticker, start, end)

    if not df.empty:
        cache.put_ohlcv(ticker, df)
        log.info(f"Fetched {len(df)} bars for {ticker}")
    else:
        log.debug(f"No OHLCV data for {ticker}")

    return df


def fetch_multiple_ohlcv(
    tickers: list[str],
    days: int = 400,
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for multiple tickers; returns dict ticker→DataFrame."""
    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            result[ticker] = fetch_ohlcv(ticker, days=days)
        except Exception as e:
            log.warning(f"Failed to fetch {ticker}: {e}")
            result[ticker] = pd.DataFrame()
    return result


def fetch_universe(exchange: str = "HOSE") -> list[str]:
    """
    Fetch listed ticker symbols via SSI iboard-query.
    Endpoint: GET https://iboard-query.ssi.com.vn/stock/group/{HOSE|HNX}
    """
    exchange = exchange.strip().upper()
    try:
        url = f"{_SSI_QUERY}/stock/group/{exchange}"
        raw = _get(url, timeout=20)

        items: list = []
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("data", raw.get("items", raw.get(exchange, [])))
            if not isinstance(items, list):
                items = []

        tickers: list[str] = []
        for item in items:
            if isinstance(item, dict):
                sym = (
                    item.get("stockNo") or item.get("s") or
                    item.get("symbol") or item.get("ticker") or ""
                ).strip().upper()
            elif isinstance(item, str):
                sym = item.strip().upper()
            else:
                continue
            if sym and 2 <= len(sym) <= 5:
                tickers.append(sym)

        if tickers:
            log.info(f"Universe {exchange}: {len(tickers)} tickers")
            return tickers

        log.warning(f"SSI universe empty for {exchange} -- using fallback")
    except Exception as e:
        log.warning(f"Universe fetch failed for {exchange}: {e}")

    return _fallback_universe()


def _fallback_universe() -> list[str]:
    """Minimal fallback universe (liquid HOSE tickers)."""
    return [
        "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "VPB", "HDB", "STB", "EIB",
        "HPG", "HSG", "NKG", "HCM", "SSI", "VND", "FPT", "VNM", "MSN", "VIC",
        "VHM", "NVL", "PDR", "DXG", "KDH", "PLX", "GAS", "PVD", "DCM", "PVT",
        "VRE", "MWG", "PNJ", "REE", "DHG", "IMP", "GMD", "HAX", "CTR", "SAB",
        "DGC", "DGW", "FRT", "CMG", "VCI", "VIX", "SHS", "BSI", "AGM", "CRE",
    ]


def fetch_foreign_flow(ticker: str, days: int = 20) -> pd.DataFrame:
    """
    Fetch foreign buy/sell data via SSI statistics/company/ssmi/stock-info.
    Date format required by SSI: MM/DD/YYYY
    Returns DataFrame with columns: date, fol_buy, fol_sell, fol_net
    """
    end_d = date.today()
    start_d = end_d - timedelta(days=max(days * 2, 40))
    try:
        url = f"{cfg.ssi_base}/statistics/company/ssmi/stock-info"
        params = {
            "symbol": ticker.upper(),
            "page": 1,
            "pageSize": days + 10,
            "fromDate": start_d.strftime("%m/%d/%Y"),
            "toDate": end_d.strftime("%m/%d/%Y"),
        }
        raw = _get(url, params, timeout=15)
        items: list = []
        if isinstance(raw, dict):
            items = raw.get("data", raw.get("items", []))
            if isinstance(items, dict):
                items = items.get("data", [])
        if not isinstance(items, list) or not items:
            return pd.DataFrame(columns=["date", "fol_buy", "fol_sell", "fol_net"])

        rows = []
        for item in items:
            if not isinstance(item, dict):
                continue
            d_str = (item.get("tradingDate") or item.get("date") or
                     item.get("TradingDate") or "")
            try:
                d = pd.to_datetime(d_str).date()
            except Exception:
                continue
            buy  = float(item.get("foreignBuyVolume") or item.get("buyForeignQtty") or
                         item.get("frBuyVol") or 0)
            sell = float(item.get("foreignSellVolume") or item.get("sellForeignQtty") or
                         item.get("frSellVol") or 0)
            rows.append({"date": d, "fol_buy": buy, "fol_sell": sell, "fol_net": buy - sell})

        if rows:
            return (pd.DataFrame(rows)
                    .sort_values("date")
                    .tail(days)
                    .reset_index(drop=True))
    except Exception as e:
        log.debug(f"Foreign flow fetch failed for {ticker}: {e}")

    return pd.DataFrame(columns=["date", "fol_buy", "fol_sell", "fol_net"])


def fetch_intraday_5m(ticker: str) -> pd.DataFrame:
    """Fetch intraday 5-minute OHLCV for today via SSI chart history."""
    today = date.today()
    try:
        url = f"{cfg.ssi_base}/statistics/charts/history"
        params = {
            "resolution": "5",
            "symbol": ticker.upper(),
            "from": _to_ts(today),
            "to": _to_ts(today) + 86400,
        }
        raw = _get(url, params, timeout=15)
        payload = raw.get("data", raw) if isinstance(raw, dict) else {}
        return _bars_from_payload(payload)
    except Exception as e:
        log.debug(f"Intraday 5m fetch failed for {ticker}: {e}")
    return pd.DataFrame()


def fetch_quote(ticker: str) -> dict:
    """
    Fetch real-time quote snapshot via SSI iboard-query.
    Endpoint: GET https://iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN
    """
    try:
        url = f"{_SSI_QUERY}/stock/{ticker.upper()}"
        raw = _get(url, params={"boardId": "MAIN"}, timeout=10)
        data = raw.get("data", raw) if isinstance(raw, dict) else {}
        if isinstance(data, list) and data:
            data = data[0]
        return data if isinstance(data, dict) else {}
    except Exception as e:
        log.debug(f"Quote fetch failed for {ticker}: {e}")
    return {}

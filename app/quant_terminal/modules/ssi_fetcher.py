"""
SSI iBoard direct API client.
All prices returned are in thousands-VND (internal convention).
  • /stock/{sym}?boardId=MAIN   → raw VND fields → divide by 1000
  • /statistics/charts/history  → already thousands-VND
  • /stock/group/VN30           → raw VND fields → divide by 1000
"""
import logging
import datetime as dt
import time as _time
from typing import Optional

import requests
import pandas as pd

_log = logging.getLogger("ssi_fetcher")

_QUERY_BASE = "https://iboard-query.ssi.com.vn"
_API_BASE   = "https://iboard-api.ssi.com.vn"

_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "vi",
    "Referer":         "https://iboard.ssi.com.vn/",
    "Origin":          "https://iboard.ssi.com.vn",
    "device-id":       "0116B7B1-976D-437A-AA2C-C72FC3E6F956",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

_TIMEOUT = 10  # seconds
_BASE_DELAY = 0.35   # minimum seconds between sequential SSI calls (H-01: ≤3 req/s)

# ── VN30 symbols (current composition) ───────────────────────────────────────
_VN30_SYMBOLS: set = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SSI", "STB", "TCB", "TPB",
    "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE", "VSH", "VCI",
}


def _get(url: str, params: dict = None) -> Optional[dict]:
    """GET with logging; returns parsed JSON or None."""
    try:
        r = _SESSION.get(url, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _log.warning("SSI GET %s: %s", url, e)
        return None


def _get_with_backoff(url: str, params: dict = None, max_retries: int = 3) -> Optional[dict]:
    """
    GET with exponential backoff on HTTP 429 / network errors (H-01 fix).
    Protects against SSI IP-level banning from >10 req/3s.
    """
    for attempt in range(max_retries):
        try:
            r = _SESSION.get(url, params=params, timeout=_TIMEOUT)
            if r.status_code == 429:
                wait = _BASE_DELAY * (2 ** attempt)
                _log.warning("SSI rate-limit (429) — waiting %.1fs before retry %d", wait, attempt + 1)
                _time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt < max_retries - 1:
                _time.sleep(_BASE_DELAY * (2 ** attempt))
            else:
                _log.warning("SSI GET %s failed after %d retries: %s", url, max_retries, e)
    return None


def _raw_to_k(raw_vnd) -> float:
    """Convert raw VND integer to thousands-VND float."""
    try:
        return float(raw_vnd) / 1000.0
    except (TypeError, ValueError):
        return 0.0


# ── REAL-TIME QUOTE ───────────────────────────────────────────────────────────

def fetch_quote(symbol: str) -> Optional[dict]:
    """Fetch live quote for one symbol. Returns dict with prices in thousands-VND."""
    data = _get_with_backoff(f"{_QUERY_BASE}/stock/{symbol.upper()}", params={"boardId": "MAIN"})
    if not data or data.get("code") != "SUCCESS":
        return None
    d = data.get("data") or {}
    if not d:
        return None

    matched = _raw_to_k(d.get("matchedPrice") or d.get("refPrice") or 0)
    if matched <= 0:
        return None

    ref       = _raw_to_k(d.get("refPrice", 0))
    change    = matched - ref
    pct       = (change / ref * 100) if ref > 0 else 0.0

    return {
        "symbol":        symbol.upper(),
        "price":         matched,
        "open":          _raw_to_k(d.get("openPrice",  matched)),
        "high":          _raw_to_k(d.get("highest",    matched)),
        "low":           _raw_to_k(d.get("lowest",     matched)),
        "volume":        float(d.get("nmTotalTradedQty", 0) or 0),
        "change":        round(change, 3),
        "pct_change":    round(pct, 2),
        "ref_price":     ref,
        "ceiling":       _raw_to_k(d.get("ceiling", 0)),
        "floor":         _raw_to_k(d.get("floor", 0)),
        "avg_price":     _raw_to_k(d.get("avgPrice", matched)),
        "time":          d.get("tradingDate", dt.date.today().isoformat()),
        "session":       d.get("session", ""),
        "foreign_buy":   float(d.get("buyForeignQtty",  0) or 0),
        "foreign_sell":  float(d.get("sellForeignQtty", 0) or 0),
        "source":        "SSI-iBoard",
    }


def fetch_vn30_batch() -> dict:
    """Fetch live quotes for all VN30 stocks in one call. Returns {symbol: quote_dict}."""
    data = _get_with_backoff(f"{_QUERY_BASE}/stock/group/VN30")
    if not data or data.get("code") != "SUCCESS":
        return {}
    items = data.get("data") or []
    result = {}
    for d in items:
        sym = d.get("stockSymbol", "").upper()
        if not sym:
            continue
        matched = _raw_to_k(d.get("matchedPrice") or d.get("refPrice") or 0)
        if matched <= 0:
            continue
        ref    = _raw_to_k(d.get("refPrice", 0))
        change = matched - ref
        pct    = (change / ref * 100) if ref > 0 else 0.0
        result[sym] = {
            "symbol":       sym,
            "price":        matched,
            "open":         _raw_to_k(d.get("openPrice",  matched)),
            "high":         _raw_to_k(d.get("highest",    matched)),
            "low":          _raw_to_k(d.get("lowest",     matched)),
            "volume":       float(d.get("nmTotalTradedQty", 0) or 0),
            "change":       round(change, 3),
            "pct_change":   round(pct, 2),
            "ref_price":    ref,
            "ceiling":      _raw_to_k(d.get("ceiling", 0)),
            "floor":        _raw_to_k(d.get("floor", 0)),
            "foreign_buy":  float(d.get("buyForeignQtty",  0) or 0),
            "foreign_sell": float(d.get("sellForeignQtty", 0) or 0),
            "source":       "SSI-iBoard-VN30",
        }
    return result


# ── HISTORICAL OHLCV ─────────────────────────────────────────────────────────

def fetch_history(symbol: str, days: int = 252) -> pd.DataFrame:
    """
    Fetch daily OHLCV history. Returns DataFrame indexed by datetime.
    Prices are already in thousands-VND from the SSI charts/history endpoint.
    """
    to_ts   = int(_time.time())
    from_ts = to_ts - int(days * 1.5 * 86400)  # extra buffer for weekends/holidays
    data = _get_with_backoff(
        f"{_API_BASE}/statistics/charts/history",
        params={"resolution": "1D", "symbol": symbol.upper(),
                "from": from_ts, "to": to_ts},
    )
    if not data or data.get("code") != "SUCCESS":
        return pd.DataFrame()
    d = data.get("data") or {}
    t_list = d.get("t", [])
    c_list = d.get("c", [])
    o_list = d.get("o", [])
    h_list = d.get("h", [])
    l_list = d.get("l", [])
    v_list = d.get("v", [])
    if not t_list or not c_list:
        return pd.DataFrame()

    n = len(t_list)
    df = pd.DataFrame({
        "time":   pd.to_datetime(t_list, unit="s", utc=True).tz_convert("Asia/Ho_Chi_Minh").tz_localize(None),
        "open":   [float(x) for x in o_list[:n]],
        "high":   [float(x) for x in h_list[:n]],
        "low":    [float(x) for x in l_list[:n]],
        "close":  [float(x) for x in c_list[:n]],
        "volume": [float(x) for x in v_list[:n]] if v_list else [0.0] * n,
    })
    df = df.set_index("time").sort_index()
    df = df[df["close"] > 0]
    return df.tail(days)


def fetch_intraday(symbol: str, resolution: str = "15", days: int = 5) -> pd.DataFrame:
    """
    Fetch intraday OHLCV. resolution: '1','5','15','30','60'.
    Returns DataFrame indexed by datetime; prices in thousands-VND.
    """
    to_ts   = int(_time.time())
    from_ts = to_ts - int(days * 86400 * 1.5)
    data = _get(
        f"{_API_BASE}/statistics/charts/history",
        params={"resolution": resolution, "symbol": symbol.upper(),
                "from": from_ts, "to": to_ts},
    )
    if not data or data.get("code") != "SUCCESS":
        return pd.DataFrame()
    d = data.get("data") or {}
    t_list = d.get("t", [])
    c_list = d.get("c", [])
    if not t_list or not c_list:
        return pd.DataFrame()

    n = len(t_list)
    df = pd.DataFrame({
        "time":   pd.to_datetime(t_list, unit="s", utc=True).tz_convert("Asia/Ho_Chi_Minh").tz_localize(None),
        "open":   [float(x) for x in d.get("o", c_list)[:n]],
        "high":   [float(x) for x in d.get("h", c_list)[:n]],
        "low":    [float(x) for x in d.get("l", c_list)[:n]],
        "close":  [float(x) for x in c_list[:n]],
        "volume": [float(x) for x in d.get("v", [0]*n)[:n]],
    })
    return df.set_index("time").sort_index()


# ── FINANCIAL RATIOS ─────────────────────────────────────────────────────────

def fetch_financials(symbol: str) -> dict:
    """
    Fetch latest financial indicators.
    roe/roa are returned as fractions (0.27 = 27%).
    """
    data = _get(
        f"{_API_BASE}/statistics/company/ssmi/finance-indicator",
        params={"symbol": symbol.upper(), "page": 1, "pageSize": 10},
    )
    if not data or data.get("code") != "SUCCESS":
        return {}

    raw_data = data.get("data") or {}
    if isinstance(raw_data, dict):
        items = raw_data.get("items") or raw_data.get("data") or []
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        items = []

    if not items:
        return {}

    # Most recent item (last in list for ascending year order, or first for desc)
    last = items[-1] if items else {}

    def _f(key, default=0.0):
        try:
            return float(last.get(key) or default)
        except (TypeError, ValueError):
            return float(default)

    return {
        "pe":          _f("pe"),
        "pb":          _f("pb"),
        "roe":         _f("roe"),          # fraction 0.27 = 27%
        "roa":         _f("roa"),          # fraction
        "eps":         _f("eps"),          # raw VND per share
        "debt_equity": _f("debtEquity"),
        "ev_ebitda":   0.0,
        "beta":        _f("beta"),
        "dividend_yield": _f("dividendYield"),
        "period":      str(last.get("yearReport", "")),
    }


# ── CORPORATE ACTIONS ────────────────────────────────────────────────────────

def fetch_corporate_actions(symbol: str, look_ahead_months: int = 12) -> list:
    """
    Fetch upcoming corporate actions (dividends, AGM, rights).
    Returns list of {date, event_type, value, source}.
    """
    today = dt.date.today()
    end   = today + dt.timedelta(days=look_ahead_months * 31)
    from_s = today.strftime("%d/%m/%Y")
    to_s   = end.strftime("%d/%m/%Y")

    data = _get(
        f"{_API_BASE}/statistics/company/ssmi/corporate-actions",
        params={
            "pageSize": 50, "page": 1, "language": "vn",
            "symbol": symbol.upper(),
            "fromDate": from_s, "toDate": to_s,
        },
    )
    if not data or data.get("code") != "SUCCESS":
        return []

    raw_data = data.get("data") or []
    if isinstance(raw_data, dict):
        items = raw_data.get("items") or []
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        items = []

    result = []
    for item in items:
        result.append({
            "date":       item.get("exrightDate") or item.get("recordDate") or item.get("eventDate", ""),
            "event_type": item.get("eventName") or item.get("eventType", ""),
            "value":      item.get("value") or item.get("rate") or "",
            "source":     "SSI-iBoard",
        })
    return result


# ── COMPANY NEWS ─────────────────────────────────────────────────────────────

def fetch_company_news(symbol: str, days: int = 30) -> list:
    """
    Fetch recent news for symbol.
    Returns list of {date, title, source}.
    """
    today  = dt.date.today()
    from_d = today - dt.timedelta(days=days)
    from_s = from_d.strftime("%d/%m/%Y")
    to_s   = today.strftime("%d/%m/%Y")

    data = _get(
        f"{_API_BASE}/statistics/company/ssmi/company-news",
        params={
            "symbol": symbol.upper(), "pageSize": 20, "page": 1,
            "fromDate": from_s, "toDate": to_s, "language": "vn",
        },
    )
    if not data or data.get("code") != "SUCCESS":
        return []

    items = data.get("data") or []
    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        result.append({
            "date":   (item.get("publicDate") or item.get("createDate") or "")[:10],
            "title":  item.get("title", ""),
            "source": item.get("newsSource") or item.get("sourceCode", "SSI"),
        })
    return result


# ── COMPANY PROFILE ───────────────────────────────────────────────────────────

def fetch_company_profile(symbol: str) -> dict:
    """Fetch company profile. Returns cleaned dict."""
    data = _get(
        f"{_API_BASE}/statistics/company/ssmi/company-profile",
        params={"symbol": symbol.upper(), "language": "vn"},
    )
    if not data or data.get("code") != "SUCCESS":
        return {}
    d = data.get("data") or {}
    if not d:
        return {}

    charter = d.get("charterCapital", 0)
    try:
        charter_str = f"{float(charter)/1e9:,.1f} tỷ đồng"
    except (TypeError, ValueError):
        charter_str = str(charter)

    # Strip HTML from description
    import re
    desc_raw = d.get("companyProfile", "")
    desc     = re.sub(r"<[^>]+>", " ", desc_raw).strip() if desc_raw else ""

    return {
        "name":            d.get("companyName") or d.get("symbol", ""),
        "industry":        d.get("industryName", ""),
        "sector":          d.get("sector", ""),
        "website":         "",   # not in this endpoint
        "charter_capital": charter_str,
        "employees":       d.get("numberOfEmployee", 0),
        "description":     desc[:1000],
        "exchange":        d.get("exchange", ""),
        "listing_date":    d.get("listingDate", ""),
    }


# ── FOREIGN FLOW ─────────────────────────────────────────────────────────────

def fetch_foreign_flow(symbol: str) -> dict:
    """
    Fetch foreign buy/sell for one symbol from live quote.
    Returns {symbol, foreign_buy_qty, foreign_buy_val, foreign_sell_qty, foreign_sell_val, foreign_net_val}.
    Values are in thousands-VND.
    """
    data = _get(f"{_QUERY_BASE}/stock/{symbol.upper()}", params={"boardId": "MAIN"})
    if not data or data.get("code") != "SUCCESS":
        return {}
    d = data.get("data") or {}
    if not d:
        return {}

    buy_qty  = float(d.get("buyForeignQtty",  0) or 0)
    buy_val  = float(d.get("buyForeignValue",  0) or 0) / 1000.0
    sell_qty = float(d.get("sellForeignQtty", 0) or 0)
    sell_val = float(d.get("sellForeignValue", 0) or 0) / 1000.0
    net_val  = buy_val - sell_val

    if buy_qty + sell_qty == 0:
        return {}

    return {
        "symbol":            symbol.upper(),
        "foreign_buy_qty":   buy_qty,
        "foreign_buy_val":   buy_val,
        "foreign_sell_qty":  sell_qty,
        "foreign_sell_val":  sell_val,
        "foreign_net_val":   net_val,
    }

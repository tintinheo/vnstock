"""
SSI iBoard Direct Data Fetcher
================================
Calls SSI's public iBoard REST APIs directly — zero vnstock dependency.
Endpoints confirmed working 2026-03-08 (verified in quant_app.py).

Waterfall for OHLCV history:
  1. iboard-api.ssi.com.vn/statistics/charts/history  (primary, UDF)
  2. iboard-query.ssi.com.vn/stock/ohlc               (secondary)
  3. fc-data.ssi.com.vn/api/v2/stock/ohlc             (tertiary)

Real-time quote:
  iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN
  → fallback: last close from history waterfall
"""
import datetime as dt
import logging

import pandas as pd
import requests

_log = logging.getLogger("ssi_fetcher")

# ─── HTTP SESSION ─────────────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "vi",
    "Referer":         "https://iboard.ssi.com.vn/",
    "Origin":          "https://iboard.ssi.com.vn",
    "device-id":       "0116B7B1-976D-437A-AA2C-C72FC3E6F956",
})
_TIMEOUT = 12


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _unix(d: dt.date) -> int:
    """Date → Unix timestamp at midnight GMT+7 (Vietnam time)."""
    tz_vn = dt.timezone(dt.timedelta(hours=7))
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=tz_vn).timestamp())


def _normalize_price(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize to 'thousands VND' scale (e.g. HPG ≈ 26.65, not 26650).
    SSI sometimes returns raw VND (26650) or unit VND/1000 (26.65).
    Rule: if median close > 500 → divide by 1000.
    """
    if df.empty or "close" not in df.columns:
        return df
    med = df["close"].median()
    if med > 500:
        for col in ("open", "high", "low", "close"):
            if col in df.columns:
                df[col] = df[col] / 1000.0
    return df


# ─── RESPONSE PARSERS ────────────────────────────────────────────────────────

def _parse_udf(raw, symbol: str = "") -> pd.DataFrame:
    """
    Parse all three SSI response shapes into a uniform OHLCV DataFrame
    indexed by DatetimeIndex('time', freq=None).

    Shape A — TradingView UDF arrays (primary):
      {"t":[unix,...], "o":[...], "h":[...], "l":[...], "c":[...], "v":[...], "s":"ok"}

    Shape B — Nested wrapper around Shape A:
      {"data": {"t":[...], ...}}

    Shape C — List of dicts:
      {"data": [{"time":unix, "open":..., "close":..., ...}, ...]}
      or  [{"time":..., "close":..., ...}, ...]
    """
    if not raw:
        return pd.DataFrame()

    # Unwrap optional outer "data" key
    inner = raw.get("data", raw) if isinstance(raw, dict) else raw

    # ── Shape C: list of dicts ────────────────────────────────────────────────
    if isinstance(inner, list) and inner:
        rows = []
        for item in inner:
            try:
                ts = item.get("time", item.get("t", item.get("date", item.get("Date"))))
                cl = item.get("close", item.get("c", item.get("Close")))
                if ts is None or cl is None:
                    continue
                date = (pd.Timestamp(ts, unit="s")
                        if isinstance(ts, (int, float))
                        else pd.Timestamp(ts))
                rows.append({
                    "time":   date.normalize(),
                    "open":   float(item.get("open",   item.get("o", cl)) or cl),
                    "high":   float(item.get("high",   item.get("h", cl)) or cl),
                    "low":    float(item.get("low",    item.get("l", cl)) or cl),
                    "close":  float(cl),
                    "volume": float(item.get("volume", item.get("v", 0)) or 0),
                })
            except Exception:
                continue
        if rows:
            df = (pd.DataFrame(rows)
                  .set_index("time")
                  .sort_index())
            df = df[~df.index.duplicated(keep="last")]
            return _normalize_price(df)
        return pd.DataFrame()

    # ── Shape A / B: UDF arrays ───────────────────────────────────────────────
    if isinstance(inner, dict):
        if raw.get("s") == "no_data":
            return pd.DataFrame()
        t_arr = inner.get("t", [])
        c_arr = inner.get("c", [])
        if not t_arr or not c_arr or len(t_arr) < 2:
            return pd.DataFrame()
        try:
            idx = pd.to_datetime(t_arr, unit="s").normalize()
            df  = pd.DataFrame({
                "open":   pd.to_numeric(inner.get("o", c_arr), errors="coerce"),
                "high":   pd.to_numeric(inner.get("h", c_arr), errors="coerce"),
                "low":    pd.to_numeric(inner.get("l", c_arr), errors="coerce"),
                "close":  pd.to_numeric(c_arr,                 errors="coerce"),
                "volume": pd.to_numeric(inner.get("v", [0] * len(t_arr)), errors="coerce"),
            }, index=idx)
            df.index.name = "time"
            df = df.dropna(subset=["close"]).sort_index()
            df = df[~df.index.duplicated(keep="last")]
            return _normalize_price(df)
        except Exception as e:
            _log.debug(f"UDF parse error [{symbol}]: {e}")

    return pd.DataFrame()


# ─── HISTORY ─────────────────────────────────────────────────────────────────

# Endpoint builder functions — tried in order
_HISTORY_ENDPOINTS = [
    # ①  iboard-api — confirmed working 2026-03-08
    lambda s, f, t: f"https://iboard-api.ssi.com.vn/statistics/charts/history?resolution=1D&symbol={s}&from={f}&to={t}",
    # ②  iboard-query
    lambda s, f, t: f"https://iboard-query.ssi.com.vn/stock/ohlc?symbol={s}&resolution=D&from={f}&to={t}",
    # ③  fc-data
    lambda s, f, t: f"https://fc-data.ssi.com.vn/api/v2/stock/ohlc?symbol={s}&resolution=D&from={f}&to={t}",
]


def fetch_history(symbol: str, days: int = 252) -> pd.DataFrame:
    """
    Fetch OHLCV history for `symbol` from SSI iBoard.

    Returns
    -------
    pd.DataFrame  indexed by DatetimeIndex('time'),
                  columns: open / high / low / close / volume
                  prices in thousands VND (e.g. HPG ≈ 26.65)
    Returns empty DataFrame on total failure.
    """
    end   = dt.date.today()
    start = end - dt.timedelta(days=days + 30)   # +30 buffer for weekends/holidays
    from_ts, to_ts = _unix(start), _unix(end)

    for url_fn in _HISTORY_ENDPOINTS:
        url = url_fn(symbol, from_ts, to_ts)
        try:
            r = _SESSION.get(url, timeout=_TIMEOUT)
            r.raise_for_status()
            raw = r.json()
            df  = _parse_udf(raw, symbol)
            if not df.empty and len(df) >= 5:
                _log.info(f"SSI ✅ {symbol}: {len(df)} rows via {url[:70]}")
                return df.tail(days)
            _log.debug(f"SSI {symbol}: empty/short from {url[:60]}")
        except requests.HTTPError as e:
            _log.warning(f"SSI HTTP [{symbol}] {url[:55]}: {e}")
        except requests.Timeout:
            _log.warning(f"SSI timeout [{symbol}] {url[:55]}")
        except requests.ConnectionError as e:
            _log.warning(f"SSI conn [{symbol}]: {e}")
        except ValueError as e:
            _log.warning(f"SSI JSON [{symbol}]: {e}")
        except Exception as e:
            _log.error(f"SSI unexpected [{symbol}]: {e}")

    _log.warning(f"SSI: all history endpoints failed for {symbol}")
    return pd.DataFrame()


# ─── INTRADAY HISTORY ─────────────────────────────────────────────────────

_INTRADAY_ENDPOINTS = [
    lambda s, f, t, r: (
        f"https://iboard-api.ssi.com.vn/statistics/charts/history"
        f"?resolution={r}&symbol={s}&from={f}&to={t}"
    ),
    lambda s, f, t, r: (
        f"https://iboard-query.ssi.com.vn/stock/ohlc"
        f"?symbol={s}&resolution={r}&from={f}&to={t}"
    ),
    lambda s, f, t, r: (
        f"https://fc-data.ssi.com.vn/api/v2/stock/ohlc"
        f"?symbol={s}&resolution={r}&from={f}&to={t}"
    ),
]


def fetch_intraday(symbol: str, resolution: str = "15", days: int = 5) -> pd.DataFrame:
    """
    Fetch intraday OHLCV for `symbol` from SSI iBoard.

    Parameters
    ----------
    resolution : "15" (15-min), "60" (1-hour)
    days       : calendar days of history to fetch (request window)

    Returns pd.DataFrame indexed by DatetimeIndex, prices in thousands-VND.
    Returns empty DataFrame on failure.
    """
    end   = dt.date.today()
    start = end - dt.timedelta(days=days + 2)   # +2 buffer for weekends
    from_ts, to_ts = _unix(start), _unix(end)

    for url_fn in _INTRADAY_ENDPOINTS:
        url = url_fn(symbol, from_ts, to_ts, resolution)
        try:
            r = _SESSION.get(url, timeout=_TIMEOUT)
            r.raise_for_status()
            raw = r.json()
            df  = _parse_udf(raw, symbol)
            if not df.empty and len(df) >= 5:
                _log.info(f"SSI intraday ✅ {symbol} {resolution}m: {len(df)} rows")
                return df
            _log.debug(f"SSI intraday {symbol}: empty/short from {url[:60]}")
        except requests.HTTPError as e:
            _log.warning(f"SSI intraday HTTP [{symbol}] {url[:55]}: {e}")
        except requests.Timeout:
            _log.warning(f"SSI intraday timeout [{symbol}] {url[:55]}")
        except requests.ConnectionError as e:
            _log.warning(f"SSI intraday conn [{symbol}]: {e}")
        except ValueError as e:
            _log.warning(f"SSI intraday JSON [{symbol}]: {e}")
        except Exception as e:
            _log.error(f"SSI intraday unexpected [{symbol}]: {e}")

    _log.warning(f"SSI: all intraday endpoints failed for {symbol}")
    return pd.DataFrame()


# ─── REAL-TIME QUOTE ─────────────────────────────────────────────────────────

def fetch_quote(symbol: str) -> dict:
    """
    Fetch real-time quote for `symbol` from SSI iboard-query.
    Falls back to last-close from the history waterfall if quote endpoint fails.

    Returns dict: {symbol, price, open, high, low, volume, change, pct_change, time, source}
    price is in thousands VND (e.g. 26.65).
    """
    # ── Primary: iboard-query real-time ──────────────────────────────────────
    try:
        url = f"https://iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN"
        r   = _SESSION.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        d    = r.json()
        # Unwrap: may be {data: {…}}, {data: [{…}]}, or direct dict/list
        data = d.get("data", d) if isinstance(d, dict) else d
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            data = {}

        def _n(v, dflt: float = 0.0) -> float:
            try:
                return float(v) if v not in (None, "", "-", "0", 0) else dflt
            except (ValueError, TypeError):
                return dflt

        price = _n(data.get("matchedPrice",
                   data.get("close",
                   data.get("lastPrice",
                   data.get("refPrice", 0)))))
        ref   = _n(data.get("refPrice", data.get("refClose", 0)))
        chg   = _n(data.get("priceChange",        price - ref))
        pct   = _n(data.get("percentPriceChange", (chg / ref * 100) if ref else 0))
        vol   = _n(data.get("totalMatchVol",       data.get("volume",    0)))
        op    = _n(data.get("openPrice",           data.get("open",      price)))
        hi    = _n(data.get("highPrice",           data.get("high",      price)))
        lo    = _n(data.get("lowPrice",            data.get("low",       price)))

        # Normalize raw VND → thousands
        if price > 1000:
            price /= 1000; op /= 1000; hi /= 1000; lo /= 1000; chg /= 1000; ref /= 1000

        if price > 0:
            return {
                "symbol":     symbol,
                "price":      price,
                "open":       op,
                "high":       hi,
                "low":        lo,
                "volume":     vol,
                "change":     chg,
                "pct_change": pct,
                "time":       dt.datetime.now().isoformat(),
                "source":     "SSI-iboard",
            }
    except Exception as e:
        _log.debug(f"SSI quote [{symbol}]: {e}")

    # ── Fallback: last close from history waterfall ───────────────────────────
    df = fetch_history(symbol, days=5)
    if not df.empty:
        last  = df.iloc[-1]
        prev  = df.iloc[-2] if len(df) > 1 else last
        price = float(last["close"])
        pp    = float(prev["close"])
        chg   = price - pp
        pct   = chg / pp * 100 if pp else 0
        return {
            "symbol":     symbol,
            "price":      price,
            "open":       float(last.get("open",   price)),
            "high":       float(last.get("high",   price)),
            "low":        float(last.get("low",    price)),
            "volume":     float(last.get("volume", 0)),
            "change":     chg,
            "pct_change": pct,
            "time":       str(df.index[-1]),
            "source":     "SSI-history-fallback",
        }

    return {
        "symbol": symbol, "price": 0, "open": 0, "high": 0, "low": 0,
        "volume": 0, "change": 0, "pct_change": 0, "time": "N/A", "source": "SSI-fail",
    }


# ─── IBOARD-API HELPER ───────────────────────────────────────────────────────

_IBOARD_API_BASE = "https://iboard-api.ssi.com.vn"


def _iboard_api_get(path: str, params: dict) -> dict:
    """
    GET from iboard-api.ssi.com.vn with device-id header.
    Returns parsed JSON dict (possibly empty on any error).
    """
    url = f"{_IBOARD_API_BASE}{path}"
    try:
        r = _SESSION.get(url, params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        _log.warning("iboard-api HTTP %s %s: %s", path, params, e)
    except requests.Timeout:
        _log.warning("iboard-api timeout %s", path)
    except requests.ConnectionError as e:
        _log.warning("iboard-api conn %s: %s", path, e)
    except ValueError as e:
        _log.warning("iboard-api JSON %s: %s", path, e)
    except Exception as e:
        _log.error("iboard-api unexpected %s: %s", path, e)
    return {}


# ─── FINANCIALS ──────────────────────────────────────────────────────────────

def fetch_financials(symbol: str) -> dict:
    """
    Fetch latest financial ratios for `symbol` from SSI iboard-api.
    Returns dict: {pe, pb, roe, roa, eps, period, source} or {} on failure.
    """
    raw = _iboard_api_get(
        "/statistics/company/ssmi/finance-indicator",
        {"symbol": symbol, "page": 1, "pageSize": 10},
    )
    items = raw.get("data", [])
    if not isinstance(items, list) or not items:
        return {}
    try:
        item = items[0]
        def _f(v) -> float:
            try:
                return float(v) if v not in (None, "", "-") else 0.0
            except (ValueError, TypeError):
                return 0.0
        return {
            "pe":     _f(item.get("priceToEarning", item.get("pe", 0))),
            "pb":     _f(item.get("priceToBook",    item.get("pb", 0))),
            "roe":    _f(item.get("roe", 0)),
            "roa":    _f(item.get("roa", 0)),
            "eps":    _f(item.get("eps", item.get("earningPerShare", 0))),
            "period": str(item.get("yearReport", item.get("period", ""))),
            "source": "SSI-iboard",
        }
    except Exception as e:
        _log.warning("fetch_financials [%s]: %s", symbol, e)
        return {}


# ─── CORPORATE ACTIONS ───────────────────────────────────────────────────────

def fetch_corporate_actions(symbol: str, look_ahead_months: int = 12) -> list:
    """
    Fetch upcoming corporate actions (dividends, AGM, rights) for `symbol`.
    Returns list of dicts: {date, event_type, value, source}; [] on failure.
    """
    today = dt.date.today()
    end   = today + dt.timedelta(days=look_ahead_months * 30)
    from_str = today.strftime("%d%%2F%m%%2F%Y")
    to_str   = end.strftime("%d%%2F%m%%2F%Y")
    raw = _iboard_api_get(
        "/statistics/company/ssmi/corporate-actions",
        {
            "symbol":   symbol,
            "page":     1,
            "pageSize": 20,
            "language": "vn",
            "fromDate": from_str,
            "toDate":   to_str,
        },
    )
    items = raw.get("data", [])
    if not isinstance(items, list):
        return []
    results = []
    for item in items:
        try:
            results.append({
                "date":       str(item.get("exRightDate", item.get("eventDate", item.get("date", "")))),
                "event_type": str(item.get("eventTitle",  item.get("event", ""))),
                "value":      str(item.get("value",        item.get("ratio", ""))),
                "source":     "SSI-iboard",
            })
        except Exception:
            continue
    return results


# ─── COMPANY NEWS ─────────────────────────────────────────────────────────────

def fetch_company_news(symbol: str, days: int = 30) -> list:
    """
    Fetch recent company news for `symbol`.
    Window capped at 30 days to avoid HTTP 400.
    Returns list of dicts: {date, title, source}; [] on failure.
    """
    days = min(days, 30)  # SSI enforces ≤1 month
    today    = dt.date.today()
    from_d   = today - dt.timedelta(days=days)
    from_str = from_d.strftime("%d%%2F%m%%2F%Y")
    to_str   = today.strftime("%d%%2F%m%%2F%Y")
    raw = _iboard_api_get(
        "/statistics/company/ssmi/company-news",
        {
            "symbol":   symbol,
            "pageSize": 10,
            "page":     1,
            "fromDate": from_str,
            "toDate":   to_str,
            "language": "vn",
        },
    )
    items = raw.get("data", [])
    if not isinstance(items, list):
        return []
    results = []
    for item in items:
        try:
            results.append({
                "date":   str(item.get("publishDate", item.get("date", ""))),
                "title":  str(item.get("title", item.get("subject", ""))),
                "source": "SSI-iboard",
            })
        except Exception:
            continue
    return results


# ─── VN30 BATCH QUOTE ─────────────────────────────────────────────────────────

_VN30_SYMBOLS = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
}


def fetch_vn30_batch() -> dict:
    """
    Fetch real-time quotes for all VN30 stocks in one HTTP call.
    Returns dict[symbol → quote_dict] (same shape as fetch_quote());
    returns {} on failure.
    """
    try:
        url = "https://iboard-query.ssi.com.vn/stock/group/VN30"
        r   = _SESSION.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        raw   = r.json()
        items = raw.get("data", raw) if isinstance(raw, dict) else raw
        if isinstance(items, dict):
            items = list(items.values())
        if not isinstance(items, list) or not items:
            return {}

        def _n(v, dflt: float = 0.0) -> float:
            try:
                return float(v) if v not in (None, "", "-", "0", 0) else dflt
            except (ValueError, TypeError):
                return dflt

        result = {}
        now = dt.datetime.now().isoformat()
        for item in items:
            if not isinstance(item, dict):
                continue
            sym = str(item.get("symbol", item.get("ticker", ""))).upper()
            if not sym:
                continue
            price = _n(item.get("matchedPrice", item.get("close", item.get("lastPrice", 0))))
            ref   = _n(item.get("refPrice", item.get("refClose", 0)))
            chg   = _n(item.get("priceChange",        price - ref))
            pct   = _n(item.get("percentPriceChange", (chg / ref * 100) if ref else 0))
            vol   = _n(item.get("totalMatchVol",       item.get("volume", 0)))
            op    = _n(item.get("openPrice",           item.get("open",   price)))
            hi    = _n(item.get("highPrice",           item.get("high",   price)))
            lo    = _n(item.get("lowPrice",            item.get("low",    price)))
            if price > 1000:
                price /= 1000; op /= 1000; hi /= 1000; lo /= 1000; chg /= 1000; ref /= 1000
            if price > 0:
                result[sym] = {
                    "symbol":     sym,
                    "price":      price,
                    "open":       op,
                    "high":       hi,
                    "low":        lo,
                    "volume":     vol,
                    "change":     chg,
                    "pct_change": pct,
                    "time":       now,
                    "source":     "SSI-VN30-batch",
                }
        if result:
            _log.info("SSI VN30 batch: %d quotes", len(result))
        return result
    except Exception as e:
        _log.warning("fetch_vn30_batch: %s", e)
        return {}


# ─── COMPANY PROFILE ──────────────────────────────────────────────────────────

def fetch_company_profile(symbol: str) -> dict:
    """
    Fetch company profile for `symbol`.
    Returns dict: {name, industry, charter_capital, website, description, source};
    returns {} on failure.
    """
    raw = _iboard_api_get(
        "/statistics/company/ssmi/company-profile",
        {"symbol": symbol, "language": "vn"},
    )
    data = raw.get("data", {})
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict) or not data:
        return {}
    try:
        return {
            "name":            str(data.get("companyName",     data.get("name",        ""))),
            "industry":        str(data.get("industryName",   data.get("industry",    ""))),
            "charter_capital": str(data.get("charterCapital", data.get("capital",     ""))),
            "website":         str(data.get("website",        data.get("websiteUrl",  ""))),
            "description":     str(data.get("businessActivities", data.get("description", ""))),
            "source":          "SSI-iboard",
        }
    except Exception as e:
        _log.warning("fetch_company_profile [%s]: %s", symbol, e)
        return {}


# ─── CONNECTIVITY CHECK ───────────────────────────────────────────────────────

def check_connectivity() -> dict:
    """Quick liveness probe against primary SSI endpoint. Returns status dict."""
    import time
    url = ("https://iboard-api.ssi.com.vn/statistics/charts/history"
           "?resolution=1D&symbol=HPG&from=1700000000&to=1700086400")
    try:
        t0 = time.time()
        r  = _SESSION.get(url, timeout=5)
        ms = int((time.time() - t0) * 1000)
        return {
            "ok":         r.ok,
            "latency_ms": ms,
            "endpoint":   "iboard-api.ssi.com.vn",
            "status":     r.status_code,
        }
    except Exception as e:
        return {
            "ok":         False,
            "latency_ms": -1,
            "endpoint":   "iboard-api.ssi.com.vn",
            "error":      str(e),
        }


# ─── FOREIGN FLOW ─────────────────────────────────────────────────────────────

def fetch_foreign_flow(symbol: str) -> dict:
    """
    Fetch foreign investor net buy/sell volumes for one symbol.
    Uses the iboard-query real-time quote endpoint which includes foreign fields.

    Returns dict: {symbol, foreign_buy_vol, foreign_sell_vol, foreign_net_vol,
                   foreign_buy_val, foreign_sell_val, foreign_net_val, source}
    All val fields are in thousands-VND. Returns empty dict on failure.
    """
    try:
        url  = f"https://iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN"
        r    = _SESSION.get(url, timeout=_TIMEOUT)
        r.raise_for_status()
        d    = r.json()
        data = d.get("data", d) if isinstance(d, dict) else d
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            data = {}

        def _n(v) -> float:
            try:
                return float(v) if v not in (None, "", 0, "0", "-") else 0.0
            except (ValueError, TypeError):
                return 0.0

        f_buy_vol  = _n(data.get("foreignBuyVol",  data.get("fBuyVol",  0)))
        f_sell_vol = _n(data.get("foreignSellVol", data.get("fSellVol", 0)))
        price      = _n(data.get("matchedPrice",   data.get("close",    0)))
        if price > 1000:
            price /= 1000.0

        f_net_vol  = f_buy_vol - f_sell_vol
        f_buy_val  = round(f_buy_vol  * price, 1)
        f_sell_val = round(f_sell_vol * price, 1)
        f_net_val  = round(f_net_vol  * price, 1)

        return {
            "symbol":           symbol,
            "foreign_buy_vol":  f_buy_vol,
            "foreign_sell_vol": f_sell_vol,
            "foreign_net_vol":  f_net_vol,
            "foreign_buy_val":  f_buy_val,
            "foreign_sell_val": f_sell_val,
            "foreign_net_val":  f_net_val,
            "source":           "SSI-iboard",
        }
    except Exception as e:
        _log.debug(f"SSI foreign_flow [{symbol}]: {e}")
        return {}

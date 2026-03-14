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
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer":         "https://iboard.ssi.com.vn/",
    "Origin":          "https://iboard.ssi.com.vn",
})
_TIMEOUT = 12


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _unix(d: dt.date) -> int:
    """Date → Unix timestamp (midnight local time)."""
    return int(dt.datetime.combine(d, dt.time.min).timestamp())


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

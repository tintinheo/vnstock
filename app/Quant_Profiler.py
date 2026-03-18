#!/usr/bin/env python3
"""
Quant_Profiler.py — Vietnam Stock Technical Analysis Profiler  v1.0
═══════════════════════════════════════════════════════════════════
Standalone CLI tool. No Streamlit. No dependency on quant_app.py.

Usage:
    python Quant_Profiler.py HPG,TCH,CII
    python Quant_Profiler.py            # interactive prompt

Data pipeline:
    OHLCV   : DNSE → SSI iboard-api → CafeF (400 ngày)
    Real-time: SSI iboard-query.ssi.com.vn

Indicators computed:
    SMA 5/10/20/50/200 · EMA 9/21/50/200 · RSI(14) · Stoch(14,3)
    MACD(12,26,9) · Bollinger Bands(20,±2σ) · ATR(14) · ADX/±DI(14)
    OBV · Williams %R(14) · CCI(20)

Signal logic: Bull/Bear score → MUA / THEO DÕI / TRUNG LẬP / BÁN
Entry/TP/SL : ATR-based (SL=1.5×ATR, TP1=2×ATR, TP2=3.5×ATR)
"""

import sys
import time
import logging
import warnings
import concurrent.futures
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ─── STRUCTURED LOGGING ──────────────────────────────────────────────────────
# Writes to both console (INFO+) and a rotating file (DEBUG+).
# Switch root level to logging.DEBUG to see HTTP detail.
logging.basicConfig(
    level=logging.WARNING,            # default: suppress third-party noise
    format="%(asctime)s %(levelname)-8s %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_log = logging.getLogger("quant_profiler")
_log.setLevel(logging.INFO)           # our own module always logs at INFO+

try:
    from logging.handlers import RotatingFileHandler as _RFH
    import os as _os
    _fh = _RFH(
        _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "quant_profiler.log"),
        maxBytes=2 * 1024 * 1024,     # 2 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _log.addHandler(_fh)
except Exception:
    pass   # non-fatal: file logging optional

# ─── API TIMEOUTS ────────────────────────────────────────────────────────────
TIMEOUT      = 12
RT_TIMEOUT   = 8
HISTORY_DAYS = 400
ASYNC_WORKERS = 4    # reduced from 8 to avoid 403 rate-limiting from DNSE/SSI

# ─── PROFILER AUDIT DIR ──────────────────────────────────────────────────────
import json as _json
import os   as _os_
_AUDIT_DIR = _os_.path.join(_os_.path.dirname(_os_.path.abspath(__file__)),
                            "data", "Profiler")
_os_.makedirs(_AUDIT_DIR, exist_ok=True)

# ─── HTTP SESSION (shared for OHLCV fetches) ─────────────────────────────────
_HTTP = requests.Session()
_HTTP.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Accept":          "application/json,text/html,*/*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer":         "https://iboard.ssi.com.vn/",
})

# ─── SSI iboard-query headers (confirmed from HAR log 2026-03-14) ────────────
_SSI_HDR = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Origin":          "https://iboard.ssi.com.vn",
    "Referer":         "https://iboard.ssi.com.vn/",
    "device-id":       "6212D3CF-D972-4CFF-8B3D-67EF96A2FD89",
    "Accept-Language": "vi",
    "Accept":          "application/json, text/plain, */*",
}


def _unix(dt: datetime) -> int:
    return int(dt.timestamp())


# ═══════════════════════════════════════════════════════════════════════════════
#  A. DATA LAYER — OHLCV
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_udf(raw: dict, source: str = "UDF") -> pd.DataFrame:
    """Parse TradingView UDF format: {t, o, h, l, c, v, s}."""
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
            "Close":  pd.to_numeric(c_arr,               errors="coerce"),
            "Volume": pd.to_numeric(raw.get("v", [0] * len(t_arr)), errors="coerce"),
        }, index=pd.to_datetime(t_arr, unit="s").normalize())
        df.index.name = "Date"
        df = df.dropna(subset=["Close"]).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        # Normalise price scale (some APIs return ×1000 VND as "k-units")
        if not df.empty and df["Close"].dropna().median() < 1000:
            for col in ["Open", "High", "Low", "Close"]:
                df[col] = df[col] * 1000
        return df
    except Exception:
        return pd.DataFrame()


def _fetch_dnse(symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    Primary: DNSE api.dnse.com.vn/chart-api/v2  (confirmed working 2026-03-08)
    Returns TradingView UDF: {t, o, h, l, c, v}.  No auth required.
    """
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    url = (
        f"https://api.dnse.com.vn/chart-api/v2/ohlcs/stock"
        f"?symbol={symbol}&resolution=1D&from={from_ts}&to={to_ts}"
    )
    try:
        r = _HTTP.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
        if isinstance(raw, dict):
            df = _parse_udf(raw, source=f"DNSE({symbol})")
            if not df.empty:
                _log.info("DNSE ✓ %s — %d bars", symbol, len(df))
            else:
                _log.debug("DNSE %s — empty response", symbol)
            return df
    except requests.exceptions.Timeout:
        _log.warning("DNSE timeout %s", symbol)
    except requests.exceptions.HTTPError as exc:
        _log.warning("DNSE HTTP %s %s", symbol, exc)
    except Exception as exc:
        _log.debug("DNSE %s — %s", symbol, exc)
    return pd.DataFrame()


def _fetch_ssi(symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    Secondary: SSI iboard-api charts/history + iboard-query fallbacks.
    Endpoint: iboard-api.ssi.com.vn/statistics/charts/history?resolution=1D
    """
    to_ts   = _unix(datetime.now())
    from_ts = _unix(datetime.now() - timedelta(days=days))
    endpoints = [
        # Confirmed working (HAR log 2026-03-14, iboard-api charts/history)
        (
            f"https://iboard-api.ssi.com.vn/statistics/charts/history"
            f"?resolution=1D&symbol={symbol}&from={from_ts}&to={to_ts}",
            {
                "User-Agent": "Mozilla/5.0",
                "Accept":     "application/json",
                "Referer":    "https://iboard.ssi.com.vn/",
                "Origin":     "https://iboard.ssi.com.vn",
            },
        ),
        # Legacy iboard-query ohlc (may still work)
        (
            f"https://iboard-query.ssi.com.vn/stock/ohlc"
            f"?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
            {"User-Agent": "Mozilla/5.0", "Referer": "https://iboard.ssi.com.vn/"},
        ),
        # fc-data subdomain
        (
            f"https://fc-data.ssi.com.vn/api/v2/stock/ohlc"
            f"?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}",
            {"User-Agent": "Mozilla/5.0", "Referer": "https://iboard.ssi.com.vn/"},
        ),
    ]
    for url, hdrs in endpoints:
        try:
            r = requests.get(url, headers=hdrs, timeout=TIMEOUT)
            r.raise_for_status()
            raw = r.json()
            if not isinstance(raw, dict):
                continue
            inner = raw.get("data", raw)
            # Format: list of OHLCV dicts
            if isinstance(inner, list) and inner:
                rows = []
                for it in inner:
                    try:
                        ts = it.get("time", it.get("t", it.get("date")))
                        cl = it.get("close", it.get("c", it.get("Close")))
                        if ts is None or cl is None:
                            continue
                        dt = (
                            pd.Timestamp(ts, unit="s")
                            if isinstance(ts, (int, float))
                            else pd.Timestamp(ts)
                        )
                        rows.append({
                            "Date":   dt,
                            "Open":   float(it.get("open",   it.get("o",  cl)) or cl),
                            "High":   float(it.get("high",   it.get("h",  cl)) or cl),
                            "Low":    float(it.get("low",    it.get("l",  cl)) or cl),
                            "Close":  float(cl),
                            "Volume": float(it.get("volume", it.get("v",   0)) or 0),
                        })
                    except Exception:
                        continue
                if rows:
                    df = (
                        pd.DataFrame(rows)
                        .set_index("Date")
                        .sort_index()
                    )
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 1000:
                        for c in ["Open", "High", "Low", "Close"]:
                            df[c] *= 1000
                    if len(df) >= 5:
                        return df
            # Format: UDF arrays
            elif isinstance(inner, dict):
                df = _parse_udf(inner, source=f"SSI({symbol})")
                if len(df) >= 5:
                    return df
        except Exception:
            continue
    return pd.DataFrame()


def _fetch_cafef(symbol: str, days: int = HISTORY_DAYS) -> pd.DataFrame:
    """
    Tertiary: CafeF historial.cafef.vn REST API with AJAX POST fallback.
    Strategy A: historial.cafef.vn/api/histdata/GetListHist
    Strategy B: s.cafef.vn/ajax/PageNew.aspx/HisDanhMuc (POST JSON)
    """
    end_date   = datetime.now().strftime("%Y/%m/%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    page_size  = min(days, 500)
    hdrs_ajax = {
        "User-Agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept":           "application/json, text/javascript, */*",
        "Content-Type":     "application/json; charset=UTF-8",
        "Referer":          f"https://cafef.vn/du-lieu-lich-su-giao-dich-{symbol.lower()}.chn",
        "Origin":           "https://cafef.vn",
        "X-Requested-With": "XMLHttpRequest",
    }

    # ─── Strategy A: historial REST ─────────────────────────────────────────
    try:
        url = (
            f"https://historial.cafef.vn/api/histdata/GetListHist"
            f"?symbol={symbol}&startDate={start_date}&endDate={end_date}"
            f"&pageIndex=1&pageSize={page_size}"
        )
        r = requests.get(url, headers=hdrs_ajax, timeout=TIMEOUT)
        if r.ok:
            items = r.json().get("Data", r.json().get("data", []))
            if items:
                rows = []
                for it in items:
                    try:
                        rows.append({
                            "Date":   pd.to_datetime(
                                it.get("TradingDate", it.get("tradingDate", it.get("date", ""))),
                                errors="coerce",
                            ),
                            "Open":   float(it.get("OpenPrice",  it.get("openPrice",  0)) or 0),
                            "High":   float(it.get("MaxPrice",   it.get("maxPrice",   0)) or 0),
                            "Low":    float(it.get("MinPrice",   it.get("minPrice",   0)) or 0),
                            "Close":  float(it.get("ClosePrice", it.get("closePrice", 0)) or 0),
                            "Volume": float(it.get("Volume",     it.get("volume",     0)) or 0),
                        })
                    except Exception:
                        continue
                if rows:
                    df = (
                        pd.DataFrame(rows)
                        .dropna(subset=["Close", "Date"])
                    )
                    df = df[df["Close"] > 0].set_index("Date").sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 1000:
                        for c in ["Open", "High", "Low", "Close"]:
                            df[c] *= 1000
                    if len(df) >= 5:
                        return df
    except Exception:
        pass

    # ─── Strategy B: AJAX POST ───────────────────────────────────────────────
    try:
        import json as _json
        payload = _json.dumps({
            "sort": "", "pageSize": page_size, "pageIndex": 1, "maChungKhoan": symbol,
        })
        r = requests.post(
            "https://s.cafef.vn/ajax/PageNew.aspx/HisDanhMuc",
            data=payload, headers=hdrs_ajax, timeout=TIMEOUT,
        )
        if r.ok:
            raw  = r.json()
            items = (
                raw.get("d", {}).get("Data")
                or raw.get("d", {}).get("data")
                or raw.get("Data")
                or raw.get("data")
                or []
            )
            if items:
                rows = []
                for it in items:
                    try:
                        rows.append({
                            "Date":   pd.to_datetime(
                                it.get("Ngay", it.get("date", "")),
                                dayfirst=True, errors="coerce",
                            ),
                            "Open":   float(it.get("GiaMoCua",    it.get("open",   0)) or 0),
                            "High":   float(it.get("GiaCaoNhat",  it.get("high",   0)) or 0),
                            "Low":    float(it.get("GiaThapNhat", it.get("low",    0)) or 0),
                            "Close":  float(it.get("GiaDongCua",  it.get("close",  0)) or 0),
                            "Volume": float(it.get("KLKhopLenh",  it.get("volume", 0)) or 0),
                        })
                    except Exception:
                        continue
                if rows:
                    df = (
                        pd.DataFrame(rows)
                        .dropna(subset=["Close", "Date"])
                    )
                    df = df[df["Close"] > 0].set_index("Date").sort_index()
                    df = df[~df.index.duplicated(keep="last")]
                    if not df.empty and df["Close"].dropna().median() < 1000:
                        for c in ["Open", "High", "Low", "Close"]:
                            df[c] *= 1000
                    if len(df) >= 5:
                        return df
    except Exception:
        pass

    return pd.DataFrame()


def fetch_ohlcv(symbol: str, days: int = HISTORY_DAYS, verbose: bool = True):
    """Cascade: DNSE → SSI → CafeF. Returns (df, source_name)."""
    if verbose: print(f"  📡 DNSE ...", end="", flush=True)
    df = _fetch_dnse(symbol, days)
    if not df.empty:
        if verbose: print(f" ✓ ({len(df)} nến)")
        return df, "DNSE"

    if verbose: print(f" ✗  →  SSI ...", end="", flush=True)
    df = _fetch_ssi(symbol, days)
    if not df.empty:
        if verbose: print(f" ✓ ({len(df)} nến)")
        return df, "SSI"

    if verbose: print(f" ✗  →  CafeF ...", end="", flush=True)
    df = _fetch_cafef(symbol, days)
    if not df.empty:
        if verbose: print(f" ✓ ({len(df)} nến)")
        return df, "CafeF"

    if verbose: print(f" ✗  KHÔNG LẤY ĐƯỢC DỮ LIỆU")
    _log.warning("fetch_ohlcv: all sources failed for %s", symbol)
    return pd.DataFrame(), None


# ═══════════════════════════════════════════════════════════════════════════════
#  A2. ASYNC BATCH FETCH (ThreadPoolExecutor — stdlib, no extra deps)
#  For ~1 600-ticker full-market scans.  Drop-in replacement for the sequential
#  loop in main().  Optional aiohttp upgrade: swap _worker with aiohttp coroutine.
# ═══════════════════════════════════════════════════════════════════════════════

def async_fetch_many(
    symbols: list,
    days: int = HISTORY_DAYS,
    max_workers: int = ASYNC_WORKERS,
    on_progress=None,           # optional callback(done, total, symbol)
) -> dict:
    """
    Fetch OHLCV + RT price for multiple tickers in parallel.

    Uses ThreadPoolExecutor (stdlib) so it works without aiohttp.
    For true async I/O upgrade, replace ``_worker`` with an aiohttp coroutine
    and wrap with ``asyncio.run(...)``.

    Returns:
        dict[symbol] = (result_dict, df)   — same shape as analyse_ticker(..., return_df=True)
    """
    results: dict = {}
    total = len(symbols)

    def _worker(sym: str):
        time.sleep(0.05 + 0.15 * float(np.random.rand()))  # jitter 50–200 ms
        try:
            res, df = analyse_ticker(sym, days=days, verbose=False, return_df=True)
            _log.info("async_fetch_many ✓ %s", sym)
            return sym, (res, df)
        except Exception as exc:
            _log.error("async_fetch_many ✗ %s — %s", sym, exc)
            return sym, ({"ticker": sym, "error": str(exc)}, pd.DataFrame())

    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, sym): sym for sym in symbols}
        for fut in concurrent.futures.as_completed(futures):
            sym, payload = fut.result()
            results[sym] = payload
            done += 1
            if on_progress:
                on_progress(done, total, sym)

    # Return in original order
    return {sym: results[sym] for sym in symbols if sym in results}


# ═══════════════════════════════════════════════════════════════════════════════
#  B. REAL-TIME PRICE — SSI iboard-query
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_ssi_realtime(symbol: str) -> dict:
    """
    SSI iboard-query real-time price, Ceiling/Floor/Reference.
    Endpoint: iboard-query.ssi.com.vn/stock/{TICKER}?boardId=MAIN
    Returns {} if unavailable (caller falls back to OHLCV close).
    """
    url = f"https://iboard-query.ssi.com.vn/stock/{symbol.upper()}?boardId=MAIN"
    try:
        r = requests.get(url, headers=_SSI_HDR, timeout=RT_TIMEOUT)
        if r.status_code == 403:
            return {}
        r.raise_for_status()
        raw = r.json()
        d    = raw if isinstance(raw, dict) else {}
        data = d.get("data", d)
        if not data:
            return {}

        def _f(k, fb=0):
            v = data.get(k, fb)
            try:
                return float(v or 0)
            except Exception:
                return float(fb)

        price   = _f("matchedPrice") or _f("close") or _f("lastPrice")
        ref     = _f("referencePrice") or _f("priorClosePrice")
        ceiling = _f("ceilingPrice")
        floor_  = _f("floorPrice")
        vol     = _f("matchedVolume") or _f("totalVolume")

        # BUG-04 pattern: only use price for scale-trigger (avoid mis-scaling UPCOM <500)
        if 0 < price < 500:
            price   *= 1000
            ref     *= 1000
            ceiling *= 1000
            floor_  *= 1000

        if price <= 0:
            return {}

        pct = ((price - ref) / ref * 100) if ref > 0 else 0.0
        return {
            "price":      price,
            "reference":  ref,
            "ceiling":    ceiling,
            "floor":      floor_,
            "pct_change": pct,
            "volume":     vol,
            "source":     "SSI-RT",
        }
    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  C. INDICATOR ENGINE (fully vectorised — no Python loops over rows)
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all technical indicators in-place (vectorised pandas/numpy).
    Requires columns: Open, High, Low, Close, Volume.
    """
    df = df.loc[:, ~df.columns.duplicated()].copy()

    # ── SMA suite ────────────────────────────────────────────────────────────
    for p in [5, 10, 20, 50, 200]:
        df[f"SMA{p}"] = df["Close"].rolling(p).mean()

    # ── EMA suite ────────────────────────────────────────────────────────────
    for p in [9, 21, 50, 200]:
        df[f"EMA{p}"] = df["Close"].ewm(span=p, adjust=False).mean()

    # ── RSI (Wilder smoothing, 14-period) ────────────────────────────────────
    delta    = df["Close"].diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - 100 / (1 + rs)
    # Pure uptrend (avg_loss=0) → RSI=100; preserve NaN for warmup bars
    df["RSI"] = df["RSI"].where(avg_loss != 0, 100.0)

    # ── Bollinger Bands (20, ±2σ) ────────────────────────────────────────────
    df["BB_Mid"]   = df["SMA20"]
    df["BB_Std"]   = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["BB_Mid"] + df["BB_Std"] * 2
    df["BB_Lower"] = df["BB_Mid"] - df["BB_Std"] * 2

    # ── MACD (12, 26, 9) ─────────────────────────────────────────────────────
    ema12            = df["Close"].ewm(span=12, adjust=False).mean()
    ema26            = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]       = ema12 - ema26
    df["MACD_Signal"]= df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"]  = df["MACD"] - df["MACD_Signal"]

    # ── Volume MA ────────────────────────────────────────────────────────────
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()

    # ── Stochastic %K/%D (14, 3) — vectorised ────────────────────────────────
    _rh14     = df["High"].rolling(14).max()
    _rl14     = df["Low"].rolling(14).min()
    _hh_ll    = (_rh14 - _rl14).replace(0, np.nan)
    df["STOCH_K"] = (df["Close"] - _rl14) / _hh_ll * 100   # retain NaN for insufficient data
    df["STOCH_D"] = df["STOCH_K"].rolling(3).mean()

    # ── ATR (Wilder 14) — vectorised True Range ───────────────────────────────
    _pc      = df["Close"].shift(1)
    _hl      = df["High"] - df["Low"]
    _hc      = (df["High"] - _pc).abs()
    _lc      = (df["Low"]  - _pc).abs()
    df["TR"] = pd.concat([_hl, _hc, _lc], axis=1).max(axis=1)
    df["ATR"]= df["TR"].ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    # ── OBV — vectorised signed-volume cumsum ────────────────────────────────
    df["OBV"]      = (df["Volume"] * np.sign(df["Close"].diff())).fillna(0).cumsum()
    df["OBV_MA20"] = df["OBV"].rolling(20).mean()

    # ── ADX / +DI / -DI (14) — vectorised directional movement ──────────────
    _up_move = df["High"].diff()
    _dn_move = -(df["Low"].diff())
    _pdm     = np.where((_up_move > _dn_move) & (_up_move > 0), _up_move, 0.0)
    _ndm     = np.where((_dn_move > _up_move) & (_dn_move > 0), _dn_move, 0.0)
    atr14    = df["TR"].ewm(alpha=1 / 14, min_periods=14, adjust=False).mean() * 14
    pdm14    = pd.Series(_pdm, index=df.index).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean() * 14
    ndm14    = pd.Series(_ndm, index=df.index).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean() * 14
    df["+DI"]= 100 * pdm14 / (atr14 + 1e-9)
    df["-DI"]= 100 * ndm14 / (atr14 + 1e-9)
    _dx      = 100 * (df["+DI"] - df["-DI"]).abs() / (df["+DI"] + df["-DI"] + 1e-9)
    df["ADX"]= _dx.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    df.drop(columns=["TR"], inplace=True, errors="ignore")

    # ── Williams %R (14) — vectorised ────────────────────────────────────────
    _wh14          = df["High"].rolling(14).max()
    _wl14          = df["Low"].rolling(14).min()
    _wdenom        = (_wh14 - _wl14).replace(0, np.nan)
    df["WILLIAMS_R"] = (-100 * (_wh14 - df["Close"]) / _wdenom).fillna(-50)

    # ── CCI (20) — vectorised via rolling.apply(raw=True) ────────────────────
    _tp      = (df["High"] + df["Low"] + df["Close"]) / 3
    _tp_mean = _tp.rolling(20).mean()
    _tp_mad  = (_tp - _tp.rolling(20).mean()).abs().rolling(20).mean()
    df["CCI"]= (_tp - _tp_mean) / (0.015 * _tp_mad.replace(0, np.nan))

    # ── VSA — Volume Spread Analysis (Wyckoff-based) ──────────────────────────
    # Identifies 4 contextual states used to filter false breakouts:
    #   ACCUM  — wide spread + above-avg vol + close in upper half → institutional buying
    #   DISTRIB— wide spread + above-avg vol + close in lower half → institutional selling
    #   NO_DEMAND—narrow spread + below-avg vol + close drifting up → weak rally, suspect
    #   NO_SUPPLY—narrow spread + below-avg vol + close drifting down → weak decline, possible floor
    #   NEUTRAL — everything else
    _spread      = df["High"] - df["Low"]
    _avg_spread  = _spread.rolling(20).mean()
    _wide_spread = _spread > _avg_spread
    _high_vol    = df["Volume"] > df["Vol_MA20"]
    # Close position within the bar: 1.0 = at high, 0.0 = at low
    _close_pos   = ((
        (df["Close"] - df["Low"]) /
        _spread.replace(0, np.nan)
    ).fillna(0.5))
    # Narrow spread = < 50 % of 20-bar avg spread
    _narrow      = _spread < (_avg_spread * 0.5)
    _low_vol     = df["Volume"] < (df["Vol_MA20"] * 0.7)

    conditions = [
        _wide_spread &  _high_vol & (_close_pos >= 0.6),   # ACCUM
        _wide_spread &  _high_vol & (_close_pos <= 0.4),   # DISTRIB
        _narrow      & _low_vol  & (df["Close"] > df["Close"].shift(1)),  # NO_DEMAND
        _narrow      & _low_vol  & (df["Close"] < df["Close"].shift(1)),  # NO_SUPPLY
    ]
    choices = ["ACCUM", "DISTRIB", "NO_DEMAND", "NO_SUPPLY"]
    df["VSA_State"] = np.select(conditions, choices, default="NEUTRAL")

    # VSA numeric score  (+1 bullish, -1 bearish, 0 neutral) — used in signal engine
    df["VSA_Score"] = np.select(
        [df["VSA_State"] == "ACCUM",
         df["VSA_State"] == "NO_SUPPLY",
         df["VSA_State"] == "DISTRIB",
         df["VSA_State"] == "NO_DEMAND"],
        [1, 0.5, -1, -0.5],
        default=0,
    )

    return df


def _last(df: pd.DataFrame, col: str):
    """Safely return the last non-NaN value of a column, or None."""
    try:
        v = float(df[col].iloc[-1])
        return None if np.isnan(v) else v
    except Exception:
        return None


def _last_str(df: pd.DataFrame, col: str) -> str:
    """Safely return the last string value of a column, or empty string."""
    try:
        return str(df[col].iloc[-1])
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  D0a. PIVOT & FIBONACCI LEVELS
# ═══════════════════════════════════════════════════════════════════════════════

def calc_monthly_pivots(df: pd.DataFrame) -> dict:
    """
    Monthly pivot points derived from last 20 bars (proxy for ~1 calendar month).
    Returns {pp, r1, r2, s1, s2} or {} if insufficient data.
    """
    if df is None or len(df) < 20:
        return {}
    last20 = df.iloc[-20:]
    H  = float(last20["High"].max())
    L  = float(last20["Low"].min())
    C  = float(df["Close"].iloc[-1])
    PP = (H + L + C) / 3
    return {
        "monthly_pp": round(PP, 0),
        "monthly_r1": round(2 * PP - L, 0),
        "monthly_r2": round(PP + (H - L), 0),
        "monthly_s1": round(2 * PP - H, 0),
        "monthly_s2": round(PP - (H - L), 0),
    }


def calc_fibonacci_levels(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    Fibonacci retracement levels from highest high / lowest low over `lookback` bars.
    Returns {swing_high, swing_low, fib_382, fib_500, fib_618} or {} if insufficient.
    """
    if df is None or len(df) < lookback:
        return {}
    window = df.iloc[-lookback:]
    sh = float(window["High"].max())
    sl = float(window["Low"].min())
    rng = sh - sl
    if rng <= 0:
        return {}
    return {
        "fib_swing_high": round(sh, 0),
        "fib_swing_low":  round(sl, 0),
        "fib_382":        round(sh - 0.382 * rng, 0),
        "fib_500":        round(sh - 0.500 * rng, 0),
        "fib_618":        round(sh - 0.618 * rng, 0),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  D0. REGIME CLASSIFIER  (multi-factor market-state detection)
# ═══════════════════════════════════════════════════════════════════════════════

def classify_regime(df: pd.DataFrame) -> dict:
    """
    Classify the current market regime using long-term trend + volatility.
    Regimes:
      BULL_TREND  — SMA200 rising, ADX>25, price>SMA200, +DI>-DI
      BEAR_TREND  — SMA200 falling or price<SMA200, ADX>25, -DI>+DI
      HIGH_VOL    — ATR spike > 1.3× its 50-bar rolling mean
      SIDEWAYS    — ADX<25 and none of the above
    Returns dict with 'regime', 'regime_label', 'regime_score' (-2..+2),
    and 'sma200_slope' (%/20d).  Used to tighten BUY thresholds in BEAR.
    """
    _EMPTY = {"regime": "UNKNOWN", "regime_label": "–", "regime_score": 0, "sma200_slope": 0.0}
    if df is None or len(df) < 50:
        return _EMPTY
    try:
        close_now = float(df["Close"].iloc[-1])
        _s200     = df["SMA200"].dropna()
        sma200_slope = 0.0
        if len(_s200) >= 20:
            sma200_slope = float((_s200.iloc[-1] - _s200.iloc[-20]) / _s200.iloc[-20] * 100)
        sma200_now   = float(_s200.iloc[-1]) if len(_s200) else None
        above_sma200 = bool(sma200_now and close_now > sma200_now)

        atr_now  = _last(df, "ATR")
        atr_ma50 = df["ATR"].rolling(50).mean().iloc[-1] if "ATR" in df.columns else None
        high_vol = bool(atr_now and atr_ma50
                        and not np.isnan(float(atr_ma50))
                        and atr_now > float(atr_ma50) * 1.3)

        adx      = _last(df, "ADX")
        pdi      = _last(df, "+DI")
        ndi      = _last(df, "-DI")
        trending = bool(adx and adx > 25)
        bull_di  = bool(pdi and ndi and pdi > ndi)
        s        = round(sma200_slope, 2)

        if high_vol:
            return {"regime": "HIGH_VOL",   "regime_label": "Biến động cao",     "regime_score":  0, "sma200_slope": s}
        if trending and above_sma200 and sma200_slope > 0.3 and bull_di:
            return {"regime": "BULL_TREND", "regime_label": "Xu hướng tăng",     "regime_score":  2, "sma200_slope": s}
        if trending and (not above_sma200 or sma200_slope < -0.3) and not bull_di:
            return {"regime": "BEAR_TREND", "regime_label": "Xu hướng giảm",     "regime_score": -2, "sma200_slope": s}
        if trending:
            if bull_di:
                return {"regime": "BULL_TREND", "regime_label": "Xu hướng tăng nhẹ", "regime_score":  1, "sma200_slope": s}
            return     {"regime": "BEAR_TREND", "regime_label": "Xu hướng giảm nhẹ", "regime_score": -1, "sma200_slope": s}
        return {"regime": "SIDEWAYS", "regime_label": "Đi ngang", "regime_score": 0, "sma200_slope": s}
    except Exception as e:
        _log.debug("classify_regime error: %s", e)
        return _EMPTY


def backtest_ticker(df: pd.DataFrame, forward_days: int = 10, key_prefix: str = "bt",
                    threshold: float = 65.0) -> dict:
    """
    Walk-forward accuracy test on BUY signals over available history.
    Scans bars [200 .. end-forward_days], computes a simplified bull/bear
    score (SMA structure + RSI + MACD) at each bar, then measures the
    forward_days-ahead return to evaluate historical signal reliability.
    Uses only MA + RSI + MACD to avoid look-ahead bias from live RT data.
    key_prefix: key namespace in returned dict (e.g. 'bt3', 'bt5', 'bt7', 'bt10').
    threshold: minimum bull% to fire a BUY signal (matches live signal logic).
    Returns prefixed metrics dict, or {} when fewer than 5 signals are found.
    """
    if df is None or len(df) < 220:
        return {}
    try:
        close   = df["Close"].values
        sma20   = df["SMA20"].values   if "SMA20"        in df.columns else None
        sma50   = df["SMA50"].values   if "SMA50"        in df.columns else None
        sma200  = df["SMA200"].values  if "SMA200"       in df.columns else None
        rsi_v   = df["RSI"].values     if "RSI"          in df.columns else None
        macd_v  = df["MACD"].values    if "MACD"         in df.columns else None
        macd_sg = df["MACD_Signal"].values if "MACD_Signal" in df.columns else None
        n       = len(close)
        returns = []
        for i in range(200, n - forward_days):
            p = close[i]
            if p <= 0 or np.isnan(p):
                continue
            bull = bear = 0.0
            if sma200 is not None and not np.isnan(sma200[i]):
                if p > sma200[i]: bull += 3
                else:             bear += 3
            if sma50 is not None and not np.isnan(sma50[i]):
                if p > sma50[i]:  bull += 2
                else:             bear += 2
            if sma20 is not None and not np.isnan(sma20[i]):
                if p > sma20[i]:  bull += 1
                else:             bear += 1
            if rsi_v is not None and not np.isnan(rsi_v[i]):
                v = rsi_v[i]
                if v < 35:   bull += min(int((35 - v) * 0.5), 10)
                elif v > 65: bear += min(int((v - 65) * 0.5), 10)
            if macd_v is not None and macd_sg is not None:
                m, ms = macd_v[i], macd_sg[i]
                if not (np.isnan(m) or np.isnan(ms)):
                    if m > ms: bull += 3
                    else:      bear += 3
            total = bull + bear
            if total == 0:
                continue
            if bull / total * 100 >= threshold:     # BUY signal fired
                fp = close[i + forward_days]
                if fp > 0 and not np.isnan(fp):
                    returns.append((fp - p) / p * 100)
        if len(returns) < 5:
            return {}
        arr    = np.array(returns)
        wins   = arr[arr > 0]
        losses = arr[arr <= 0]
        streak = max_streak = 0
        for x in arr:
            if x <= 0:
                streak += 1; max_streak = max(max_streak, streak)
            else:
                streak = 0
        p = key_prefix
        return {
            f"{p}_signals":         int(len(arr)),
            f"{p}_win_rate":        round(float(len(wins) / len(arr) * 100), 1),
            f"{p}_avg_return":      round(float(arr.mean()), 2),
            f"{p}_avg_win":         round(float(wins.mean()),   2) if len(wins)   else 0.0,
            f"{p}_avg_loss":        round(float(losses.mean()), 2) if len(losses) else 0.0,
            f"{p}_max_loss_streak": int(max_streak),
            f"{p}_forward_days":    forward_days,
            f"{p}_threshold":       threshold,
        }
    except Exception as e:
        _log.debug("backtest_ticker error: %s", e)
        return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  D. SIGNAL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _vn_tick_round(price: float) -> int:
    """Round price to nearest VN exchange tick size."""
    if price is None:
        return 0
    if price >= 50_000:
        return int(round(price / 100) * 100)
    if price >= 10_000:
        return int(round(price / 50) * 50)
    return int(round(price / 10) * 10)


def analyse_ticker(symbol: str, days: int = HISTORY_DAYS, verbose: bool = True, return_df: bool = False):
    """
    Full pipeline: OHLCV → Indicators → Real-time price → Signal → Output dict.
    verbose=False suppresses all console prints (used by Streamlit UI).
    return_df=True returns (result_dict, df_with_indicators) instead of just result_dict.
    """
    symbol = symbol.strip().upper()
    if verbose:
        print(f"\n{'─' * 58}")
        print(f"  🔍 Đang phân tích: {symbol}")

    # ① OHLCV ─────────────────────────────────────────────────────────────────
    df, ohlcv_src = fetch_ohlcv(symbol, days, verbose=verbose)
    if df is None or df.empty:
        err = {"ticker": symbol, "error": "Không lấy được dữ liệu OHLCV"}
        return (err, pd.DataFrame()) if return_df else err

    # ② Real-time price ────────────────────────────────────────────────────────
    if verbose: print(f"  📡 SSI real-time ...", end="", flush=True)
    rt = fetch_ssi_realtime(symbol)
    if verbose:
        if rt:
            print(f" ✓  giá={rt['price']:,.0f}  ({rt['pct_change']:+.2f}%)")
        else:
            print(f" ✗  (dùng giá đóng cửa gần nhất)")

    # ③ Indicators ────────────────────────────────────────────────────────────
    df = calculate_indicators(df)
    _log.debug("%s indicators computed — %d rows", symbol, len(df))

    # ③b Regime classification + walk-forward backtest (vectorised, no I/O) ──
    _regime  = classify_regime(df)
    _pivots  = calc_monthly_pivots(df)
    _fib     = calc_fibonacci_levels(df)
    _bt3    = backtest_ticker(df, forward_days=3,  key_prefix="bt3")
    _bt5    = backtest_ticker(df, forward_days=5,  key_prefix="bt5")
    _bt7    = backtest_ticker(df, forward_days=7,  key_prefix="bt7")
    _bt10   = backtest_ticker(df, forward_days=10, key_prefix="bt10")

    # ④ Extract latest values ─────────────────────────────────────────────────
    price    = rt.get("price")    or _last(df, "Close")
    ref      = rt.get("reference") or _last(df, "Close")
    ceiling  = rt.get("ceiling", 0) or 0
    floor_   = rt.get("floor",   0) or 0
    pct_chg  = rt.get("pct_change", 0.0)

    vol_last  = _last(df, "Volume")
    vol_avg   = _last(df, "Vol_MA20")
    kl_ratio  = (vol_last / vol_avg) if vol_avg and vol_avg > 0 and vol_last else None
    vsa_state = _last_str(df, "VSA_State")   # latest Wyckoff VSA state
    vsa_score = _last(df, "VSA_Score") or 0.0

    sma20    = _last(df, "SMA20")
    sma50    = _last(df, "SMA50")
    sma200   = _last(df, "SMA200")
    ema9     = _last(df, "EMA9")
    ema21    = _last(df, "EMA21")
    ema50    = _last(df, "EMA50")
    ema200   = _last(df, "EMA200")

    rsi      = _last(df, "RSI")
    stoch_k  = _last(df, "STOCH_K")
    stoch_d  = _last(df, "STOCH_D")
    macd     = _last(df, "MACD")
    macd_sig = _last(df, "MACD_Signal")
    macd_hst = _last(df, "MACD_Hist")
    bb_upper = _last(df, "BB_Upper")
    bb_lower = _last(df, "BB_Lower")
    bb_mid   = _last(df, "BB_Mid")
    atr      = _last(df, "ATR")
    adx      = _last(df, "ADX")
    pdi      = _last(df, "+DI")
    ndi      = _last(df, "-DI")
    obv      = _last(df, "OBV")
    obv_ma   = _last(df, "OBV_MA20")
    wr       = _last(df, "WILLIAMS_R")
    cci      = _last(df, "CCI")

    # ⑤ Trend structure ───────────────────────────────────────────────────────
    above_sma200 = bool(price and sma200 and price > sma200)
    above_sma50  = bool(price and sma50  and price > sma50)
    above_sma20  = bool(price and sma20  and price > sma20)
    sma_layers   = sum([above_sma200, above_sma50, above_sma20])

    if adx and adx > 25:
        if pdi and ndi and pdi > ndi:
            adx_dir   = "UP"
            adx_label = f"TRENDING ↑  (ADX={adx:.1f})"
        else:
            adx_dir   = "DOWN"
            adx_label = f"TRENDING ↓  (ADX={adx:.1f})"
    else:
        adx_dir   = "FLAT"
        adx_label = f"SIDEWAYS    (ADX={adx:.1f})" if adx else "SIDEWAYS"

    # Ceiling / floor proximity (within 0.5%)
    ceiling_pct = ((ceiling - price) / price * 100) if ceiling and price else None
    floor_pct   = ((price - floor_)  / price * 100) if floor_  and price else None
    at_ceiling  = ceiling_pct is not None and ceiling_pct < 0.5
    at_floor    = floor_pct   is not None and floor_pct   < 0.5

    # VSA signal override flags (false-breakout filters) — informational only
    _vsa_bull_state = vsa_state in ("ACCUM",   "NO_SUPPLY")
    _vsa_bear_state = vsa_state in ("DISTRIB", "NO_DEMAND")

    # ⑥ Bull / Bear scoring ───────────────────────────────────────────────────
    bull = 0.0
    bear = 0.0
    confirms = []

    # MA structure (6 pts)
    if above_sma200:  bull += 3; confirms.append("↑SMA200")
    else:             bear += 3
    if above_sma50:   bull += 2; confirms.append("↑SMA50")
    else:             bear += 2
    if above_sma20:   bull += 1; confirms.append("↑SMA20")
    else:             bear += 1

    # EMA cross (2 pts)
    if ema9 and ema21:
        if ema9 > ema21:  bull += 2; confirms.append("EMA9↑21")
        else:             bear += 2

    # RSI (up to 10 pts)
    # FIX: use round() before int() so RSI=34.5 gives 1 pt instead of 0
    if rsi is not None:
        if rsi < 35:
            pts = min(round((35 - rsi) * 0.5), 10)
            bull += pts; confirms.append(f"RSI={rsi:.0f}↓")
        elif rsi > 65:
            pts = min(round((rsi - 65) * 0.5), 10)
            bear += pts; confirms.append(f"RSI={rsi:.0f}↑")

    # Stochastic (3 pts)
    if stoch_k is not None:
        if stoch_k < 20:   bull += 3; confirms.append(f"Stoch={stoch_k:.0f}↓")
        elif stoch_k > 80: bear += 3; confirms.append(f"Stoch={stoch_k:.0f}↑")

    # MACD (3 pts)
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:  bull += 3; confirms.append("MACD↑")
        else:                bear += 3; confirms.append("MACD↓")

    # ADX direction (2 pts)
    if adx and adx > 20:
        if adx_dir == "UP":    bull += 2; confirms.append(f"ADX↑{adx:.0f}")
        elif adx_dir == "DOWN":bear += 2

    # OBV (2 pts)
    if obv is not None and obv_ma is not None:
        if obv > obv_ma:  bull += 2; confirms.append("OBV↑")
        else:             bear += 2

    # Bollinger (4 pts)
    if price and bb_lower and price < bb_lower:
        bull += 4; confirms.append("Giá<BB↓")
    if price and bb_upper and price > bb_upper:
        bear += 4; confirms.append("Giá>BB↑")

    # Williams %R (2 pts)
    if wr is not None:
        if wr < -80:  bull += 2; confirms.append(f"W%R={wr:.0f}↓")
        elif wr > -20: bear += 2; confirms.append(f"W%R={wr:.0f}↑")

    # Volume + trend (2 pts)
    if kl_ratio and kl_ratio > 1.5:
        confirms.append(f"KL={kl_ratio:.1f}×")
        if adx_dir == "UP":    bull += 2
        elif adx_dir == "DOWN":bear += 2

    # Ceiling / floor (2 pts)
    if at_ceiling: bear += 2
    if at_floor:   bull += 2

    # VSA / Wyckoff (up to ±4 pts — prevents false breakout signals)
    # ACCUM  (+4): wide spread + high vol + close near high → institutional accumulation
    # DISTRIB(−4): wide spread + high vol + close near low  → institutional distribution
    # NO_DEMAND(−2): narrow spread + low vol on up-close    → weak rally, fade risk
    # NO_SUPPLY (+2): narrow spread + low vol on down-close → selling exhaustion
    _vsa_bull_pts = {"ACCUM": 4, "NO_SUPPLY": 2, "NEUTRAL": 0, "NO_DEMAND": 0, "DISTRIB": 0}
    _vsa_bear_pts = {"DISTRIB": 4, "NO_DEMAND": 2, "NEUTRAL": 0, "ACCUM": 0, "NO_SUPPLY": 0}
    bull += _vsa_bull_pts.get(vsa_state, 0)
    bear += _vsa_bear_pts.get(vsa_state, 0)
    if vsa_state not in ("NEUTRAL", ""):
        confirms.append(f"VSA:{vsa_state}")

    # ⑦ Signal label (regime-adjusted thresholds) ─────────────────────────────
    total    = bull + bear
    bull_pct = (bull / total * 100) if total > 0 else 50.0

    # BEAR_TREND regime → raise BUY bar to 70% to suppress weak-rally false positives
    _buy_thr = 70 if _regime.get("regime") == "BEAR_TREND" else 65
    _wup_thr = 58 if _regime.get("regime") == "BEAR_TREND" else 55

    if bull_pct >= _buy_thr:
        signal     = "MUA"
        signal_sym = "🟢"
    elif bull_pct >= _wup_thr:
        signal     = "THEO DÕI–TĂNG"
        signal_sym = "🔵"
    elif bull_pct <= 35:
        signal     = "BÁN / TRÁNH"
        signal_sym = "🔴"
    elif bull_pct <= 45:
        signal     = "THEO DÕI–GIẢM"
        signal_sym = "🟠"
    else:
        signal     = "TRUNG LẬP"
        signal_sym = "⚪"

    # ⑦a Turnover guard — require 2-of-3 prior bars to agree with signal direction
    # Prevents single-bar noise from flipping the output (parameter stability).
    _is_bull      = bull_pct > 50
    _confirm_bars = 0
    for _idx in (-4, -3, -2):
        try:
            _row   = df.iloc[_idx]
            _votes = 0
            _mh    = _row["MACD_Hist"]
            if not pd.isna(_mh):  _votes += int((_mh  > 0)   == _is_bull)
            _rs    = _row["RSI"]
            if not pd.isna(_rs):  _votes += int((_rs  > 50)  == _is_bull)
            _s20   = _row["SMA20"]; _cl = _row["Close"]
            if not pd.isna(_s20): _votes += int((_cl  > _s20) == _is_bull)
            _confirm_bars += int(_votes >= 2)
        except Exception:
            pass
    signal_confirmed = _confirm_bars >= 2   # True if ≥2 of 3 trailing bars agree

    # ⑧ ATR-based Entry / TP / SL ─────────────────────────────────────────────
    entry = price
    if atr and price:
        sl  = _vn_tick_round(price - 1.5 * atr)
        tp1 = _vn_tick_round(price + 2.0 * atr)
        tp2 = _vn_tick_round(price + 3.5 * atr)
        rr1 = (tp1 - price) / (price - sl) if price > sl else None
    else:
        sl = tp1 = tp2 = rr1 = None

    # ⑨ Trend structure label ─────────────────────────────────────────────────
    _layer_labels = {
        3: "TĂNG  (trên cả 3 MA)",
        2: "TĂNG NHẸ  (2/3 MA)",
        1: "GIẢM NHẸ  (1/3 MA)",
        0: "GIẢM  (dưới cả 3 MA)",
    }
    trend_struct = _layer_labels[sma_layers]

    # ⑩ Commentary ─────────────────────────────────────────────────────────────
    commentary = _build_commentary(
        symbol, price, ref,
        sma20, sma50, sma200,
        rsi, stoch_k, adx, adx_dir, pdi, ndi,
        macd, macd_sig,
        kl_ratio, bb_upper, bb_lower,
        at_ceiling, at_floor,
    )

    _log.info(
        "%s  price=%.0f  signal=%s  VSA=%s  regime=%s  bull=%.0f  bear=%.0f  confirmed=%s",
        symbol, price or 0, signal, vsa_state, _regime.get("regime", "?"), bull, bear, signal_confirmed,
    )

    result = {
        "ticker":       symbol,
        "price":        price,
        "pct_change":   pct_chg,
        "reference":    ref,
        "ceiling":      ceiling or None,
        "floor":        floor_  or None,
        "sma20":        sma20,
        "sma50":        sma50,
        "sma200":       sma200,
        "ema9":         ema9,
        "ema21":        ema21,
        "ema50":        ema50,
        "ema200":       ema200,
        "rsi":          rsi,
        "stoch_k":      stoch_k,
        "stoch_d":      stoch_d,
        "macd":         macd,
        "macd_signal":  macd_sig,
        "macd_hist":    macd_hst,
        "bb_upper":     bb_upper,
        "bb_mid":       bb_mid,
        "bb_lower":     bb_lower,
        "atr":          atr,
        "adx":          adx,
        "pdi":          pdi,
        "ndi":          ndi,
        "obv":          obv,
        "obv_ma":       obv_ma,
        "williams_r":   wr,
        "cci":          cci,
        "vol_last":     vol_last,
        "vol_avg":      vol_avg,
        "kl_ratio":     kl_ratio,
        "trend_struct": trend_struct,
        "adx_label":    adx_label,
        "signal":       signal,
        "signal_sym":   signal_sym,
        "bull_score":   bull,
        "bear_score":   bear,
        "bull_pct":     bull_pct,
        "confirmations":confirms,
        "entry":        entry,
        "sl":           sl,
        "tp1":          tp1,
        "tp2":          tp2,
        "rr1":          rr1,
        "at_ceiling":   at_ceiling,
        "at_floor":     at_floor,
        "vsa_state":    vsa_state,
        "vsa_score":    vsa_score,
        "regime":              _regime.get("regime",       "UNKNOWN"),
        "regime_label":        _regime.get("regime_label", ""),
        "regime_score":        _regime.get("regime_score", 0),
        "sma200_slope":        _regime.get("sma200_slope", 0.0),
        "signal_confirmed":    signal_confirmed,
        "signal_confirm_bars": _confirm_bars,
        **_pivots,
        **_fib,
        **_bt3,
        **_bt5,
        **_bt7,
        **_bt10,
        "commentary":   commentary,
        "ohlcv_src":    ohlcv_src,
        "bars":         len(df),
        "last_date":    str(df.index[-1].date()),
        "scan_time":    datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    if return_df:
        return result, df
    return result


def _build_commentary(
    symbol, price, ref,
    sma20, sma50, sma200,
    rsi, stoch_k, adx, adx_dir, pdi, ndi,
    macd, macd_sig,
    kl_ratio, bb_upper, bb_lower,
    at_ceiling, at_floor,
) -> str:
    lines = []

    # Ceiling / floor warnings first
    if at_ceiling:
        lines.append("⚠️  Giá chạm TRẦN — rủi ro rất cao, không mua mới ngày hôm nay.")
    if at_floor:
        lines.append("✅  Giá chạm SÀN — vùng hỗ trợ kỹ thuật mạnh nhất.")

    # MA position
    if sma200 and price:
        d200 = (price - sma200) / sma200 * 100
        pos  = "trên" if price > sma200 else "dưới"
        lines.append(f"• {symbol} đang {pos} SMA200 {d200:+.1f}%.")
    if sma50 and price:
        d50  = (price - sma50) / sma50 * 100
        pos  = "trên" if price > sma50 else "dưới"
        lines.append(f"• Giá {pos} SMA50 {d50:+.1f}%.")
    if sma20 and price:
        d20  = (price - sma20) / sma20 * 100
        pos  = "trên" if price > sma20 else "dưới"
        lines.append(f"• Giá {pos} SMA20 {d20:+.1f}%.")

    # ADX / trend
    if adx:
        if adx > 25:
            dir_vi = "TĂNG (+DI>-DI)" if adx_dir == "UP" else "GIẢM (-DI>+DI)"
            lines.append(f"• Xu hướng rõ ràng — ADX={adx:.1f} (>25), hướng {dir_vi}.")
        elif adx > 20:
            lines.append(f"• Xu hướng đang hình thành — ADX={adx:.1f}.")
        else:
            lines.append(f"• Cổ phiếu đang đi ngang — ADX={adx:.1f} (<20).")

    # RSI
    if rsi is not None:
        if rsi < 30:
            lines.append(f"• ✅ RSI={rsi:.0f} — vùng QUÁ BÁN, có thể đảo chiều ngắn hạn.")
        elif rsi < 40:
            lines.append(f"• RSI={rsi:.0f} — tiệm cận vùng quá bán.")
        elif rsi > 70:
            lines.append(f"• ⚠️ RSI={rsi:.0f} — vùng QUÁ MUA, cẩn thận đảo chiều.")
        elif rsi > 60:
            lines.append(f"• RSI={rsi:.0f} — tiệm cận vùng quá mua.")
        else:
            lines.append(f"• RSI={rsi:.0f} — trung tính.")

    # Stochastic
    if stoch_k is not None:
        if stoch_k < 20:
            lines.append(f"• ✅ Stoch %K={stoch_k:.0f} — quá bán, hỗ trợ mua.")
        elif stoch_k > 80:
            lines.append(f"• ⚠️ Stoch %K={stoch_k:.0f} — quá mua, cẩn thận.")

    # MACD
    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            lines.append(f"• ✅ MACD cắt lên Signal — động lượng dương.")
        else:
            lines.append(f"• ⛔ MACD dưới Signal — động lượng âm.")

    # Bollinger
    if price and bb_lower and price < bb_lower:
        lines.append(f"• ✅ Giá dưới BB dưới ({bb_lower:,.0f}) — vùng quá bán kỹ thuật.")
    if price and bb_upper and price > bb_upper:
        lines.append(f"• ⚠️ Giá trên BB trên ({bb_upper:,.0f}) — vùng quá mua kỹ thuật.")

    # Volume
    if kl_ratio:
        if kl_ratio >= 2.0:
            lines.append(f"• 🔊 Khối lượng tăng vọt {kl_ratio:.1f}× MA20 — xác nhận tín hiệu mạnh.")
        elif kl_ratio >= 1.5:
            lines.append(f"• 🔊 Khối lượng cao {kl_ratio:.1f}× MA20.")
        elif kl_ratio < 0.5:
            lines.append(f"• 📉 Khối lượng yếu {kl_ratio:.1f}× MA20 — tín hiệu kém tin cậy.")

    return "\n".join(lines) if lines else "Không có nhận xét bổ sung."


# ═══════════════════════════════════════════════════════════════════════════════
#  E. REPORT PRINTER
# ═══════════════════════════════════════════════════════════════════════════════

def _fp(v) -> str:
    """Format price with thousands separator."""
    if v is None: return "–"
    return f"{v:,.0f}"


def _fd(v, price) -> str:
    """Format delta: 'MA vs Price' as percentage string."""
    if v is None or price is None or price == 0:
        return ""
    pct  = (v - price) / price * 100
    sign = "+" if pct >= 0 else ""
    return f"({sign}{pct:.2f}%)"


def print_report(r: dict) -> None:
    if "error" in r:
        print(f"\n  ❌  {r['ticker']}: {r['error']}\n")
        return

    W    = 62
    sep  = "═" * W
    sep2 = "─" * W
    p    = r["price"]
    pct_str = f"  {r['pct_change']:+.2f}%" if r.get("pct_change") else ""

    print(f"\n{sep}")
    print(f"  {r['signal_sym']}  {r['ticker']:<6}  Giá: {_fp(p)}{pct_str}   ➤ {r['signal']}")
    print(f"  📅 {r['last_date']}   Nguồn: {r['ohlcv_src']} ({r['bars']} nến)   ⏱ {r['scan_time']}")
    print(sep2)

    # Price board
    print(f"  {'Trần':>12}: {_fp(r['ceiling']):<14}  {'Sàn':>6}: {_fp(r['floor'])}")
    print(f"  {'Tham chiếu':>12}: {_fp(r['reference']):<14}  {'ATR':>6}: {_fp(r['atr'])}")
    print(sep2)

    # MA table
    print(f"  {'Chỉ số':<12}  {'Giá trị':>11}  {'vs Giá':>10}")
    for label, key in [
        ("SMA20",  "sma20"),
        ("SMA50",  "sma50"),
        ("SMA200", "sma200"),
        ("EMA9",   "ema9"),
        ("EMA21",  "ema21"),
        ("BB Mid", "bb_mid"),
        ("BB Trên","bb_upper"),
        ("BB Dưới","bb_lower"),
    ]:
        val = r.get(key)
        print(f"  {label:<12}  {_fp(val):>11}  {_fd(val, p):>10}")
    print(sep2)

    # Momentum
    print(f"  {'RSI(14)':<14}  {r['rsi']:>7.1f}" if r["rsi"] is not None else
          f"  {'RSI(14)':<14}  {'–':>7}")
    print(f"  {'Stoch %K/%D':<14}  {r['stoch_k']:>5.1f} / {r['stoch_d']:>5.1f}"
          if r["stoch_k"] is not None and r["stoch_d"] is not None else
          f"  {'Stoch %K/%D':<14}  {'–':>13}")
    print(f"  {r['adx_label']:<30}  +DI={r['pdi']:.1f}  -DI={r['ndi']:.1f}"
          if r["adx"] and r["pdi"] and r["ndi"] else
          f"  {'ADX':<14}  {'–':>12}")
    macd_str = (f"{r['macd']:+,.0f}  /  Signal {r['macd_signal']:+,.0f}  /  Hist {r['macd_hist']:+,.0f}"
                if r["macd"] is not None and r["macd_signal"] is not None else "–")
    print(f"  {'MACD':<14}  {macd_str}")
    kl_str = f"{r['kl_ratio']:.1f}× MA20" if r["kl_ratio"] else "–"
    print(f"  {'Khối lượng':<14}  {kl_str}")
    if r["williams_r"] is not None:
        print(f"  {'Williams %R':<14}  {r['williams_r']:>7.1f}")
    if r["cci"] is not None:
        print(f"  {'CCI(20)':<14}  {r['cci']:>7.1f}")
    print(sep2)

    # Signal summary
    print(f"  Cấu trúc MA : {r['trend_struct']}")
    print(f"  ADX         : {r['adx_label']}")
    c_str = "  ·  ".join(r["confirmations"]) if r["confirmations"] else "–"
    print(f"  Xác nhận    : {c_str}")
    print(f"  Bull / Bear : {r['bull_score']:.0f}pt  /  {r['bear_score']:.0f}pt  "
          f"({r['bull_pct']:.0f}% bull)")
    print(sep2)

    # Entry / TP / SL
    if r["entry"] and r["sl"] and r["tp1"]:
        print(f"  {'Vào lệnh':<20}  {_fp(r['entry']):>10}")
        print(f"  {'Cắt lỗ  SL (ATR×1.5)':<20}  {_fp(r['sl']):>10}")
        print(f"  {'Mục tiêu TP1 (ATR×2.0)':<20}  {_fp(r['tp1']):>10}")
        print(f"  {'Mục tiêu TP2 (ATR×3.5)':<20}  {_fp(r['tp2']):>10}")
        if r["rr1"]:
            print(f"  {'R:R':<20}  {r['rr1']:>9.1f}:1")
        print(sep2)

    # Multi-timeframe backtest summary
    _bt_rows = []
    for _pfx, _lbl in [("bt3", "3 ngày"), ("bt5", "5 ngày"), ("bt7", "7 ngày"), ("bt10", "10 ngày")]:
        if r.get(f"{_pfx}_signals"):
            _wr  = r[f"{_pfx}_win_rate"]
            _ar  = r[f"{_pfx}_avg_return"]
            _aw  = r[f"{_pfx}_avg_win"]
            _al  = r[f"{_pfx}_avg_loss"]
            _mls = r[f"{_pfx}_max_loss_streak"]
            _sig = r[f"{_pfx}_signals"]
            _bt_rows.append(
                f"  {_lbl:<8}  tín hiệu={_sig:>3}  win={_wr:>5.1f}%  "
                f"avg={_ar:>+6.2f}%  thắng={_aw:>+6.2f}%  thua={_al:>+6.2f}%  "
                f"thua liên tiếp tối đa={_mls}"
            )
    if _bt_rows:
        print(f"\n  📊 Backtest walk-forward (SMA+RSI+MACD):\n")
        print(f"  {'Khung':<8}  {'Tín hiệu':>9}  {'Win%':>6}  "
              f"{'Avg%':>7}  {'Thắng%':>8}  {'Thua%':>8}  {'Thua liên tiếp tối đa'}")
        print(f"  {'─'*80}")
        for _row in _bt_rows:
            print(_row)
        print(sep2)

    # Commentary
    print(f"\n  📝 Nhận xét:\n")
    for line in r["commentary"].split("\n"):
        print(f"     {line}")
    print()


def print_summary_table(results: list) -> None:
    W = 78
    print(f"\n{'═' * W}")
    print(f"  {'BẢNG TỔNG KẾT':^{W - 4}}")
    print(f"{'─' * W}")
    hdr = (
        f"  {'Mã':<6}  {'Giá':>10}  {'%Δ':>6}  "
        f"{'RSI':>5}  {'ADX':>5}  {'Stoch':>6}  {'KL×':>5}  {'Tín hiệu'}"
    )
    print(hdr)
    print(f"{'─' * W}")
    for r in results:
        if "error" in r:
            print(f"  {r['ticker']:<6}  {'–':>10}  {'–':>6}  {'–':>5}  {'–':>5}  {'–':>6}  {'–':>5}  ❌ ERROR")
            continue
        pct  = f"{r['pct_change']:+.1f}%" if r.get("pct_change") else "–"
        rsi  = f"{r['rsi']:.0f}"        if r["rsi"] is not None else "–"
        adx  = f"{r['adx']:.0f}"        if r["adx"] is not None else "–"
        stk  = f"{r['stoch_k']:.0f}"    if r["stoch_k"] is not None else "–"
        klr  = f"{r['kl_ratio']:.1f}"   if r["kl_ratio"] else "–"
        ceil_flag = " ⚠️TRẦN" if r.get("at_ceiling") else ""
        print(
            f"  {r['ticker']:<6}  {r['price']:>10,.0f}  {pct:>6}  "
            f"{rsi:>5}  {adx:>5}  {stk:>6}  {klr:>5}  "
            f"{r['signal_sym']} {r['signal']:<14}{ceil_flag}"
        )
    print(f"{'═' * W}")


# ═══════════════════════════════════════════════════════════════════════════════
#  F. MAIN
# ═══════════════════════════════════════════════════════════════════════════════

BANNER = """
╔══════════════════════════════════════════════════════╗
║   QUANT PROFILER  —  Vietnam Stock Analyser  v1.0   ║
║   Data:  DNSE → SSI → CafeF  (400 ngày lịch sử)    ║
║   RT  :  SSI iboard-query.ssi.com.vn                ║
╚══════════════════════════════════════════════════════╝"""


def main() -> None:
    # --web / --ui flag: launch the Streamlit browser UI
    if len(sys.argv) > 1 and sys.argv[1] in ("--web", "--ui"):
        import subprocess, os as _os
        _here = _os.path.dirname(_os.path.abspath(__file__))
        subprocess.run(["streamlit", "run",
                        _os.path.join(_here, "Quant_Profiler_ui.py")])
        sys.exit(0)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None
    print(BANNER)

    # Accept tickers from CLI args or interactive prompt
    if len(sys.argv) > 1:
        ticker_str = " ".join(sys.argv[1:])
    else:
        ticker_str = input(
            "\nNhập mã cổ phiếu (phân cách bởi dấu phẩy  ','):\n> "
        ).strip()

    if not ticker_str:
        print("Không có mã nào được nhập. Thoát.")
        sys.exit(0)

    import re as _re_cli
    _VN_TICKER_RE = _re_cli.compile(r'^(?=.*[A-Za-z])[A-Za-z0-9]{2,6}$')
    _raw = [t.strip().upper() for t in ticker_str.replace(";", ",").split(",") if t.strip()]
    tickers = [t for t in _raw if _VN_TICKER_RE.match(t)]
    _skipped = [t for t in _raw if not _VN_TICKER_RE.match(t)]
    if _skipped:
        print(f"⚠️  Bỏ qua mã không hợp lệ: {', '.join(_skipped)}")
    if not tickers:
        print("Không có mã hợp lệ. Thoát.")
        sys.exit(0)

    print(f"\n  Danh sách phân tích: {', '.join(tickers)}\n")

    results = []
    for ticker in tickers:
        result = analyse_ticker(ticker)
        results.append(result)
        save_profiler_audit(result)
        print_report(result)
        if len(tickers) > 1:
            time.sleep(0.4)   # courteous rate-limit delay between tickers

    if len(results) > 1:
        print_summary_table(results)

    print(f"\n  ⏱  Hoàn thành lúc {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("─" * 62 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
#  AUDIT — persist every profiler result to data/Profiler/<TICKER>.json
# ─────────────────────────────────────────────────────────────────────────────

def save_profiler_audit(result: dict) -> str:
    """
    Append the latest profiler snapshot for one ticker to
    data/Profiler/<TICKER>.json   (JSON-Lines format — one record per line).

    Each record contains the full result dict plus a 'run_ts' ISO timestamp.
    Returns the absolute path of the file written, or '' on failure.
    """
    if not isinstance(result, dict):
        return ""
    ticker = result.get("ticker", "UNKNOWN").upper()
    # Sanitise ticker name to a safe filename (strip any path chars)
    safe = "".join(c for c in ticker if c.isalnum() or c in "-_")
    if not safe:
        return ""
    path = _os_.path.join(_AUDIT_DIR, f"{safe}.json")
    try:
        # Build a serialisable snapshot (replace None-safe floats, copy confirmations)
        snapshot = {}
        for k, v in result.items():
            if isinstance(v, float) and (v != v):          # NaN guard
                snapshot[k] = None
            elif hasattr(v, "item"):                        # numpy scalar
                snapshot[k] = v.item()
            elif isinstance(v, list):
                snapshot[k] = list(v)
            else:
                snapshot[k] = v
        snapshot["run_ts"] = datetime.now().isoformat(timespec="seconds")
        line = _json.dumps(snapshot, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        _log.debug("audit saved: %s", path)
        return path
    except Exception as exc:
        _log.warning("save_profiler_audit(%s) failed: %s", ticker, exc)
        return ""


if __name__ == "__main__":
    main()

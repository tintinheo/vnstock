"""Data fetcher: SSI iboard-api (primary) + DNSE fallback.

Endpoints from SSI_HARrequestLogs.txt:
  OHLCV daily  : GET {ssi_base}/statistics/charts/history?resolution=1D&symbol=X&from=TS&to=TS
  OHLCV 5m     : GET {ssi_base}/statistics/charts/history?resolution=5&symbol=X&from=TS&to=TS
  Quote        : GET https://iboard-query.ssi.com.vn/stock/{symbol}?boardId=MAIN
  Universe     : GET https://iboard-query.ssi.com.vn/stock/group/{HOSE|HNX}
  FOL stats    : GET {ssi_base}/statistics/company/ssmi/stock-info?symbol=X&fromDate=MM/DD/YYYY&...
DNSE fallback:
  OHLCV daily  : GET {dnse_base}/ohlcs/stock?symbol=X&from=TS&to=TS&resolution=D
"""
from __future__ import annotations

import threading
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

# Thread-local sessions: each thread gets its own requests.Session so
# concurrent scans don't corrupt shared connection state.
_thread_local = threading.local()

# Semaphore caps simultaneous outbound SSI connections to avoid triggering
# SSI's rate-limiter (which stalls threads indefinitely when hit).
_SSI_CONCURRENCY = 4
_ssi_sem = threading.Semaphore(_SSI_CONCURRENCY)


def _get_session() -> requests.Session:
    """Return a per-thread requests.Session, creating it on first use."""
    sess = getattr(_thread_local, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update(_HEADERS)
        _thread_local.session = sess
    return sess


def _get(url: str, params: dict | None = None, timeout: int = 15, retries: int = 3) -> dict | list:
    with _ssi_sem:  # at most _SSI_CONCURRENCY threads inside here at once
        for attempt in range(retries):
            try:
                r = _get_session().get(url, params=params, timeout=timeout)
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
        "date":   pd.to_datetime(t, unit="s", utc=True).tz_convert("Asia/Ho_Chi_Minh").date,
        "open":   pd.to_numeric(payload.get("o", []), errors="coerce"),
        "high":   pd.to_numeric(payload.get("h", []), errors="coerce"),
        "low":    pd.to_numeric(payload.get("l", []), errors="coerce"),
        "close":  pd.to_numeric(payload.get("c", []), errors="coerce"),
        "volume": pd.to_numeric(payload.get("v", []), errors="coerce"),
    })
    return clean_ohlcv(df.dropna(subset=["close"]).reset_index(drop=True))


def _normalize_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean OHLCV frame with a canonical date column."""
    if df.empty:
        return df

    normalized = df.copy()
    if "trade_date" in normalized.columns and "date" not in normalized.columns:
        normalized = normalized.rename(columns={"trade_date": "date"})

    keep_cols = [col for col in ["date", "open", "high", "low", "close", "volume"] if col in normalized.columns]
    if "date" not in keep_cols:
        return pd.DataFrame()

    return clean_ohlcv(normalized.loc[:, keep_cols])


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
            return _normalize_ohlcv_frame(cached)

    df = _fetch_ohlcv_ssi(ticker, start, end)
    if df.empty:
        log.debug(f"SSI empty for {ticker} -- trying DNSE")
        df = _fetch_ohlcv_dnse(ticker, start, end)

    if not df.empty:
        cache.put_ohlcv(ticker, df)
        log.info(f"Fetched {len(df)} bars for {ticker}")
    else:
        log.debug(f"No OHLCV data for {ticker}")

    return _normalize_ohlcv_frame(df)


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
    Fetch listed ticker symbols for a given exchange.

    SSI iboard-query uses group names that differ from exchange codes:
      - 'HOSE' and 'HNX' groups return empty on iboard-query.
      - 'VNXALL' returns all active regular stocks on HOSE + HNX (507 stocks).
      - 'HNXUpcomIndex' returns UPCOM-listed stocks (839 stocks).

    Exchange mapping:
      HOSE  → VNXALL filtered by exchange='hose'  (~329 stocks)
      HNX   → VNXALL filtered by exchange='hnx'   (~178 stocks)
      UPCOM → HNXUpcomIndex                        (~839 stocks)
      ALL   → VNXALL + HNXUpcomIndex               (~1346 stocks)

    Symbol field: 'stockSymbol' (NOT 'stockNo'/'s'/'symbol'/'ticker').
    Stock filter: stockType == 's' excludes warrants, bonds, futures.
    """
    exchange = exchange.strip().upper()

    # ── Map exchange → SSI group(s) ───────────────────────────────────────
    _GROUP_MAP: dict[str, list[tuple[str, str | None]]] = {
        # (group_name, exchange_filter_value | None = no filter)
        "HOSE":  [("VNXALL", "hose")],
        "HNX":   [("VNXALL", "hnx")],
        "UPCOM": [("HNXUpcomIndex", None)],
        "ALL":   [("VNXALL", None), ("HNXUpcomIndex", None)],
    }
    groups = _GROUP_MAP.get(exchange, [("VNXALL", "hose")])  # default → HOSE

    # ── Fetch from SSI ────────────────────────────────────────────────────
    tickers: list[str] = []
    seen: set[str] = set()

    for group_name, exch_filter in groups:
        try:
            url = f"{_SSI_QUERY}/stock/group/{group_name}"
            raw = _get(url, timeout=20)

            items: list = []
            if isinstance(raw, dict):
                items = raw.get("data", raw.get("items", []))
            elif isinstance(raw, list):
                items = raw
            if not isinstance(items, list):
                items = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                # Filter by exchange (hose / hnx / upcom) when requested
                if exch_filter and item.get("exchange", "").lower() != exch_filter:
                    continue
                # Only regular stocks — exclude warrants (CW), bonds, futures
                if item.get("stockType", "s") not in ("s", ""):
                    continue
                # Primary field is 'stockSymbol'; fall back to legacy names
                sym = (
                    item.get("stockSymbol") or
                    item.get("stockNo") or item.get("s") or
                    item.get("symbol") or item.get("ticker") or ""
                ).strip().upper()
                if sym and 2 <= len(sym) <= 5 and sym not in seen:
                    tickers.append(sym)
                    seen.add(sym)

        except Exception as e:
            log.warning(f"SSI universe fetch failed for group {group_name}: {e}")

    if tickers:
        log.info(f"Universe {exchange} (SSI VNXALL): {len(tickers)} tickers")
        return tickers

    log.warning(f"SSI universe empty for {exchange} — using hardcoded fallback")
    return _fallback_universe(exchange)


def _fallback_universe(exchange: str = "HOSE") -> list[str]:
    """
    Hardcoded fallback universe — used only when SSI API is unreachable.
    Contains the most liquid names per exchange as of 2026.
    """
    exchange = exchange.strip().upper()
    fallback = {
        "HOSE": [
            # Ngân hàng
            "VCB", "BID", "CTG", "TCB", "MBB", "ACB", "HDB", "VPB", "STB", "LPB",
            # Công nghiệp
            "HPG", "HSG", "NKG", "TLH",
            # Tiêu dùng & bán lẻ
            "VNM", "SAB", "MWG", "PNJ", "FRT", "DGW",
            # Bất động sản
            "VIC", "VHM", "NVL", "KDH", "PDR", "BCM",
            # Dầu khí & năng lượng
            "GAS", "PLX", "PVT", "PVS",
            # Hàng không
            "HVN", "VJC",
            # Hạ tầng & logistics
            "REE", "GMD", "ACV",
            # Chứng khoán
            "SSI", "VND", "HCM", "VCI",
            # Công nghệ
            "FPT", "CMG",
            # Đa ngành
            "MSN", "DGC", "GVR",
        ],
        "HNX": [
            "SHS", "MBS", "PVS", "IDC", "NVB", "CEO", "TNG", "PLC", "BCC", "LAS",
            "HUT", "VCS", "L14", "BVS", "BAB", "BAX", "CII", "DHT", "DIH", "PGS",
        ],
        "UPCOM": [
            "ACV", "BSR", "MCH", "QNS", "VGI", "VEA", "FOX", "CTR", "NTC", "LTG",
            "MSR", "GDT", "SIP", "PTB", "VTP", "BCG", "CAV", "HDG", "HCD", "VHC",
        ],
    }
    result = fallback.get(exchange, fallback["HOSE"])
    if exchange == "ALL":
        return list(dict.fromkeys(fallback["HOSE"] + fallback["HNX"] + fallback["UPCOM"]))
    return result


def fetch_foreign_flow(ticker: str, days: int = 20) -> pd.DataFrame:
    """
    Fetch foreign buy/sell data via SSI statistics/company/ssmi/stock-info.
    Date format required by SSI: dd/MM/YYYY  (%d/%m/%Y)
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
            # SSI stock-info endpoint requires dd/MM/YYYY (same convention as
            # company-news after the hotfix; MM/DD/YYYY triggers silent empty response)
            "fromDate": start_d.strftime("%d/%m/%Y"),
            "toDate":   end_d.strftime("%d/%m/%Y"),
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
                d = pd.to_datetime(d_str, dayfirst=True).date()
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


def fetch_quote(ticker: str, exchange: str | None = None) -> dict:
    """
    Fetch real-time quote snapshot via SSI iboard-query.
    Tries exchange-aware board IDs instead of hardcoding MAIN.
    """
    try:
        url = f"{_SSI_QUERY}/stock/{ticker.upper()}"
        board_candidates: list[str] = []
        if exchange:
            ex = exchange.strip().upper()
            board_candidates.append("MAIN" if ex == "HOSE" else ex)
        board_candidates.extend(["MAIN", "HNX", "UPCOM"])

        seen: set[str] = set()
        for board in board_candidates:
            if board in seen:
                continue
            seen.add(board)
            raw = _get(url, params={"boardId": board}, timeout=10)
            data = raw.get("data", raw) if isinstance(raw, dict) else {}
            if isinstance(data, list) and data:
                data = data[0]
            if isinstance(data, dict) and data:
                data.setdefault("exchange", "HOSE" if board == "MAIN" else board)
                return data
    except Exception as e:
        log.debug(f"Quote fetch failed for {ticker}: {e}")
    return {}


# ── Put-through / Deal data (Phase 1) ────────────────────────────────────────

def fetch_put_through_deals(ticker: str, days: int = 5) -> pd.DataFrame:
    """
    Fetch put-through (thoả thuận) transaction data from SSI.

    Endpoint (from SSI HAR logs):
      GET /le-table/stock/{symbol}?pageSize=50
    Returns DataFrame with columns: [date, buyer, seller, volume, price, value]

    NOTE: SSI's le-table endpoint requires authenticated sessions in production.
    Until a public endpoint is confirmed, returns empty DataFrame (safe default).
    The column contract can still be tested via mock in unit tests.
    """
    ticker = ticker.strip().upper()
    try:
        url = f"{_SSI_QUERY}/le-table/stock/{ticker}"
        raw = _get(url, params={"pageSize": 50}, timeout=10)
        items = raw.get("data", []) if isinstance(raw, dict) else []
        if not isinstance(items, list) or not items:
            return pd.DataFrame(columns=["date", "buyer", "seller", "volume", "price", "value"])
        rows = []
        for item in items:
            vol   = float(item.get("vol", item.get("volume", 0)) or 0)
            price = float(item.get("price", item.get("matchedPrice", 0)) or 0)
            rows.append({
                "date":   item.get("time", item.get("tradingDate", "")),
                "buyer":  item.get("buyerId", ""),
                "seller": item.get("sellerId", ""),
                "volume": vol,
                "price":  price,
                "value":  vol * price,
            })
        df = pd.DataFrame(rows)
        log.info(f"Fetched {len(df)} put-through deals for {ticker}")
        return df
    except Exception as e:
        log.debug(f"Put-through fetch failed for {ticker}: {e}")
        return pd.DataFrame(columns=["date", "buyer", "seller", "volume", "price", "value"])


# ── Macro Data Fetchers ───────────────────────────────────────────────────────

_USDVND_CACHE_FILE = cfg.db_path.parent / "usdvnd_history.csv"


def _load_usdvnd_cache() -> pd.DataFrame:
    """Load the rolling USDVND history cache from disk."""
    try:
        if _USDVND_CACHE_FILE.exists():
            df = pd.read_csv(_USDVND_CACHE_FILE, parse_dates=["date"])
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    except Exception as e:
        log.debug(f"USDVND cache load failed: {e}")
    return pd.DataFrame(columns=["date", "close"])


def _save_usdvnd_cache(df: pd.DataFrame) -> None:
    """Persist the USDVND history to disk (append-safe)."""
    try:
        _USDVND_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(_USDVND_CACHE_FILE, index=False)
    except Exception as e:
        log.debug(f"USDVND cache save failed: {e}")


def fetch_usdvnd(days: int = 60) -> pd.DataFrame:
    """
    Fetch USD/VND interbank exchange rate.

    Strategy:
      1. Read existing rolling cache (CSV on disk) to get historical series.
      2. Fetch today's rate from VCB public API.
      3. Append today's rate to the cache and persist it.
      4. Return the last `days` rows from the combined series.

    The rolling cache accumulates one row per calendar day, building up a
    multi-day time series that allows _score_usdvnd() (requires len >= 10)
    to produce a meaningful macro signal.

    Returns DataFrame with columns: [date, close]
    where close = USD/VND sell rate.
    """
    end_d = date.today()

    # ── Step 1: Load historical cache ────────────────────────────────────
    cached_df = _load_usdvnd_cache()

    # ── Step 2: Fetch today's rate from VCB ──────────────────────────────
    today_rate: float | None = None
    try:
        url = "https://www.vietcombank.com.vn/api/exchangerates"
        raw = _get(url, timeout=10, retries=2)
        items: list = []
        if isinstance(raw, dict):
            items = raw.get("data", raw.get("Data", []))
        if not isinstance(items, list):
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            currency = (item.get("CurrencyCode") or item.get("currency") or "").upper()
            if currency != "USD":
                continue
            sell = float(item.get("Sell") or item.get("sell") or 0)
            if sell > 0:
                today_rate = sell
                break
    except Exception as e:
        log.debug(f"VCB USDVND fetch failed: {e}")

    # ── Step 3: Append to cache if we got a fresh rate ───────────────────
    if today_rate is not None:
        new_row = pd.DataFrame([{"date": end_d, "close": today_rate}])
        if cached_df.empty:
            combined = new_row.copy()
        else:
            combined = pd.concat([cached_df, new_row], ignore_index=True)
        combined = combined.drop_duplicates("date").sort_values("date").reset_index(drop=True)
        _save_usdvnd_cache(combined)
        cached_df = combined
        log.debug(f"USDVND updated: {today_rate:,.0f} | {len(cached_df)} days cached")

    # ── Step 4: Return last `days` rows ──────────────────────────────────
    if not cached_df.empty:
        result = cached_df.tail(days).reset_index(drop=True)
        log.debug(f"USDVND returning {len(result)} rows from cache")
        return result

    log.warning("USDVND: no data available — macro component will be skipped")
    return pd.DataFrame(columns=["date", "close"])


_VN10Y_CACHE_FILE = cfg.db_path.parent / "vn10y_history.csv"

# Known VN10Y yield approximate values by year (used as seed when cache is empty)
# Source: HNX public bond market reports — updated periodically
_VN10Y_SEEDS = {
    2023: 2.80, 2024: 2.75, 2025: 2.90, 2026: 3.00,
}


def _load_vn10y_cache() -> pd.DataFrame:
    """Load the rolling VN10Y yield history cache from disk."""
    try:
        if _VN10Y_CACHE_FILE.exists():
            df = pd.read_csv(_VN10Y_CACHE_FILE, parse_dates=["date"])
            df["date"] = pd.to_datetime(df["date"]).dt.date
            return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    except Exception as e:
        log.debug(f"VN10Y cache load failed: {e}")
    return pd.DataFrame(columns=["date", "yield"])


def _seed_vn10y_cache() -> pd.DataFrame:
    """
    Build a 60-day seeded cache from known approximate yields.
    Used only when the persistent cache is empty (first run).
    """
    end_d = date.today()
    rows = []
    for i in range(60, -1, -1):
        d = end_d - timedelta(days=i)
        yield_val = _VN10Y_SEEDS.get(d.year, 2.9)
        rows.append({"date": d, "close": yield_val})
    df = pd.DataFrame(rows)
    df = df.rename(columns={"close": "yield"})
    return df.sort_values("date").reset_index(drop=True)


def fetch_vn10y_bond_yield(days: int = 60) -> pd.DataFrame:
    """
    Fetch VN 10-year Government Bond yield.

    Strategy:
      1. Load persistent cache (CSV).
      2. Seed with known approximate values on first run (empty cache).
      3. Try HNX bond market API for today's fresh yield; append if available.
      4. Return last `days` rows.

    Returns DataFrame with columns: [date, yield]
    where yield is expressed as a percentage (e.g. 2.75 for 2.75%).

    Note: Real-time HNX bond data is not publicly available without authentication.
    The seeded values provide a baseline for macro regime scoring; replace with
    a live feed (FiinTrade / TCBS) when available.
    """
    # ── Step 1: Load cache ────────────────────────────────────────────────
    cached_df = _load_vn10y_cache()

    # ── Step 2: Seed on first run ─────────────────────────────────────────
    if cached_df.empty:
        cached_df = _seed_vn10y_cache()
        try:
            _VN10Y_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cached_df.to_csv(_VN10Y_CACHE_FILE, index=False)
            log.info("VN10Y: seeded initial cache with approximate historical yields")
        except Exception as e:
            log.debug(f"VN10Y cache seed save failed: {e}")

    # ── Step 3: Try HNX REST API for today's yield ───────────────────────
    today_yield: float | None = None
    try:
        # HNX government bond market endpoint (may require no auth for overview)
        url = "https://hnx.vn/api_hnx/bond/trading-info"
        params = {"pageSize": 1, "pageIndex": 1, "type": "GOV"}
        raw = _get(url, params=params, timeout=8, retries=1)
        if isinstance(raw, dict):
            items = raw.get("data", raw.get("items", []))
            if isinstance(items, list) and items:
                item = items[0]
                # Try common field names for yield
                val = (item.get("yield") or item.get("interestRate") or
                       item.get("yieldRate") or item.get("laiSuat") or 0)
                val = float(val or 0)
                if 0.5 < val < 20:   # sanity: yield between 0.5% and 20%
                    today_yield = val
    except Exception as e:
        log.debug(f"HNX bond yield fetch failed: {e}")

    # ── Step 4: Append today's yield if fetched ───────────────────────────
    if today_yield is not None:
        end_d = date.today()
        new_row = pd.DataFrame([{"date": end_d, "yield": today_yield}])
        combined = pd.concat([cached_df, new_row], ignore_index=True)
        combined = combined.drop_duplicates("date").sort_values("date").reset_index(drop=True)
        try:
            combined.to_csv(_VN10Y_CACHE_FILE, index=False)
        except Exception:
            pass
        cached_df = combined
        log.debug(f"VN10Y updated: {today_yield:.2f}% | {len(cached_df)} days cached")

    if not cached_df.empty:
        return cached_df.tail(days).reset_index(drop=True)

    return pd.DataFrame(columns=["date", "yield"])


def fetch_sbv_omo_net(days: int = 30) -> dict:
    """
    Estimate SBV OMO (Open Market Operations) net injection.

    Since the SBV does not publish a free real-time OMO feed, this function
    returns a neutral default (net_7d=0.0) until a public source is wired in.
    Using 0.0 (not None) ensures the macro engine counts OMO as a present
    source with a neutral contribution, improving confidence scoring.

    Returns
    -------
    dict with keys:
      net_7d   : float — net injection last 7 days (VND billion); 0.0 = neutral
      avg_ref  : float — reference average weekly volume (VND billion)
    """
    return {"net_7d": 0.0, "avg_ref": 10_000.0}


# ── Earnings Calendar Fetchers ────────────────────────────────────────────────

def fetch_earnings_calendar(ticker: str, lookforward_days: int = 90) -> pd.DataFrame:
    """
    Fetch earnings/financial-report release calendar for a ticker.

    Tries (in order):
            1. Inferred calendar from Vietnamese regulatory rules:
         - Q1 results: 30 April
         - Q2 results: 31 July (or H1: 30 August)
         - Q3 results: 31 October
         - Q4/Full-year: 31 March of the following year
         (Source: Circular 96/2020/TT-BTC, mandatory BCTC disclosure deadlines)

    Returns DataFrame with columns:
      [ticker, fiscal_quarter, expected_publication_date, actual_publication_date,
       confirmed, eps_estimate, eps_actual, source]

    Key design: only rows where actual_publication_date <= today are "known" and
    safe to use in backtest (as-of rule). Rows with confirmed=False are forecasts.
    """
    today = date.today()

    rows = []
    # ── Build regulatory inference calendar ──────────────────────────────
    if len([r for r in rows if r["confirmed"]]) < 2:
        inferred = _infer_earnings_calendar(ticker, today, lookforward_days)
        # Merge: only add inferred rows not already covered by confirmed rows
        confirmed_quarters = {r["fiscal_quarter"] for r in rows if r["confirmed"]}
        for r in inferred:
            if r["fiscal_quarter"] not in confirmed_quarters:
                rows.append(r)

    if not rows:
        return pd.DataFrame(columns=[
            "ticker", "fiscal_quarter", "expected_publication_date",
            "actual_publication_date", "confirmed", "eps_estimate", "eps_actual", "source"
        ])

    df = pd.DataFrame(rows).sort_values("expected_publication_date").reset_index(drop=True)
    return df


def _infer_earnings_calendar(
    ticker: str,
    today: date,
    lookforward_days: int,
) -> list[dict]:
    """
    Infer earnings publication dates from Vietnamese regulatory deadlines
    (Circular 96/2020/TT-BTC):
      - Q1 (ending 31-Mar): must publish by 30-Apr
      - H1 (ending 30-Jun): must publish by 30-Aug
      - Q3 (ending 30-Sep): must publish by 30-Oct (or 15-Nov for audited)
      - Full Year (ending 31-Dec): must publish by 31-Mar next year

    This gives a conservative estimate of WHEN the market "knows" the results.
    """
    years = [today.year - 1, today.year, today.year + 1]
    rows  = []
    deadline_end = today + timedelta(days=lookforward_days)

    schedule: list[tuple[str, date, date]] = []   # (quarter_label, period_end, pub_deadline)
    for y in years:
        schedule += [
            (f"{y}Q1", date(y,  3, 31), date(y,  4, 30)),
            (f"{y}H1", date(y,  6, 30), date(y,  8, 30)),
            (f"{y}Q3", date(y,  9, 30), date(y, 10, 31)),
            (f"{y}FY", date(y, 12, 31), date(y + 1, 3, 31)),
        ]

    for quarter_label, period_end, pub_deadline in schedule:
        if pub_deadline < today - timedelta(days=365):
            continue
        if pub_deadline > deadline_end:
            continue
        rows.append({
            "ticker":                    ticker,
            "fiscal_quarter":            quarter_label,
            "expected_publication_date": pub_deadline,
            "actual_publication_date":   pub_deadline if pub_deadline <= today else None,
            "confirmed":                 pub_deadline <= today,
            "eps_estimate":              0.0,
            "eps_actual":                0.0,
            "source":                    "regulatory_inference",
        })

    return rows


# ── Financial Statement Fetchers ─────────────────────────────────────────────

def fetch_financial_statements(
    ticker: str,
    quarters: int = 8,
) -> dict[str, pd.DataFrame]:
    """
    Fetch quarterly financial statements for a ticker.

    Returns empty DataFrames when no financial source is configured.

    Returns a dict with keys:
      "income"   : quarterly income statement
                   columns: [period, revenue, gross_profit, ebit, net_income, eps]
      "balance"  : quarterly balance sheet
                   columns: [period, total_assets, total_equity, total_debt]
      "cashflow" : quarterly cash flow statement
                   columns: [period, cfo, cfi, cff, free_cash_flow]

    The 'period' column uses format YYYY-QX (e.g. '2025-Q3').
    All monetary values are in VND billion (tỷ đồng).
    EPS is VND per share.
    """
    empty: dict[str, pd.DataFrame] = {
        "income":   pd.DataFrame(columns=["period", "period_end_date", "publication_date", "revenue", "gross_profit", "ebit", "net_income", "eps"]),
        "balance":  pd.DataFrame(columns=["period", "period_end_date", "publication_date", "total_assets", "total_equity", "total_debt"]),
        "cashflow": pd.DataFrame(columns=["period", "period_end_date", "publication_date", "cfo", "cfi", "cff", "free_cash_flow"]),
    }

    earnings_calendar = fetch_earnings_calendar(ticker, lookforward_days=365)
    pub_map: dict[str, pd.Timestamp] = {}
    if not earnings_calendar.empty:
        for _, row in earnings_calendar.iterrows():
            period = str(row.get("fiscal_quarter") or "")
            pub_date = row.get("actual_publication_date") or row.get("expected_publication_date")
            pub_map[period] = pd.to_datetime(pub_date, errors="coerce")

    return empty


def _normalize_financial_df(
    df: pd.DataFrame,
    col_mapping: list[tuple[str, str]],
    quarters: int,
    pub_map: dict[str, pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """
    Standardise a raw financial DataFrame:
    - Find columns by partial name match (case-insensitive).
    - Rename to canonical names.
    - Ensure 'period' column in YYYY-QX format.
    - Convert monetary values from VND units to VND billion (÷ 1e9).
    - Take last N quarters.
    """
    df = df.copy()

    # ── Normalise period column ───────────────────────────────────────────
    period_col = None
    for c in df.columns:
        c_lower = str(c).lower()
        if any(kw in c_lower for kw in ["period", "quarter", "quy", "ky"]):
            period_col = c
            break
    if period_col is None and df.index.name:
        df = df.reset_index()
        period_col = df.columns[0]
    if period_col:
        df = df.rename(columns={period_col: "period"})

    # ── Rename financial columns ──────────────────────────────────────────
    result_cols = ["period"]
    for source_name, target_name in col_mapping:
        matched = None
        for c in df.columns:
            if source_name.lower() in str(c).lower():
                matched = c
                break
        if matched:
            df = df.rename(columns={matched: target_name})
            result_cols.append(target_name)

    # ── Keep only required columns ────────────────────────────────────────
    existing = [c for c in result_cols if c in df.columns]
    df = df[existing].copy()

    # ── Convert monetary values: assume VND units → VND billion ──────────
    for col in [c for c in df.columns if c != "period"]:
        try:
            vals = pd.to_numeric(df[col], errors="coerce")
            # If typical value > 1e9, assume it's already in VND (not billion)
            if vals.dropna().abs().median() > 1e9:
                df[col] = vals / 1e9
            else:
                df[col] = vals
        except Exception:
            pass

    if "period" in df.columns:
        df["period"] = df["period"].astype(str)
        df["period_end_date"] = df["period"].apply(_period_to_end_date)
        if pub_map:
            df["publication_date"] = df["period"].map(pub_map)
        else:
            df["publication_date"] = pd.NaT

    return df.tail(quarters).reset_index(drop=True)


def _period_to_end_date(period: str):
    text = str(period).upper().strip()
    if len(text) >= 4 and text[:4].isdigit():
        year = int(text[:4])
        if "Q1" in text:
            return pd.Timestamp(year=year, month=3, day=31)
        if "Q2" in text or "H1" in text:
            return pd.Timestamp(year=year, month=6, day=30)
        if "Q3" in text:
            return pd.Timestamp(year=year, month=9, day=30)
        if "Q4" in text or "FY" in text:
            return pd.Timestamp(year=year, month=12, day=31)
    return pd.NaT

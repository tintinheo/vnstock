"""CafeF foreign-flow history helpers."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

logger = logging.getLogger("TradingOS.foreign_flow")

CAFEF_FOREIGN_HISTORY_URL = (
    "https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx"
)
CAFEF_REFERER_TEMPLATE = (
    "https://cafef.vn/du-lieu/lich-su-giao-dich/{exchange_slug}/{symbol_slug}-3.chn"
)
CAFEF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}
CAFEF_PAGE_SIZE = 20
CAFEF_LOOKBACK_DAYS = 45
CACHE_PATH = Path("data/foreign_flow_cache.csv")
MARKET_CACHE_PATH = Path("data/foreign_flow_market_history.csv")
MARKET_EXCHANGES = ("HOSE", "HNX", "UPCOM")

_CACHE_TTL = timedelta(minutes=30)
_history_cache: dict[tuple[str, str, int], tuple[pd.DataFrame, datetime]] = {}
_market_history_cache: dict[int, tuple[pd.DataFrame, datetime]] = {}
_MARKET_CACHE_TTL = timedelta(hours=8)


def _normalize_exchange(exchange: str | None) -> str:
    exch = (exchange or "HOSE").strip().upper()
    return exch if exch in {"HOSE", "HNX", "UPCOM"} else "HOSE"


def _normalize_symbol(symbol: str | None) -> str:
    return (symbol or "ALL").strip().upper() or "ALL"


def _page_referer(symbol: str, exchange: str) -> str:
    return CAFEF_REFERER_TEMPLATE.format(
        exchange_slug=exchange.lower(),
        symbol_slug=symbol.lower(),
    )


def _format_cafef_date(value: date | datetime | str | None) -> str:
    if value is None:
        value = datetime.now().date()
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return datetime.now().strftime("%d/%m/%Y")
    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid CafeF date: {value!r}")
    return parsed.strftime("%d/%m/%Y")


def _session_trend(net_value: float) -> str:
    if net_value > 5e10:
        return "accumulate"
    if net_value < -5e10:
        return "distribute"
    return "neutral"


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


def save_cached_foreign_flow(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE_PATH, index=False)


def save_cached_market_foreign_flow(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    MARKET_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(MARKET_CACHE_PATH, index=False)


def _load_cached_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def _path_is_fresh(path: Path, ttl: timedelta) -> bool:
    if not path.exists():
        return False
    modified_at = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - modified_at) < ttl


def _fetch_cafef_history_page(
    symbol: str,
    exchange: str,
    page_index: int,
    start_text: str,
    end_text: str,
) -> tuple[dict, list[dict]]:
    params = {
        "Symbol": symbol,
        "Exchange": exchange,
        "StartDate": start_text,
        "EndDate": end_text,
        "PageIndex": page_index,
        "PageSize": CAFEF_PAGE_SIZE,
    }
    headers = dict(CAFEF_HEADERS)
    headers["Referer"] = _page_referer(symbol, exchange)
    response = requests.get(
        CAFEF_FOREIGN_HISTORY_URL,
        params=params,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("Success", False):
        raise RuntimeError(payload.get("Message") or "CafeF foreign history request failed")
    root = payload.get("Data") or {}
    page_rows = root.get("Data") or []
    if not isinstance(page_rows, list):
        raise RuntimeError("CafeF foreign history payload missing Data list")
    return root, page_rows


def _normalize_history_rows(rows: list[dict], symbol: str, exchange: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).rename(columns={
        "Symbol": "ticker",
        "Ngay": "date",
        "KLGDRong": "net_volume",
        "GTDGRong": "net_value",
        "ThayDoi": "change",
        "KLMua": "buy_volume",
        "GtMua": "buy_value",
        "KLBan": "sell_volume",
        "GtBan": "sell_value",
        "RoomConLai": "room_remaining",
        "DangSoHuu": "foreign_ownership_pct",
    }).copy()

    expected = [
        "ticker", "date", "net_volume", "net_value", "change",
        "buy_volume", "buy_value", "sell_volume", "sell_value",
        "room_remaining", "foreign_ownership_pct",
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = 0

    df["ticker"] = df["ticker"].fillna(symbol).astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date", "ticker"])
    for col in (
        "net_volume", "net_value", "buy_volume", "buy_value",
        "sell_volume", "sell_value", "room_remaining",
        "foreign_ownership_pct",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df["exchange"] = exchange
    df["source"] = "CafeF foreign history"
    df = df.sort_values(["ticker", "date"], ascending=[True, False])
    df = df.drop_duplicates(subset=["ticker", "date"], keep="first")
    return df.reset_index(drop=True)


def fetch_cafef_foreign_flow_history(
    symbol: str,
    exchange: str = "HOSE",
    sessions: int = 20,
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
) -> pd.DataFrame:
    """Fetch per-symbol CafeF foreign-flow history and normalize it."""
    symbol = _normalize_symbol(symbol)
    exchange = _normalize_exchange(exchange)
    sessions = max(1, int(sessions or 20))
    cache_key = (symbol, exchange, sessions)

    cached = _history_cache.get(cache_key)
    if cached and (datetime.now() - cached[1]) < _CACHE_TTL:
        return cached[0].copy()

    if end_date is None:
        end_date = datetime.now().date()
    if start_date is None:
        start_date = pd.to_datetime(end_date, dayfirst=True).date() - timedelta(days=CAFEF_LOOKBACK_DAYS)

    start_text = _format_cafef_date(start_date)
    end_text = _format_cafef_date(end_date)
    page_count = max(1, (sessions + CAFEF_PAGE_SIZE - 1) // CAFEF_PAGE_SIZE)

    rows: list[dict] = []
    for page_index in range(1, page_count + 1):
        _root, page_rows = _fetch_cafef_history_page(
            symbol,
            exchange,
            page_index,
            start_text,
            end_text,
        )
        rows.extend(page_rows)
        if len(page_rows) < CAFEF_PAGE_SIZE:
            break

    history = _normalize_history_rows(rows, symbol=symbol, exchange=exchange)
    if not history.empty:
        history = history.head(sessions).reset_index(drop=True)
    _history_cache[cache_key] = (history.copy(), datetime.now())
    return history


def fetch_cafef_foreign_flow_histories(
    symbols: Iterable[str],
    exchange_map: dict[str, str] | None = None,
    sessions: int = 20,
    max_workers: int = 6,
) -> pd.DataFrame:
    """Fetch normalized CafeF foreign-flow history for many symbols."""
    exchange_map = {str(k).upper(): str(v).upper() for k, v in (exchange_map or {}).items()}
    unique_symbols = sorted({_normalize_symbol(symbol) for symbol in symbols if str(symbol).strip()})
    if not unique_symbols:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    def _worker(symbol: str) -> pd.DataFrame:
        exchange = _normalize_exchange(exchange_map.get(symbol, "HOSE"))
        return fetch_cafef_foreign_flow_history(symbol, exchange=exchange, sessions=sessions)

    worker_count = min(max_workers, len(unique_symbols))
    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as pool:
        future_map = {pool.submit(_worker, symbol): symbol for symbol in unique_symbols}
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                history = future.result()
            except Exception as exc:
                logger.debug("CafeF foreign history %s: %s", symbol, exc)
                continue
            if history is not None and not history.empty:
                frames.append(history)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    save_cached_foreign_flow(combined)
    return combined.sort_values(["ticker", "date"], ascending=[True, False]).reset_index(drop=True)


def summarize_foreign_flow_history(
    history: pd.DataFrame,
    sessions: int = 20,
) -> dict[str, dict]:
    """Summarize normalized history into the app's foreign-flow contract."""
    if history is None or history.empty:
        return {}

    history = history.copy()
    history["ticker"] = history["ticker"].astype(str).str.upper()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history = history.dropna(subset=["ticker", "date"])
    history = history.sort_values(["ticker", "date"], ascending=[True, False])

    summaries: dict[str, dict] = {}
    for ticker, group in history.groupby("ticker", sort=False):
        recent = group.head(sessions).copy()
        if recent.empty:
            continue
        latest = recent.iloc[0]
        history_sessions = int(len(recent))
        has_full_window = history_sessions >= sessions
        latest_net = float(latest.get("net_value", 0.0) or 0.0)
        net_20d = float(recent["net_value"].sum()) if has_full_window else 0.0
        summaries[ticker] = {
            "net_buy_value": latest_net,
            "buy_value": float(latest.get("buy_value", 0.0) or 0.0),
            "sell_value": float(latest.get("sell_value", 0.0) or 0.0),
            "net_20d": net_20d,
            "trend_20d": _session_trend(net_20d) if has_full_window else "neutral",
            "session_net_proxy": latest_net,
            "session_trend": _session_trend(latest_net),
            "history_sessions": history_sessions,
            "is_20d_proxy": False,
            "basis": f"CafeF foreign history | {history_sessions} sessions",
        }
    return summaries


def fetch_cafef_foreign_flow_ticker(
    symbol: str,
    exchange: str = "HOSE",
    sessions: int = 20,
) -> dict:
    history = fetch_cafef_foreign_flow_history(symbol, exchange=exchange, sessions=sessions)
    return summarize_foreign_flow_history(history, sessions=sessions).get(
        _normalize_symbol(symbol),
        _empty_foreign_flow(),
    )


def fetch_cafef_foreign_flow_tickers(
    symbols: Iterable[str],
    exchange_map: dict[str, str] | None = None,
    sessions: int = 20,
    max_workers: int = 6,
) -> dict[str, dict]:
    history = fetch_cafef_foreign_flow_histories(
        symbols,
        exchange_map=exchange_map,
        sessions=sessions,
        max_workers=max_workers,
    )
    return summarize_foreign_flow_history(history, sessions=sessions)


def _aggregate_market_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        return pd.DataFrame()

    grouped = history.groupby(["date", "exchange"], as_index=False).agg(
        buy_value=("buy_value", "sum"),
        sell_value=("sell_value", "sum"),
        net_value=("net_value", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        net_volume=("net_volume", "sum"),
        symbol_count=("ticker", "nunique"),
    )
    grouped["source"] = "CafeF market history backfill"
    return grouped.sort_values(["date", "exchange"], ascending=[False, True]).reset_index(drop=True)


def _fetch_cafef_market_exchange_history(
    exchange: str,
    sessions: int = 20,
    max_pages: int = 250,
    start_date: date | datetime | str | None = None,
    end_date: date | datetime | str | None = None,
) -> pd.DataFrame:
    exchange = _normalize_exchange(exchange)
    if end_date is None:
        end_date = datetime.now().date()
    if start_date is None:
        start_date = pd.to_datetime(end_date, dayfirst=True).date() - timedelta(days=CAFEF_LOOKBACK_DAYS)

    start_text = _format_cafef_date(start_date)
    end_text = _format_cafef_date(end_date)

    frames: list[pd.DataFrame] = []
    ordered_dates: list[pd.Timestamp] = []
    seen_dates: set[pd.Timestamp] = set()
    cutoff_date: pd.Timestamp | None = None

    for page_index in range(1, max_pages + 1):
        _root, page_rows = _fetch_cafef_history_page(
            "ALL",
            exchange,
            page_index,
            start_text,
            end_text,
        )
        if not page_rows:
            break

        page_df = _normalize_history_rows(page_rows, symbol="ALL", exchange=exchange)
        if page_df.empty:
            break
        frames.append(page_df)

        page_dates = [
            pd.to_datetime(row.get("Ngay"), dayfirst=True, errors="coerce")
            for row in page_rows
        ]
        page_dates = [pd.Timestamp(value).normalize() for value in page_dates if not pd.isna(value)]
        for value in page_dates:
            if value not in seen_dates:
                seen_dates.add(value)
                ordered_dates.append(value)

        if len(ordered_dates) >= sessions:
            cutoff_date = ordered_dates[sessions - 1]
            if page_dates and min(page_dates) < cutoff_date:
                break

        if len(page_rows) < CAFEF_PAGE_SIZE:
            break

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    if cutoff_date is not None:
        combined = combined[combined["date"] >= cutoff_date]
    return _aggregate_market_history(combined)


def fetch_cafef_market_foreign_flow_history(
    sessions: int = 20,
    exchanges: Iterable[str] = MARKET_EXCHANGES,
    max_pages_per_exchange: int = 250,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Backfill and cache market-wide CafeF foreign-flow history by date."""
    sessions = max(1, int(sessions or 20))
    cache_key = sessions
    cached = _market_history_cache.get(cache_key)
    if not force_refresh and cached and (datetime.now() - cached[1]) < _MARKET_CACHE_TTL:
        return cached[0].copy()

    if not force_refresh and _path_is_fresh(MARKET_CACHE_PATH, _MARKET_CACHE_TTL):
        cached_df = load_cached_market_foreign_flow()
        if not cached_df.empty:
            distinct_dates = cached_df["date"].dropna().dt.normalize().nunique()
            if distinct_dates >= sessions:
                _market_history_cache[cache_key] = (cached_df.copy(), datetime.now())
                return cached_df.copy()

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=min(3, len(tuple(exchanges)) or 1)) as pool:
        future_map = {
            pool.submit(
                _fetch_cafef_market_exchange_history,
                exchange,
                sessions,
                max_pages_per_exchange,
            ): exchange
            for exchange in exchanges
        }
        for future in as_completed(future_map):
            exchange = future_map[future]
            try:
                frame = future.result()
            except Exception as exc:
                logger.debug("CafeF market foreign history %s: %s", exchange, exc)
                continue
            if frame is not None and not frame.empty:
                frames.append(frame)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    daily = combined.groupby("date", as_index=False).agg(
        buy_value=("buy_value", "sum"),
        sell_value=("sell_value", "sum"),
        net_value=("net_value", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        net_volume=("net_volume", "sum"),
        symbol_count=("symbol_count", "sum"),
    )
    daily["source"] = "CafeF market history backfill"
    daily = daily.sort_values("date", ascending=False).reset_index(drop=True).head(sessions)
    save_cached_market_foreign_flow(daily)
    _market_history_cache[cache_key] = (daily.copy(), datetime.now())
    return daily


def summarize_market_foreign_flow_history(
    history: pd.DataFrame,
    sessions: int = 20,
) -> dict:
    if history is None or history.empty:
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

    daily = history.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
    daily = daily.dropna(subset=["date"]).sort_values("date", ascending=False).reset_index(drop=True)
    recent = daily.head(sessions).copy()
    latest = recent.iloc[0]
    history_sessions = int(len(recent))
    net_20d = float(recent["net_value"].sum()) if history_sessions >= sessions else 0.0
    signal_net_buy = float(net_20d / history_sessions) if history_sessions >= sessions and history_sessions > 0 else float(latest["net_value"])

    return {
        "net_buy": float(latest["net_value"]),
        "buy": float(latest["buy_value"]),
        "sell": float(latest["sell_value"]),
        "trend": "Mua ròng" if float(latest["net_value"]) > 0 else "Bán ròng" if float(latest["net_value"]) < 0 else "Trung tính",
        "fetch_ok": True,
        "net_buy_20d": net_20d,
        "trend_20d": _session_trend(net_20d) if history_sessions >= sessions else "neutral",
        "history_sessions": history_sessions,
        "signal_net_buy": signal_net_buy,
        "basis": f"CafeF market history backfill | {history_sessions} sessions",
        "history": [
            {
                "date": row["date"].date().isoformat(),
                "net_buy": float(row["net_value"]),
                "buy": float(row["buy_value"]),
                "sell": float(row["sell_value"]),
                "symbol_count": int(row.get("symbol_count", 0) or 0),
            }
            for _, row in recent.iterrows()
        ],
        "history_as_of": latest["date"].date().isoformat(),
    }


def fetch_cafef_market_foreign_flow(
    sessions: int = 20,
    exchanges: Iterable[str] = MARKET_EXCHANGES,
    max_pages_per_exchange: int = 250,
    force_refresh: bool = False,
) -> dict:
    if force_refresh:
        history = fetch_cafef_market_foreign_flow_history(
            sessions=sessions,
            exchanges=exchanges,
            max_pages_per_exchange=max_pages_per_exchange,
            force_refresh=True,
        )
    else:
        history = load_cached_market_foreign_flow()
    return summarize_market_foreign_flow_history(history, sessions=sessions)


def fetch_cafef_weekly_foreign_flow() -> pd.DataFrame:
    """Backward-compatible wrapper for the old exploratory test surface."""
    return fetch_cafef_foreign_flow_history("ALL", exchange="HOSE", sessions=20)


def load_cached_foreign_flow() -> pd.DataFrame:
    return _load_cached_frame(CACHE_PATH)


def load_cached_market_foreign_flow() -> pd.DataFrame:
    return _load_cached_frame(MARKET_CACHE_PATH)


if __name__ == "__main__":
    print(fetch_cafef_foreign_flow_history("VCB").head().to_string())

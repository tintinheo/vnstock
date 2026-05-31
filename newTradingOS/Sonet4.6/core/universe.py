from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os

import pandas as pd

from config import HNX_LIST, HOSE_LIST, MARKET_SCAN_LIST, TICKER_EXCHANGE, UPCOM_LIST, VN100_LIST, VN30_LIST

logger = logging.getLogger("TradingOS.universe")

_UNIVERSE_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "listing_master_cache.csv",
)
_UNIVERSE_CACHE_TTL = timedelta(hours=12)
_LIVE_EXCHANGES = ("HOSE", "HNX", "UPCOM")


def _empty_listing_master() -> pd.DataFrame:
    return pd.DataFrame(columns=["symbol", "exchange", "type", "source", "fetched_at"])


def _cache_is_fresh(path: str, ttl: timedelta = _UNIVERSE_CACHE_TTL) -> bool:
    if not os.path.exists(path):
        return False
    try:
        modified_at = datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return False
    return (datetime.now() - modified_at) <= ttl


def _normalize_listing_master(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return _empty_listing_master()

    working = df.copy()
    working.columns = [str(column).strip().lower() for column in working.columns]
    if "symbol" not in working.columns or "exchange" not in working.columns:
        return _empty_listing_master()

    if "type" not in working.columns:
        working["type"] = "stock"

    working["symbol"] = working["symbol"].astype(str).str.strip().str.upper()
    working["exchange"] = working["exchange"].astype(str).str.strip().str.upper()
    working["type"] = working["type"].astype(str).str.strip().str.lower()
    working = working[
        working["symbol"].str.fullmatch(r"[A-Z0-9]{2,10}", na=False)
        & working["exchange"].isin(_LIVE_EXCHANGES)
        & (working["type"] == "stock")
    ]
    if working.empty:
        return _empty_listing_master()

    keep_columns = [column for column in ("symbol", "exchange", "type") if column in working.columns]
    normalized = working[keep_columns].drop_duplicates(subset=["symbol", "exchange"])
    normalized["source"] = "vnstock:kbs"
    normalized["fetched_at"] = datetime.now().isoformat()
    return normalized.sort_values(["exchange", "symbol"]).reset_index(drop=True)


def load_cached_listing_master() -> pd.DataFrame:
    if not os.path.exists(_UNIVERSE_CACHE_PATH):
        return _empty_listing_master()
    try:
        df = pd.read_csv(_UNIVERSE_CACHE_PATH)
    except Exception as exc:
        logger.debug("load_cached_listing_master: %s", exc)
        return _empty_listing_master()
    return _normalize_listing_master(df)


def save_cached_listing_master(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    os.makedirs(os.path.dirname(_UNIVERSE_CACHE_PATH), exist_ok=True)
    df.to_csv(_UNIVERSE_CACHE_PATH, index=False)


def _fetch_listing_master_vnstock(listing_factory=None) -> pd.DataFrame:
    if listing_factory is None:
        from vnstock import Listing

        listing_factory = Listing

    listing = listing_factory(source="kbs", show_log=False)
    raw = listing.symbols_by_exchange()
    return _normalize_listing_master(raw)


def fetch_listing_master(force_refresh: bool = False) -> tuple[pd.DataFrame, str]:
    if not force_refresh and _cache_is_fresh(_UNIVERSE_CACHE_PATH):
        cached = load_cached_listing_master()
        if not cached.empty:
            return cached, "cache"

    try:
        live_df = _fetch_listing_master_vnstock()
        if not live_df.empty:
            save_cached_listing_master(live_df)
            return live_df, "live"
    except Exception as exc:
        logger.warning("Live listing master unavailable: %s", exc)

    cached = load_cached_listing_master()
    if not cached.empty:
        return cached, "stale-cache"
    return _empty_listing_master(), "unavailable"


def get_cached_exchange_counts() -> dict[str, int]:
    cached = load_cached_listing_master()
    if cached.empty:
        return {}
    return {
        str(exchange): int(count)
        for exchange, count in cached.groupby("exchange")["symbol"].nunique().to_dict().items()
    }


def _build_listing_exchange_map(df: pd.DataFrame) -> dict[str, str]:
    if df is None or df.empty:
        return {}
    deduped = df.drop_duplicates(subset=["symbol"], keep="first")
    return {
        str(symbol).strip().upper(): str(exchange).strip().upper()
        for symbol, exchange in deduped[["symbol", "exchange"]].itertuples(index=False, name=None)
    }


def resolve_exchange_map(
    symbols: list[str],
    *,
    listing_master: pd.DataFrame | None = None,
    listing_source: str | None = None,
    prefer_live: bool = False,
    force_refresh: bool = False,
) -> tuple[dict[str, str], str]:
    normalized_symbols = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    if not normalized_symbols:
        return {}, "configured-only"

    working_listing = listing_master if listing_master is not None and not listing_master.empty else _empty_listing_master()
    exchange_source = "configured-only"

    if working_listing.empty:
        if prefer_live and listing_source != "unavailable":
            working_listing, exchange_source = fetch_listing_master(force_refresh=force_refresh)
        else:
            if prefer_live:
                exchange_source = "configured-only"
            else:
                working_listing = load_cached_listing_master()
                exchange_source = "cache" if not working_listing.empty else "configured-only"
    else:
        exchange_source = listing_source or "listing-master"

    listing_map = _build_listing_exchange_map(working_listing)
    exchange_map = {
        symbol: listing_map.get(symbol, TICKER_EXCHANGE.get(symbol, "HOSE"))
        for symbol in normalized_symbols
    }
    return exchange_map, exchange_source


def resolve_universe_symbols(
    selections: list[str],
    watchlist: list[str],
    *,
    force_refresh: bool = False,
) -> tuple[list[str], dict]:
    normalized = selections or ["Watchlist"]
    symbols: set[str] = set()
    warnings: list[str] = []
    selection_sources: dict[str, str] = {}

    live_requested = [selection for selection in normalized if selection in _LIVE_EXCHANGES]
    listing_master = _empty_listing_master()
    listing_source = "configured-only"
    if live_requested:
        listing_master, listing_source = fetch_listing_master(force_refresh=force_refresh)

    fallback_buckets = {
        "HOSE": HOSE_LIST,
        "HNX": HNX_LIST,
        "UPCOM": UPCOM_LIST,
    }

    for selection in normalized:
        if selection == "Watchlist":
            symbols.update(symbol.strip().upper() for symbol in watchlist if symbol.strip())
            selection_sources[selection] = "session-watchlist"
        elif selection == "VN30":
            symbols.update(VN30_LIST)
            selection_sources[selection] = "configured-index"
        elif selection == "VN100":
            symbols.update(VN100_LIST)
            selection_sources[selection] = "configured-index"
        elif selection == "Market Scan":
            symbols.update(MARKET_SCAN_LIST)
            selection_sources[selection] = "configured-market-scan"
        elif selection in _LIVE_EXCHANGES:
            live_symbols = sorted(
                listing_master.loc[listing_master["exchange"] == selection, "symbol"].drop_duplicates().tolist()
            ) if not listing_master.empty else []
            if live_symbols:
                symbols.update(live_symbols)
                selection_sources[selection] = f"live-listing:{listing_source}"
            else:
                fallback = fallback_buckets.get(selection, [])
                symbols.update(fallback)
                selection_sources[selection] = "configured-fallback"
                warnings.append(
                    f"{selection}: live listing unavailable, dùng fallback {len(fallback)} mã cấu hình."
                )

    resolved = sorted(symbols)
    exchange_map, exchange_map_source = resolve_exchange_map(
        resolved,
        listing_master=listing_master,
        listing_source=listing_source,
        prefer_live=bool(live_requested),
        force_refresh=force_refresh,
    )
    return resolved, {
        "selection_sources": selection_sources,
        "listing_source": listing_source,
        "exchange_map": exchange_map,
        "exchange_map_source": exchange_map_source,
        "resolved_count": len(resolved),
        "warnings": warnings,
        "used_live_listing": any(source.startswith("live-listing") for source in selection_sources.values()),
    }
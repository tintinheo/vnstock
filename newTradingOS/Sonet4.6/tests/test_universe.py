from __future__ import annotations

import pandas as pd

from core.universe import _fetch_listing_master_vnstock, resolve_universe_symbols


class _FakeListing:
    def __init__(self, source: str = "kbs", show_log: bool = False):
        self.source = source
        self.show_log = show_log

    def symbols_by_exchange(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"symbol": "vcb", "exchange": "hose", "type": "stock"},
            {"symbol": " pvs ", "exchange": "hnx", "type": "stock"},
            {"symbol": "cfw1", "exchange": "hose", "type": "cw"},
        ])


def test_fetch_listing_master_vnstock_filters_to_stock_rows():
    df = _fetch_listing_master_vnstock(listing_factory=_FakeListing)

    assert list(df["symbol"]) == ["PVS", "VCB"]
    assert set(df["exchange"]) == {"HOSE", "HNX"}
    assert set(df["type"]) == {"stock"}


def test_resolve_universe_symbols_prefers_live_listing(monkeypatch):
    live_df = pd.DataFrame([
        {"symbol": "AAA", "exchange": "HOSE", "type": "stock", "source": "vnstock:kbs", "fetched_at": "2026-05-31T00:00:00"},
        {"symbol": "BBB", "exchange": "HOSE", "type": "stock", "source": "vnstock:kbs", "fetched_at": "2026-05-31T00:00:00"},
        {"symbol": "CCC", "exchange": "HNX", "type": "stock", "source": "vnstock:kbs", "fetched_at": "2026-05-31T00:00:00"},
    ])

    monkeypatch.setattr("core.universe.fetch_listing_master", lambda force_refresh=False: (live_df, "cache"))

    symbols, meta = resolve_universe_symbols(["HOSE", "Watchlist"], ["VCB"])

    assert symbols == ["AAA", "BBB", "VCB"]
    assert meta["selection_sources"]["HOSE"] == "live-listing:cache"
    assert meta["used_live_listing"] is True


def test_resolve_universe_symbols_falls_back_when_live_listing_unavailable(monkeypatch):
    monkeypatch.setattr("core.universe.fetch_listing_master", lambda force_refresh=False: (pd.DataFrame(), "unavailable"))

    symbols, meta = resolve_universe_symbols(["HNX"], [])

    assert len(symbols) > 0
    assert meta["selection_sources"]["HNX"] == "configured-fallback"
    assert meta["warnings"]
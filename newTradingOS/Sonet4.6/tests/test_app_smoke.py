from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from core.audit import ACTION_LOAD, ACTION_MACRO
from core.regime import RegimeResult
from portfolio.tracker import Portfolio


APP_FILE = Path(__file__).resolve().parents[1] / "app.py"


def _make_ohlcv(n: int = 180, start_price: float = 50_000.0) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-05-29", periods=n)
    closes = pd.Series([start_price + (i * 120.0) for i in range(n)], index=dates)
    return pd.DataFrame(
        {
            "Open": closes * 0.997,
            "High": closes * 1.004,
            "Low": closes * 0.994,
            "Close": closes,
            "Volume": [1_500_000 + (i * 1_000) for i in range(n)],
        },
        index=dates,
    )


def _patch_tab_renderers(monkeypatch) -> None:
    import ui.audit_tab as audit_tab
    import ui.backtest_tab as backtest_tab
    import ui.guide_tab as guide_tab
    import ui.macro_tab as macro_tab
    import ui.ml_tab as ml_tab
    import ui.portfolio_tab as portfolio_tab
    import ui.scanner_tab as scanner_tab

    monkeypatch.setattr(scanner_tab, "render_scanner_tab", lambda *args, **kwargs: st.caption("scanner-ok"))
    monkeypatch.setattr(macro_tab, "render_macro_tab", lambda *args, **kwargs: st.caption("macro-ok"))
    monkeypatch.setattr(ml_tab, "render_ml_tab", lambda *args, **kwargs: st.caption("ml-ok"))
    monkeypatch.setattr(backtest_tab, "render_backtest_tab", lambda *args, **kwargs: st.caption("backtest-ok"))
    monkeypatch.setattr(audit_tab, "render_audit_tab", lambda *args, **kwargs: st.caption("audit-ok"))
    monkeypatch.setattr(guide_tab, "render_guide_tab", lambda *args, **kwargs: st.caption("guide-ok"))

    def _portfolio_stub(portfolio: Portfolio, *args, **kwargs) -> Portfolio:
        st.caption("portfolio-ok")
        return portfolio

    monkeypatch.setattr(portfolio_tab, "render_portfolio_tab", _portfolio_stub)


def _base_app_patches(monkeypatch, *, event_calls: list[tuple]) -> None:
    import core.audit as audit
    import core.macro_data as macro_data
    import core.regime as regime
    import core.universe as universe

    _patch_tab_renderers(monkeypatch)

    monkeypatch.setattr(
        Portfolio,
        "load",
        classmethod(lambda cls, path=None: cls()),
    )
    monkeypatch.setattr(audit, "log_event", lambda *args, **kwargs: event_calls.append((args, kwargs)))
    monkeypatch.setattr(universe, "get_cached_exchange_counts", lambda: {"HOSE": 403, "HNX": 300, "UPCOM": 829})
    monkeypatch.setattr(
        macro_data,
        "fetch_macro_indicators",
        lambda: {
            "dxy_trend": "neutral",
            "vix_level": "normal",
            "foreign_flow": {"signal_net_buy": 25_000_000_000.0, "trend": "accumulate"},
            "breadth": {"advance": 180, "decline": 95, "fetch_ok": True},
            "ad_ratio": 0.65,
            "stale_fields": [],
        },
    )
    monkeypatch.setattr(macro_data, "get_macro_score", lambda payload: (6.75, "bull", []))
    def _fetch_vni_stub(days=365):
        df = _make_ohlcv(n=220, start_price=1_200.0)
        df.index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=len(df))
        df.attrs["source_mode"] = "live"
        df.attrs["source_name"] = "DNSE"
        return df

    monkeypatch.setattr(macro_data, "fetch_vni_data", _fetch_vni_stub)
    monkeypatch.setattr(
        macro_data,
        "fetch_foreign_flow_tickers",
        lambda tickers, exchange_map=None: {
            ticker: {
                "basis": "cafef-20d",
                "signal_net_buy": 12_500_000_000.0,
                "net_buy_20d": 12_500_000_000.0,
                "trend_20d": "accumulate",
            }
            for ticker in tickers
        },
    )
    monkeypatch.setattr(
        regime,
        "detect_regime",
        lambda prices: RegimeResult("bull", 0.82, ["bull"] * max(len(prices) - 1, 1), "rule", {"bull": 0.2}),
    )


def test_app_smoke_watchlist_load_then_macro_refresh(monkeypatch):
    import core.data_fetcher as data_fetcher
    import core.universe as universe

    batch_calls: list[dict] = []
    event_calls: list[tuple] = []
    sample_df = _make_ohlcv()

    _base_app_patches(monkeypatch, event_calls=event_calls)

    monkeypatch.setattr(
        universe,
        "resolve_universe_symbols",
        lambda selections, watchlist, force_refresh=False: (
            ["VCB"],
            {
                "selection_sources": {"Watchlist": "session-watchlist"},
                "listing_source": "configured-only",
                "exchange_map": {"VCB": "HOSE"},
                "exchange_map_source": "configured-only",
                "resolved_count": 1,
                "warnings": [],
                "used_live_listing": False,
            },
        ),
    )

    def _batch_download(symbols, days=730, max_workers=8, delay=0.05, chunk_size=120, on_progress=None):
        batch_calls.append(
            {
                "symbols": list(symbols),
                "days": days,
                "max_workers": max_workers,
                "chunk_size": chunk_size,
            }
        )
        total = len(symbols)
        for index, symbol in enumerate(symbols, start=1):
            if on_progress is not None:
                on_progress(index, total, symbol)
        return {symbol: (sample_df.copy(), "TEST") for symbol in symbols}

    monkeypatch.setattr(data_fetcher, "batch_download", _batch_download)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)

    at.sidebar.text_area[0].set_value("VCB").run(timeout=120)
    at.sidebar.multiselect[0].set_value(["Watchlist"]).run(timeout=120)
    at.sidebar.button[0].click().run(timeout=120)

    assert len(at.exception) == 0
    assert at.session_state["watchlist"] == ["VCB"]
    assert batch_calls == [
        {"symbols": ["VCB"], "days": 730, "max_workers": 8, "chunk_size": 120}
    ]
    assert sorted(at.session_state["data_dict"].keys()) == ["VCB"]
    assert at.session_state["exchange_map"] == {"VCB": "HOSE"}
    assert at.session_state["universe_meta"]["selection_sources"] == {"Watchlist": "session-watchlist"}
    assert at.session_state["data_version"] == 1
    assert at.session_state["data_loaded_at"]

    at.sidebar.button[1].click().run(timeout=120)

    assert len(at.exception) == 0
    assert at.session_state["macro_score"] == 6.75
    assert at.session_state["macro_regime"] == "bull"
    assert at.session_state["macro_stale"] == []
    assert at.session_state["macro_updated_at"]
    assert at.session_state["regime_result"].regime == "bull"
    assert at.session_state["regime_stale"] is False
    assert at.session_state["regime_source"] == "live (DNSE)"
    assert at.session_state["vni_df"] is not None
    assert "Close" in at.session_state["vni_df"].columns
    assert at.session_state["foreign_flows_cache"]["VCB"]["basis"] == "cafef-20d"
    assert at.session_state["foreign_flow_meta"]["requested_symbols"] == 1
    assert at.session_state["foreign_flow_meta"]["bounded_mode"] is False
    assert [args[0] for args, _ in event_calls] == [ACTION_LOAD, ACTION_MACRO]


def test_app_smoke_macro_refresh_passes_live_exchange_map_to_foreign_flow(monkeypatch):
    import core.data_fetcher as data_fetcher
    import core.macro_data as macro_data
    import core.universe as universe

    event_calls: list[tuple] = []
    foreign_flow_calls: list[dict] = []
    sample_df = _make_ohlcv()

    _base_app_patches(monkeypatch, event_calls=event_calls)

    monkeypatch.setattr(
        universe,
        "resolve_universe_symbols",
        lambda selections, watchlist, force_refresh=False: (
            ["ZZZ"],
            {
                "selection_sources": {"Watchlist": "session-watchlist"},
                "listing_source": "cache",
                "exchange_map": {"ZZZ": "HNX"},
                "exchange_map_source": "cache",
                "resolved_count": 1,
                "warnings": [],
                "used_live_listing": False,
            },
        ),
    )

    monkeypatch.setattr(
        data_fetcher,
        "batch_download",
        lambda symbols, days=730, max_workers=8, delay=0.05, chunk_size=120, on_progress=None: {
            symbol: (sample_df.copy(), "TEST") for symbol in symbols
        },
    )

    def _capture_foreign_flow(tickers, exchange_map=None):
        foreign_flow_calls.append({
            "tickers": list(tickers),
            "exchange_map": dict(exchange_map or {}),
        })
        return {
            ticker: {
                "basis": "cafef-20d",
                "signal_net_buy": 12_500_000_000.0,
                "net_buy_20d": 12_500_000_000.0,
                "trend_20d": "accumulate",
            }
            for ticker in tickers
        }

    monkeypatch.setattr(macro_data, "fetch_foreign_flow_tickers", _capture_foreign_flow)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)

    at.sidebar.text_area[0].set_value("ZZZ").run(timeout=120)
    at.sidebar.multiselect[0].set_value(["Watchlist"]).run(timeout=120)
    at.sidebar.button[0].click().run(timeout=120)
    at.sidebar.button[1].click().run(timeout=120)

    assert len(at.exception) == 0
    assert foreign_flow_calls == [{"tickers": ["ZZZ"], "exchange_map": {"ZZZ": "HNX"}}]


def test_app_smoke_macro_refresh_expands_vni_history_for_long_loaded_data(monkeypatch):
    import core.data_fetcher as data_fetcher
    import core.macro_data as macro_data
    import core.universe as universe

    event_calls: list[tuple] = []
    vni_days_calls: list[int] = []
    sample_df = _make_ohlcv(n=540)

    _base_app_patches(monkeypatch, event_calls=event_calls)

    monkeypatch.setattr(
        universe,
        "resolve_universe_symbols",
        lambda selections, watchlist, force_refresh=False: (
            ["VCB"],
            {
                "selection_sources": {"Watchlist": "session-watchlist"},
                "listing_source": "configured-only",
                "exchange_map": {"VCB": "HOSE"},
                "exchange_map_source": "configured-only",
                "resolved_count": 1,
                "warnings": [],
                "used_live_listing": False,
            },
        ),
    )

    monkeypatch.setattr(
        data_fetcher,
        "batch_download",
        lambda symbols, days=730, max_workers=8, delay=0.05, chunk_size=120, on_progress=None: {
            symbol: (sample_df.copy(), "TEST") for symbol in symbols
        },
    )

    def _capture_vni(days=365):
        vni_days_calls.append(int(days))
        df = _make_ohlcv(n=min(max(int(days), 30), 260), start_price=1_200.0)
        df.attrs["source_mode"] = "live"
        df.attrs["source_name"] = "DNSE"
        return df

    monkeypatch.setattr(macro_data, "fetch_vni_data", _capture_vni)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)

    at.sidebar.text_area[0].set_value("VCB").run(timeout=120)
    at.sidebar.multiselect[0].set_value(["Watchlist"]).run(timeout=120)
    at.sidebar.button[0].click().run(timeout=120)
    at.sidebar.button[1].click().run(timeout=120)

    assert len(at.exception) == 0
    assert vni_days_calls, "Expected macro refresh to request VNINDEX history"
    assert vni_days_calls[-1] > 365


def test_app_smoke_passes_exchange_map_to_ml_tab(monkeypatch):
    import core.data_fetcher as data_fetcher
    import core.universe as universe
    import ui.ml_tab as ml_tab

    event_calls: list[tuple] = []
    ml_calls: list[dict] = []
    sample_df = _make_ohlcv()

    _base_app_patches(monkeypatch, event_calls=event_calls)

    monkeypatch.setattr(
        universe,
        "resolve_universe_symbols",
        lambda selections, watchlist, force_refresh=False: (
            ["ZZZ"],
            {
                "selection_sources": {"Watchlist": "session-watchlist"},
                "listing_source": "cache",
                "exchange_map": {"ZZZ": "UPCOM"},
                "exchange_map_source": "cache",
                "resolved_count": 1,
                "warnings": [],
                "used_live_listing": False,
            },
        ),
    )

    monkeypatch.setattr(
        data_fetcher,
        "batch_download",
        lambda symbols, days=730, max_workers=8, delay=0.05, chunk_size=120, on_progress=None: {
            symbol: (sample_df.copy(), "TEST") for symbol in symbols
        },
    )

    def _capture_ml_tab(data_dict, regime, macro_data, lang="VI", exchange_map=None):
        ml_calls.append({
            "tickers": sorted(data_dict.keys()),
            "exchange_map": dict(exchange_map or {}),
        })
        st.caption("ml-ok-captured")

    monkeypatch.setattr(ml_tab, "render_ml_tab", _capture_ml_tab)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)
    at.sidebar.text_area[0].set_value("ZZZ").run(timeout=120)
    at.sidebar.multiselect[0].set_value(["Watchlist"]).run(timeout=120)
    at.sidebar.button[0].click().run(timeout=120)

    assert len(at.exception) == 0
    assert ml_calls
    assert ml_calls[-1] == {"tickers": ["ZZZ"], "exchange_map": {"ZZZ": "UPCOM"}}


def test_app_smoke_hose_hnx_load_uses_large_universe_mode(monkeypatch):
    import core.data_fetcher as data_fetcher
    import core.universe as universe

    batch_calls: list[dict] = []
    event_calls: list[tuple] = []
    large_symbols = [f"S{index:03d}" for index in range(125)]
    large_exchange_map = {
        symbol: ("HOSE" if index < 60 else "HNX")
        for index, symbol in enumerate(large_symbols)
    }
    sample_df = _make_ohlcv(n=120)

    _base_app_patches(monkeypatch, event_calls=event_calls)

    monkeypatch.setattr(
        universe,
        "resolve_universe_symbols",
        lambda selections, watchlist, force_refresh=False: (
            large_symbols,
            {
                "selection_sources": {
                    "HOSE": "live-listing:cache",
                    "HNX": "live-listing:cache",
                },
                "listing_source": "cache",
                "exchange_map": large_exchange_map,
                "exchange_map_source": "cache",
                "resolved_count": len(large_symbols),
                "warnings": [],
                "used_live_listing": True,
            },
        ),
    )

    def _batch_download(symbols, days=730, max_workers=8, delay=0.05, chunk_size=120, on_progress=None):
        batch_calls.append(
            {
                "symbol_count": len(symbols),
                "days": days,
                "max_workers": max_workers,
                "chunk_size": chunk_size,
            }
        )
        total = len(symbols)
        for index, symbol in enumerate(symbols, start=1):
            if on_progress is not None:
                on_progress(index, total, symbol)
        return {symbol: (sample_df.copy(), "TEST") for symbol in symbols}

    monkeypatch.setattr(data_fetcher, "batch_download", _batch_download)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)

    at.sidebar.multiselect[0].set_value(["HOSE", "HNX"]).run(timeout=120)
    at.sidebar.button[0].click().run(timeout=120)
    at.sidebar.button[1].click().run(timeout=120)

    assert len(at.exception) == 0
    assert batch_calls == [
        {"symbol_count": 125, "days": 730, "max_workers": 6, "chunk_size": 120}
    ]
    assert len(at.session_state["data_dict"]) == 125
    assert at.session_state["exchange_map"]["S000"] == "HOSE"
    assert at.session_state["exchange_map"]["S124"] == "HNX"
    assert at.session_state["universe_meta"]["used_live_listing"] is True
    assert at.session_state["universe_meta"]["resolved_count"] == 125
    assert at.session_state["foreign_flow_meta"]["requested_symbols"] == 125
    assert at.session_state["foreign_flow_meta"]["bounded_mode"] is True
    assert at.session_state["regime_source"] == "live (DNSE)"
    assert [args[0] for args, _ in event_calls] == [ACTION_LOAD, ACTION_MACRO]


def test_app_smoke_vni_fetch_failure_marks_regime_stale_without_macro_partial(monkeypatch):
    import core.macro_data as macro_data

    event_calls: list[tuple] = []

    _base_app_patches(monkeypatch, event_calls=event_calls)
    monkeypatch.setattr(macro_data, "fetch_vni_data", lambda days=365: pd.DataFrame())

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)
    at.sidebar.button[1].click().run(timeout=120)

    assert len(at.exception) == 0
    assert at.session_state["macro_stale"] == []
    assert at.session_state["regime_stale"] is True
    assert at.session_state["regime_result"] is None
    assert at.session_state["regime_source"] == "unavailable"
    assert [args[0] for args, _ in event_calls] == [ACTION_MACRO]


def test_app_smoke_auto_refreshes_vni_regime_on_startup(monkeypatch):
    import core.macro_data as macro_data

    event_calls: list[tuple] = []
    fetch_vni_calls: list[int] = []

    _base_app_patches(monkeypatch, event_calls=event_calls)

    def _capture_vni(days=365):
        fetch_vni_calls.append(int(days))
        df = _make_ohlcv(n=120, start_price=1_200.0)
        df.index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=len(df))
        df.attrs["source_mode"] = "live"
        df.attrs["source_name"] = "DNSE"
        return df

    monkeypatch.setattr(macro_data, "fetch_vni_data", _capture_vni)

    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=120)

    assert len(at.exception) == 0
    assert fetch_vni_calls, "Expected startup auto-refresh to request VNINDEX data"
    assert at.session_state["regime_result"].regime == "bull"
    assert at.session_state["regime_stale"] is False
    assert at.session_state["regime_updated_at"]
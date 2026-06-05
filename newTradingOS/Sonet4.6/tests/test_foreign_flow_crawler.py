"""Unit tests for CafeF foreign-flow history helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from core.foreign_flow_crawler import (
    fetch_cafef_foreign_flow_history,
    fetch_cafef_market_foreign_flow,
    fetch_cafef_market_foreign_flow_history,
    load_cached_foreign_flow,
    load_cached_market_foreign_flow,
    summarize_market_foreign_flow_history,
    summarize_foreign_flow_history,
)


def _cafef_payload(rows: list[dict]) -> dict:
    return {
        "Data": {
            "TotalCount": len(rows),
            "Index": "VNINDEX",
            "DateIndex": "29/05/2026",
            "TradingReport": {
                "klMua": 1,
                "klBan": 1,
                "gtMua": 1.0,
                "gtBan": 1.0,
            },
            "Data": rows,
        },
        "Message": None,
        "Success": True,
    }


@patch("core.foreign_flow_crawler.requests.get")
def test_fetch_cafef_foreign_flow_history_normalizes_payload(mock_get):
    rows = [
        {
            "Symbol": "VCB",
            "Ngay": "29/05/2026",
            "KLGDRong": 280800,
            "GTDGRong": 17447020000,
            "ThayDoi": "62,00 (-1,27%)",
            "KLMua": 427800,
            "GtMua": 26644080000,
            "KLBan": 147000,
            "GtBan": 9197060000,
            "RoomConLai": 813723803,
            "DangSoHuu": 20.26,
        },
        {
            "Symbol": "VCB",
            "Ngay": "28/05/2026",
            "KLGDRong": 371200,
            "GTDGRong": 23242190000,
            "ThayDoi": "62,80 (-2,18%)",
            "KLMua": 690400,
            "GtMua": 43458230000,
            "KLBan": 319200,
            "GtBan": 20216040000,
            "RoomConLai": 814094877,
            "DangSoHuu": 20.26,
        },
    ]
    response = MagicMock()
    response.json.return_value = _cafef_payload(rows)
    response.raise_for_status.return_value = None
    mock_get.return_value = response

    history = fetch_cafef_foreign_flow_history("VCB", exchange="HOSE", sessions=20)

    assert len(history) == 2
    assert list(history["ticker"]) == ["VCB", "VCB"]
    assert set([
        "ticker", "date", "buy_value", "sell_value", "net_value",
        "buy_volume", "sell_volume", "net_volume", "room_remaining",
        "foreign_ownership_pct", "exchange", "source",
    ]).issubset(history.columns)
    assert history.iloc[0]["net_value"] == 17447020000
    assert history.iloc[0]["exchange"] == "HOSE"


def test_summarize_foreign_flow_history_builds_verified_20d_contract():
    rows = []
    for day in range(20):
        rows.append({
            "ticker": "VCB",
            "date": pd.Timestamp("2026-05-29") - pd.Timedelta(days=day),
            "buy_value": 20_000_000_000 + day,
            "sell_value": 5_000_000_000 + day,
            "net_value": 15_000_000_000,
            "buy_volume": 1000 + day,
            "sell_volume": 500 + day,
            "net_volume": 500,
            "room_remaining": 1_000_000,
            "foreign_ownership_pct": 20.0,
            "exchange": "HOSE",
            "source": "CafeF foreign history",
        })
    history = pd.DataFrame(rows)

    result = summarize_foreign_flow_history(history, sessions=20)["VCB"]

    assert result["net_buy_value"] == 15_000_000_000
    assert result["net_20d"] == 300_000_000_000
    assert result["trend_20d"] == "accumulate"
    assert result["history_sessions"] == 20
    assert result["is_20d_proxy"] is False


def test_load_cached_foreign_flow(tmp_path):
    cache_path = tmp_path / "foreign_flow_cache.csv"
    expected = pd.DataFrame([
        {
            "ticker": "VCB",
            "date": "2026-05-29",
            "buy_value": 10,
            "sell_value": 5,
            "net_value": 5,
        }
    ])
    expected.to_csv(cache_path, index=False)

    with patch("core.foreign_flow_crawler.CACHE_PATH", cache_path):
        df = load_cached_foreign_flow()

    assert set(["date", "ticker", "buy_value", "sell_value", "net_value"]).issubset(df.columns)
    assert len(df) == 1


def test_summarize_market_foreign_flow_history_builds_signal_from_20_sessions():
    rows = []
    for day in range(20):
        rows.append({
            "date": pd.Timestamp("2026-05-29") - pd.Timedelta(days=day),
            "buy_value": 100_000_000_000,
            "sell_value": 70_000_000_000,
            "net_value": 30_000_000_000,
            "buy_volume": 1_000_000,
            "sell_volume": 700_000,
            "net_volume": 300_000,
            "symbol_count": 300,
            "source": "CafeF market history backfill",
        })
    history = pd.DataFrame(rows)

    result = summarize_market_foreign_flow_history(history, sessions=20)

    assert result["net_buy"] == 30_000_000_000
    assert result["net_buy_20d"] == 600_000_000_000
    assert result["signal_net_buy"] == 30_000_000_000
    assert result["trend_20d"] == "accumulate"
    assert result["history_sessions"] == 20
    assert len(result["history"]) == 20


@patch("core.foreign_flow_crawler.requests.get")
def test_fetch_cafef_market_foreign_flow_history_backfills_until_cutoff(mock_get, tmp_path):
    def _rows(day: str, symbols: list[str]) -> list[dict]:
        return [
            {
                "Symbol": symbol,
                "Ngay": day,
                "KLGDRong": 100,
                "GTDGRong": 1_000_000_000,
                "ThayDoi": "10,00 (+1,00%)",
                "KLMua": 200,
                "GtMua": 2_000_000_000,
                "KLBan": 100,
                "GtBan": 1_000_000_000,
                "RoomConLai": 1000,
                "DangSoHuu": 10.0,
            }
            for symbol in symbols
        ]

    pages = [
        _cafef_payload(_rows("29/05/2026", [f"A{i:02d}" for i in range(20)])),
        _cafef_payload(
            _rows("28/05/2026", [f"B{i:02d}" for i in range(10)])
            + _rows("27/05/2026", [f"C{i:02d}" for i in range(10)])
        ),
    ]

    def _response(payload: dict) -> MagicMock:
        response = MagicMock()
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    mock_get.side_effect = [_response(payload) for payload in pages]

    with patch("core.foreign_flow_crawler.MARKET_CACHE_PATH", tmp_path / "market.csv"):
        history = fetch_cafef_market_foreign_flow_history(
            sessions=2,
            exchanges=("HOSE",),
            max_pages_per_exchange=2,
            force_refresh=True,
        )

    assert list(history["date"].dt.strftime("%Y-%m-%d")) == ["2026-05-29", "2026-05-28"]
    assert list(history["net_value"]) == [20_000_000_000, 10_000_000_000]
    assert mock_get.call_count == 2


def test_fetch_cafef_market_foreign_flow_uses_cached_history_when_not_force_refresh(tmp_path):
    cache_path = tmp_path / "foreign_flow_market_history.csv"
    cached = pd.DataFrame([
        {
            "date": "2026-05-29",
            "buy_value": 100_000_000_000,
            "sell_value": 70_000_000_000,
            "net_value": 30_000_000_000,
            "buy_volume": 1,
            "sell_volume": 1,
            "net_volume": 0,
            "symbol_count": 300,
            "source": "CafeF market history backfill",
        },
        {
            "date": "2026-05-28",
            "buy_value": 80_000_000_000,
            "sell_value": 60_000_000_000,
            "net_value": 20_000_000_000,
            "buy_volume": 1,
            "sell_volume": 1,
            "net_volume": 0,
            "symbol_count": 300,
            "source": "CafeF market history backfill",
        },
    ])
    cached.to_csv(cache_path, index=False)

    with patch("core.foreign_flow_crawler.MARKET_CACHE_PATH", cache_path):
        result = fetch_cafef_market_foreign_flow(sessions=2, force_refresh=False)
        loaded = load_cached_market_foreign_flow()

    assert result["fetch_ok"] is True
    assert result["history_sessions"] == 2
    assert result["net_buy_20d"] == 50_000_000_000
    assert len(loaded) == 2

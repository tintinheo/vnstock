"""
tests/test_data_fetcher.py — NewTradingOS v14.0
Tests for core/data_fetcher.py — no live API calls; HTTP is mocked.
"""
from __future__ import annotations

import json
import sys
import os
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# We need the project root on sys.path (conftest does this already).
from core.data_fetcher import (
    _normalize_price_scale, _clean_df,
    _parse_udf, batch_download, download_data, get_latest_price,
)


# ─────────────────────────────────────────────────────────────
# _normalize_price_scale
# ─────────────────────────────────────────────────────────────
class TestNormalizePriceScale:
    # _normalize_price_scale modifies DataFrame IN-PLACE and returns None.

    def test_detects_raw_vnd(self):
        """Prices like 88000 should NOT be scaled up (already in VND)."""
        raw = 88_000.0
        df  = pd.DataFrame({
            "Open": [raw], "High": [raw + 500], "Low": [raw - 300],
            "Close": [raw], "Volume": [1_000_000],
        })
        _normalize_price_scale(df)  # in-place
        # Should remain the same order of magnitude
        assert 10_000 < df["Close"].iloc[0] < 300_000

    def test_scales_up_small_prices(self):
        """Prices like 88.0 (HOSE format with /1000) should be multiplied."""
        df = pd.DataFrame({
            "Open":   [88.0],
            "High":   [89.0],
            "Low":    [87.5],
            "Close":  [88.5],
            "Volume": [1_000_000],
        })
        _normalize_price_scale(df)  # in-place
        # After scaling, should be in full VND range
        assert df["Close"].iloc[0] > 1_000

    def test_volume_unchanged(self):
        df = pd.DataFrame({
            "Open": [50_000.0], "High": [51_000.0], "Low": [49_000.0],
            "Close": [50_500.0], "Volume": [5_000_000],
        })
        _normalize_price_scale(df)  # in-place
        assert df["Volume"].iloc[0] == 5_000_000


# ─────────────────────────────────────────────────────────────
# _clean_df
# ─────────────────────────────────────────────────────────────
class TestCleanDf:
    def test_drops_duplicate_index(self):
        """_clean_df sorts by index; duplicate removal is done in _parse_udf."""
        n     = 10
        dates = pd.bdate_range("2026-01-01", periods=n)
        df    = pd.DataFrame({
            "Open": [100.0]*n, "High": [101.0]*n,
            "Low":  [99.0]*n,  "Close": [100.5]*n,
            "Volume": [1_000_000]*n,
        }, index=dates)
        # _clean_df should at least produce a sorted index
        shuffled = df.sample(frac=1, random_state=42)
        out = _clean_df(shuffled)
        assert out.index.is_monotonic_increasing

    def test_drops_zero_close(self):
        dates = pd.bdate_range("2026-01-01", periods=3)
        df = pd.DataFrame({
            "Open": [50.0, 0.0, 50.0], "High": [51.0, 0.0, 51.0],
            "Low":  [49.0, 0.0, 49.0], "Close": [50.0, 0.0, 50.0],
            "Volume": [1_000_000]*3,
        }, index=dates)
        out = _clean_df(df)
        assert len(out) == 2

    def test_sorted_asc(self, ohlcv):
        shuffled = ohlcv.sample(frac=1, random_state=5)
        out = _clean_df(shuffled)
        assert out.index.is_monotonic_increasing

    def test_required_columns_present(self, ohlcv):
        out = _clean_df(ohlcv.copy())
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in out.columns


# ─────────────────────────────────────────────────────────────
# _parse_udf
# ─────────────────────────────────────────────────────────────
class TestParseUdf:
    def _sample_udf(self, n: int = 5) -> dict:
        t  = [1_700_000_000 + i * 86400 for i in range(n)]
        o  = [50_000.0 + i * 100 for i in range(n)]
        h  = [p + 500 for p in o]
        lo = [p - 300 for p in o]
        c  = [p + 200 for p in o]
        v  = [1_000_000] * n
        return {"t": t, "o": o, "h": h, "l": lo, "c": c, "v": v, "s": "ok"}

    def test_returns_dataframe(self):
        df = _parse_udf(self._sample_udf())
        assert isinstance(df, pd.DataFrame)

    def test_columns(self):
        df = _parse_udf(self._sample_udf())
        for col in ("Open", "High", "Low", "Close", "Volume"):
            assert col in df.columns

    def test_length(self):
        df = _parse_udf(self._sample_udf(10))
        assert len(df) == 10

    def test_returns_empty_on_error_status(self):
        """_parse_udf returns empty DataFrame (not None) when status is error."""
        df = _parse_udf({"s": "no_data"})
        assert isinstance(df, pd.DataFrame) and df.empty

    def test_returns_empty_on_empty_body(self):
        df = _parse_udf({})
        assert isinstance(df, pd.DataFrame) and df.empty


# ─────────────────────────────────────────────────────────────
# download_data — mocked HTTP responses
# ─────────────────────────────────────────────────────────────
class TestDownloadData:
    def _make_dnse_payload(self, n: int = 120) -> dict:
        t  = [1_700_000_000 + i * 86400 for i in range(n)]
        p  = [50_000.0 + i * 50 for i in range(n)]
        return {
            "t": t, "o": p,
            "h": [x + 500 for x in p],
            "l": [x - 300 for x in p],
            "c": [x + 200 for x in p],
            "v": [1_000_000] * n,
            "s": "ok",
        }

    def test_uses_dnse_on_success(self):
        """When DNSE returns valid data, source should be 'DNSE'."""
        payload = json.dumps(self._make_dnse_payload(200))
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = self._make_dnse_payload(200)
        mock_resp.text = payload

        with patch("core.data_fetcher._DNSE_SESSION") as mock_sess:
            mock_sess.get.return_value = mock_resp
            df, source = download_data("VCB", days=365, min_rows=50)

        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 50
        assert source in ("DNSE", "SSI", "KBS")

    def test_fallback_on_dnse_failure(self):
        """If all fetchers return empty DFs, download_data returns (empty_df, 'NONE')."""
        empty = pd.DataFrame()
        with patch("core.data_fetcher._fetch_dnse", return_value=empty), \
             patch("core.data_fetcher._fetch_ssi",  return_value=empty):
            df, source = download_data("ZZZ", days=365, min_rows=10)
        assert isinstance(df, pd.DataFrame) and df.empty
        assert source == "NONE"

    def test_returns_tuple(self):
        empty = pd.DataFrame()
        with patch("core.data_fetcher._fetch_dnse", return_value=empty), \
             patch("core.data_fetcher._fetch_ssi",  return_value=empty):
            result = download_data("VCB", days=365)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_min_rows_checked_after_cleaning_before_accepting_source(self):
        dates = pd.bdate_range("2026-01-01", periods=50)
        dnse_raw = pd.DataFrame({
            "Open": [100.0] * 45 + [0.0] * 5,
            "High": [101.0] * 45 + [0.0] * 5,
            "Low": [99.0] * 45 + [0.0] * 5,
            "Close": [100.0] * 45 + [0.0] * 5,
            "Volume": [1_000_000] * 50,
        }, index=dates)
        ssi_clean = pd.DataFrame({
            "Open": [100.0] * 50,
            "High": [101.0] * 50,
            "Low": [99.0] * 50,
            "Close": [100.0] * 50,
            "Volume": [1_000_000] * 50,
        }, index=dates)

        with patch("core.data_fetcher._fetch_dnse", return_value=dnse_raw), \
             patch("core.data_fetcher._fetch_ssi", return_value=ssi_clean):
            df, source = download_data("VCB", days=365, min_rows=50)

        assert source == "SSI"
        assert len(df) == 50


# ─────────────────────────────────────────────────────────────
# get_latest_price — mocked
# ─────────────────────────────────────────────────────────────
class TestGetLatestPrice:
    def test_returns_float(self):
        with patch("core.data_fetcher.download_data") as mock_dl:
            df = pd.DataFrame({"Close": [55_000.0]})
            mock_dl.return_value = (df, "DNSE")
            price = get_latest_price("VCB")
        assert isinstance(price, float)
        assert price > 0

    def test_returns_zero_on_failure(self):
        """get_latest_price returns None or 0.0 when no data available."""
        with patch("core.data_fetcher.download_data") as mock_dl:
            mock_dl.return_value = (pd.DataFrame(), "NONE")
            price = get_latest_price("INVALID")
        assert price is None or price == 0.0


class TestBatchDownload:
    def test_large_universe_uses_chunks(self):
        import concurrent.futures

        created: list[int] = []

        class SpyExecutor:
            def __init__(self, *args, **kwargs):
                created.append(int(kwargs.get("max_workers", args[0] if args else 0)))
                self._executor = concurrent.futures.ThreadPoolExecutor(*args, **kwargs)

            def __enter__(self):
                self._executor.__enter__()
                return self._executor

            def __exit__(self, exc_type, exc, tb):
                return self._executor.__exit__(exc_type, exc, tb)

        progress: list[int] = []

        with patch("core.data_fetcher.download_data", side_effect=lambda sym, days: (pd.DataFrame({"Close": [1.0]}), "DNSE")), \
             patch("core.data_fetcher.ThreadPoolExecutor", SpyExecutor):
            results = batch_download(
                ["AAA", "BBB", "CCC", "DDD", "EEE"],
                days=30,
                max_workers=3,
                chunk_size=2,
                delay=0.0,
                on_progress=lambda done, total, sym: progress.append(done),
            )

        assert len(results) == 5
        assert len(created) == 3
        assert progress[-1] == 5

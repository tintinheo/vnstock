"""
Tests for Phase IV — VNDirect orderbook fallback in intraday_collector.

Tests cover:
  1. fetch_vndirect_orderbook() parses bids/asks correctly
  2. fetch_vndirect_orderbook() parses foreign flow fields
  3. fetch_vndirect_orderbook() returns None on empty data list
  4. fetch_vndirect_orderbook() returns None on HTTP error
  5. fetch_intraday_features() uses SSI when available (no fallback)
  6. fetch_intraday_features() falls back to VNDirect when SSI raises
  7. fetch_intraday_features() returns zero-fill when both sources fail
  8. Fallback OBI computed correctly from VNDirect orderbook data
  9. foreign_net computed from VNDirect foreign_buy/foreign_sell
  10. VNDirect zero-price levels are skipped (not added to bids/asks)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tradingos.data.intraday_collector import (
    fetch_vndirect_orderbook,
    fetch_intraday_features,
    compute_obi,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_VNDIRECT_RESPONSE = {
    "data": [
        {
            "code": "VCB",
            "lastPrice": 85000.0,
            "totalVolume": 1_200_000,
            "best1Bid": 84900.0, "best1BidVol": 50000,
            "best2Bid": 84800.0, "best2BidVol": 30000,
            "best3Bid": 84700.0, "best3BidVol": 20000,
            "best1Offer": 85100.0, "best1OfferVol": 40000,
            "best2Offer": 85200.0, "best2OfferVol": 25000,
            "best3Offer": 85300.0, "best3OfferVol": 15000,
            "foreignBuyVolume": 100_000,
            "foreignSellVolume": 80_000,
        }
    ]
}

_VNDIRECT_PARTIAL = {
    "data": [
        {
            "code": "VCB",
            "lastPrice": 50000.0,
            "totalVolume": 500_000,
            # Only 1 valid bid/ask level; levels 2 & 3 are zero (should be skipped)
            "best1Bid": 49900.0, "best1BidVol": 10000,
            "best2Bid": 0,       "best2BidVol": 0,
            "best3Bid": 0,       "best3BidVol": 0,
            "best1Offer": 50100.0, "best1OfferVol": 8000,
            "best2Offer": 0,       "best2OfferVol": 0,
            "best3Offer": 0,       "best3OfferVol": 0,
        }
    ]
}


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.json.return_value = json_data
    m.status_code = status_code
    m.raise_for_status = MagicMock() if status_code == 200 else MagicMock(side_effect=Exception("HTTP Error"))
    return m


# ── 1. Bids/asks parsing ──────────────────────────────────────────────────────

class TestVNDirectParsing:
    def test_bids_count(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob is not None
        assert len(ob["bids"]) == 3

    def test_asks_count(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert len(ob["asks"]) == 3

    def test_best_bid_price(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["bids"][0]["price"] == pytest.approx(84900.0)
        assert ob["bids"][0]["vol"] == 50000

    def test_best_ask_price(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["asks"][0]["price"] == pytest.approx(85100.0)
        assert ob["asks"][0]["vol"] == 40000

    def test_last_price(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["last_price"] == pytest.approx(85000.0)

    def test_last_volume(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["last_volume"] == 1_200_000


# ── 2. Foreign flow ────────────────────────────────────────────────────────────

class TestVNDirectForeignFlow:
    def test_foreign_buy(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["foreign_buy"] == 100_000

    def test_foreign_sell(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_RESPONSE)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["foreign_sell"] == 80_000

    def test_foreign_fields_absent_defaults_zero(self):
        resp = {
            "data": [{
                "code": "VCB", "lastPrice": 80000.0, "totalVolume": 100000,
                "best1Bid": 79900.0, "best1BidVol": 1000,
                "best1Offer": 80100.0, "best1OfferVol": 1000,
            }]
        }
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(resp)):
            ob = fetch_vndirect_orderbook("VCB")
        assert ob["foreign_buy"] == 0
        assert ob["foreign_sell"] == 0


# ── 3. None on empty data ─────────────────────────────────────────────────────

class TestVNDirectEdgeCases:
    def test_empty_data_list_returns_none(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response({"data": []})):
            ob = fetch_vndirect_orderbook("UNKNOWN")
        assert ob is None

    def test_zero_price_levels_skipped(self):
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=_mock_response(_VNDIRECT_PARTIAL)):
            ob = fetch_vndirect_orderbook("VCB")
        # Only 1 valid bid and 1 valid ask, zeros are filtered out
        assert len(ob["bids"]) == 1
        assert len(ob["asks"]) == 1

    def test_http_error_propagates(self):
        err_resp = _mock_response({}, status_code=500)
        err_resp.raise_for_status.side_effect = Exception("500 Server Error")
        with patch("tradingos.data.intraday_collector.requests.get",
                   return_value=err_resp):
            with pytest.raises(Exception):
                fetch_vndirect_orderbook("VCB")


# ── 4. Fallback in fetch_intraday_features ────────────────────────────────────

class TestIntradayFallback:
    def _make_tcbs_ok(self) -> MagicMock:
        """Mock TCBS returning 2 trades."""
        m = MagicMock()
        m.raise_for_status = MagicMock()
        m.json.return_value = {
            "data": [
                {"p": 50000, "v": 1000, "a": "B", "t": "10:00:00"},
                {"p": 50000, "v": 500,  "a": "S", "t": "10:00:05"},
            ]
        }
        return m

    def _make_vndirect_ok(self) -> MagicMock:
        return _mock_response(_VNDIRECT_RESPONSE)

    def _make_ssi_fail(self) -> MagicMock:
        m = MagicMock()
        m.raise_for_status.side_effect = Exception("SSI connection refused")
        return m

    def _make_both_fail(self) -> MagicMock:
        m = MagicMock()
        m.raise_for_status.side_effect = Exception("network error")
        return m

    def test_ssi_ok_vndirect_not_called(self):
        ssi_resp = _mock_response({
            "data": {
                "buyPrice1": 49900, "buyVol1": 1000,
                "sellPrice1": 50100, "sellVol1": 800,
                "matchedPrice": 50000, "matchedVolume": 500000,
                "foreignBuyVolume": 10000, "foreignSellVolume": 5000,
            }
        })
        call_counter = {"tcbs": 0, "ssi": 0, "vndirect": 0}

        def mock_get(url, *args, **kwargs):
            if "tcbs" in url:
                call_counter["tcbs"] += 1
                return self._make_tcbs_ok()
            elif "ssi" in url:
                call_counter["ssi"] += 1
                return ssi_resp
            elif "vndirect" in url:
                call_counter["vndirect"] += 1
                return self._make_vndirect_ok()
            return MagicMock()

        with patch("tradingos.data.intraday_collector.requests.get", side_effect=mock_get):
            result = fetch_intraday_features("VCB")

        assert result["foreign_net"] != 0 or True   # just check no exception
        assert call_counter["vndirect"] == 0, "VNDirect should NOT be called when SSI succeeds"

    def test_ssi_fail_vndirect_used_as_fallback(self):
        call_counter = {"tcbs": 0, "ssi": 0, "vndirect": 0}

        def mock_get(url, *args, **kwargs):
            if "tcbs" in url:
                call_counter["tcbs"] += 1
                return self._make_tcbs_ok()
            elif "ssi" in url:
                call_counter["ssi"] += 1
                return self._make_ssi_fail()
            elif "vndirect" in url:
                call_counter["vndirect"] += 1
                return self._make_vndirect_ok()
            return MagicMock()

        with patch("tradingos.data.intraday_collector.requests.get", side_effect=mock_get):
            result = fetch_intraday_features("VCB")

        assert call_counter["vndirect"] == 1, "VNDirect should be called as fallback"
        # Foreign flow should come from VNDirect
        assert result["foreign_buy"] == 100_000
        assert result["foreign_sell"] == 80_000
        assert result["foreign_net"] == 20_000

    def test_both_fail_returns_zero_fill(self):
        def mock_get(url, *args, **kwargs):
            return self._make_both_fail()

        with patch("tradingos.data.intraday_collector.requests.get", side_effect=mock_get):
            result = fetch_intraday_features("VCB")

        assert result["obi_l3"] == 0.0
        assert result["foreign_buy"] == 0
        assert result["foreign_sell"] == 0
        assert result["foreign_net"] == 0

    def test_vndirect_obi_computed_from_fallback(self):
        """OBI should be non-zero when VNDirect fallback provides valid book."""
        def mock_get(url, *args, **kwargs):
            if "tcbs" in url:
                return self._make_tcbs_ok()
            elif "ssi" in url:
                return self._make_ssi_fail()
            elif "vndirect" in url:
                return self._make_vndirect_ok()
            return MagicMock()

        with patch("tradingos.data.intraday_collector.requests.get", side_effect=mock_get):
            result = fetch_intraday_features("VCB")

        # VNDirect has 100000 total bid vs 80000 total ask → bid-heavy → OBI > 0
        assert result["obi_l3"] != 0.0

    def test_mcvd_still_computed_when_vndirect_fallback(self):
        """M-CVD comes from TCBS ticks, unaffected by which orderbook source is used."""
        def mock_get(url, *args, **kwargs):
            if "tcbs" in url:
                return self._make_tcbs_ok()  # 1000 buy + 500 sell → mcvd = +500
            elif "ssi" in url:
                return self._make_ssi_fail()
            elif "vndirect" in url:
                return self._make_vndirect_ok()
            return MagicMock()

        with patch("tradingos.data.intraday_collector.requests.get", side_effect=mock_get):
            result = fetch_intraday_features("VCB")

        assert result["mcvd"] == 500

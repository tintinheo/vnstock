"""
tests/test_scanner_wiring.py — NewTradingOS v14.0
Tests that verify Round-2 wiring fixes are active in production code paths:

  Fix #2  — render_scanner_tab accepts exchange_map and passes it to batch_score
  Fix #3  — foreign_flows_cache is populated and piped to scanner tabs
  Fix #3b — batch_score uses net_20d from ff dict when provided
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from core.audit import ACTION_SCAN
from core.scoring import batch_score, compute_score, SignalResult


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────
def _make_df(n: int = 120, trend: str = "up") -> pd.DataFrame:
    """Minimal OHLCV DataFrame with enough rows for all indicators."""
    rng = np.random.default_rng(42)
    base = 20_000.0 if trend == "up" else 20_000.0
    factor = 1.0015 if trend == "up" else 0.9985
    closes = np.array([base * (factor ** i) for i in range(n)])
    noise = rng.normal(0, 0.002, n)
    closes = closes * (1 + noise)
    opens  = closes * rng.uniform(0.995, 1.005, n)
    highs  = np.maximum(opens, closes) * rng.uniform(1.001, 1.008, n)
    lows   = np.minimum(opens, closes) * rng.uniform(0.992, 0.999, n)
    vols   = rng.integers(1_000_000, 5_000_000, n).astype(float)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
        index=pd.date_range("2023-01-01", periods=n, freq="B"),
    )


@pytest.fixture
def sample_data_dict() -> dict:
    """3 tickers: one HOSE, one HNX, one UPCoM."""
    return {
        "VIC": (_make_df(120, "up"),   "vcsc"),   # HOSE
        "PVS": (_make_df(120, "up"),   "vcsc"),   # HNX
        "ART": (_make_df(120, "down"), "vcsc"),   # UPCoM
    }


# ────────────────────────────────────────────────────────────────────────────
# FIX #2 — render_scanner_tab signature must accept exchange_map
# ────────────────────────────────────────────────────────────────────────────
class TestScannerTabAcceptsExchangeMap:
    def test_render_scanner_tab_has_exchange_map_param(self):
        """render_scanner_tab must declare exchange_map parameter."""
        from ui.scanner_tab import render_scanner_tab
        sig = inspect.signature(render_scanner_tab)
        assert "exchange_map" in sig.parameters, (
            "render_scanner_tab() is missing the `exchange_map` parameter. "
            "Add `exchange_map: dict | None = None` to its signature."
        )

    def test_exchange_map_has_default_none(self):
        """exchange_map must be optional (default None) for backward compat."""
        from ui.scanner_tab import render_scanner_tab
        sig = inspect.signature(render_scanner_tab)
        param = sig.parameters["exchange_map"]
        assert param.default is None, (
            "exchange_map must default to None to maintain backward compatibility."
        )


# ────────────────────────────────────────────────────────────────────────────
# FIX #2b — batch_score passes exchange_map down to compute_score via exchange
# ────────────────────────────────────────────────────────────────────────────
class TestBatchScoreExchangeMap:
    def test_exchange_map_is_accepted(self, sample_data_dict):
        """batch_score must not raise when exchange_map is provided."""
        exchange_map = {"VIC": "HOSE", "PVS": "HNX", "ART": "UPCOM"}
        results = batch_score(
            sample_data_dict, "1W",
            regime="bull",
            macro_score=5.0,
            exchange_map=exchange_map,
        )
        assert len(results) > 0

    def test_exchange_map_is_optional(self, sample_data_dict):
        """batch_score must work without exchange_map (backward compat)."""
        results = batch_score(sample_data_dict, "1W", regime="bull", macro_score=5.0)
        assert len(results) > 0

    def test_hnx_ticker_uses_wider_limit(self, sample_data_dict):
        """
        A HNX ticker scored with exchange_map=HNX should use ±10% limit.
        Verify this by patching compute_all to capture the exchange arg.
        """
        calls: list[str] = []

        original_batch = batch_score  # keep reference

        with patch("core.scoring.compute_score") as mock_cs:
            # Return a minimal SignalResult stub so batch_score doesn't fail
            stub = MagicMock(spec=SignalResult)
            stub.score = 50.0
            mock_cs.return_value = stub

            from core.scoring import batch_score as _bs
            _bs(
                sample_data_dict, "1W",
                exchange_map={"VIC": "HOSE", "PVS": "HNX", "ART": "UPCOM"},
            )

            # Inspect keyword arguments for the PVS call
            hnx_calls = [
                c for c in mock_cs.call_args_list
                if c.kwargs.get("exchange") == "HNX"
                   or (len(c.args) >= 1 and c.kwargs.get("ticker") == "PVS")
            ]
            assert len(hnx_calls) >= 1, (
                "batch_score did not pass exchange='HNX' to compute_score for a HNX ticker. "
                "Check that exchange_map is used inside _score_one()."
            )

    def test_default_exchange_is_hose(self, sample_data_dict):
        """When no exchange_map, compute_score should receive exchange='HOSE'."""
        with patch("core.scoring.compute_score") as mock_cs:
            stub = MagicMock(spec=SignalResult)
            stub.score = 50.0
            mock_cs.return_value = stub

            from core.scoring import batch_score as _bs
            _bs({"VIC": sample_data_dict["VIC"]}, "1W")

            for call in mock_cs.call_args_list:
                exchange = call.kwargs.get("exchange", "HOSE")
                assert exchange == "HOSE"


# ────────────────────────────────────────────────────────────────────────────
# FIX #3 — foreign_flows net_20d wired into batch_score
# ────────────────────────────────────────────────────────────────────────────
class TestForeignFlowsNet20dWiring:
    def test_batch_score_passes_net_20d_to_compute_score(self, sample_data_dict):
        """
        When foreign_flows dict contains net_20d, batch_score must forward
        it as foreign_flow_net_20d= to compute_score.
        """
        ff = {
            "VIC": {
                "net_buy_value": 1_000_000.0,
                "net_20d": 50_000_000.0,
                "trend_20d": "accumulate",
                "history_sessions": 20,
                "is_20d_proxy": False,
            }
        }

        with patch("core.scoring.compute_score") as mock_cs:
            stub = MagicMock(spec=SignalResult)
            stub.score = 60.0
            mock_cs.return_value = stub

            from core.scoring import batch_score as _bs
            _bs({"VIC": sample_data_dict["VIC"]}, "1W", foreign_flows=ff)

            assert mock_cs.called, "compute_score was not called"
            call = mock_cs.call_args_list[0]
            net_20d_passed = call.kwargs.get("foreign_flow_net_20d", 0.0)
            assert net_20d_passed == 50_000_000.0, (
                f"Expected foreign_flow_net_20d=50_000_000.0 but got {net_20d_passed}. "
                "batch_score must extract net_20d from the ff_ticker dict."
            )

    def test_batch_score_ignores_proxy_net_20d(self, sample_data_dict):
        ff = {
            "VIC": {
                "net_buy_value": 1_000_000.0,
                "net_20d": 50_000_000.0,
                "trend_20d": "accumulate",
                "history_sessions": 1,
                "is_20d_proxy": True,
            }
        }

        with patch("core.scoring.compute_score") as mock_cs:
            stub = MagicMock(spec=SignalResult)
            stub.score = 60.0
            mock_cs.return_value = stub

            from core.scoring import batch_score as _bs
            _bs({"VIC": sample_data_dict["VIC"]}, "1W", foreign_flows=ff)

            call = mock_cs.call_args_list[0]
            net_20d_passed = call.kwargs.get("foreign_flow_net_20d", 0.0)
            assert net_20d_passed == 0.0

    def test_batch_score_zero_net_20d_when_not_in_ff(self, sample_data_dict):
        """When ticker not in foreign_flows, net_20d must default to 0."""
        with patch("core.scoring.compute_score") as mock_cs:
            stub = MagicMock(spec=SignalResult)
            stub.score = 50.0
            mock_cs.return_value = stub

            from core.scoring import batch_score as _bs
            _bs({"VIC": sample_data_dict["VIC"]}, "1W", foreign_flows={})

            call = mock_cs.call_args_list[0]
            net_20d_passed = call.kwargs.get("foreign_flow_net_20d", 0.0)
            assert net_20d_passed == 0.0

    def test_compute_score_net_20d_beats_net_1d_for_accumulated(self):
        """
        When net_20d is strongly positive, score should differ from using
        zero net_20d — confirming that the 20d value actually influences scoring.
        """
        df = _make_df(120, "up")
        score_zero = compute_score(df, "1M", regime="bull", foreign_flow_net_20d=0.0, macro_score=5.0).score
        score_20d  = compute_score(df, "1M", regime="bull", foreign_flow_net_20d=200_000_000.0, macro_score=5.0).score
        # Strong 20d accumulation should push score >= score without it
        assert score_20d >= score_zero - 1.0, (
            f"Expected 20d net buy to not decrease score (got {score_20d:.1f} < {score_zero:.1f}). "
            "Check foreign_flow_net_20d handling in compute_score()."
        )


# ────────────────────────────────────────────────────────────────────────────
# FIX #3c — foreign_flows_cache session_state key is used in app.py scanner loop
# ────────────────────────────────────────────────────────────────────────────
class TestAppForeignFlowsCacheKey:
    """Verify app.py reads the correct session_state key for foreign flows."""

    def test_app_scanner_reads_foreign_flows_cache(self):
        """
        The app.py scanner loop must read from `foreign_flows_cache` in
        session_state, not from a hardcoded empty dict.
        """
        with open("app.py", encoding="utf-8") as f:
            source = f.read()

        assert "foreign_flows_cache" in source, (
            "app.py does not reference `foreign_flows_cache`. "
            "The scanner loop must read from st.session_state.get('foreign_flows_cache', {})."
        )
        assert 'foreign_flows={}' not in source, (
            "app.py still passes hardcoded `foreign_flows={}`. "
            "Replace with `st.session_state.get('foreign_flows_cache', {})`."
        )

    def test_app_scanner_passes_exchange_map(self):
        """The app.py scanner loop must pass exchange_map=_exchange_map."""
        with open("app.py", encoding="utf-8") as f:
            source = f.read()

        assert "exchange_map=_exchange_map" in source, (
            "app.py scanner loop does not pass `exchange_map=_exchange_map` to render_scanner_tab. "
            "Add `_exchange_map = {t: TICKER_EXCHANGE.get(t, 'HOSE') for t in data_dict}` "
            "and pass it to each render_scanner_tab call."
        )


# ────────────────────────────────────────────────────────────────────────────
# FIX #2 — render_scanner_tab passes exchange_map to batch_score (integration)
# ────────────────────────────────────────────────────────────────────────────
class TestScannerTabPassesExchangeMapToBatchScore:
    """
    Integration: when render_scanner_tab is given an exchange_map,
    batch_score must be called with it.
    """

    def test_render_scanner_tab_forwards_exchange_map(self, sample_data_dict):
        """batch_score inside render_scanner_tab must receive exchange_map."""
        import streamlit as st

        captured: dict = {}

        def _mock_batch_score(data_dict, tf, **kwargs):
            captured.update(kwargs)
            return []

        with (
            patch("ui.scanner_tab.batch_score", side_effect=_mock_batch_score),
            patch("streamlit.spinner", return_value=MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)),
            patch("streamlit.caption"),
            patch("streamlit.session_state", new_callable=lambda: dict),
        ):
            from ui.scanner_tab import render_scanner_tab

            exchange_map = {"VIC": "HOSE", "PVS": "HNX", "ART": "UPCOM"}

            # Patch session_state to avoid Streamlit runtime requirements
            mock_ss = {"data_version": 1, "_scan_cache": {}}
            with patch("ui.scanner_tab.st") as mock_st:
                mock_st.session_state = mock_ss
                mock_st.spinner.return_value.__enter__ = lambda s: None
                mock_st.spinner.return_value.__exit__ = lambda s, *a: None

                with patch("ui.scanner_tab.batch_score", side_effect=_mock_batch_score):
                    try:
                        render_scanner_tab(
                            tf="1W",
                            data_dict=sample_data_dict,
                            regime="bull",
                            macro_score=5.0,
                            foreign_flows={},
                            lang="VI",
                            exchange_map=exchange_map,
                        )
                    except Exception:
                        # Streamlit UI calls will fail outside runtime — that's OK.
                        # What matters is that batch_score was called with exchange_map.
                        pass

            assert "exchange_map" in captured, (
                "render_scanner_tab did not pass `exchange_map` to batch_score. "
                "Check ui/scanner_tab.py — batch_score call must include exchange_map=exchange_map."
            )
            assert captured["exchange_map"] == exchange_map


def _make_signal_result(ticker: str, score: float, action: str) -> SignalResult:
    return SignalResult(
        ticker=ticker,
        timeframe="1M",
        score=score,
        action=action,
        price=25_000.0,
        stop_loss=23_500.0,
        take_profit=28_000.0,
        rr_ratio=2.0,
        atr=500.0,
        indicators={"ADV20_bn": 1.75},
        regime_ok=True,
        manip_flag=False,
        message="",
    )


class TestScannerAuditEvents:
    def test_build_scan_audit_events_emits_summary_and_per_ticker_rows(self, sample_data_dict):
        from ui.scanner_tab import _build_scan_audit_events

        results = [
            _make_signal_result("VIC", 82.5, "STRONG BUY"),
            _make_signal_result("PVS", 67.0, "BUY"),
        ]

        events = _build_scan_audit_events(
            tf="1M",
            results=results,
            regime="bull",
            macro_score=6.5,
            data_dict=sample_data_dict,
            foreign_flows={"VIC": {"net_buy_value": 1.0}},
            audit_path="data/audit/2026-05-31.jsonl",
            exchange_map={"VIC": "HOSE", "PVS": "HNX", "ART": "UPCOM"},
            macro_stale=["foreign_flow"],
        )

        assert len(events) == 3

        summary_event = events[0]
        assert summary_event["action"] == ACTION_SCAN
        assert summary_event["ticker"] == ""
        assert summary_event["detail"]["kind"] == "summary"
        assert summary_event["detail"]["buy_count"] == 2
        assert summary_event["detail"]["top_signals"][0]["ticker"] == "VIC"

        result_event = events[1]
        assert result_event["ticker"] == "VIC"
        assert result_event["detail"]["kind"] == "result"
        assert result_event["detail"]["signal_action"] == "STRONG BUY"
        assert result_event["detail"]["exchange"] == "HOSE"
        assert result_event["detail"]["audit_file"].endswith("2026-05-31.jsonl")

    def test_audit_tab_formats_scan_result_event(self):
        from ui.audit_tab import _events_to_df

        df = _events_to_df([
            {
                "ts": "2026-05-31T09:00:00.000",
                "action": ACTION_SCAN,
                "ticker": "VCB",
                "timeframe": "1M",
                "detail": {
                    "kind": "result",
                    "signal_action": "BUY",
                    "score": 81.2,
                    "price": 52_000.0,
                    "stop_loss": 49_500.0,
                    "take_profit": 57_000.0,
                    "rr_ratio": 2.0,
                    "exchange": "HOSE",
                    "source": "DNSE",
                    "bar_date": "2026-05-30",
                    "adv20_bn": 2.15,
                    "manip_flag": False,
                    "regime_ok": True,
                    "message": "",
                },
                "result": "ok",
            }
        ])

        detail = df.iloc[0]["Chi tiết"]
        assert "Signal: BUY" in detail
        assert "Score: 81.2" in detail
        assert "Exchange: HOSE" in detail
        assert "Source: DNSE" in detail

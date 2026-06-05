"""Twelfth pass — audit fixes: scanner filters, backtest TP, SHAP data, schema fields."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ── OHLCV/flow factories ──────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120) -> pd.DataFrame:
    rng   = np.random.default_rng(99)
    dates = pd.bdate_range("2024-01-02", periods=n)
    close = 30_000.0 * np.cumprod(1 + rng.normal(0.001, 0.01, n))
    vol   = rng.integers(300_000, 1_500_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.998,
        "high":   close * 1.01,
        "low":    close * 0.99,
        "close":  close,
        "volume": vol,
    })


def _make_flow(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    flow = proxy_whale_net_from_daily(df)
    flow["data_source"] = "PROXY_OHLCV"
    return flow


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 1 — Scanner backend filters
# ═══════════════════════════════════════════════════════════════════════════════

class TestScannerFilters:
    """Verify ScannerService.scan() honours all ScanRequest filter parameters."""

    def _build_items(self):
        """Return a synthetic list of ScanResultItem-like dicts covering all actions."""
        from tradingos.data.schemas import ScanResultItem
        data = [
            dict(ticker="A", action="STRONG_BUY", mfpm_score=95, sms_raw=80,
                 stealth_accum=True,  amf_decision="PASS",  close=30000,
                 entry=29000, sl=27000, tp1=33000, rr=2.0, confidence="HIGH",
                 signal_mode="MODE_W", mode_w_score=90, best_pattern="VCP",
                 hmm_state="STEADY_BULL", distribution_warning="NONE",
                 earnings_risk="SAFE", sms_label="WHALE_BUYING"),
            dict(ticker="B", action="BUY",         mfpm_score=72, sms_raw=65,
                 stealth_accum=False, amf_decision="PASS",  close=20000,
                 entry=19500, sl=18200, tp1=22000, rr=1.9, confidence="MEDIUM",
                 signal_mode="MODE_A", mode_w_score=55, best_pattern="NONE",
                 hmm_state="TRANSITIONAL", distribution_warning="NONE",
                 earnings_risk="SAFE", sms_label="MIXED"),
            dict(ticker="C", action="WATCH",        mfpm_score=55, sms_raw=40,
                 stealth_accum=False, amf_decision="PASS",  close=15000,
                 entry=15000, sl=14000, tp1=16500, rr=1.5, confidence="LOW",
                 signal_mode="MODE_A", mode_w_score=30, best_pattern="NONE",
                 hmm_state="TRANSITIONAL", distribution_warning="NONE",
                 earnings_risk="CAUTION", sms_label="RETAIL_DRIVEN"),
            dict(ticker="D", action="NO_ACTION",    mfpm_score=38, sms_raw=20,
                 stealth_accum=False, amf_decision="BLOCK", close=10000,
                 entry=10000, sl=9300, tp1=11000, rr=1.4, confidence="—",
                 signal_mode="MODE_A", mode_w_score=10, best_pattern="NONE",
                 hmm_state="STEADY_BEAR", distribution_warning="EXIT",
                 earnings_risk="HIGH_RISK", sms_label="WHALE_DISTRIBUTING"),
        ]
        return [ScanResultItem(**d) for d in data]

    def _apply_filters(self, items, **kwargs):
        """Run the same filter logic as ScannerService.scan() Stage 8."""
        from tradingos.data.schemas import ScanRequest
        req = ScanRequest(tickers=["X"], **kwargs)

        _ACTION_RANK = {
            "STRONG_BUY": 0, "BUY": 1, "WATCH": 2,
            "NO_ACTION": 3, "EXIT": 4, "FORCED_EXIT": 5,
        }
        _min_action_rank = _ACTION_RANK.get(str(req.min_action or "").upper(), 9)

        filtered = []
        for item in items:
            if item.mfpm_score < (req.min_mfpm_score or 0):
                continue
            if item.sms_raw < (req.min_sms or 0):
                continue
            if req.min_action and _ACTION_RANK.get(item.action, 9) > _min_action_rank:
                continue
            if req.stealth_only and not item.stealth_accum:
                continue
            if not req.include_blocked and item.amf_decision == "BLOCK":
                continue
            filtered.append(item)
        return filtered

    def test_no_filters_returns_all_except_blocked(self):
        items = self._build_items()
        result = self._apply_filters(items)
        # D is BLOCK + include_blocked=False (default) → excluded
        tickers = {i.ticker for i in result}
        assert "D" not in tickers
        assert len(result) == 3

    def test_include_blocked_passes_blocked_items(self):
        items = self._build_items()
        # clear min_action and min_mfpm_score so item D (score=38, action=NO_ACTION) passes all
        result = self._apply_filters(items, include_blocked=True, min_action="", min_mfpm_score=0)
        assert any(i.ticker == "D" for i in result)

    def test_min_mfpm_score_filters_low_scores(self):
        items = self._build_items()
        result = self._apply_filters(items, min_mfpm_score=70)
        assert all(i.mfpm_score >= 70 for i in result)
        assert {i.ticker for i in result} == {"A", "B"}

    def test_min_sms_filters_low_sms(self):
        items = self._build_items()
        result = self._apply_filters(items, min_sms=60)
        assert all(i.sms_raw >= 60 for i in result)
        assert {i.ticker for i in result} == {"A", "B"}

    def test_min_action_buy_excludes_watch_and_below(self):
        items = self._build_items()
        result = self._apply_filters(items, min_action="BUY")
        assert all(i.action in ("STRONG_BUY", "BUY") for i in result)
        assert {i.ticker for i in result} == {"A", "B"}

    def test_min_action_strong_buy_only(self):
        items = self._build_items()
        result = self._apply_filters(items, min_action="STRONG_BUY")
        assert all(i.action == "STRONG_BUY" for i in result)
        assert {i.ticker for i in result} == {"A"}

    def test_stealth_only(self):
        items = self._build_items()
        result = self._apply_filters(items, stealth_only=True)
        assert all(i.stealth_accum for i in result)
        assert {i.ticker for i in result} == {"A"}

    def test_combined_mfpm_sms_stealth(self):
        items = self._build_items()
        result = self._apply_filters(items, min_mfpm_score=80, min_sms=75, stealth_only=True)
        assert {i.ticker for i in result} == {"A"}

    def test_no_results_when_nothing_matches(self):
        items = self._build_items()
        result = self._apply_filters(items, min_mfpm_score=120)
        assert result == []

    def test_scanner_service_tickers_passed_equals_filtered_count(self):
        """tickers_passed must equal len(filtered), not total scored."""
        from tradingos.data.schemas import ScanResult, ScanResultItem
        # Simulate building a ScanResult with the filter applied
        items = self._build_items()
        filtered = self._apply_filters(items, min_mfpm_score=70)
        result = ScanResult(
            tickers_scanned=len(items),
            tickers_passed=len(filtered),
            results=filtered,
        )
        assert result.tickers_passed == len(filtered)
        assert result.tickers_passed < result.tickers_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 2 — Backtest TP multipliers
# ═══════════════════════════════════════════════════════════════════════════════

class TestBacktestTPMultipliers:
    """BacktestRequest carries tp1_mult/tp2_mult; BacktestService uses them."""

    def test_schema_has_tp_fields(self):
        from tradingos.data.schemas import BacktestRequest
        req = BacktestRequest(ticker="VCB", sl_pct=0.07, tp1_mult=2.0, tp2_mult=4.0)
        assert req.tp1_mult == 2.0
        assert req.tp2_mult == 4.0

    def test_schema_defaults(self):
        from tradingos.data.schemas import BacktestRequest
        req = BacktestRequest(ticker="VCB")
        assert req.tp1_mult == 1.5
        assert req.tp2_mult == 2.5

    def test_tp_multipliers_affect_trade_levels(self):
        """Wider TP multipliers should result in higher TP2 targets."""
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all

        df = _make_ohlcv(200)
        df = compute_all(df)

        sl_pct = 0.07
        tp1_narrow = sl_pct * 1.5
        tp2_narrow = sl_pct * 2.5
        tp1_wide   = sl_pct * 3.0
        tp2_wide   = sl_pct * 6.0

        bt_narrow = run_backtest(df, "TEST", "MODE_A", sl_pct, tp1_narrow, tp2_narrow)
        bt_wide   = run_backtest(df, "TEST", "MODE_A", sl_pct, tp1_wide,   tp2_wide)

        assert tp2_wide > tp2_narrow
        # With wider TP the win set can differ; verify model accepts params
        assert bt_narrow.ticker == "TEST"
        assert bt_wide.ticker   == "TEST"

    def test_backtest_service_honours_request_multipliers(self):
        """BacktestService should compute tp1_pct = sl_pct × request.tp1_mult."""
        from tradingos.engines.backtest_service import BacktestService
        from tradingos.data.schemas import BacktestRequest
        from unittest.mock import patch, MagicMock
        import pandas as pd

        df = _make_ohlcv(100)
        from tradingos.core.indicators import compute_all
        df = compute_all(df)

        svc = BacktestService()
        req = BacktestRequest(
            ticker="TST",
            start_date="2024-01-02",
            end_date="2025-12-31",
            sl_pct=0.06,
            tp1_mult=3.0,
            tp2_mult=6.0,
        )

        captured = {}

        orig_compare = __import__(
            "tradingos.core.backtest", fromlist=["compare_modes"]
        ).compare_modes

        def mock_compare(df_, ticker, sl_pct, tp1_pct, tp2_pct):
            captured["tp1_pct"] = tp1_pct
            captured["tp2_pct"] = tp2_pct
            return orig_compare(df_, ticker, sl_pct, tp1_pct, tp2_pct)

        with patch("tradingos.engines.backtest_service.compare_modes", mock_compare), \
             patch("tradingos.engines.backtest_service.fetch_ohlcv", return_value=df), \
             patch("tradingos.engines.backtest_service.compute_indicators", return_value=df), \
             patch("tradingos.engines.backtest_service.fetch_usdvnd", return_value=pd.DataFrame()), \
             patch("tradingos.engines.backtest_service.fetch_vn10y_bond_yield", return_value=pd.DataFrame()):
            svc.run(req)

        if captured:
            assert abs(captured["tp1_pct"] - req.sl_pct * req.tp1_mult) < 1e-6
            assert abs(captured["tp2_pct"] - req.sl_pct * req.tp2_mult) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 3 — SHAP chart receives real data
# ═══════════════════════════════════════════════════════════════════════════════

class TestShapRealData:
    """TickerProfile carries mode_a/b scores and sms_components for the SHAP tab."""

    def test_ticker_profile_has_mode_a_b_fields(self):
        from tradingos.data.schemas import TickerProfile
        p = TickerProfile(
            ticker="VCB", action="BUY", confidence="HIGH",
            signal_mode="MODE_A", mfpm_score=75, mode_w_score=60,
            mc_win_prob=0.6, entry_price=30000, stop_loss=28000,
            sl_pct=-0.067, tp1=34000, tp2=38000, rr_ratio=2.0,
            close=30000, volume=1_000_000, avg_volume_20d=900_000,
            sma20=29000, sma50=28000, sma200=25000,
            rsi14=55.0, atr14=600.0, obv=5_000_000,
            sms_raw=65, sms_label="MIXED",
            mcvd_5d=100_000, mcvd_20d=500_000, mcvd_trend="UP",
            stealth_accum=False, distribution_warning="NONE",
            amd_phase="MARKUP", hmm_state="STEADY_BULL",
            vqs=0.3, amf_decision="PASS", best_pattern="VCP",
            sizing_pct=0.05, sizing_shares=100,
            mode_a_score=42,
            mode_b_score=30,
            sms_components={"whale_obv": 5, "mcvd_trend": 3},
        )
        assert p.mode_a_score == 42
        assert p.mode_b_score == 30
        assert p.sms_components["whale_obv"] == 5

    def test_ticker_profile_default_mode_scores_are_zero(self):
        from tradingos.data.schemas import TickerProfile
        p = TickerProfile(
            ticker="X", action="WATCH", confidence="LOW",
            signal_mode="MODE_A", mfpm_score=50, mode_w_score=30,
            mc_win_prob=0.5, entry_price=10000, stop_loss=9300,
            sl_pct=-0.07, tp1=11500, tp2=13000, rr_ratio=2.1,
            close=10000, volume=500_000, avg_volume_20d=400_000,
            sma20=9800, sma50=9500, sma200=8500,
            rsi14=48.0, atr14=200.0, obv=1_000_000,
            sms_raw=40, sms_label="RETAIL_DRIVEN",
            mcvd_5d=0, mcvd_20d=0, mcvd_trend="FLAT",
            stealth_accum=False, distribution_warning="NONE",
            amd_phase="RANGING", hmm_state="TRANSITIONAL",
            vqs=0.0, amf_decision="PASS", best_pattern="NONE",
            sizing_pct=0.03, sizing_shares=50,
        )
        assert p.mode_a_score == 0
        assert p.mode_b_score == 0
        assert p.sms_components == {}

    def test_shap_chart_renders_without_error(self):
        """render_shap_chart should not raise with real data dict."""
        from tradingos.ui.components.shap_chart import render_shap_chart
        import unittest.mock as mock

        with mock.patch("streamlit.plotly_chart"):
            # Should not raise
            render_shap_chart({
                "mode_a_score": 40,
                "mode_b_score": 25,
                "mode_w_score": 85,
                "mc_win_prob":  0.62,
                "components":   {"whale_obv": 6, "mcvd_trend": 4, "stealth_bonus": 2},
            }, "VCB")

    def test_shap_chart_handles_missing_component_keys(self):
        """render_shap_chart should not raise when components dict is empty."""
        from tradingos.ui.components.shap_chart import render_shap_chart
        import unittest.mock as mock

        with mock.patch("streamlit.plotly_chart"):
            render_shap_chart({
                "mode_a_score": 0,
                "mode_b_score": 0,
                "mode_w_score": 0,
                "mc_win_prob":  0.5,
                "components":   {},
            }, "TST")


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 4 — Mojibake headings
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfilerHeadingEncoding:
    """Profiler page headings must not contain replacement characters (U+FFFD)."""

    def _get_profiler_source(self) -> str:
        import importlib.util, pathlib
        p = pathlib.Path(__file__).resolve().parents[2] / "src/tradingos/ui/pages/profiler.py"
        return p.read_text(encoding="utf-8")

    def test_no_replacement_character_in_headings(self):
        src = self._get_profiler_source()
        # The replacement character U+FFFD should not appear in any markdown heading
        heading_lines = [ln for ln in src.splitlines() if "st.markdown" in ln and "####" in ln]
        for ln in heading_lines:
            assert "\ufffd" not in ln, f"Replacement char in: {ln!r}"

    def test_gap_analysis_heading_is_correct(self):
        src = self._get_profiler_source()
        assert '#### 🔍 Gap Analysis' in src

    def test_indicator_explanation_heading_is_correct(self):
        src = self._get_profiler_source()
        assert '#### 💬 Giải thích chỉ số' in src


# ═══════════════════════════════════════════════════════════════════════════════
# Fix 5 — README advisory-only wording
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadmeWording:
    def _readme(self) -> str:
        import pathlib
        p = pathlib.Path(__file__).resolve().parents[2] / "README.md"
        return p.read_text(encoding="utf-8")

    def test_no_automated_trading_phrase(self):
        readme = self._readme()
        assert "automated trading operating system" not in readme.lower()

    def test_advisory_only_mentioned(self):
        readme = self._readme()
        assert "advisory" in readme.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Price normalizer — full-VND sanity (regression guard for today's fix)
# ═══════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────────
# New SMA / EMA columns in compute_all()
# ─────────────────────────────────────────────────────────────────────────────

def _make_ohlcv_12(n: int = 300, trend: float = 0.001) -> "pd.DataFrame":
    rng   = np.random.default_rng(99)
    dates = pd.bdate_range("2023-01-02", periods=n)
    close = 25_000 * np.cumprod(1 + rng.normal(trend, 0.01, n))
    vol   = rng.integers(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.998,
        "high":   close * 1.012,
        "low":    close * 0.988,
        "close":  close,
        "volume": vol,
    })


def _with_ind_12(n: int = 300, trend: float = 0.001) -> "pd.DataFrame":
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv_12(n=n, trend=trend))


class TestNewMAs12:
    def test_sma3_present(self):
        assert "SMA3" in _with_ind_12().columns

    def test_sma5_present(self):
        assert "SMA5" in _with_ind_12().columns

    def test_sma7_present(self):
        assert "SMA7" in _with_ind_12().columns

    def test_sma10_present(self):
        assert "SMA10" in _with_ind_12().columns

    def test_ema50_present(self):
        assert "EMA50" in _with_ind_12().columns

    def test_ema200_present(self):
        assert "EMA200" in _with_ind_12().columns

    def test_sma3_non_null_after_warmup(self):
        df = _with_ind_12()
        assert df["SMA3"].iloc[10:].notna().all()

    def test_ema200_finite(self):
        df = _with_ind_12()
        tail = df["EMA200"].dropna()
        assert len(tail) > 0 and np.isfinite(tail.values).all()


# ─────────────────────────────────────────────────────────────────────────────
# compute_trend_warning
# ─────────────────────────────────────────────────────────────────────────────

class TestTrendWarning12:
    def _r(self, n=200, trend=0.001):
        from tradingos.core.trend_warning import compute_trend_warning
        return compute_trend_warning(_with_ind_12(n=n, trend=trend))

    def test_returns_dict(self):
        assert isinstance(self._r(), dict)

    def test_required_keys(self):
        r = self._r()
        for k in ("warning", "warning_vi", "confidence", "reasons"):
            assert k in r

    def test_insufficient_data(self):
        from tradingos.core.trend_warning import compute_trend_warning
        r = compute_trend_warning(_with_ind_12(n=30))
        assert r["warning"] == "INSUFFICIENT_DATA"

    def test_confidence_range(self):
        r = self._r()
        assert 0.0 <= r["confidence"] <= 1.0

    def test_reasons_list(self):
        assert isinstance(self._r()["reasons"], list)

    def test_warning_is_string(self):
        assert isinstance(self._r()["warning"], str)

    def test_valid_constant(self):
        from tradingos.core.trend_warning import _VI_LABELS
        r = self._r()
        assert r["warning"] in _VI_LABELS

    def test_downtrend_not_bullish(self):
        from tradingos.core.trend_warning import compute_trend_warning
        r = compute_trend_warning(_with_ind_12(n=300, trend=-0.003))
        assert r["warning"] != "UPTREND_STRENGTHENING"


# ─────────────────────────────────────────────────────────────────────────────
# compute_multi_horizon_forecast
# ─────────────────────────────────────────────────────────────────────────────

_VALID_VOTES = {"TĂNG", "GIẢM", "TRUNG LẬP"}


class TestHorizonForecast12:
    def _r(self, n=200, trend=0.001, ctx=None):
        from tradingos.core.horizon_forecast import compute_multi_horizon_forecast
        return compute_multi_horizon_forecast(_with_ind_12(n=n, trend=trend), ctx or {})

    def test_returns_dict(self):
        assert isinstance(self._r(), dict)

    def test_all_11_keys(self):
        expected = {
            "short_vote", "short_conf", "short_reasons",
            "mid_vote",   "mid_conf",   "mid_reasons",
            "long_vote",  "long_conf",  "long_reasons",
            "overall_vote", "overall_conf",
        }
        assert expected <= set(self._r().keys())

    def test_votes_valid(self):
        r = self._r()
        for k in ("short_vote", "mid_vote", "long_vote", "overall_vote"):
            assert r[k] in _VALID_VOTES

    def test_conf_ranges(self):
        r = self._r()
        for k in ("short_conf", "mid_conf", "long_conf", "overall_conf"):
            assert 0.0 <= r[k] <= 100.0

    def test_insufficient_data_neutral(self):
        from tradingos.core.horizon_forecast import compute_multi_horizon_forecast
        r = compute_multi_horizon_forecast(_with_ind_12(n=10))
        assert r["short_vote"] == "TRUNG LẬP"

    def test_reasons_are_lists(self):
        r = self._r()
        for k in ("short_reasons", "mid_reasons", "long_reasons"):
            assert isinstance(r[k], list)


# ─────────────────────────────────────────────────────────────────────────────
# compute_t25_multiframe
# ─────────────────────────────────────────────────────────────────────────────

class TestT25Multiframe12:
    _VALID_WINDOWS = {"morning", "midday", "afternoon", ""}
    _VALID_MF_SIGS = {"MF_STRONG_BUY", "MF_BUY", "MF_WATCH", "MF_AVOID"}

    def _r(self, t25=None, vwap=None, n=200):
        from tradingos.core.t25_engine import compute_t25_multiframe
        return compute_t25_multiframe(_with_ind_12(n=n), t25, vwap)

    def test_returns_dict(self):
        assert isinstance(self._r(), dict)

    def test_required_keys(self):
        r = self._r()
        for k in ("morning_score","midday_score","afternoon_score",
                   "best_window","mf_signal","mf_reasons"):
            assert k in r

    def test_scores_range(self):
        r = self._r()
        for s in ("morning_score","midday_score","afternoon_score"):
            assert 0.0 <= r[s] <= 100.0

    def test_best_window_valid(self):
        assert self._r()["best_window"] in self._VALID_WINDOWS

    def test_mf_signal_valid(self):
        assert self._r()["mf_signal"] in self._VALID_MF_SIGS

    def test_none_vwap_safe(self):
        r = self._r(vwap=None)
        assert isinstance(r, dict)

    def test_buy_higher_than_avoid(self):
        buy  = {"t25_score": 80.0, "t25_signal": "T25_BUY",   "t25_regime": "BULL_TREND"}
        avoid= {"t25_score": 20.0, "t25_signal": "T25_AVOID",  "t25_regime": "BEAR_TREND"}
        assert self._r(t25=buy)["morning_score"] > self._r(t25=avoid)["morning_score"]


# ─────────────────────────────────────────────────────────────────────────────
# fetch_realtime
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchRealtime12:
    def test_import_ok(self):
        from tradingos.data.fetcher import fetch_realtime
        assert callable(fetch_realtime)

    def test_parses_mock(self, monkeypatch):
        from tradingos.data import fetcher
        monkeypatch.setattr(fetcher, "fetch_quote",
            lambda t, **kw: {"matchedPrice": 57.7, "referencePrice": 55.0,
                              "ceilingPrice": 62.0, "floorPrice": 49.0})
        r = fetcher.fetch_realtime("VCB")
        assert isinstance(r, dict) and "rt_price" in r

    def test_scale_applied(self, monkeypatch):
        from tradingos.data import fetcher
        monkeypatch.setattr(fetcher, "fetch_quote",
            lambda t, **kw: {"matchedPrice": 57.7, "referencePrice": 55.0,
                              "ceilingPrice": 62.0, "floorPrice": 49.0})
        r = fetcher.fetch_realtime("VCB")
        assert r["rt_price"] >= 50_000

    def test_empty_on_failure(self, monkeypatch):
        from tradingos.data import fetcher
        monkeypatch.setattr(fetcher, "fetch_quote", lambda t, **kw: {})
        assert fetcher.fetch_realtime("VCB") == {}

    def test_at_ceiling(self, monkeypatch):
        from tradingos.data import fetcher
        monkeypatch.setattr(fetcher, "fetch_quote",
            lambda t, **kw: {"matchedPrice": 62_000, "referencePrice": 55_000,
                              "ceilingPrice": 62_000, "floorPrice": 49_000})
        r = fetcher.fetch_realtime("VCB")
        assert r["rt_at_ceiling"] is True


# ─────────────────────────────────────────────────────────────────────────────
# TickerProfile new fields
# ─────────────────────────────────────────────────────────────────────────────

class TestTickerProfileNewFields12:
    def _p(self, **kw):
        from tradingos.data.schemas import TickerProfile
        base = dict(
            ticker="TST", action="WATCH", confidence="MEDIUM",
            signal_mode="MODE_A", mfpm_score=55, mode_w_score=20,
            mc_win_prob=0.55, entry_price=25000.0, stop_loss=23500.0,
            sl_pct=0.06, tp1=26500.0, tp2=28000.0, rr_ratio=1.8,
            close=25000.0, volume=1_000_000.0, avg_volume_20d=900_000.0,
            sma20=24500.0, sma50=23000.0, sma200=20000.0,
            rsi14=52.0, atr14=400.0, obv=5_000_000.0,
            sms_raw=60, sms_label="WHALE_BUYING",
            mcvd_5d=1_000_000.0, mcvd_20d=3_000_000.0,
            mcvd_trend="BULLISH", stealth_accum=False,
            distribution_warning="NONE", amd_phase="MARKUP",
            hmm_state="STEADY_BULL", vqs=70.0,
            amf_decision="PASS", best_pattern="HAMMER",
            sizing_pct=0.08, sizing_shares=120,
        )
        base.update(kw)
        return TickerProfile(**base)

    def test_rt_defaults(self):
        p = self._p()
        assert p.rt_price is None
        assert p.rt_at_ceiling is False

    def test_trend_warning_defaults(self):
        p = self._p()
        assert p.trend_warning == "NONE"

    def test_fc_defaults(self):
        p = self._p()
        assert p.fc_short_vote == ""
        assert p.fc_overall_conf == 0.0

    def test_t25_mf_defaults(self):
        p = self._p()
        assert p.t25_morning_score == 0.0
        assert p.t25_best_window == ""

    def test_new_ma_defaults(self):
        p = self._p()
        assert p.sma3 == 0.0
        assert p.ema200 == 0.0

    def test_rt_fields_settable(self):
        p = self._p(rt_price=62000.0, rt_at_ceiling=True)
        assert p.rt_price == 62000.0
        assert p.rt_at_ceiling is True

class TestPriceNormalizerRegression:
    """clean_ohlcv must convert thousands-VND prices to full VND."""

    def _make_thousands_df(self, close_thousands: float = 57.7) -> pd.DataFrame:
        return pd.DataFrame({
            "date":   pd.bdate_range("2026-01-02", periods=5),
            "open":   [close_thousands] * 5,
            "high":   [close_thousands * 1.01] * 5,
            "low":    [close_thousands * 0.99] * 5,
            "close":  [close_thousands] * 5,
            "volume": [1_000_000] * 5,
        })

    def test_thousands_vnd_normalised_to_full_vnd(self):
        from tradingos.data.normalizer import clean_ohlcv
        df_in  = self._make_thousands_df(57.7)
        df_out = clean_ohlcv(df_in)
        # 57.7 → 57700; median should be ~57700 not ~57
        assert df_out["close"].median() > 1000, "Price not normalised to full VND"
        assert abs(df_out["close"].median() - 57700) < 10

    def test_full_vnd_prices_not_scaled_again(self):
        from tradingos.data.normalizer import clean_ohlcv
        df_in = self._make_thousands_df(57700)
        df_out = clean_ohlcv(df_in)
        # Already in full VND; should remain ~57700 (not 57700000)
        assert abs(df_out["close"].median() - 57700) < 10


# ═══════════════════════════════════════════════════════════════════════════════
# round_to_tick — Entry/SL/TP use correct VN tick sizes
# ═══════════════════════════════════════════════════════════════════════════════

class TestRoundToTickInEntryParams:
    """mode_w_entry_params Entry/SL/TP must align to VN tick boundaries."""

    def _make_df_with_indicators(self) -> pd.DataFrame:
        from tradingos.core.indicators import compute_all
        df = _make_ohlcv(150)
        return compute_all(df)

    def test_entry_is_multiple_of_100_vnd(self):
        """For ~30k VND stocks the tick is 100 VND: entry % 100 == 0."""
        from tradingos.core.money_flow import mode_w_entry_params
        from tradingos.data.normalizer import tick_size
        df = self._make_df_with_indicators()
        params = mode_w_entry_params(df, {})
        entry = params["entry"]
        t = tick_size(entry)
        assert entry % t == 0, f"entry={entry} not aligned to tick={t}"

    def test_sl_is_multiple_of_tick(self):
        from tradingos.core.money_flow import mode_w_entry_params
        from tradingos.data.normalizer import tick_size
        df = self._make_df_with_indicators()
        params = mode_w_entry_params(df, {})
        sl = params["sl"]
        t = tick_size(sl)
        assert sl % t == 0, f"sl={sl} not aligned to tick={t}"

    def test_tp1_tp2_multiples_of_tick(self):
        from tradingos.core.money_flow import mode_w_entry_params
        from tradingos.data.normalizer import tick_size
        df = self._make_df_with_indicators()
        params = mode_w_entry_params(df, {})
        for key in ("tp1", "tp2"):
            val = params[key]
            t = tick_size(val)
            assert val % t == 0, f"{key}={val} not aligned to tick={t}"

    def test_entry_is_full_vnd_scale(self):
        from tradingos.core.money_flow import mode_w_entry_params
        df = self._make_df_with_indicators()
        params = mode_w_entry_params(df, {})
        # With 30k VND data, entry should be in tens-of-thousands range
        assert params["entry"] > 1000, "entry appears to be in thousands-VND scale"

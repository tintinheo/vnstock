from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest


class _Macro:
    def __init__(self, regime: str):
        self.macro_regime = regime


class _EarningsRisk:
    def __init__(self, gate_delta: float, risk: str = "SAFE"):
        self.gate_delta = gate_delta
        self.rollover_risk = type("Risk", (), {"value": risk})()


class _Fundamental:
    def __init__(self, score: float | None):
        self.fundamental_score = score


def _make_ohlcv(n: int = 120, trend: float = 0.001, start_date: str = "2024-01-02") -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(start_date, periods=n)
    close = 50_000.0 * np.cumprod(1 + rng.normal(trend, 0.01, n))
    volume = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date": dates,
        "open": close * 0.995,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "volume": volume,
    })


def _mfpm_inputs():
    from tradingos.core.indicators import compute_all

    df = compute_all(_make_ohlcv())
    sms_result = {
        "sms": 72,
        "sms_label": "WHALE_BUYING",
        "components": {"cvd_today": 8},
        "mcvd_detail": {
            "mcvd_trend": "UP",
            "consistency": 0.8,
            "mcvd_vs_price": "CONFIRM",
            "data_source": "PARTIAL_PROXY",
        },
        "stealth_detail": {"detected": True, "confidence": "HIGH"},
        "distribution_warning": "NONE",
    }
    amf_result = {"decision": "PASS", "flags": []}
    pattern_result = {"pattern_bonus": 10, "pivot": float(df["high"].tail(20).iloc[:-1].max()) * 0.99}
    return df, sms_result, amf_result, pattern_result


class TestOverlayMFPM:
    def test_macro_and_earnings_raise_gate(self):
        from tradingos.core.mfpm import compute_mfpm

        df, sms_result, amf_result, pattern_result = _mfpm_inputs()
        base = compute_mfpm(df, sms_result, amf_result, pattern_result, hmm_state="STEADY_BULL", amd_phase="ACCUMULATION")
        gated = compute_mfpm(
            df,
            sms_result,
            amf_result,
            pattern_result,
            hmm_state="STEADY_BULL",
            amd_phase="ACCUMULATION",
            macro_result=_Macro("RESTRICTIVE"),
            earnings_risk=_EarningsRisk(10.0, "HIGH_RISK"),
        )
        assert gated["gate_delta"] >= 20
        assert gated["action"] in ("WATCH", "NO_ACTION")
        assert base["mfpm_score"] == gated["mfpm_score"] or gated["mfpm_score"] <= base["mfpm_score"] + 12

    def test_strong_fundamentals_add_bonus(self):
        from tradingos.core.mfpm import compute_mfpm

        df, sms_result, amf_result, pattern_result = _mfpm_inputs()
        weak = compute_mfpm(df, sms_result, amf_result, pattern_result, fundamental_snapshot=_Fundamental(30.0))
        strong = compute_mfpm(df, sms_result, amf_result, pattern_result, fundamental_snapshot=_Fundamental(80.0))
        assert strong["fundamental_bonus"] > weak["fundamental_bonus"]
        assert strong["blended_canslim_score"] >= weak["blended_canslim_score"]


class TestBacktestOverlays:
    def test_macro_regime_column_blocks_entries(self):
        from tradingos.core.backtest import _apply_overlay_signal_filters

        df = _make_ohlcv(20)
        df["_signal"] = 1
        df["macro_regime"] = "RESTRICTIVE"
        filtered = _apply_overlay_signal_filters(df, "VCB")
        assert int(filtered["_signal"].sum()) == 0

    def test_high_risk_earnings_block_entries(self, monkeypatch):
        from tradingos.core.backtest import _apply_overlay_signal_filters

        df = _make_ohlcv(20)
        df["_signal"] = 1
        monkeypatch.setattr("tradingos.core.backtest.fetch_earnings_calendar", lambda ticker, lookforward_days=365: pd.DataFrame())
        monkeypatch.setattr(
            "tradingos.core.backtest.fetch_financial_statements",
            lambda ticker, quarters=8: {},
        )
        monkeypatch.setattr(
            "tradingos.core.backtest.compute_earnings_risk",
            lambda ticker, current_date=None, earnings_df=None: _EarningsRisk(10.0, "HIGH_RISK"),
        )
        filtered = _apply_overlay_signal_filters(df, "VCB")
        assert int(filtered["_signal"].sum()) == 0

    def test_low_fundamental_score_blocks_entries(self, monkeypatch):
        from tradingos.core.backtest import _apply_overlay_signal_filters

        df = _make_ohlcv(20)
        df["_signal"] = 1
        monkeypatch.setattr("tradingos.core.backtest.fetch_earnings_calendar", lambda ticker, lookforward_days=365: pd.DataFrame())
        monkeypatch.setattr("tradingos.core.backtest.fetch_financial_statements", lambda ticker, quarters=8: {})
        monkeypatch.setattr(
            "tradingos.core.backtest.compute_fundamental_snapshot",
            lambda ticker, current_date=None, statements=None: _Fundamental(20.0),
        )
        filtered = _apply_overlay_signal_filters(df, "VCB")
        assert int(filtered["_signal"].sum()) == 0


class TestSectorIndexArchitecture:
    def test_sector_service_builds_one_row_per_date(self):
        from tradingos.engines.money_flow_service import MoneyFlowService

        svc = MoneyFlowService()
        df1 = _make_ohlcv(30)
        df2 = _make_ohlcv(30, trend=0.002)
        sector_df = svc._build_sector_index([df1, df2])
        assert len(sector_df) == len(df1)
        assert sector_df["date"].is_unique
        assert "OBV" in sector_df.columns

    def test_sector_service_no_longer_concats_duplicate_dates(self, monkeypatch):
        from tradingos.engines.money_flow_service import MoneyFlowService

        svc = MoneyFlowService()
        monkeypatch.setattr(
            "tradingos.engines.money_flow_service.fetch_ohlcv",
            lambda ticker, days=60: _make_ohlcv(30, trend=0.002 if ticker.endswith("1") else 0.001),
        )
        result = svc.get_sector_flows(["BĐS"])
        assert "rotation_phase" in result
        assert isinstance(result["rankings"], list)

    def test_sector_service_skips_empty_tickers_until_three_valid_frames(self, monkeypatch):
        from tradingos.engines import money_flow_service as mfs

        svc = mfs.MoneyFlowService()
        monkeypatch.setattr(mfs, "_load_sector_groups", lambda: {"BĐS": ["BAD1", "BAD2", "GOOD1", "GOOD2"]})
        monkeypatch.setattr(
            mfs,
            "fetch_ohlcv",
            lambda ticker, days=60: pd.DataFrame() if ticker.startswith("BAD") else _make_ohlcv(30, trend=0.002),
        )

        result = svc.get_sector_flows(["BĐS"])
        assert result["rankings"]
        assert result["rankings"][0]["sector"] == "BĐS"


class TestFetchOhlcvNormalization:
    def test_fetch_ohlcv_normalizes_cached_trade_date_column(self, monkeypatch):
        from tradingos.data import fetcher

        cached = _make_ohlcv(60).rename(columns={"date": "trade_date"})
        cached["ticker"] = "VCB"
        cached["fetched_at"] = pd.Timestamp("2026-04-02")

        monkeypatch.setattr(fetcher.cache, "get_ohlcv", lambda ticker, start, end: cached)

        df = fetcher.fetch_ohlcv("VCB", days=60)
        assert "date" in df.columns
        assert "trade_date" not in df.columns
        assert len(df) == 60
        assert df["date"].is_monotonic_increasing


class TestExchangeAwareFetch:
    def test_fallback_universe_is_exchange_aware(self):
        from tradingos.data.fetcher import _fallback_universe

        hose = _fallback_universe("HOSE")
        hnx = _fallback_universe("HNX")
        upcom = _fallback_universe("UPCOM")
        assert hose != hnx
        assert hnx != upcom

    def test_fetch_universe_falls_back_without_vnstock(self, monkeypatch):
        from tradingos.data.fetcher import _fallback_universe, fetch_universe

        monkeypatch.setattr("tradingos.data.fetcher._get", lambda *a, **kw: {})
        result = fetch_universe("HOSE")
        expected_fallback = _fallback_universe("HOSE")
        assert result == expected_fallback

    def test_fetch_universe_uses_vnxall_group(self, monkeypatch):
        """fetch_universe must call VNXALL (not HOSE) and parse stockSymbol field."""
        from tradingos.data.fetcher import fetch_universe

        called_urls = []

        def fake_get(url, *args, **kwargs):
            called_urls.append(url)
            if "VNXALL" in url:
                return {
                    "data": [
                        {"stockSymbol": "VCB", "exchange": "hose", "stockType": "s"},
                        {"stockSymbol": "ACB", "exchange": "hose", "stockType": "s"},
                        {"stockSymbol": "BVS", "exchange": "hnx",  "stockType": "s"},
                        # warrant — should be excluded if stockType filtering added
                        {"stockSymbol": "ACB01", "exchange": "hose", "stockType": "cw"},
                    ]
                }
            return {}

        monkeypatch.setattr("tradingos.data.fetcher._get", fake_get)
        result = fetch_universe("HOSE")
        # Should have called VNXALL, not HOSE
        assert any("VNXALL" in u for u in called_urls)
        assert "VCB" in result
        assert "ACB" in result
        # Warrants (CW) should be excluded
        assert "ACB01" not in result

    def test_fetch_universe_hnx_filters_by_exchange(self, monkeypatch):
        """fetch_universe('HNX') must only return HNX-listed stocks."""
        from tradingos.data.fetcher import fetch_universe

        def fake_get(url, *args, **kwargs):
            if "VNXALL" in url:
                return {
                    "data": [
                        {"stockSymbol": "VCB", "exchange": "hose", "stockType": "s"},
                        {"stockSymbol": "BVS", "exchange": "hnx",  "stockType": "s"},
                        {"stockSymbol": "SHS", "exchange": "hnx",  "stockType": "s"},
                    ]
                }
            return {}

        monkeypatch.setattr("tradingos.data.fetcher._get", fake_get)
        result = fetch_universe("HNX")
        assert "BVS" in result
        assert "SHS" in result
        # HOSE stock must not appear in HNX universe
        assert "VCB" not in result

    def test_fetch_universe_all_combines_vnxall_and_upcom(self, monkeypatch):
        """fetch_universe('ALL') must include both VNXALL and HNXUpcomIndex stocks."""
        from tradingos.data.fetcher import fetch_universe

        def fake_get(url, *args, **kwargs):
            if "VNXALL" in url:
                return {"data": [
                    {"stockSymbol": "VCB", "exchange": "hose", "stockType": "s"},
                    {"stockSymbol": "BVS", "exchange": "hnx",  "stockType": "s"},
                ]}
            if "HNXUpcomIndex" in url:
                return {"data": [
                    {"stockSymbol": "ACV", "exchange": "upcom", "stockType": "s"},
                ]}
            return {}

        monkeypatch.setattr("tradingos.data.fetcher._get", fake_get)
        result = fetch_universe("ALL")
        assert "VCB" in result
        assert "BVS" in result
        assert "ACV" in result

    def test_fetch_quote_tries_requested_exchange_first(self, monkeypatch):
        from tradingos.data.fetcher import fetch_quote

        calls = []

        def fake_get(url, params=None, timeout=10, retries=1):
            board = params["boardId"]
            calls.append(board)
            if board == "HNX":
                return {"data": {"symbol": "SHS", "lastPrice": 10.0}}
            return {}

        monkeypatch.setattr("tradingos.data.fetcher._get", fake_get)
        quote = fetch_quote("SHS", exchange="HNX")
        assert calls[0] == "HNX"
        assert quote.get("exchange") == "HNX"

    def test_fetch_universe_falls_back_without_vnstock(self, monkeypatch):
        from tradingos.data.fetcher import fetch_universe

        monkeypatch.setattr("tradingos.data.fetcher._get", lambda *args, **kwargs: {})

        tickers = fetch_universe("HNX")
        assert tickers
        assert "SHS" in tickers

    def test_profiler_no_longer_hardcodes_hose_exchange(self):
        from tradingos.engines import profiler_service

        src = inspect.getsource(profiler_service.ProfilerService.run)
        assert 'exchange="HOSE"' not in src


class TestAsOfFundamentals:
    def test_future_publication_rows_filtered_out(self):
        from tradingos.core.fundamental import compute_fundamental_snapshot

        statements = {
            "income": pd.DataFrame([
                {"period": "2024Q1", "publication_date": pd.Timestamp("2024-04-30"), "revenue": 100.0, "net_income": 10.0, "eps": 100.0},
                {"period": "2024Q2", "publication_date": pd.Timestamp("2024-08-30"), "revenue": 110.0, "net_income": 12.0, "eps": 120.0},
                {"period": "2024Q3", "publication_date": pd.Timestamp("2026-12-31"), "revenue": 130.0, "net_income": 16.0, "eps": 160.0},
            ]),
            "balance": pd.DataFrame(),
            "cashflow": pd.DataFrame(),
        }
        snap = compute_fundamental_snapshot("VCB", current_date=date(2025, 1, 1), statements=statements)
        assert snap.quarters_available == 2
        assert snap.fiscal_quarter == "2024Q2"


class TestMoneyFlowProxyOutput:
    def test_sms_returns_fol_pct(self):
        from tradingos.core.indicators import compute_all
        from tradingos.core.money_flow import compute_smart_money_score, proxy_whale_net_from_daily

        df = compute_all(_make_ohlcv())
        flow = proxy_whale_net_from_daily(df)
        flow["fol_net"] = 100_000
        result = compute_smart_money_score("VCB", df, flow)
        assert "fol_pct" in result
        assert result["fol_pct"] >= 0


# ═══════════════════════════════════════════════════════════════════════════════
# Regression tests for bug-fixes (LỖI #1..#9 documented in analysis)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapWinProbFix:
    """LỖI #8 — bootstrap_win_prob denominator fix (wins/n → wins/(wins+losses))."""

    def test_win_prob_in_valid_range(self):
        from tradingos.core.sizing import bootstrap_win_prob

        df = _make_ohlcv(200, trend=0.001)
        p = bootstrap_win_prob(df, sl_pct=0.06, tp_pct=0.08, n=400)
        assert 0.0 <= p <= 1.0

    def test_win_prob_trending_up_higher_than_trending_down(self):
        """Uptrend should produce higher win probability than downtrend."""
        from tradingos.core.sizing import bootstrap_win_prob

        up_df   = _make_ohlcv(200, trend=+0.005)
        down_df = _make_ohlcv(200, trend=-0.005)
        p_up   = bootstrap_win_prob(up_df,   sl_pct=0.06, tp_pct=0.10, n=600)
        p_down = bootstrap_win_prob(down_df, sl_pct=0.06, tp_pct=0.10, n=600)
        assert p_up > p_down, f"Expected p_up({p_up}) > p_down({p_down})"

    def test_win_prob_returns_half_for_short_series(self):
        from tradingos.core.sizing import bootstrap_win_prob

        df = _make_ohlcv(10)   # < 20 bars
        p = bootstrap_win_prob(df, sl_pct=0.05, tp_pct=0.10)
        assert p == 0.5

    def test_win_prob_returns_half_when_no_conclusive_paths(self):
        """With unreachable TP (100x price) and SL (100x loss), no path concludes."""
        from tradingos.core.sizing import bootstrap_win_prob

        df = _make_ohlcv(200, trend=0.0)
        p = bootstrap_win_prob(df, sl_pct=10.0, tp_pct=10.0, n=200)
        assert p == 0.5


class TestVnTimezone:
    """LỖI #7 — _session_phase / _is_atc_time must use Vietnam UTC+7."""

    def test_vn_now_is_timezone_aware(self):
        from tradingos.utils.dates import vn_now

        dt = vn_now()
        assert dt.tzinfo is not None

    def test_vn_now_offset_is_utcplus7(self):
        from datetime import timedelta
        from tradingos.utils.dates import vn_now

        dt = vn_now()
        offset = dt.utcoffset()
        assert offset == timedelta(hours=7)

    def test_vn_session_phase_returns_known_phase(self):
        from tradingos.utils.dates import vn_session_phase

        phase = vn_session_phase()
        valid = {"PRE_MARKET", "PRE_ATO", "ATO", "MORNING", "LUNCH",
                 "AFTERNOON", "NEAR_ATC", "ATC", "CLOSED"}
        assert phase in valid

    def test_is_atc_time_returns_bool(self):
        from tradingos.utils.dates import vn_is_atc_time

        result = vn_is_atc_time()
        assert isinstance(result, bool)

    def test_t25_session_phase_uses_vn_time(self):
        """t25_engine._session_phase must return a valid phase (not crash)."""
        from tradingos.core.t25_engine import _session_phase

        phase = _session_phase()
        valid = {"PRE_OPEN", "ATO", "CONTINUOUS", "NEAR_CLOSE", "ATC", "CLOSED"}
        assert phase in valid

    def test_execution_advisory_uses_vn_session_phase(self):
        """execution_advisory._session_phase must now delegate to vn_session_phase."""
        import inspect
        from tradingos.core import execution_advisory

        src = inspect.getsource(execution_advisory._session_phase)
        assert "vn_session_phase" in src


class TestSbvOmoFix:
    """LỖI #3 — fetch_sbv_omo_net now returns 0.0 (not None) for net_7d."""

    def test_sbv_omo_net_returns_float_not_none(self):
        from tradingos.data.fetcher import fetch_sbv_omo_net

        result = fetch_sbv_omo_net()
        assert result["net_7d"] is not None
        assert isinstance(result["net_7d"], float)

    def test_sbv_omo_net_zero_feeds_macro_as_neutral_source(self):
        """When net_7d=0.0, macro engine counts it as a source (improves confidence)."""
        from tradingos.core.macro import compute_macro_regime

        result = compute_macro_regime(sbv_net_injection_7d=0.0, sbv_avg_vol_ref=10_000.0)
        # OMO component should be included → n_sources updated
        assert any(ind.name == "SBV_OMO" for ind in result.indicators)


class TestVn10yBondYield:
    """LỖI #2 — fetch_vn10y_bond_yield no longer always returns empty."""

    def test_vn10y_returns_dataframe_with_correct_columns(self, monkeypatch, tmp_path):
        """First call (no cache) should return seeded historical data."""
        import tradingos.data.fetcher as fetcher

        # Point cache file to tmp dir so test doesn't touch real files
        monkeypatch.setattr(fetcher, "_VN10Y_CACHE_FILE", tmp_path / "vn10y.csv")
        monkeypatch.setattr(fetcher, "_get", lambda *a, **kw: {})  # HNX API offline

        df = fetcher.fetch_vn10y_bond_yield(days=30)
        assert not df.empty
        assert "date" in df.columns
        assert "yield" in df.columns

    def test_vn10y_yields_are_plausible_range(self, monkeypatch, tmp_path):
        import tradingos.data.fetcher as fetcher

        monkeypatch.setattr(fetcher, "_VN10Y_CACHE_FILE", tmp_path / "vn10y.csv")
        monkeypatch.setattr(fetcher, "_get", lambda *a, **kw: {})

        df = fetcher.fetch_vn10y_bond_yield(days=60)
        for val in df["yield"]:
            assert 0.5 <= val <= 20.0, f"Implausible yield value: {val}"

    def test_vn10y_cache_persists_across_calls(self, monkeypatch, tmp_path):
        import tradingos.data.fetcher as fetcher

        cache_file = tmp_path / "vn10y.csv"
        monkeypatch.setattr(fetcher, "_VN10Y_CACHE_FILE", cache_file)
        monkeypatch.setattr(fetcher, "_get", lambda *a, **kw: {})

        fetcher.fetch_vn10y_bond_yield(days=30)
        assert cache_file.exists()

    def test_vn10y_feeds_macro_bond_component(self, monkeypatch, tmp_path):
        """With seeded bond data, macro engine should include VN10Y indicator."""
        import tradingos.data.fetcher as fetcher
        from tradingos.core.macro import compute_macro_regime

        monkeypatch.setattr(fetcher, "_VN10Y_CACHE_FILE", tmp_path / "vn10y.csv")
        monkeypatch.setattr(fetcher, "_get", lambda *a, **kw: {})

        bond_df = fetcher.fetch_vn10y_bond_yield(days=30)
        result = compute_macro_regime(bond_yield_df=bond_df)
        assert any(ind.name == "VN10Y_YIELD" for ind in result.indicators)


class TestUsdVndCache:
    """LỖI #6 — fetch_usdvnd builds rolling cache to enable multi-day time series."""

    def test_fetch_usdvnd_returns_dataframe(self, monkeypatch, tmp_path):
        import tradingos.data.fetcher as fetcher

        monkeypatch.setattr(fetcher, "_USDVND_CACHE_FILE", tmp_path / "usdvnd.csv")
        monkeypatch.setattr(fetcher, "_get", lambda *a, **kw: {})

        df = fetcher.fetch_usdvnd(days=10)
        assert isinstance(df, pd.DataFrame)
        assert "date" in df.columns
        assert "close" in df.columns

    def test_fetch_usdvnd_appends_new_rate_to_cache(self, monkeypatch, tmp_path):
        import tradingos.data.fetcher as fetcher
        from datetime import date

        cache_file = tmp_path / "usdvnd.csv"
        monkeypatch.setattr(fetcher, "_USDVND_CACHE_FILE", cache_file)

        # Simulate VCB returning a valid sell rate
        def fake_get(url, *args, **kwargs):
            if "vietcombank" in url:
                return {"data": [{"CurrencyCode": "USD", "Sell": "25500", "Date": str(date.today())}]}
            return {}

        monkeypatch.setattr(fetcher, "_get", fake_get)

        fetcher.fetch_usdvnd(days=30)
        assert cache_file.exists()

        # Second call should read from cache
        cached = fetcher._load_usdvnd_cache()
        assert not cached.empty
        assert float(cached["close"].iloc[-1]) == 25500.0


class TestConfigConsistency:
    """LỖI #4 — TP/SL multipliers must be consistent across default.toml & strategy.yaml."""

    def test_default_toml_sl_matches_strategy_yaml(self):
        from tradingos.utils.config import cfg

        toml_sl  = float(cfg.get("strategy", "default_atr_mult_sl",  default=1.5))
        yaml_sl  = float(cfg.strategy("entry_exit", "atr_sl_mult",   default=1.5))
        assert toml_sl == yaml_sl, f"SL mismatch: toml={toml_sl}, yaml={yaml_sl}"

    def test_default_toml_tp1_matches_strategy_yaml(self):
        from tradingos.utils.config import cfg

        toml_tp1 = float(cfg.get("strategy", "default_atr_mult_tp1", default=4.0))
        yaml_tp1 = float(cfg.strategy("entry_exit", "atr_tp1_mult",  default=4.0))
        assert toml_tp1 == yaml_tp1, f"TP1 mismatch: toml={toml_tp1}, yaml={yaml_tp1}"

    def test_default_toml_tp2_matches_strategy_yaml(self):
        from tradingos.utils.config import cfg

        toml_tp2 = float(cfg.get("strategy", "default_atr_mult_tp2", default=8.0))
        yaml_tp2 = float(cfg.strategy("entry_exit", "atr_tp2_mult",  default=8.0))
        assert toml_tp2 == yaml_tp2, f"TP2 mismatch: toml={toml_tp2}, yaml={yaml_tp2}"


# ── NLP: generate_indicator_explanation ──────────────────────────────────────

class TestGenerateIndicatorExplanation:
    """Tests for the new indicator-level NLP function."""

    def _call(self, **kwargs):
        from tradingos.core.nlp import generate_indicator_explanation
        defaults = dict(
            rsi14=50.0, close=25_000, sma20=24_800, sma50=23_500,
            sma200=22_000, atr14=600, volume=1_500_000, avg_volume_20d=1_000_000,
        )
        defaults.update(kwargs)
        return generate_indicator_explanation(**defaults)

    def test_returns_list_of_strings(self):
        result = self._call()
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_rsi_oversold_detected(self):
        result = self._call(rsi14=25.0)
        assert any("quá bán" in s for s in result)

    def test_rsi_overbought_detected(self):
        result = self._call(rsi14=78.0)
        assert any("quá mua" in s for s in result)

    def test_below_sma50_warning_present(self):
        result = self._call(close=20_000, sma50=25_000)
        assert any("Dưới SMA50" in s for s in result)

    def test_above_sma50_positive(self):
        result = self._call(close=30_000, sma50=25_000, sma200=22_000)
        assert any("Trên SMA50" in s for s in result)

    def test_volume_spike_flagged(self):
        result = self._call(volume=4_000_000, avg_volume_20d=1_000_000)
        assert any("đột biến" in s or "3" in s or "4" in s for s in result)

    def test_low_volume_flagged(self):
        result = self._call(volume=300_000, avg_volume_20d=1_000_000)
        assert any("thấp" in s for s in result)

    def test_high_atr_volatility_flagged(self):
        result = self._call(close=10_000, atr14=600)  # 6% ATR
        assert any("cao" in s.lower() for s in result)

    def test_low_atr_stable_flagged(self):
        result = self._call(close=100_000, atr14=1_000)  # 1% ATR
        assert any("thấp" in s.lower() or "ổn định" in s for s in result)

    def test_sma200_below_flagged(self):
        result = self._call(close=20_000, sma200=25_000, sma50=21_000)
        assert any("SMA200" in s and "dưới" in s.lower() for s in result)

    def test_pullback_to_sma20_detected(self):
        # close within 2% of sma20
        result = self._call(close=25_000, sma20=25_100, sma50=23_000)
        assert any("SMA20" in s for s in result)

    def test_zero_avg_volume_no_crash(self):
        result = self._call(avg_volume_20d=0)
        assert isinstance(result, list)


# ── NLP: generate_summary_headline ───────────────────────────────────────────

class TestGenerateSummaryHeadline:
    """Tests for the scanner one-liner NLP headline function."""

    def _call(self, **kwargs):
        from tradingos.core.nlp import generate_summary_headline
        defaults = dict(
            ticker="VCB", action="BUY", mfpm_score=75,
            signal_mode="MODE_A", rsi14=45.0, sms_raw=30,
            stealth_accum=False, best_pattern="NONE",
            distribution_warning="NONE", hmm_state="TRENDING_UP",
        )
        defaults.update(kwargs)
        return generate_summary_headline(**defaults)

    def test_returns_string(self):
        assert isinstance(self._call(), str)

    def test_includes_mode_pullback(self):
        h = self._call(signal_mode="MODE_A")
        assert "Pullback" in h

    def test_includes_mode_breakout(self):
        h = self._call(signal_mode="MODE_B")
        assert "Breakout" in h

    def test_includes_mode_whale(self):
        h = self._call(signal_mode="MODE_W")
        assert "Whale" in h

    def test_includes_mfpm_score(self):
        h = self._call(mfpm_score=88)
        assert "88" in h

    def test_stealth_flag_present(self):
        h = self._call(stealth_accum=True)
        assert "Stealth" in h

    def test_high_sms_flag_present(self):
        h = self._call(sms_raw=70)
        assert "SMS" in h and "70" in h

    def test_vcp_pattern_present(self):
        h = self._call(best_pattern="VCP")
        assert "VCP" in h

    def test_distribution_exit_override(self):
        h = self._call(distribution_warning="EXIT")
        assert "Phân phối" in h

    def test_distribution_forced_exit(self):
        h = self._call(distribution_warning="FORCED_EXIT")
        assert "cực mạnh" in h

    def test_rsi_oversold_tagged(self):
        h = self._call(rsi14=28.0)
        assert "quá bán" in h

    def test_rsi_overbought_tagged(self):
        h = self._call(rsi14=75.0)
        assert "quá mua" in h

    def test_hmm_emoji_present(self):
        h = self._call(hmm_state="STEADY_BEAR")
        assert "🔴" in h

    def test_no_pattern_none_not_shown(self):
        h = self._call(best_pattern="NONE")
        assert "NONE" not in h


# ── NLP: generate_f0_explanation ─────────────────────────────────────────────

class TestGenerateF0Explanation:
    """Tests for the F0 beginner-mode narrative function (6 sections)."""

    _DEFAULTS = dict(
        ticker="VCB", action="BUY", mfpm_score=75, signal_mode="MODE_A",
        confidence="HIGH", close=25_000, entry_price=24_800, stop_loss=23_000,
        sl_pct=0.074, tp1=28_000, tp2=32_000, rr_ratio=1.8,
        rsi14=42.0, sms_raw=60, sms_label="WHALE_BUYING",
        stealth_accum=False, distribution_warning="NONE",
        hmm_state="TRENDING_UP", amd_phase="ACCUMULATION",
        amf_decision="PASS", best_pattern="VCP", mcvd_trend="UP",
        mc_win_prob=0.58, mode_w_score=0, mode_a_score=55, mode_b_score=0,
        macro_regime="ACCOMMODATIVE", earnings_risk="SAFE",
        sma20=24_800, sma50=23_000, sma200=21_000,
        volume=1_500_000, avg_volume_20d=900_000, atr14=600,
        mode_w_conditions_failed=[],
    )

    def _call(self, **kwargs):
        from tradingos.core.nlp import generate_f0_explanation
        params = {**self._DEFAULTS, **kwargs}
        return generate_f0_explanation(**params)

    # ── Return type ──────────────────────────────────────────────────────────

    def test_returns_string(self):
        assert isinstance(self._call(), str)

    def test_has_all_six_section_headers(self):
        r = self._call()
        assert "Kết luận" in r
        assert "Tại sao" in r
        assert "Tín hiệu" in r or "ủng hộ" in r
        assert "Rủi ro" in r
        assert "Kế hoạch" in r
        assert "Bạn nên" in r

    # ── Section 1: verdict / action label ────────────────────────────────────

    def test_strong_buy_verdict(self):
        r = self._call(action="STRONG_BUY", mfpm_score=95)
        assert "MUA MẠNH" in r or "rất mạnh" in r

    def test_no_action_verdict_text(self):
        r = self._call(action="NO_ACTION", mfpm_score=30)
        assert "CHƯA CÓ TÍN HIỆU" in r or "chưa có tín hiệu" in r.lower()

    def test_watch_action_label(self):
        r = self._call(action="WATCH", mfpm_score=55)
        assert "THEO DÕI" in r

    def test_exit_action_label(self):
        r = self._call(action="EXIT", mfpm_score=40)
        assert "THOÁT" in r or "EXIT" in r

    # ── Section 2: score / mode explanation ──────────────────────────────────

    def test_mfpm_score_appears_in_section2(self):
        r = self._call(mfpm_score=88)
        assert "88" in r

    def test_mode_a_explanation_present(self):
        r = self._call(signal_mode="MODE_A")
        assert "pullback" in r.lower() or "MODE_A" in r or "điều chỉnh" in r.lower()

    def test_mode_b_explanation_present(self):
        r = self._call(signal_mode="MODE_B")
        assert "breakout" in r.lower() or "MODE_B" in r or "bứt phá" in r.lower()

    def test_mode_w_explanation_present(self):
        r = self._call(signal_mode="MODE_W", mode_w_score=60)
        assert "tiền cá mập" in r.lower() or "whale" in r.lower() or "MODE_W" in r

    # ── Section 3: supporting signals ────────────────────────────────────────

    def test_rsi_oversold_in_supports(self):
        r = self._call(rsi14=25.0, action="BUY")
        assert "quá bán" in r.lower() or "RSI" in r

    def test_whale_sms_in_supports(self):
        r = self._call(sms_raw=72, sms_label="WHALE_BUYING")
        assert "cá mập" in r.lower() or "SMS" in r or "72" in r

    def test_stealth_accum_in_supports(self):
        r = self._call(stealth_accum=True, action="BUY")
        assert "stealth" in r.lower() or "ngầm" in r.lower()

    def test_vcp_pattern_in_supports(self):
        r = self._call(best_pattern="VCP", action="BUY")
        assert "VCP" in r

    def test_above_sma50_in_supports(self):
        r = self._call(close=30_000, sma50=25_000, action="BUY")
        assert "SMA50" in r or "MA50" in r

    # ── Section 4: risks ─────────────────────────────────────────────────────

    def test_distribution_exit_in_risks(self):
        r = self._call(distribution_warning="EXIT", action="EXIT")
        assert "phân phối" in r.lower() or "EXIT" in r

    def test_distribution_forced_exit_in_risks(self):
        r = self._call(distribution_warning="FORCED_EXIT", action="FORCED_EXIT")
        assert "FORCED" in r or "mạnh" in r.lower() or "phân phối" in r.lower()

    def test_amf_block_in_risks(self):
        r = self._call(amf_decision="BLOCK", action="WATCH")
        assert "BLOCK" in r or "chặn" in r.lower() or "AMF" in r

    def test_rsi_overbought_in_risks(self):
        r = self._call(rsi14=78.0, action="WATCH")
        assert "quá mua" in r.lower() or "RSI" in r

    def test_hmm_bear_in_risks(self):
        r = self._call(hmm_state="STEADY_BEAR", action="WATCH")
        assert "gấu" in r.lower() or "bear" in r.lower() or "HMM" in r

    def test_earnings_risk_in_risks(self):
        r = self._call(earnings_risk="HIGH_RISK", action="WATCH")
        assert "kết quả kinh doanh" in r.lower() or "earnings" in r.lower() or "HIGH_RISK" in r

    def test_macro_restrictive_in_risks(self):
        r = self._call(macro_regime="RESTRICTIVE", action="WATCH")
        assert "thắt chặt" in r.lower() or "RESTRICTIVE" in r

    # ── Section 5: trading plan ───────────────────────────────────────────────

    def test_trading_plan_has_entry_and_sl_and_tp(self):
        r = self._call(entry_price=24_800, stop_loss=23_000, tp1=28_000)
        assert "24,800" in r or "24800" in r or "24.800" in r
        assert "23,000" in r or "23000" in r or "23.000" in r
        assert "28,000" in r or "28000" in r or "28.000" in r

    def test_trading_plan_missing_when_no_entry_price(self):
        r = self._call(entry_price=0, stop_loss=0, tp1=0, tp2=0, action="NO_ACTION")
        assert "Chưa đủ điều kiện" in r or "chưa" in r.lower()

    def test_rr_ratio_appears_in_plan(self):
        r = self._call(rr_ratio=2.5)
        assert "2.5" in r or "R:R" in r or "tỉ lệ" in r.lower()

    # ── Section 6: upgrade advice ─────────────────────────────────────────────

    def test_forced_exit_section6_thoat_ngay(self):
        r = self._call(action="FORCED_EXIT", distribution_warning="FORCED_EXIT")
        assert "THOÁT NGAY" in r or "thoát ngay" in r.lower()

    def test_watch_section6_shows_mfpm_threshold(self):
        r = self._call(action="WATCH", mfpm_score=55)
        # Should tell user how many points needed to reach BUY (70)
        assert "70" in r or "điểm" in r.lower()

    def test_no_action_section6_shows_50_threshold(self):
        r = self._call(action="NO_ACTION", mfpm_score=30)
        # Should mention the 50-point WATCH threshold
        assert "50" in r or "điểm" in r.lower()

    def test_buy_section6_has_concrete_advice(self):
        r = self._call(action="BUY", mfpm_score=75)
        # Must have some actionable Vietnamese text in section 6
        assert "vào lệnh" in r.lower() or "mua" in r.lower() or "lệnh" in r.lower()

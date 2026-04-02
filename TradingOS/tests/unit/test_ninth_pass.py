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

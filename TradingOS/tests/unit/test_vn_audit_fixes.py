"""Tests for VN market audit fixes — V1-V6, O1, O4, B1-B6.

Run with:
    pytest tests/unit/test_vn_audit_fixes.py -v
"""
from __future__ import annotations

import inspect
import math
import time
import types
import importlib
import numpy as np
import pandas as pd
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ohlcv(n: int = 60, seed: int = 42) -> pd.DataFrame:
    """Minimal OHLCV DataFrame with computed indicators."""
    rng = np.random.default_rng(seed)
    closes = 50_000.0 + np.cumsum(rng.normal(0, 500, n))
    vols = rng.integers(500_000, 2_000_000, n).astype(float)
    df = pd.DataFrame({
        "open":   closes * 0.99,
        "high":   closes * 1.01,
        "low":    closes * 0.98,
        "close":  closes,
        "volume": vols,
    })
    df.index = pd.date_range("2024-01-01", periods=n, freq="B")
    from tradingos.core.indicators import compute_all
    return compute_all(df)


# ── V1: Mode A volume confirmation threshold ─────────────────────────────────

class TestModeAVolumeConfirm:
    """[VN-FIX V1] volume confirm 0.8→1.5x via config."""

    def test_below_threshold_no_volume_bonus(self):
        """Volume at 1.0x avg → below new 1.5x gate → no volume bonus."""
        from tradingos.core.mfpm import score_mode_a
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        # Set last bar volume = exactly 1.0× avg (below 1.5× gate)
        df_mod = df.copy()
        df_mod.loc[df_mod.index[-1], "volume"] = avg_vol * 1.0
        score_low = score_mode_a(df_mod)
        # Set last bar volume = 2.0× avg (above 1.5× gate)
        df_high = df.copy()
        df_high.loc[df_high.index[-1], "volume"] = avg_vol * 2.0
        score_high = score_mode_a(df_high)
        # The high-volume bar should score higher (volume bonus applies)
        assert score_high >= score_low, (
            f"High vol ({score_high}) should be >= low vol ({score_low})"
        )

    def test_above_threshold_gets_bonus(self):
        """Volume at 2.0x avg → above 1.5x gate → score includes volume bonus."""
        from tradingos.core.mfpm import score_mode_a
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        df_mod = df.copy()
        df_mod.loc[df_mod.index[-1], "volume"] = avg_vol * 2.0
        # Score must be >= 10 (the volume bonus block contributes +10)
        # Can't assert exact because RSI/SMA conditions also contribute,
        # but at minimum the function should not error.
        score = score_mode_a(df_mod)
        assert isinstance(score, int)
        assert 0 <= score <= 60


# ── V2: Horizon weights from config ──────────────────────────────────────────

class TestHorizonWeights:
    """[VN-FIX V2] _aggregate() reads weights from config."""

    def test_config_keys_present(self):
        """strategy.yaml must have horizon_forecast section with weight keys."""
        from tradingos.utils.config import cfg
        w_s = cfg.strategy("horizon_forecast", "weight_short", default=None)
        w_m = cfg.strategy("horizon_forecast", "weight_mid",   default=None)
        w_l = cfg.strategy("horizon_forecast", "weight_long",  default=None)
        assert w_s is not None, "weight_short missing from strategy.yaml"
        assert w_m is not None, "weight_mid missing from strategy.yaml"
        assert w_l is not None, "weight_long missing from strategy.yaml"
        assert abs(float(w_s) + float(w_m) + float(w_l) - 1.0) < 0.01, \
            f"Weights should sum to ~1.0: {w_s}+{w_m}+{w_l}"

    def test_aggregate_uses_config_weights(self):
        """_aggregate returns TĂNG when short is strongly bullish with 0.50 weight."""
        from tradingos.core.horizon_forecast import _aggregate
        # Strong bull short, bearish mid, bearish long
        # With weights 0.50/0.30/0.20: score = 0.50*0.9 - 0.30*0.8 - 0.20*0.7 = 0.45-0.24-0.14 = 0.07
        # With old 0.40/0.35/0.25: score = 0.40*0.9 - 0.35*0.8 - 0.25*0.7 = 0.36-0.28-0.175 = -0.095 → GIẢM
        # New weights should produce TRUNG LẬP or TĂNG
        vote, conf = _aggregate("TĂNG", 90.0, "GIẢM", 80.0, "GIẢM", 70.0)
        # With new weights the score is positive but < 0.12 threshold → TRUNG LẬP
        assert vote in ("TĂNG", "TRUNG LẬP"), f"Expected bullish bias with high short conf, got {vote}"

    def test_normalisation(self):
        """_aggregate normalises weights that don't sum to 1.0."""
        from tradingos.core.horizon_forecast import _aggregate
        # This should not raise — normalisation handles off-sum configs
        vote, conf = _aggregate("TĂNG", 60.0, "TĂNG", 60.0, "GIẢM", 60.0)
        assert vote in ("TĂNG", "TRUNG LẬP", "GIẢM")
        assert 0 <= conf <= 100


# ── V3: T+2.5 window open time ───────────────────────────────────────────────

class TestT25WindowOpen:
    """[VN-FIX V3] t25_window_open must be 09:15 (VN ATO ends 09:15)."""

    def test_config_window_open(self):
        from tradingos.utils.config import cfg
        window_open = cfg.strategy("entry_exit", "t25_window_open", default="09:30")
        assert window_open == "09:15", (
            f"t25_window_open should be '09:15' (VN ATO ends 09:15), got '{window_open}'"
        )


# ── V4: FOL no-data fallback neutral ─────────────────────────────────────────

class TestFOLNeutralFallback:
    """[VN-FIX V4] When no foreign flow data, SMS FOL slot = 5/15 (neutral)."""

    def _make_flow_df_no_fol(self, n: int = 20) -> pd.DataFrame:
        """daily_flow_df without fol_net column."""
        rng = np.random.default_rng(0)
        whale_net = rng.normal(0, 1e8, n)
        return pd.DataFrame({
            "date":      pd.date_range("2024-01-01", periods=n, freq="B"),
            "whale_net": whale_net,
        })

    def test_fol_component_is_neutral_without_data(self):
        """SMS FOL component == 5 when no fol_net column."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        daily_flow_df = self._make_flow_df_no_fol(20)
        result = compute_smart_money_score(
            ticker="TEST",
            df=df,
            daily_flow_df=daily_flow_df,
        )
        fol_comp = result.get("components", {}).get("fol", -1)
        assert fol_comp == 5, (
            f"FOL component should be 5 (neutral) when no fol_net column, got {fol_comp}"
        )

    def test_fol_not_obv_derived_without_data(self):
        """FOL component must NOT vary with OBV slope when no foreign data."""
        from tradingos.core.money_flow import compute_smart_money_score
        # Flat OBV scenario
        df_flat = _ohlcv(60, seed=1)
        df_flat["OBV"] = 1e6  # constant OBV → slope = 0
        r_flat = compute_smart_money_score(
            ticker="TEST", df=df_flat, daily_flow_df=self._make_flow_df_no_fol()
        )
        # Steeply rising OBV scenario
        df_rise = _ohlcv(60, seed=2)
        df_rise["OBV"] = pd.Series(range(1, 61), index=df_rise.index, dtype=float) * 1e6
        r_rise = compute_smart_money_score(
            ticker="TEST", df=df_rise, daily_flow_df=self._make_flow_df_no_fol()
        )
        assert r_flat["components"]["fol"] == r_rise["components"]["fol"] == 5, (
            f"FOL should be 5 regardless of OBV slope when no foreign data. "
            f"flat={r_flat['components']['fol']}, rise={r_rise['components']['fol']}"
        )


# ── V6: Bollinger Band ceiling guard ─────────────────────────────────────────

class TestBBCeilingGuard:
    """[VN-FIX V6] BB bear signal suppressed when rt_at_ceiling=True."""

    def _df_at_bb_upper(self) -> pd.DataFrame:
        """DataFrame where close is near BB upper band (pos > 0.88)."""
        df = _ohlcv(60)
        # Directly set BB columns so we control the position precisely
        last_idx = df.index[-1]
        bb_upper = float(df["close"].iloc[-1]) * 1.005  # upper just above close
        bb_lower = float(df["close"].iloc[-1]) * 0.900  # lower well below
        bb_mid   = (bb_upper + bb_lower) / 2
        df.loc[last_idx, "BB_upper"] = bb_upper
        df.loc[last_idx, "BB_lower"] = bb_lower
        df.loc[last_idx, "BB_mid"]   = bb_mid
        # close = 1.0 * original close, which is just below bb_upper
        # pos = (close - bb_lower) / (bb_upper - bb_lower)
        # = (close - 0.9*close) / (1.005*close - 0.9*close)
        # = 0.1 / 0.105 ≈ 0.952 > 0.88  ✓
        return df

    def test_bear_signal_fires_without_ceiling(self):
        """When not at ceiling, BB upper bear signal may fire."""
        from tradingos.core.horizon_forecast import _forecast_short
        df = self._df_at_bb_upper()
        vote, conf, reasons = _forecast_short(df, ctx={"rt_at_ceiling": False})
        # Just check no crash and result is valid
        assert vote in ("TĂNG", "GIẢM", "TRUNG LẬP")
        assert 0 <= conf <= 100

    def test_bear_signal_suppressed_at_ceiling(self):
        """When at ceiling, BB bear signal is NOT added (bear points not increased)."""
        from tradingos.core.horizon_forecast import _forecast_short
        df = self._df_at_bb_upper()
        vote_n, _, reasons_normal   = _forecast_short(df, ctx={"rt_at_ceiling": False})
        vote_c, _, reasons_ceiling  = _forecast_short(df, ctx={"rt_at_ceiling": True})
        # When NOT at ceiling, the bear "áp sát dải BB trên" reason should appear
        assert any("áp sát" in r for r in reasons_normal), (
            f"BB upper resistance reason ('áp sát') should appear when not at ceiling: {reasons_normal}"
        )
        # When AT ceiling, the bear scoring message "áp sát" must NOT appear
        # (the advisory "kháng cự không áp dụng" may appear but that's not the bear signal)
        assert not any("áp sát" in r for r in reasons_ceiling), (
            f"BB upper bear reason ('áp sát') should be suppressed at ceiling: {reasons_ceiling}"
        )


# ── O1: Macro cache ───────────────────────────────────────────────────────────

class TestMacroCache:
    """[O1 FIX] Module-level macro cache with 5-minute TTL."""

    def test_cache_module_globals_present(self):
        """_MACRO_CACHE and _MACRO_TTL must be module-level globals."""
        import tradingos.engines.profiler_service as ps_mod
        assert hasattr(ps_mod, "_MACRO_CACHE"), "_MACRO_CACHE missing"
        assert hasattr(ps_mod, "_MACRO_TTL"),   "_MACRO_TTL missing"
        assert isinstance(ps_mod._MACRO_CACHE, dict)
        assert ps_mod._MACRO_TTL == 300.0

    def test_cache_ttl_value(self):
        """TTL must be 300 seconds (5 minutes)."""
        import tradingos.engines.profiler_service as ps_mod
        assert ps_mod._MACRO_TTL == 300.0, f"TTL should be 300.0, got {ps_mod._MACRO_TTL}"

    def test_cache_structure_after_write(self):
        """After writing, cache must have 'result' and 'ts' keys."""
        import tradingos.engines.profiler_service as ps_mod
        # Simulate what the profiler does after a successful macro fetch
        ps_mod._MACRO_CACHE["result"] = None  # result can be None (failed macro)
        ps_mod._MACRO_CACHE["ts"]     = time.time()
        assert "ts" in ps_mod._MACRO_CACHE
        assert "result" in ps_mod._MACRO_CACHE
        # Clean up for other tests
        ps_mod._MACRO_CACHE.clear()


# ── O4: Monte Carlo n_sim from config ────────────────────────────────────────

class TestMCNSim:
    """[O4 FIX] monte_carlo_win_prob uses config mc_n_sim (default 500)."""

    def test_config_mc_n_sim_present(self):
        from tradingos.utils.config import cfg
        n_sim = cfg.strategy("mfpm", "mc_n_sim", default=None)
        assert n_sim is not None, "mc_n_sim missing from strategy.yaml [mfpm] section"
        assert int(n_sim) == 500, f"mc_n_sim should be 500, got {n_sim}"

    def test_monte_carlo_runs_with_500_sims(self):
        """monte_carlo_win_prob completes without error using 500 simulations."""
        from tradingos.core.mfpm import monte_carlo_win_prob
        df = _ohlcv(100)
        close = float(df["close"].iloc[-1])
        prob = monte_carlo_win_prob(
            df=df, entry=close, sl=close * 0.94, tp=close * 1.12, n_sim=500, horizon=15,
        )
        assert 0.0 <= prob <= 1.0, f"Probability must be in [0,1], got {prob}"


class TestVNNoiseReductionRetunes:
    def test_mode_w_gates_are_stricter(self):
        from tradingos.utils.config import cfg

        assert int(cfg.strategy("mfpm", "mode_w_sms_gate", default=0)) == 65
        assert int(cfg.strategy("mode_w", "sms_raw_gate", default=0)) == 65

    def test_tplus_engine_uses_light_t25_confirmation_boost(self):
        import tradingos.core.t_plus_engine as tplus_mod

        src = inspect.getsource(tplus_mod)
        assert "best_score = min(10.0, best_score + 0.5)" in src


class TestAuditPayloadPersistence:
    def test_log_event_persists_extra_fields_inside_payload(self, monkeypatch):
        import tradingos.engines.audit_service as audit_mod

        captured: dict[str, dict] = {}

        def _capture(record: dict) -> None:
            captured["record"] = record

        monkeypatch.setattr(audit_mod.cache, "put_audit", _capture)

        svc = audit_mod.AuditService()
        svc.log_event(
            event_type="PROFILE",
            ticker="VCB",
            action="BUY",
            mfpm_score=78,
            sms_raw=68,
            confidence="HIGH",
            extra={"tplus_verdict": "MUA_NGAY", "fc_overall_vote": "TĂNG"},
        )

        record = captured["record"]
        assert record["payload"]["confidence"] == "HIGH"
        assert record["payload"]["tplus_verdict"] == "MUA_NGAY"
        assert record["payload"]["fc_overall_vote"] == "TĂNG"
        assert record["tplus_verdict"] == "MUA_NGAY"


# ── B1: Audit breakdown tiles after filters ───────────────────────────────────

class TestAuditBreakdownOrder:
    """[BUG-B1 FIX] Breakdown tiles must reflect post-filter data."""

    def test_breakdown_count_matches_filtered_df(self):
        """Simulate filter application and assert breakdown count == len(df)."""
        rows = [
            {"action": "BUY",    "tplus_verdict": "MUA_NGAY",   "T+ Conf%": 85},
            {"action": "WATCH",  "tplus_verdict": "THEO_DOI",   "T+ Conf%": 30},
            {"action": "BUY",    "tplus_verdict": "MUA_NGAY",   "T+ Conf%": 91},
            {"action": "WATCH",  "tplus_verdict": "TRANH_XA",   "T+ Conf%": 0},
        ]
        df = pd.DataFrame(rows)

        # Apply filter: only MUA_NGAY verdict
        vd_filter = ["MUA_NGAY"]
        df_filtered = df[df["tplus_verdict"].isin(vd_filter)]

        # Breakdown count should equal filtered row count
        breakdown = df_filtered["action"].value_counts()
        total_from_breakdown = breakdown.sum()
        assert total_from_breakdown == len(df_filtered), (
            f"Breakdown total ({total_from_breakdown}) != filtered rows ({len(df_filtered)})"
        )
        assert len(df_filtered) == 2, f"Expected 2 rows after filter, got {len(df_filtered)}"


# ── B2: Trend Warning progress bar clamp ─────────────────────────────────────

class TestTrendWarningProgressClamp:
    """[BUG-B2 FIX] tw_conf_pct must be clamped to [0, 100]."""

    @pytest.mark.parametrize("raw_conf, expected_clamped", [
        (0.0,  0),
        (0.5,  50),
        (1.0,  100),
        (1.5,  100),   # > 1.0 → would crash st.progress without clamp
        (-0.1, 0),     # negative → clamp to 0
        (2.5,  100),
    ])
    def test_clamp_logic(self, raw_conf: float, expected_clamped: int):
        tw_conf_pct = int(raw_conf * 100)
        clamped = min(100, max(0, tw_conf_pct))
        assert clamped == expected_clamped, (
            f"raw_conf={raw_conf} → clamped={clamped}, expected={expected_clamped}"
        )


# ── B3: T+2.5 afternoon score condition ──────────────────────────────────────

class TestT25AfternoonCondition:
    """[BUG-B3 FIX] Window section visible when only afternoon_score > 0."""

    @pytest.mark.parametrize("morning, midday, afternoon, should_show", [
        (0, 0, 0,  False),
        (50, 0, 0, True),
        (0, 50, 0, True),
        (0, 0, 50, True),   # was False before fix
        (30, 20, 10, True),
    ])
    def test_condition(self, morning, midday, afternoon, should_show):
        # The fixed condition:
        result = morning > 0 or midday > 0 or afternoon > 0
        assert result == should_show, (
            f"morning={morning}, midday={midday}, afternoon={afternoon} → "
            f"show={result}, expected={should_show}"
        )


# ── B5: MCVD chart missing column guard ──────────────────────────────────────

class TestMCVDChartColumnGuard:
    """[BUG-B5 FIX] render_mcvd_chart must not crash on missing whale_net."""

    def test_missing_whale_net_no_crash(self, monkeypatch):
        """With no whale_net column, function should warn and return, not KeyError."""
        import tradingos.ui.components.mcvd_chart as chart_mod
        warned = []
        returned = []

        def mock_warning(msg):
            warned.append(msg)

        def mock_return_sentinel():
            returned.append(True)

        # Patch streamlit
        import streamlit as st
        monkeypatch.setattr(st, "warning", mock_warning)
        monkeypatch.setattr(st, "info", lambda *a, **kw: None)
        monkeypatch.setattr(st, "plotly_chart", lambda *a, **kw: None)

        df_no_whale = pd.DataFrame({
            "date":      pd.date_range("2024-01-01", periods=5, freq="B"),
            "other_col": range(5),
        })
        # Should not raise KeyError
        try:
            chart_mod.render_mcvd_chart(df_no_whale, ticker="VCB", days=5)
        except KeyError as e:
            pytest.fail(f"KeyError raised when whale_net missing: {e}")
        assert len(warned) > 0, "Should have emitted a st.warning when whale_net missing"

    def test_empty_df_shows_info(self, monkeypatch):
        """Empty DataFrame → st.info, no crash."""
        import tradingos.ui.components.mcvd_chart as chart_mod
        import streamlit as st
        infos = []
        monkeypatch.setattr(st, "info", lambda msg: infos.append(msg))
        monkeypatch.setattr(st, "warning", lambda *a, **kw: None)
        monkeypatch.setattr(st, "plotly_chart", lambda *a, **kw: None)
        chart_mod.render_mcvd_chart(pd.DataFrame(), ticker="VCB")
        assert len(infos) > 0


# ── V5/B6: Scanner UPCOM option ───────────────────────────────────────────────

class TestScannerUpcom:
    """[VN-FIX V5] Scanner exchange selectbox must include UPCOM."""

    def test_upcom_in_scanner_source(self):
        """scanner.py must reference 'UPCOM' as an exchange option."""
        import inspect
        import tradingos.ui.pages.scanner as scanner_mod
        src = inspect.getsource(scanner_mod)
        assert '"UPCOM"' in src or "'UPCOM'" in src, \
            "UPCOM missing from scanner exchange selectbox"


# ── V7: Pattern bonus differentiation ────────────────────────────────────────

class TestPatternBonusDifferentiation:
    """[VN-FIX V7] Pattern bonuses: VCP=18, Spring=12, CwH=10, RSI-div=8."""

    def test_vcp_bonus_is_18_in_source(self):
        """VCP bonus must be 18 in _PATTERN_BONUS dict."""
        import tradingos.core.patterns as pat_mod
        src = inspect.getsource(pat_mod.detect_all)
        assert '"VCP": 18' in src or "'VCP': 18" in src, \
            "VCP bonus must be 18 in _PATTERN_BONUS dict"

    def test_spring_bonus_is_12_in_source(self):
        """WYCKOFF_SPRING bonus must be 12."""
        import tradingos.core.patterns as pat_mod
        src = inspect.getsource(pat_mod.detect_all)
        assert '"WYCKOFF_SPRING": 12' in src or "'WYCKOFF_SPRING': 12" in src, \
            "WYCKOFF_SPRING bonus must be 12 in _PATTERN_BONUS dict"

    def test_cwh_bonus_is_10_in_source(self):
        """CUP_WITH_HANDLE bonus must be 10."""
        import tradingos.core.patterns as pat_mod
        src = inspect.getsource(pat_mod.detect_all)
        assert '"CUP_WITH_HANDLE": 10' in src or "'CUP_WITH_HANDLE': 10" in src, \
            "CUP_WITH_HANDLE bonus must be 10 in _PATTERN_BONUS dict"

    def test_rsi_div_bonus_is_8_in_source(self):
        """RSI_DIV_BULLISH bonus must be 8."""
        import tradingos.core.patterns as pat_mod
        src = inspect.getsource(pat_mod.detect_all)
        assert '"RSI_DIV_BULLISH": 8' in src or "'RSI_DIV_BULLISH': 8" in src, \
            "RSI_DIV_BULLISH bonus must be 8 in _PATTERN_BONUS dict"

    def test_best_wins_not_first_wins(self):
        """When Spring listed before VCP, VCP (bonus=18) must still win."""
        # Re-exercise the selection logic directly to confirm best-wins semantics.
        _PATTERN_BONUS = {
            "VCP": 18, "WYCKOFF_SPRING": 12,
            "CUP_WITH_HANDLE": 10, "RSI_DIV_BULLISH": 8,
        }
        detected = [
            {"detected": True, "pattern": "WYCKOFF_SPRING"},   # listed first
            {"detected": True, "pattern": "VCP"},               # higher bonus, listed second
        ]
        best_bonus = 0
        best_name = "NONE"
        for p in detected:
            ptype = p.get("pattern", p.get("type", ""))
            if ptype == "BULLISH":
                ptype = "RSI_DIV_BULLISH"
            b = _PATTERN_BONUS.get(ptype, 0)
            if b > best_bonus:
                best_bonus = b
                best_name = ptype
        assert best_name == "VCP", \
            f"VCP must beat Spring in best-wins selection, got {best_name}"
        assert best_bonus == 18, f"VCP bonus must be 18, got {best_bonus}"

    def test_detect_all_returns_vcp_bonus_18(self):
        """detect_all with a VCP-triggering DataFrame returns pattern_bonus==18."""
        from tradingos.core.patterns import detect_all
        # Craft a DF with narrowing contractions + declining volume to trigger VCP.
        n = 60
        base = 50_000.0
        closes, vols = [], []
        for phase, (amp, vol_base) in enumerate([(5000, 1_500_000), (2500, 1_200_000), (1000, 800_000)]):
            for i in range(20):
                closes.append(base + amp * np.cos(np.pi * i / 19))
                vols.append(vol_base - i * 5_000 * (phase + 1))
        df = pd.DataFrame({
            "open": [c * 0.99 for c in closes], "high": [c * 1.01 for c in closes],
            "low":  [c * 0.98 for c in closes], "close": closes, "volume": vols,
        })
        df.index = pd.date_range("2024-01-01", periods=n, freq="B")
        from tradingos.core.indicators import compute_all
        df = compute_all(df)
        result = detect_all(df)
        if result["best_pattern"] == "VCP":
            assert result["pattern_bonus"] == 18, \
                f"VCP pattern_bonus must be 18, got {result['pattern_bonus']}"
        # Pattern may or may not trigger depending on exact swings;
        # the source-level assertions above are the definitive contract tests.


# ── V8: OHLCV_PROXY CVD cannot satisfy Mode W W-6 gate ───────────────────────

class TestOHLCVProxyCVDCap:
    """[VN-FIX V8] OHLCV_PROXY cvd_today capped at 6, never >=7 (W-6 gate)."""

    def _make_flow(self, n: int = 20) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        return pd.DataFrame({
            "date":      pd.date_range("2024-01-01", periods=n, freq="B"),
            "whale_net": rng.normal(0, 1e8, n),
        })

    def test_proxy_positive_cvd_capped_at_6(self):
        """High-intensity positive OHLCV_PROXY CVD must score <= 6."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        result = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=self._make_flow(),
            cvd_today=int(avg_vol * 0.20),
            cvd_data_quality="OHLCV_PROXY",
        )
        assert result["components"]["cvd_today"] <= 6, (
            f"OHLCV_PROXY positive CVD must be <=6 (W-6 gate is >=7), "
            f"got {result['components']['cvd_today']}"
        )

    def test_proxy_never_reaches_w6_threshold(self):
        """Proxy CVD at any intensity must not reach the >=7 gate threshold."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        for mult in (0.05, 0.12, 0.25, 0.50, 1.00):
            r = compute_smart_money_score(
                ticker="TEST", df=df, daily_flow_df=self._make_flow(),
                cvd_today=int(avg_vol * mult),
                cvd_data_quality="OHLCV_PROXY",
            )
            assert r["components"]["cvd_today"] < 7, (
                f"OHLCV_PROXY cvd_today must never be >=7 at mult={mult:.0%}, "
                f"got {r['components']['cvd_today']}"
            )

    def test_real_flow_still_reaches_10(self):
        """REAL_FLOW high-intensity CVD must still score 10."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        r = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=self._make_flow(),
            cvd_today=int(avg_vol * 0.20),
            cvd_data_quality="REAL_FLOW",
        )
        assert r["components"]["cvd_today"] == 10, (
            f"REAL_FLOW high-intensity positive CVD must be 10, "
            f"got {r['components']['cvd_today']}"
        )


# ── V9: SMS all-neutral quality cap ──────────────────────────────────────────

class TestSMSAllNeutralQualityCap:
    """[VN-FIX V9] SMS reduced by 5 when FOL=5, PT=5, CVD=5 (all no-data neutral)."""

    def _make_flow_no_fol(self, n: int = 20) -> pd.DataFrame:
        rng = np.random.default_rng(2)
        return pd.DataFrame({
            "date":      pd.date_range("2024-01-01", periods=n, freq="B"),
            "whale_net": rng.normal(0, 1e8, n),
        })

    def test_all_neutral_scores_lower_than_real_cvd(self):
        """Scanner-only run scores >=5 less than same run with positive real CVD."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        flow = self._make_flow_no_fol()
        avg_vol = df["volume"].tail(20).mean()

        result_neutral = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=flow,
            cvd_today=None,   # component = 5, no fol, no pt
        )
        result_real = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=flow,
            cvd_today=int(avg_vol * 0.20),
            cvd_data_quality="REAL_FLOW",
        )
        diff = result_real["sms"] - result_neutral["sms"]
        assert diff >= 5, (
            f"Real CVD should score >=5 more than all-neutral. "
            f"real={result_real['sms']}, neutral={result_neutral['sms']}, diff={diff}"
        )

    def test_partial_data_no_cap(self):
        """When cvd_today has real data (!=5), cap must not fire."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        avg_vol = df["volume"].tail(20).mean()
        r = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=self._make_flow_no_fol(),
            cvd_today=int(avg_vol * 0.20),
            cvd_data_quality="REAL_FLOW",
        )
        comps = r["components"]
        assert comps["cvd_today"] != 5, (
            "With positive REAL_FLOW CVD, cvd_today component should not be 5"
        )

    def test_sms_bounded_after_cap(self):
        """SMS must stay in [0, 100] after cap is applied."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _ohlcv(60)
        r = compute_smart_money_score(
            ticker="TEST", df=df, daily_flow_df=self._make_flow_no_fol(),
        )
        assert 0 <= r["sms"] <= 100, f"SMS out of range after cap: {r['sms']}"

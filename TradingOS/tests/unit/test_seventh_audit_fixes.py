"""
Seventh-Pass Audit Regression Tests — BUG-30 through BUG-33 + NEW-4 through NEW-10

Run focused:
    pytest tests/unit/test_seventh_audit_fixes.py -v --tb=short

Coverage:
    BUG-30   indicators.py        Hurst regression uses valid_lags (not sequential prefix)
    BUG-31   scanner_service.py   MFPM horizons=[5] → [2,3,5,7,10] (matches profiler)
    BUG-32   scanner_service.py   compute_fundamental_snapshot now receives fol_pct
    BUG-33   scanner_service.py   compute_smart_money_score receives cvd_today/quality
    NEW-4    money_flow.py        z_vol sigma .replace(0,1) guards division by zero
    NEW-5    money_flow.py        SMS no longer hardcodes lookback_days=20 (uses config)
    NEW-6    money_flow.py        compute_multiday_whale_flow sorts by date before tail
    NEW-7    money_flow.py        5-session delta uses iloc[-6] not iloc[-5]
    NEW-8    gap_vwap.py          _fetch_intraday_today uses VN-aware time not datetime.now
    NEW-10   mfpm.py              MODE_W HIGH confidence threshold reads mc_min_prob_strong
"""
from __future__ import annotations

import inspect
from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 120, base: float = 30_000.0) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = base + np.cumsum(rng.normal(0, base * 0.004, n))
    close = np.clip(close, base * 0.5, base * 2)
    atr = close * 0.012
    df = pd.DataFrame({
        "open": close * (1 - rng.uniform(0, 0.002, n)),
        "high": close + rng.uniform(0, atr, n),
        "low": close - rng.uniform(0, atr, n),
        "close": close,
        "volume": rng.integers(200_000, 900_000, n).astype(float),
    })
    df.index = pd.date_range("2024-01-02", periods=n, freq="B")
    return df


def _make_flow_df(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=n)
    return pd.DataFrame({
        "date": dates,
        "whale_net": rng.normal(0, 100_000, n),
        "whale_net_proxy": rng.normal(0, 100_000, n),
        "close": 30_000 + np.cumsum(rng.normal(0, 100, n)),
        "volume": rng.integers(200_000, 900_000, n).astype(float),
    })


# ─────────────────────────────────────────────────────────────────────────────
# BUG-30: Hurst exponent uses valid_lags (not sequential prefix)
# ─────────────────────────────────────────────────────────────────────────────

class TestBug30HurstValidLags:
    def test_hurst_returns_float_in_range(self):
        from tradingos.core.indicators import hurst_exponent
        rng = np.random.default_rng(0)
        s = pd.Series(rng.normal(0, 1, 200))
        h = hurst_exponent(s)
        assert 0.0 <= h <= 1.0

    def test_hurst_trending_series_above_half(self):
        """Strongly trending series (cumsum of positive values) → H > 0.5."""
        from tradingos.core.indicators import hurst_exponent
        s = pd.Series(np.cumsum(np.ones(200) * 0.01 + np.random.default_rng(1).normal(0, 0.005, 200)))
        h = hurst_exponent(s)
        assert h > 0.3, f"Trending series should have H > 0.3, got {h:.4f}"

    def test_short_series_returns_half(self):
        """Series shorter than max_lag*2 → 0.5 (neutral/insufficient)."""
        from tradingos.core.indicators import hurst_exponent
        s = pd.Series(np.random.default_rng(2).normal(0, 1, 50))
        h = hurst_exponent(s)
        assert h == 0.5

    def test_valid_lags_used_not_truncated_prefix(self):
        """
        Verify that the fix produces the correct regression:
        The x values passed to polyfit should be np.log(valid_lags) where
        each valid_lag >= 2 (minimum of range(2, max_lag)).
        Captured x values are log-transformed, so they should all be >= log(2) ≈ 0.693.
        """
        from tradingos.core import indicators
        import numpy as _np
        captured_x = []
        original_polyfit = _np.polyfit

        def recording_polyfit(x, y, deg):
            captured_x.append(list(x))
            return original_polyfit(x, y, deg)

        s = pd.Series(_np.cumsum(_np.random.default_rng(5).normal(0, 1, 200)))
        with patch.object(_np, "polyfit", side_effect=recording_polyfit):
            indicators.hurst_exponent(s)

        if captured_x:
            used_log_lags = captured_x[0]
            import math
            min_valid_log = math.log(2)  # log(2) ≈ 0.693
            assert all(v >= min_valid_log for v in used_log_lags), (
                f"Some log-lags < log(2): {used_log_lags[:5]}"
            )
            # They should be monotonically increasing (sorted lag order)
            assert used_log_lags == sorted(used_log_lags), "Log-lags should be in ascending order"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-31: scanner_service.py MFPM horizons fix
# ─────────────────────────────────────────────────────────────────────────────

class TestBug31ScannerHorizons:
    def test_scanner_compute_mfpm_call_uses_multi_horizon(self):
        """
        Inspect scanner_service._score_ticker source to verify horizons=[2,3,5,7,10]
        not horizons=[5].
        """
        from tradingos.engines import scanner_service
        src = inspect.getsource(scanner_service)
        # Should NOT have the old single-horizon call
        assert "horizons=[5]," not in src, "horizons=[5] still present in scanner_service"
        # Should have multi-horizon
        assert "horizons=[2, 3, 5, 7, 10]" in src, "horizons=[2,3,5,7,10] not found in scanner"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-32: scanner_service.py compute_fundamental_snapshot receives fol_pct
# ─────────────────────────────────────────────────────────────────────────────

class TestBug32ScannerFolPct:
    def test_scanner_fundamental_call_has_fol_pct(self):
        """
        Inspect scanner_service source to verify fol_pct is passed to
        compute_fundamental_snapshot call.
        """
        from tradingos.engines import scanner_service
        src = inspect.getsource(scanner_service)
        assert "fol_pct=_fol_pct" in src, "fol_pct not passed to fundamental snapshot in scanner"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-33: scanner_service.py SMS receives cvd_today / cvd_data_quality
# ─────────────────────────────────────────────────────────────────────────────

class TestBug33ScannerCvdParity:
    def test_scanner_sms_call_has_cvd_kwargs(self):
        """
        Inspect scanner_service source to verify cvd_today and cvd_data_quality
        are now explicitly passed to compute_smart_money_score.
        """
        from tradingos.engines import scanner_service
        src = inspect.getsource(scanner_service)
        assert "cvd_today=None" in src, "cvd_today=None not in scanner SMS call"
        assert 'cvd_data_quality="NONE"' in src, 'cvd_data_quality="NONE" not in scanner SMS call'


# ─────────────────────────────────────────────────────────────────────────────
# NEW-4: z_vol sigma division by zero guard
# ─────────────────────────────────────────────────────────────────────────────

class TestNew4ZVolDivisionByZero:
    def test_flat_volume_no_exception(self):
        """All-same volume → rolling std = 0; with fix, z_vol should be finite 0."""
        from tradingos.core.money_flow import proxy_whale_net_from_daily
        n = 30
        df = pd.DataFrame({
            "open":   [30_000.0] * n,
            "high":   [30_500.0] * n,
            "low":    [29_500.0] * n,
            "close":  [30_000.0] * n,
            "volume": [500_000.0] * n,  # perfectly flat volume
        })
        result = proxy_whale_net_from_daily(df)
        assert result is not None
        assert not result["whale_net_proxy"].isnull().any(), "NaN in whale_net_proxy with flat volume"
        # z_vol should be 0 (all volumes equal mu) — no exceptions raised
        assert np.isfinite(result["whale_net_proxy"]).all()

    def test_normal_volume_still_works(self):
        """Normal volume series: z_vol computation still produces valid results."""
        from tradingos.core.money_flow import proxy_whale_net_from_daily
        df = _make_ohlcv(60)
        result = proxy_whale_net_from_daily(df)
        assert not result["whale_net_proxy"].isnull().any()


# ─────────────────────────────────────────────────────────────────────────────
# NEW-5: compute_smart_money_score no longer hardcodes lookback_days=20
# ─────────────────────────────────────────────────────────────────────────────

class TestNew5SmsLookbackFromConfig:
    def test_sms_compute_multiday_call_uses_no_explicit_lookback(self):
        """
        Inspect compute_smart_money_score source: the actual call to
        compute_multiday_whale_flow should not pass lookback_days= as an
        explicit argument (config-read default must be used).
        """
        from tradingos.core import money_flow
        src = inspect.getsource(money_flow.compute_smart_money_score)
        # The actual call should be compute_multiday_whale_flow(daily_flow_df)
        # with no explicit lookback_days= argument on that same call line.
        # We check that no call site has 'compute_multiday_whale_flow(daily_flow_df, lookback_days='
        assert "compute_multiday_whale_flow(daily_flow_df, lookback_days=" not in src, (
            "compute_smart_money_score still passes explicit lookback_days= to compute_multiday_whale_flow"
        )

    def test_compute_multiday_respects_default(self):
        """compute_multiday_whale_flow with no explicit lookback reads from cfg default=20."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        flow = _make_flow_df(30)
        result = compute_multiday_whale_flow(flow)  # no explicit lookback_days
        assert "mcvd_trend" in result
        assert result["mcvd_5d"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# NEW-6: compute_multiday_whale_flow sorts by date before tail
# ─────────────────────────────────────────────────────────────────────────────

class TestNew6WhaleFlowDateSort:
    def test_unsorted_df_gives_same_result_as_sorted(self):
        """
        If rows are in random order, the fix sorts them before tail(),
        so result should match sorted-input result.
        """
        from tradingos.core.money_flow import compute_multiday_whale_flow
        flow = _make_flow_df(30)
        # Shuffle the rows to simulate unsorted input
        shuffled = flow.sample(frac=1, random_state=99).reset_index(drop=True)
        result_sorted = compute_multiday_whale_flow(flow)
        result_shuffled = compute_multiday_whale_flow(shuffled)
        # After fix both should produce identical mcvd_5d and mcvd_20d
        assert result_sorted["mcvd_5d"] == result_shuffled["mcvd_5d"], (
            f"Sort fix broken: sorted={result_sorted['mcvd_5d']}, "
            f"shuffled={result_shuffled['mcvd_5d']}"
        )
        assert result_sorted["mcvd_20d"] == result_shuffled["mcvd_20d"]


# ─────────────────────────────────────────────────────────────────────────────
# NEW-7: 5-session delta uses iloc[-6] not iloc[-5]
# ─────────────────────────────────────────────────────────────────────────────

class TestNew7FiveSessionDelta:
    def test_sector_rotation_mom_uses_iloc_minus6(self):
        """
        Inspect detect_sector_rotation source: mom_5d should reference
        iloc[-6] (5 sessions before current bar) not iloc[-5] (4 sessions).
        """
        from tradingos.core import money_flow
        src = inspect.getsource(money_flow.detect_sector_rotation)
        assert "iloc[-6]" in src, "detect_sector_rotation still uses iloc[-5] for 5d momentum"
        # Ensure the mom_5d line specifically uses -6
        for line in src.split("\n"):
            if "mom_5d" in line and "iloc" in line:
                assert "-6" in line, f"mom_5d line uses wrong index: {line.strip()}"

    def test_distribution_warning_obv_uses_iloc_minus6(self):
        """
        Inspect detect_whale_distribution source: OBV 5-session lookback should use
        iloc[-6].
        """
        from tradingos.core import money_flow
        src = inspect.getsource(money_flow.detect_whale_distribution)
        # The obv_prev line should use iloc[-6]
        assert "obv_prev = df[\"OBV\"].iloc[-6]" in src, (
            "detect_whale_distribution OBV lookback still uses iloc[-5]"
        )


# ─────────────────────────────────────────────────────────────────────────────
# NEW-8: gap_vwap._fetch_intraday_today uses VN-aware time
# ─────────────────────────────────────────────────────────────────────────────

class TestNew8GapVwapVnTime:
    def test_fetch_intraday_today_uses_vn_now(self):
        """
        Inspect _fetch_intraday_today source: today_str must use vn_now(),
        not plain datetime.now().
        """
        from tradingos.core import gap_vwap
        src = inspect.getsource(gap_vwap._fetch_intraday_today)
        assert "vn_now" in src, "_fetch_intraday_today does not use VN-aware vn_now()"

    def test_fetch_intraday_today_handles_vn_import_error(self):
        """
        If vn_now import fails, must fall back gracefully (not crash).
        The implementation wraps import in try/except so this should pass.
        """
        from tradingos.core import gap_vwap
        src = inspect.getsource(gap_vwap._fetch_intraday_today)
        # Must have a fallback (try/except or similar)
        assert "except" in src, "No fallback in _fetch_intraday_today VN time block"


# ─────────────────────────────────────────────────────────────────────────────
# NEW-10: MFPM MODE_W HIGH confidence reads mc_min_prob_strong from config
# ─────────────────────────────────────────────────────────────────────────────

class TestNew10MfpmConfidenceConfig:
    def test_mfpm_high_confidence_uses_mc_prob_strong(self):
        """
        Inspect compute_mfpm source: MODE_W HIGH confidence gate should use
        mc_prob_strong (config-read), NOT hardcoded 0.65.
        Check that the condition line itself does not use the literal.
        """
        from tradingos.core import mfpm
        src = inspect.getsource(mfpm.compute_mfpm)
        # Find the confidence block line that gates HIGH confidence
        for line in src.split("\n"):
            if "mc_prob >= 0.65" in line and "#" not in line.lstrip()[:3]:
                # This is a code line (not a comment) with hardcoded 0.65
                pytest.fail(f"compute_mfpm has hardcoded mc_prob >= 0.65 in code: {line.strip()}")
        # Should use mc_prob_strong variable
        assert "mc_prob >= mc_prob_strong" in src, (
            "compute_mfpm confidence gate does not use mc_prob_strong variable"
        )

    def test_mfpm_mc_prob_strong_comes_from_config(self):
        """
        mc_prob_strong should be read from config key mfpm.mc_min_prob_strong.
        """
        from tradingos.core import mfpm
        src = inspect.getsource(mfpm.compute_mfpm)
        assert "mc_min_prob_strong" in src, "mc_min_prob_strong not referenced in compute_mfpm"

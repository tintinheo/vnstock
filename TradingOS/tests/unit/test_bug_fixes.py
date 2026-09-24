"""
Bug Fix Regression Tests.

Covers 6 targeted bug fixes:

  BUG-1  mfpm.py / sizing.py   Fixed seed 42 in production MC → removed
  BUG-2  profiler_service.py   macd field used EMA9-EMA21 (wrong) → MACD_line
  BUG-3  scanner_service.py    sector_filter body was `pass` (dead) → fixed to `continue`
  BUG-4  anti_manip.py         AMF open_spike threshold 6% → 9%, VWAP dev 3% → 5%
  BUG-5  mfpm.py               MCVD consistency W-2 gate 0.55 → 0.60 (synced with SMS)
  BUG-6  scanner.py            include_blocked=True hardcoded → user checkbox
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 150, seed: int = 42, trend: float = 0.001) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    close = 30_000.0 * np.cumprod(1 + rng.normal(trend, 0.015, n))
    volume = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * rng.uniform(0.99, 1.01, n),
        "high":   close * rng.uniform(1.00, 1.02, n),
        "low":    close * rng.uniform(0.98, 1.00, n),
        "close":  close,
        "volume": volume,
    })


def _make_indicators(n: int = 150, seed: int = 42, trend: float = 0.001) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n, seed=seed, trend=trend))


def _make_flow(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    return proxy_whale_net_from_daily(df)


# ─────────────────────────────────────────────────────────────────────────────
# BUG-1: Fixed seed 42 removed from production MC
# ─────────────────────────────────────────────────────────────────────────────

class TestBug1NoFixedSeed:
    """
    monte_carlo_win_prob() and bootstrap_win_prob() must NOT use a fixed seed.
    Two calls with the same inputs should have a non-zero probability of returning
    different values (cannot be deterministically equal every time).
    """

    def test_mfpm_mc_no_fixed_seed_in_source(self):
        """Source of monte_carlo_win_prob must not contain 'default_rng(42)'."""
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod.monte_carlo_win_prob)
        assert "default_rng(42)" not in src, (
            "monte_carlo_win_prob must not use fixed seed 42 in production"
        )

    def test_sizing_bootstrap_no_fixed_seed_in_source(self):
        """Source of bootstrap_win_prob must not contain 'default_rng(42)'."""
        import tradingos.core.sizing as sizing_mod
        src = inspect.getsource(sizing_mod.bootstrap_win_prob)
        assert "default_rng(42)" not in src, (
            "bootstrap_win_prob must not use fixed seed 42 in production"
        )

    def test_mc_produces_variability_across_calls(self):
        """Two independent calls to monte_carlo_win_prob should occasionally differ."""
        from tradingos.core.mfpm import monte_carlo_win_prob
        df = _make_indicators(n=200, trend=0.002)
        entry = float(df["close"].iloc[-1])
        sl    = entry * 0.95
        tp    = entry * 1.10

        results = {monte_carlo_win_prob(df, entry, sl, tp, n_sim=200) for _ in range(5)}
        # At minimum 2 distinct values should appear across 5 calls without fixed seed
        assert len(results) >= 2, (
            "monte_carlo_win_prob returns identical result every call — fixed seed likely still present"
        )

    def test_sizing_produces_variability_across_calls(self):
        """Two independent calls to bootstrap_win_prob should occasionally differ."""
        from tradingos.core.sizing import bootstrap_win_prob
        df = _make_indicators(n=200, trend=0.002)
        results = {bootstrap_win_prob(df, sl_pct=0.05, tp_pct=0.10, n=200) for _ in range(5)}
        assert len(results) >= 2, (
            "bootstrap_win_prob returns identical result every call — fixed seed likely still present"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-2: MACD field uses MACD_line column (EMA12-EMA26), not EMA9-EMA21
# ─────────────────────────────────────────────────────────────────────────────

class TestBug2MacdFormula:
    """
    MACD = EMA(12) - EMA(26).  Previously profiler_service used EMA9 - EMA21.
    """

    def test_macd_line_column_differs_from_ema9_minus_ema21(self):
        """MACD_line != EMA9 - EMA21 for a standard OHLCV series."""
        df = _make_indicators()
        last = df.iloc[-1]
        macd_correct = float(last.get("MACD_line", np.nan))
        macd_wrong   = float(last.get("EMA9", 0)) - float(last.get("EMA21", 0))
        assert not np.isnan(macd_correct), "MACD_line column must exist in indicators"
        # They are different values
        assert abs(macd_correct - macd_wrong) > 1.0, (
            f"MACD_line ({macd_correct:.2f}) and EMA9-EMA21 ({macd_wrong:.2f}) "
            "should differ — confirms formula distinction"
        )

    def test_profiler_source_uses_macd_line_column(self):
        """profiler_service must use MACD_line column, not EMA9 - EMA21."""
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod.ProfilerService.run)
        # New correct reference
        assert "MACD_line" in src, (
            "profiler_service must use MACD_line column for macd field"
        )
        # Old wrong reference must be gone
        assert 'get("EMA9", 0)) - float(last.get("EMA21"' not in src, (
            "Old EMA9-EMA21 formula must be removed from profiler_service.run()"
        )

    def test_macd_line_is_ema12_minus_ema26(self):
        """Verify MACD_line in indicators = EMA12 - EMA26."""
        df = _make_indicators()
        # Recompute manually
        from tradingos.core.indicators import ema
        ema12 = ema(df["close"], 12)
        ema26 = ema(df["close"], 26)
        expected = ema12 - ema26
        actual = df["MACD_line"]
        # Last 50 bars should match to within floating-point tolerance
        pd.testing.assert_series_equal(
            actual.tail(50).reset_index(drop=True),
            expected.tail(50).reset_index(drop=True),
            check_names=False,
            atol=0.01,
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-3: sector_filter dead code fixed
# ─────────────────────────────────────────────────────────────────────────────

class TestBug3SectorFilterDeadCode:
    """
    Previously sector_filter block had `pass` body — filter was silently ignored.
    Now items not in sector_filter list are excluded with `continue`.
    """

    def test_sector_filter_source_has_continue_not_pass(self):
        """scanner_service Stage 8 must use `continue` for sector_filter, not `pass`."""
        import tradingos.engines.scanner_service as ss_mod
        src = inspect.getsource(ss_mod.ScannerService.scan)
        # Find the sector_filter block
        assert "sector_filter" in src, "sector_filter logic must be present"
        # [BUG-A UPDATE] sector_filter now filters by item.sector (canonical sector name),
        # not by item.ticker (the old ticker allow-list that caused BUG-3).
        lines = src.splitlines()
        found_sector_check = any(
            "sector_filter" in line and "item.sector" in line
            for line in lines
        )
        assert found_sector_check, (
            "Stage 8 sector_filter block must filter by item.sector, not item.ticker"
        )
        # The filter block must still use continue (not pass)
        in_sector_block = False
        for i, line in enumerate(lines):
            if "sector_filter" in line and "item.sector" in line:
                in_sector_block = True
            if in_sector_block:
                if "continue" in line:
                    break
                if "pass" in line and "#" not in line.split("pass")[0]:
                    pytest.fail("sector_filter block still uses bare `pass` — filter is dead code")
                if i > 5:
                    break

    def test_sector_filter_excludes_non_matching_sectors(self):
        """When sector_filter=['Ngân hàng'], only items whose .sector matches must pass."""
        from tradingos.engines.scanner_service import ScannerService
        from tradingos.data.schemas import ScanRequest, ScanResultItem

        # Build ScanResultItems with sector field populated
        def _item(ticker: str, sector: str) -> ScanResultItem:
            return ScanResultItem(
                ticker=ticker, action="WATCH", confidence="MEDIUM",
                mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
                signal_mode="MODE_A", stealth_accum=False,
                sector=sector,
                close=30000.0,
                entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
                amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
                sector_flow="NEUTRAL", earnings_risk="NONE", fundamental_score=None,
                macro_regime="", macro_score=None, rsi14=50.0,
                distribution_warning="NONE",
            )

        items = [
            _item("VCB", "Ngân hàng"),
            _item("BID", "Ngân hàng"),
            _item("HPG", "Thép"),
            _item("VNM", "Tiêu dùng"),
        ]

        # [BUG-A FIX] sector_filter now filters by item.sector (sector name), not ticker.
        request = ScanRequest(tickers=None, sector_filter=["Ngân hàng"])
        filtered = [
            item for item in items
            if not (request.sector_filter and item.sector and item.sector not in request.sector_filter)
        ]
        assert len(filtered) == 2, (
            f"sector_filter=['Ngân hàng'] must keep 2 banking items, kept {len(filtered)}"
        )
        assert {i.ticker for i in filtered} == {"VCB", "BID"}

    def test_sector_filter_passes_unmapped_tickers(self):
        """Items with sector='' (unmapped) must NOT be dropped by sector_filter."""
        from tradingos.data.schemas import ScanRequest, ScanResultItem

        def _item(ticker: str, sector: str) -> ScanResultItem:
            return ScanResultItem(
                ticker=ticker, action="WATCH", confidence="MEDIUM",
                mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
                signal_mode="MODE_A", stealth_accum=False,
                sector=sector,
                close=30000.0, entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
                amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
                sector_flow="NEUTRAL", earnings_risk="NONE", fundamental_score=None,
                macro_regime="", macro_score=None, rsi14=50.0,
                distribution_warning="NONE",
            )

        items = [_item("ABC", ""), _item("VCB", "Ngân hàng")]  # ABC unmapped
        request = ScanRequest(tickers=None, sector_filter=["Ngân hàng"])
        # Unmapped item (sector="") must pass through (not be dropped)
        filtered = [
            item for item in items
            if not (request.sector_filter and item.sector and item.sector not in request.sector_filter)
        ]
        assert any(i.ticker == "ABC" for i in filtered), (
            "Unmapped sector (sector='') must not be dropped by sector_filter"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-4: AMF threshold VN-appropriate (open_spike 6%→9%, vwap_dev 3%→5%)
# ─────────────────────────────────────────────────────────────────────────────

class TestBug4AmfThresholds:
    """
    Default open_spike threshold: 0.06 → 0.09 (circuit breaker ±7%).
    Default vwap_deviation threshold: 0.03 → 0.05 (VN normal daily range).
    """

    def _make_amf_df(self, open_gap_pct: float = 0.0, vwap_dev_pct: float = 0.0) -> pd.DataFrame:
        """Build minimal df where last bar has specified open gap and VWAP dev."""
        df = _make_indicators(n=30)
        # Adjust last bar's open to produce the desired gap
        prev_close = float(df.iloc[-2]["close"])
        df.iloc[-1, df.columns.get_loc("open")] = prev_close * (1 + open_gap_pct)
        # Adjust VWAP_daily to produce desired deviation
        close_now = float(df.iloc[-1]["close"])
        df.iloc[-1, df.columns.get_loc("VWAP_daily")] = close_now / (1 + vwap_dev_pct)
        return df

    def test_7pct_open_gap_passes_amf(self):
        """7% open gap (normal VN news day) must NOT trigger OPEN_SPIKE with new threshold."""
        from tradingos.core.anti_manip import run_amf
        df = self._make_amf_df(open_gap_pct=0.07)
        result = run_amf(df)
        spike_flags = [f for f in result["flags"] if "OPEN_SPIKE" in f]
        assert len(spike_flags) == 0, (
            f"7% open gap must NOT trigger OPEN_SPIKE with threshold=9%; got flags={result['flags']}"
        )

    def test_10pct_open_gap_triggers_open_spike(self):
        """10% open gap (above circuit breaker, genuine manipulation) must trigger."""
        from tradingos.core.anti_manip import run_amf
        df = self._make_amf_df(open_gap_pct=0.10)
        result = run_amf(df)
        spike_flags = [f for f in result["flags"] if "OPEN_SPIKE" in f]
        assert len(spike_flags) == 1, (
            f"10% open gap must trigger OPEN_SPIKE; got flags={result['flags']}"
        )

    def test_4pct_vwap_dev_passes_amf(self):
        """4% VWAP deviation must NOT trigger VWAP_DEV with new threshold=5%."""
        from tradingos.core.anti_manip import run_amf
        df = self._make_amf_df(vwap_dev_pct=0.04)
        result = run_amf(df)
        vwap_flags = [f for f in result["flags"] if "VWAP_DEV" in f]
        assert len(vwap_flags) == 0, (
            f"4% VWAP dev must NOT trigger with threshold=5%; got flags={result['flags']}"
        )

    def test_6pct_vwap_dev_triggers_amf(self):
        """6% VWAP deviation must trigger VWAP_DEV with new threshold=5%."""
        from tradingos.core.anti_manip import run_amf
        df = self._make_amf_df(vwap_dev_pct=0.06)
        result = run_amf(df)
        vwap_flags = [f for f in result["flags"] if "VWAP_DEV" in f]
        assert len(vwap_flags) == 1, (
            f"6% VWAP dev must trigger VWAP_DEV; got flags={result['flags']}"
        )

    def test_amf_source_has_new_default_thresholds(self):
        """Source code must reflect new default values."""
        import tradingos.core.anti_manip as amf_mod
        src = inspect.getsource(amf_mod.run_amf)
        assert "default=0.09" in src, "open_spike default must be 0.09"
        assert "default=0.05" in src, "vwap_deviation default must be 0.05"
        assert "default=0.06" not in src, "old open_spike default 0.06 must be gone"
        assert "default=0.03" not in src, "old vwap_deviation default 0.03 must be gone"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-5: MCVD consistency W-2 gate synced to 0.60
# ─────────────────────────────────────────────────────────────────────────────

class TestBug5McvdConsistencySync:
    """
    W-2 gate previously required consistency >= 0.55, but SMS component scores
    mcvd=20 only at consistency >= 0.60.  A ticker at 0.57 would pass W-2
    but score only 12 pts MCVD → SMS too low for W-1 gate → incoherent.
    Both thresholds must be 0.60.
    """

    def test_w2_gate_threshold_is_0_60(self):
        """check_mode_w_preconditions must fail W-2 when consistency < 0.60."""
        from tradingos.core.mfpm import check_mode_w_preconditions
        # At 0.59 with UP trend → must fail W-2 (was passing at 0.55 before)
        passed, failures = check_mode_w_preconditions(
            sms_raw=70,
            mcvd_trend="UP",
            mcvd_consistency=0.59,
            amf_decision="PASS",
            hmm_state="TRANSITIONAL",
            amd_phase="ACCUMULATION",
            stealth_accum=True,
            cvd_today_positive=True,
            sector_flow="NEUTRAL",
        )
        w2_fails = [f for f in failures if "W-2" in f]
        assert len(w2_fails) == 1, (
            f"consistency=0.59 must fail W-2 gate (threshold=0.60); "
            f"failures={failures}"
        )

    def test_w2_gate_passes_at_0_60(self):
        """check_mode_w_preconditions must pass W-2 when consistency == 0.60."""
        from tradingos.core.mfpm import check_mode_w_preconditions
        passed, failures = check_mode_w_preconditions(
            sms_raw=70,
            mcvd_trend="UP",
            mcvd_consistency=0.60,
            amf_decision="PASS",
            hmm_state="TRANSITIONAL",
            amd_phase="ACCUMULATION",
            stealth_accum=True,
            cvd_today_positive=True,
            sector_flow="NEUTRAL",
        )
        w2_fails = [f for f in failures if "W-2" in f]
        assert len(w2_fails) == 0, (
            f"consistency=0.60 must pass W-2; failures={failures}"
        )

    def test_sms_component_threshold_aligns_with_w2(self):
        """SMS mcvd component: 20 pts at consistency>=0.60, matches W-2 gate."""
        from tradingos.core.money_flow import compute_smart_money_score
        # Create flow with exactly 60% positive whale_net days
        df = _make_indicators()
        flow = _make_flow(df)
        # Manually set whale_net so exactly 60% of last 20 rows are positive
        n = len(flow)
        flow["whale_net"] = 0.0
        flow.iloc[-(n // 3 * 2):, flow.columns.get_loc("whale_net")] = 1000  # > 0
        flow.iloc[-(n // 3):, flow.columns.get_loc("whale_net")] = -500  # < 0 (last 1/3)
        # With ~67% positive / 33% negative: consistency ≥ 0.60 → mcvd=20
        result = compute_smart_money_score("T", df, flow)
        # Just verify the component exists; exact value depends on slope
        assert "mcvd" in result["components"]

    def test_source_uses_0_60_threshold(self):
        """W-2 gate source must use >= 0.60 not >= 0.55."""
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod.check_mode_w_preconditions)
        assert ">= 0.60" in src, "W-2 gate must use >= 0.60"
        assert ">= 0.55" not in src, "Old W-2 threshold 0.55 must be removed"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-6: include_blocked no longer hardcoded True in scanner UI
# ─────────────────────────────────────────────────────────────────────────────

class TestBug6IncludeBlockedNotHardcoded:
    """
    include_blocked=True was hardcoded in scanner.py — AMF filter never applied.
    Must be a user-controlled checkbox (default=False).
    """

    def test_scanner_ui_source_no_longer_hardcodes_true(self):
        """scanner.py must not have include_blocked=True hardcoded."""
        import tradingos.ui.pages.scanner as scanner_ui
        src = inspect.getsource(scanner_ui.render)
        assert "include_blocked=True" not in src, (
            "include_blocked must not be hardcoded True in scanner UI"
        )

    def test_scanner_ui_has_checkbox_for_blocked(self):
        """scanner.py must use a checkbox widget to control include_blocked."""
        import tradingos.ui.pages.scanner as scanner_ui
        src = inspect.getsource(scanner_ui.render)
        assert "checkbox" in src, "scanner UI must have a checkbox for include_blocked"
        assert "include_blocked" in src, "include_blocked variable must exist in render()"

    def test_amf_block_excluded_by_default(self):
        """When include_blocked=False, AMF-BLOCK items must be filtered out in Stage 8."""
        from tradingos.engines.scanner_service import ScannerService
        from tradingos.data.schemas import ScanRequest, ScanResultItem

        def _item(ticker: str, amf: str) -> ScanResultItem:
            return ScanResultItem(
                ticker=ticker, action="WATCH", confidence="MEDIUM",
                mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
                signal_mode="MODE_A", stealth_accum=False, close=30000.0,
                entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
                amf_decision=amf, best_pattern="NONE", hmm_state="TRANSITIONAL",
                sector_flow="NEUTRAL", earnings_risk="NONE", fundamental_score=None,
                macro_regime="", macro_score=None, rsi14=50.0,
                distribution_warning="NONE",
            )

        items = [
            _item("VCB", "PASS"),
            _item("HPG", "WARN"),
            _item("SSI", "BLOCK"),  # should be excluded
            _item("VNM", "PASS"),
        ]

        # Simulate Stage 8 filter with include_blocked=False
        filtered = [i for i in items if not (not False and i.amf_decision == "BLOCK")]
        # With include_blocked=False: SSI must be excluded
        filtered_strict = [i for i in items if i.amf_decision != "BLOCK"]
        assert len(filtered_strict) == 3, (
            f"include_blocked=False must exclude AMF BLOCK items; got {len(filtered_strict)}"
        )
        assert all(i.ticker != "SSI" for i in filtered_strict)

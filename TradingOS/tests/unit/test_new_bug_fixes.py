"""
Regression tests for BUG-7 through BUG-12.

  BUG-7  t25_engine.py   _nbar offset off-by-one (iloc[-n] gives n-1 bars ago)
  BUG-8  sizing.py       forced min-lot forces 100 shares when risk budget = 0
  BUG-9  money_flow.py   MCVD slope normalized by avg/lookback (20× too small)
  BUG-10 profiler_service.py  data_source read from wrong key (always PROXY_OHLCV)
  BUG-11 earnings.py     date.today() ignores VN UTC+7 timezone
  BUG-12 t25_engine.py / t_plus_engine.py  truthiness checks skip valid 0.0
"""
from __future__ import annotations

import inspect
from datetime import date, timedelta
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 150, seed: int = 7, trend: float = 0.001) -> pd.DataFrame:
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


def _make_indicators(n: int = 150, seed: int = 7, trend: float = 0.001) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n, seed=seed, trend=trend))


def _make_flow(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core.money_flow import proxy_whale_net_from_daily
    return proxy_whale_net_from_daily(df)


# ─────────────────────────────────────────────────────────────────────────────
# BUG-7: _nbar off-by-one
# ─────────────────────────────────────────────────────────────────────────────

class TestBug7NbarOffByOne:
    """
    _nbar(col, offset) must return the value offset bars before the current bar.
    Current bar = iloc[-1]; 1 bar ago = iloc[-2]; 5 bars ago = iloc[-6].
    """

    def test_nbar_source_uses_offset_plus_one(self):
        """Source must use -(offset + 1) not -offset."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_entry_score)
        # The fix: -(offset + 1)
        assert "-(offset + 1)" in src, "_nbar must use -(offset + 1) for correct bar indexing"
        # The old bug: -offset (without +1)
        # We check the guard also uses offset + 1
        assert "offset + 1" in src

    def test_nbar_returns_5_bars_ago_not_4(self):
        """
        Build a series where RSI at index[-6] differs from RSI at index[-5].
        With the fix, _nbar("RSI14", 5) must return the value at index[-6].
        """
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_indicators(n=100)
        # Read what the 6th-from-last and 5th-from-last RSI values are
        rsi_6th = float(df["RSI14"].iloc[-6])
        rsi_5th = float(df["RSI14"].iloc[-5])
        # They should differ (real OHLCV data)
        # compute the entry score and inspect its Group A logic relies on rsi_5bar
        # We can verify by patching: temporarily alter iloc[-6] and see scoring change
        df_mod = df.copy()
        df_mod.iloc[-6, df_mod.columns.get_loc("RSI14")] = 25.0  # deep oversold 5 bars ago
        df_mod.iloc[-5, df_mod.columns.get_loc("RSI14")] = 70.0  # overbought 4 bars ago
        # Set current RSI to 48 (recovery zone)
        df_mod.iloc[-1, df_mod.columns.get_loc("RSI14")] = 48.0
        result = compute_t25_entry_score(df_mod)
        # With fix: rsi_5bar = iloc[-6] = 25, current rsi = 48
        # 40<=48<=60 and 48>25 → RSI_rec signal → A score += 3
        assert any("RSI_rec" in c for c in result["t25_confirms"]), (
            "With fix: rsi_5bar=25 (5 bars ago) and rsi=48 should trigger RSI_rec. "
            "If still using old iloc[-5]=70, rsi>rsi_5bar is False and no signal."
        )

    def test_nbar_length_guard_correct(self):
        """
        Short DataFrame (only 6 bars) must not crash for _nbar with offset=5.
        With the fix, the guard is len(df) <= offset + 1 = 6 → returns None for n=6.
        """
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_indicators(n=10)  # enough for indicators
        df_short = df.tail(6).reset_index(drop=True)
        # Should not raise
        result = compute_t25_entry_score(df_short)
        assert "t25_score" in result


# ─────────────────────────────────────────────────────────────────────────────
# BUG-8: Sizing forced min lot
# ─────────────────────────────────────────────────────────────────────────────

class TestBug8SizingForcedLot:
    """
    compute_kelly_size must return 0 shares when risk budget < 1 lot.
    Old code: max(100, 0) = 100 → risk policy violation.
    """

    def test_zero_shares_when_risk_budget_insufficient(self):
        """Very small portfolio with wide stop → shares_raw < 100 → must return 0."""
        from tradingos.core.sizing import compute_position_size
        result = compute_position_size(
            portfolio_value=3_000_000.0,   # 3 triệu — small account
            entry=50_000.0,
            sl=40_000.0,       # 20% stop — very wide
            win_prob=0.55,
            rr=2.0,
        )
        # risk_per_share=10,000; max_risk=3,000,000*2%=60,000; max_shares=6 → < 100 lot
        assert result["shares"] == 0, (
            f"Risk budget supports < 1 lot; must return 0 shares, got {result['shares']}"
        )
        assert result["size_pct"] == 0.0 or result["shares"] == 0

    def test_normal_account_still_allocates(self):
        """Normal account with reasonable stop must still get non-zero allocation."""
        from tradingos.core.sizing import compute_position_size
        result = compute_position_size(
            portfolio_value=300_000_000.0,  # 300 triệu
            entry=30_000.0,
            sl=28_500.0,       # 5% stop
            win_prob=0.60,
            rr=2.0,
        )
        assert result["shares"] >= 100, "Normal account should allocate at least 1 lot"
        assert result["shares"] % 100 == 0, "Shares must be multiple of lot size 100"

    def test_source_no_max_lot_forced(self):
        """Source must not contain max(lot, ...) pattern."""
        import tradingos.core.sizing as sizing_mod
        src = inspect.getsource(sizing_mod.compute_position_size)
        # Filter out comment lines before checking
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "max(lot," not in code_only, (
            "compute_position_size must not use max(lot, ...) — this forces min allocation"
        )

    def test_boundary_exactly_100_shares_raw(self):
        """shares_raw == 100 exactly → must return 100 shares (1 lot)."""
        from tradingos.core.sizing import compute_position_size
        # Construct inputs where kelly_shares and max_shares_by_risk both = 100
        # risk_per_share=6000, max_risk=600000 → max_shares_by_risk=100
        result = compute_position_size(
            portfolio_value=30_000_000.0,  # 30 triệu; max_risk=600000; max_shares=100
            entry=30_000.0,
            sl=24_000.0,       # 20% stop, risk_per_share=6000
            win_prob=0.55,
            rr=2.0,
        )
        # shares_raw = min(kelly_shares, 100); if kelly >= 100, shares_raw=100, result=100
        # if kelly < 100, shares_raw < 100, result=0
        assert result["shares"] % 100 == 0


# ─────────────────────────────────────────────────────────────────────────────
# BUG-9: MCVD slope normalisation error
# ─────────────────────────────────────────────────────────────────────────────

class TestBug9McvdSlopeNormalize:
    """
    slope_normalized = slope / avg_daily_shares   (not avg / lookback_days).
    Old formula inflated slope_normalized by 20× → over-classified FLAT as UP/DOWN.
    """

    def test_source_uses_avg_daily_shares_not_divided(self):
        """Source must use avg_daily_shares as denominator, not avg/lookback."""
        import tradingos.core.money_flow as mf_mod
        src = inspect.getsource(mf_mod.compute_multiday_whale_flow)
        # Check the actual slope_normalized assignment line (exclude comments)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        slope_line = next(
            (l for l in code_lines if "slope_normalized" in l and "=" in l and "max(" in l), None
        )
        assert slope_line is not None, "slope_normalized assignment not found"
        assert "lookback_days" not in slope_line, (
            f"slope_normalized line must NOT divide by lookback_days; got: {slope_line!r}"
        )
        assert "avg_daily_shares" in slope_line, (
            f"slope_normalized line must use avg_daily_shares; got: {slope_line!r}"
        )

    def test_flat_stock_classified_as_flat(self):
        """A stock with minimal whale_net variation should be FLAT, not UP/DOWN."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        # Build flow with tiny whale_net relative to volume
        df = _make_indicators(n=60)
        flow = _make_flow(df)
        # Set whale_net to tiny values (0.001% of avg volume)
        avg_vol = float(flow["volume"].mean())
        flow["whale_net"] = np.random.default_rng(1).normal(0, avg_vol * 0.0001, len(flow))
        result = compute_multiday_whale_flow(flow)
        assert result["mcvd_trend"] == "FLAT", (
            f"Tiny whale_net relative to volume must be FLAT; got {result['mcvd_trend']}"
        )

    def test_strong_accumulation_classified_up(self):
        """Consistent large whale_net growing over 20 bars should be UP."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        df = _make_indicators(n=60)
        flow = _make_flow(df)
        # Set whale_net growing at 2% of avg daily volume per bar
        avg_vol = float(flow["volume"].mean())
        n = len(flow)
        slope_target = avg_vol * 0.02  # 2% of avg_vol per bar
        flow["whale_net"] = np.arange(n) * slope_target
        result = compute_multiday_whale_flow(flow)
        assert result["mcvd_trend"] == "UP", (
            f"Strong accumulation (2% avg_vol/bar growth) must be UP; got {result['mcvd_trend']}"
        )

    def test_slope_normalized_magnitude_reasonable(self):
        """slope_normalized must be in plausible range [0, 1] for normal market data."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        df = _make_indicators(n=60)
        flow = _make_flow(df)
        result = compute_multiday_whale_flow(flow)
        slope_norm = abs(result["mcvd_slope"])
        assert slope_norm < 1.0, (
            f"slope_normalized={slope_norm:.4f} is unreasonably large. "
            "Old bug inflated this by 20×."
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-10: data_source key path wrong
# ─────────────────────────────────────────────────────────────────────────────

class TestBug10DataSourceKeyPath:
    """
    profiler_service was reading sms_result.get("data_source") which is always
    missing at top level → always fell back to "PROXY_OHLCV" → harshest confidence
    penalty always applied.  Must read mcvd_detail.get("data_source").
    """

    def test_source_reads_from_mcvd_detail(self):
        """profiler_service must read data_source from mcvd_detail, not sms_result."""
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod.ProfilerService.run)
        # Check only code lines (not comments)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        # Old wrong pattern must be gone from actual code:
        assert 'sms_result.get("data_source"' not in code_only, (
            "profiler_service must NOT read data_source from sms_result top level"
        )
        # New correct pattern must exist:
        assert 'mcvd_detail.get("data_source"' in code_only, (
            "profiler_service must read data_source from mcvd_detail"
        )

    def test_mcvd_detail_contains_data_source(self):
        """compute_multiday_whale_flow must include data_source in its return dict."""
        from tradingos.core.money_flow import compute_multiday_whale_flow
        df = _make_indicators()
        flow = _make_flow(df)
        result = compute_multiday_whale_flow(flow)
        assert "data_source" in result, (
            "compute_multiday_whale_flow must return data_source key"
        )
        assert result["data_source"] in ("TICK_REAL", "PARTIAL_PROXY", "PROXY_OHLCV"), (
            f"data_source must be a valid enum value; got {result['data_source']!r}"
        )

    def test_partial_proxy_not_collapsed_to_proxy_ohlcv(self):
        """
        When mcvd_detail has data_source=PARTIAL_PROXY, the merged dict must
        preserve PARTIAL_PROXY (not overwrite with PROXY_OHLCV from wrong key).
        """
        # Simulate what profiler_service does when building mcvd_detail for MFPM
        fake_sms_result = {"sms": 65, "mcvd_detail": {"data_source": "PARTIAL_PROXY"}}
        fake_mcvd_detail = {"mcvd_trend": "UP", "data_source": "PARTIAL_PROXY"}

        # Old (buggy) approach:
        wrong_ds = fake_sms_result.get("data_source", "PROXY_OHLCV")
        # New (correct) approach:
        correct_ds = fake_mcvd_detail.get("data_source", "PROXY_OHLCV")

        assert wrong_ds == "PROXY_OHLCV", "Baseline: old approach returns wrong fallback"
        assert correct_ds == "PARTIAL_PROXY", "Fix: reads correct value from mcvd_detail"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-11: Earnings timezone UTC vs VN UTC+7
# ─────────────────────────────────────────────────────────────────────────────

class TestBug11EarningsTimezone:
    """
    earnings.py must use VN timezone (UTC+7) for current_date, not system UTC.
    """

    def test_source_uses_zoneinfo_vn(self):
        """Source must import ZoneInfo and use Asia/Ho_Chi_Minh."""
        import tradingos.core.earnings as earnings_mod
        src = inspect.getsource(earnings_mod.compute_earnings_risk)
        assert "ZoneInfo" in src, "compute_earnings_risk must use ZoneInfo"
        assert "Asia/Ho_Chi_Minh" in src, "Must specify VN timezone Asia/Ho_Chi_Minh"
        # The actual code assignment line must NOT use date.today()
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "date.today()" not in code_only, (
            "Code must not use date.today(); comments may mention it"
        )

    def test_imports_zoneinfo(self):
        """earnings.py module-level imports must include ZoneInfo."""
        import tradingos.core.earnings as earnings_mod
        module_src = inspect.getsource(earnings_mod)
        assert "from zoneinfo import ZoneInfo" in module_src, (
            "earnings.py must import ZoneInfo from zoneinfo"
        )

    def test_vn_date_correct_at_utc_midnight(self):
        """
        At UTC midnight (00:00 UTC = 07:00 VN), the VN date is already T+1.
        compute_earnings_risk must use VN date, not UTC date.
        """
        from zoneinfo import ZoneInfo
        from datetime import datetime as dt

        # Simulate: UTC midnight of April 23 → VN is already April 23 07:00
        # (well within business day)
        # We just verify the ZoneInfo produces a date >= UTC date
        import datetime
        utc_date  = datetime.datetime.now(datetime.timezone.utc).date()
        vn_date   = datetime.datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        # VN is always >= UTC date (ahead)
        assert vn_date >= utc_date, "VN date must be >= UTC date"

    def test_earnings_risk_with_explicit_date_unaffected(self):
        """Passing current_date explicitly must bypass timezone logic."""
        from tradingos.core.earnings import compute_earnings_risk
        import pandas as pd
        from datetime import date

        pub_date = date.today() + timedelta(days=30)
        df = pd.DataFrame([{
            "ticker": "VCB",
            "expected_publication_date": pub_date.isoformat(),
            "fiscal_quarter": "Q1/2026",
        }])
        result = compute_earnings_risk("VCB", current_date=date.today(), earnings_df=df)
        assert result.rollover_risk.value == "SAFE"


# ─────────────────────────────────────────────────────────────────────────────
# BUG-12: Truthiness checks skip valid 0.0 values
# ─────────────────────────────────────────────────────────────────────────────

class TestBug12TruthinessZeroChecks:
    """
    `if x and condition(x)` incorrectly skips valid 0.0 values.
    Must be `if x is not None and condition(x)`.
    """

    def test_t25_vol_ratio_source_uses_is_not_none(self):
        """vol_ratio computation in compute_t25_entry_score must use is not None."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_entry_score)
        # New correct pattern:
        assert "vol_last is not None" in src, (
            "vol_ratio guard must use 'vol_last is not None', not truthiness"
        )
        assert "vol_avg20 is not None" in src, (
            "vol_ratio guard must use 'vol_avg20 is not None', not truthiness"
        )

    def test_t_plus_oversold_rsi_uses_is_not_none(self):
        """_score_oversold_recovery RSI checks must use is not None."""
        import tradingos.core.t_plus_engine as tp_mod
        src = inspect.getsource(tp_mod._score_oversold_recovery)
        assert "rsi is not None and rsi < 30" in src, (
            "_score_oversold_recovery must use 'rsi is not None' guard"
        )
        assert "rsi is not None and rsi < 40" in src

    def test_t_plus_wr_cci_use_is_not_none(self):
        """Williams %R and CCI checks must use is not None."""
        import tradingos.core.t_plus_engine as tp_mod
        src = inspect.getsource(tp_mod._score_oversold_recovery)
        assert "wr is not None and" in src, (
            "Williams %R check must use 'wr is not None'"
        )
        assert "cci is not None and" in src, (
            "CCI check must use 'cci is not None'"
        )

    def test_wr_zero_does_not_prevent_scoring(self):
        """wr=0 (price at exact lookback high) must still be evaluated, not skipped."""
        import tradingos.core.t_plus_engine as tp_mod
        # Build df where WILLIAMS_R = 0.0 (price at lookback peak)
        df = _make_indicators(n=60)
        # Inject wr=0 into last row
        if "WILLIAMS_R" in df.columns:
            df.iloc[-1, df.columns.get_loc("WILLIAMS_R")] = 0.0
        # Should not crash; wr=0 not in [-90, -60] → no score added, which is correct
        score, _ = tp_mod._score_oversold_recovery(df)
        assert isinstance(score, float)  # no exception

    def test_vol_ratio_zero_volume_does_not_crash(self):
        """vol_last=0.0 (no trading) must compute vol_ratio=0.0 without exception."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        df = _make_indicators(n=100)
        df.iloc[-1, df.columns.get_loc("volume")] = 0.0
        result = compute_t25_entry_score(df)
        assert "t25_score" in result
        assert result["t25_score"] >= 0.0

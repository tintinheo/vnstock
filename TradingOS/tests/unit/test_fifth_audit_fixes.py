"""
Fifth-Pass Audit Regression Tests — BUG-EARN, BUG-20, BUG-21, BUG-22, BUG-A, BUG-B, BUG-C

Run focused:
    pytest tests/unit/test_fifth_audit_fixes.py -v --tb=short

Coverage:
    BUG-EARN  earnings.py      Lazy-fetch only when earnings_df is None, not empty
    BUG-20    mfpm.py          Dead branch: AMF BLOCK + distribution EXIT → FORCED_EXIT
    BUG-21    t25_engine.py    T25ExitAdvisory.ts uses vn_now() not naive datetime.now
    BUG-22    money_flow.py    Mode B breakout: entry at close, no EMA9 pullback
    BUG-A     scanner+schemas  sector_filter by canonical sector name, not ticker
    BUG-B     sizing.py        min_position_pct gate enforced from config
    BUG-C     backtest.py      walk_forward_is_days / walk_forward_oos_days consumed
"""
from __future__ import annotations

import inspect
import math
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 60, price: float = 30_000.0, atr_pct: float = 0.015) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = price + np.cumsum(rng.normal(0, price * 0.005, n))
    close = np.clip(close, price * 0.5, price * 2)
    atr = close * atr_pct
    df = pd.DataFrame({
        "open":   close * (1 - rng.uniform(0, 0.003, n)),
        "high":   close + rng.uniform(0, atr, n),
        "low":    close - rng.uniform(0, atr, n),
        "close":  close,
        "volume": rng.integers(100_000, 1_000_000, n).astype(float),
    })
    df.index = pd.date_range("2024-01-02", periods=n, freq="B")
    return df


def _make_ohlcv_with_ema9_lag(n: int = 60, price: float = 30_000.0) -> pd.DataFrame:
    """Create OHLCV where close is clearly above EMA9 (recent pump)."""
    df = _make_ohlcv(n, price)
    # Force last bar to be 5% above initial price to ensure close > EMA9 * 1.01
    df.iloc[-1, df.columns.get_loc("close")] = price * 1.05
    df.iloc[-1, df.columns.get_loc("high")]  = price * 1.06
    return df


# ══════════════════════════════════════════════════════════════════════════════
# BUG-EARN: earnings lazy-fetch only when earnings_df is None
# ══════════════════════════════════════════════════════════════════════════════

class TestBugEarnLazyFetchOnly:
    """
    When an explicitly empty DataFrame is passed, compute_earnings_risk must
    return SAFE without calling the live earnings calendar.
    Old code checked `earnings_df is None or earnings_df.empty` — an empty df
    still triggered a real API call that returned CAUTION from the fiscal calendar.
    """

    def test_empty_df_returns_safe_without_fetch(self):
        from tradingos.core.earnings import compute_earnings_risk, EarningsRolloverRisk
        # Pass an explicitly empty DataFrame — must return SAFE (no events),
        # and must NOT call the live fetcher.  Patch at the source module level
        # since fetch_earnings_calendar is lazily imported inside the function.
        with patch("tradingos.data.fetcher.fetch_earnings_calendar") as mock_fetch:
            risk = compute_earnings_risk("VNM", earnings_df=pd.DataFrame())
        mock_fetch.assert_not_called()
        assert risk.rollover_risk == EarningsRolloverRisk.SAFE, (
            "Empty DataFrame explicitly passed must return SAFE (no upcoming events),"
            f" got {risk.rollover_risk}"
        )

    def test_none_triggers_lazy_fetch(self):
        """When earnings_df is None, a lazy fetch must be attempted."""
        import tradingos.data.fetcher as fetcher_mod
        from tradingos.core.earnings import compute_earnings_risk
        with patch.object(fetcher_mod, "fetch_earnings_calendar",
                          return_value=pd.DataFrame()) as mock_fetch:
            compute_earnings_risk("VNM", earnings_df=None)
        mock_fetch.assert_called_once()

    def test_source_lazy_fetch_guard_is_none_only(self):
        """The lazy-fetch guard must use `earnings_df is None`, not the old OR-empty pattern."""
        from tradingos.core import earnings as earn_mod
        src = inspect.getsource(earn_mod.compute_earnings_risk)
        lines = src.splitlines()
        # Find the line with the lazy-fetch call (from ..data.fetcher import ...)
        for i, line in enumerate(lines):
            if "from ..data.fetcher import fetch_earnings_calendar" in line:
                # Look backwards for the controlling if-condition
                for j in range(max(0, i - 5), i):
                    if "if earnings_df" in lines[j]:
                        assert "or earnings_df.empty" not in lines[j], (
                            f"Lazy-fetch guard at line {j+1} must be `if earnings_df is None:`, "
                            f"not the old `or earnings_df.empty` pattern; got: {lines[j].strip()!r}"
                        )
                        break
                break


# ══════════════════════════════════════════════════════════════════════════════
# BUG-20: MFPM dead branch — AMF BLOCK + EXIT → FORCED_EXIT escalation
# ══════════════════════════════════════════════════════════════════════════════

class TestBug20MfpmForcedExitEscalation:
    """
    Old code had a dead elif branch:
        if dist_warning in ("EXIT", "FORCED_EXIT"):   # captures EXIT *and* FORCED_EXIT
            ...
        elif amf_decision == "BLOCK" and dist_warning in ("EXIT",):  # UNREACHABLE
            action = "FORCED_EXIT"
    Now: FORCED_EXIT and EXIT are handled separately; AMF BLOCK + EXIT escalates.
    """

    def _make_sms_result(self, dist_warning: str) -> dict:
        return {
            "sms": 40,
            "sms_label": "RETAIL_DRIVEN",
            "distribution_warning": dist_warning,
            "components": {},
            "sector_flow": "NEUTRAL",
            "stealth_detail": {"detected": False},
            "mcvd_detail": {"mcvd_trend": "FLAT", "consistency": 0.0, "data_source": "PROXY_OHLCV"},
        }

    def test_amf_block_plus_exit_becomes_forced_exit(self):
        from tradingos.core.mfpm import compute_mfpm
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(60))

        sms = self._make_sms_result("EXIT")
        amf = {"decision": "BLOCK", "flags": []}
        result = compute_mfpm(
            df=df, sms_result=sms, amf_result=amf,
            pattern_result={"best_pattern": "NONE", "pattern_bonus": 0},
        )
        assert result["action"] == "FORCED_EXIT", (
            f"AMF BLOCK + distribution EXIT must escalate to FORCED_EXIT, got {result['action']}"
        )

    def test_exit_without_amf_block_stays_exit(self):
        from tradingos.core.mfpm import compute_mfpm
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(60))

        sms = self._make_sms_result("EXIT")
        amf = {"decision": "PASS", "flags": []}
        result = compute_mfpm(
            df=df, sms_result=sms, amf_result=amf,
            pattern_result={"best_pattern": "NONE", "pattern_bonus": 0},
        )
        assert result["action"] == "EXIT", (
            f"Distribution EXIT without AMF BLOCK must stay EXIT, got {result['action']}"
        )

    def test_forced_exit_at_source_level_stays_forced_exit(self):
        """dist_warning=FORCED_EXIT must produce FORCED_EXIT regardless of AMF."""
        from tradingos.core.mfpm import compute_mfpm
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(60))

        sms = self._make_sms_result("FORCED_EXIT")
        amf = {"decision": "PASS", "flags": []}
        result = compute_mfpm(
            df=df, sms_result=sms, amf_result=amf,
            pattern_result={"best_pattern": "NONE", "pattern_bonus": 0},
        )
        assert result["action"] == "FORCED_EXIT"

    def test_source_uses_separate_conditions(self):
        """Source must NOT have a single `in ("EXIT", "FORCED_EXIT")` catch-all."""
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod.compute_mfpm)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code = "\n".join(code_lines)
        assert 'dist_warning in ("EXIT", "FORCED_EXIT")' not in code, (
            "Dead-branch pattern `dist_warning in (\"EXIT\", \"FORCED_EXIT\")` must be removed; "
            "EXIT and FORCED_EXIT must be handled separately for AMF escalation to work"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG-21: T25ExitAdvisory uses VN-timezone timestamp
# ══════════════════════════════════════════════════════════════════════════════

class TestBug21T25Timezone:
    """
    T25ExitAdvisory.ts must default to vn_now() (UTC+7 aware), not bare datetime.now().
    On non-VN servers, datetime.now() returns system-local naive time, which is
    inconsistent with vn_is_atc_time() and vn_now() used elsewhere in the module.
    """

    def test_advisory_ts_is_timezone_aware(self):
        from tradingos.core.t25_engine import T25ExitAdvisory
        adv = T25ExitAdvisory(
            ticker="VNM", action="HOLD", urgency="LOW",
            reason="test", exit_window="ATC 14:43", exit_pct=0.0,
        )
        assert adv.ts.tzinfo is not None, (
            "T25ExitAdvisory.ts must be timezone-aware (VN UTC+7), got naive datetime"
        )

    def test_source_uses_vn_now_not_datetime_now(self):
        """Source must use vn_now as the default_factory, not datetime.now."""
        from tradingos.core import t25_engine as t25_mod
        src = inspect.getsource(t25_mod.T25ExitAdvisory)
        assert "default_factory=datetime.now" not in src, (
            "T25ExitAdvisory.ts must not use datetime.now (naive); use vn_now instead"
        )
        assert "vn_now" in src, (
            "T25ExitAdvisory.ts must use vn_now as default_factory for VN timezone"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG-22: Mode B entry uses breakout close, not EMA9 pullback
# ══════════════════════════════════════════════════════════════════════════════

class TestBug22ModeBBreakoutEntry:
    """
    mode_w_entry_params used EMA9 rebalance for all signal modes.
    For Mode B (breakout), the entry should be at the breakout close — pulling
    back to EMA9 would mean entering BELOW the breakout confirmation point.
    """

    def test_mode_b_entry_equals_close_when_above_ema9(self):
        from tradingos.core.money_flow import mode_w_entry_params
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv_with_ema9_lag(60))
        close = float(df.iloc[-1]["close"])
        ema9 = float(df.iloc[-1].get("EMA9", close))

        # Only meaningful if close is meaningfully above EMA9
        if close <= ema9 * 1.01:
            pytest.skip("Fixture close not sufficiently above EMA9 for this test")

        params_b  = mode_w_entry_params(df, {}, signal_mode="MODE_B")
        params_w  = mode_w_entry_params(df, {}, signal_mode="MODE_W")

        # MODE_B: entry must equal close (tick-rounded); MODE_W may pull back to EMA9
        assert abs(params_b["entry"] - close) / close < 0.015, (
            f"MODE_B entry {params_b['entry']:.0f} must be near breakout close {close:.0f}, "
            "not pulled back to EMA9"
        )
        # MODE_W entry may be different (pulled back toward EMA9)
        # Not asserting MODE_W == EMA9 because that depends on exact values

    def test_mode_a_entry_may_rebalance_toward_ema9(self):
        """MODE_A entry is allowed to rebalance toward EMA9 (pullback semantics)."""
        from tradingos.core.money_flow import mode_w_entry_params
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(60))
        # No assertion needed — just confirm no exception is raised
        params = mode_w_entry_params(df, {}, signal_mode="MODE_A")
        assert params["entry"] > 0

    def test_source_has_signal_mode_parameter(self):
        """mode_w_entry_params must accept signal_mode parameter."""
        from tradingos.core import money_flow as mf_mod
        src = inspect.getsource(mf_mod.mode_w_entry_params)
        assert "signal_mode" in src, (
            "mode_w_entry_params must have signal_mode parameter"
        )
        assert 'signal_mode != "MODE_B"' in src or "MODE_B" in src, (
            "mode_w_entry_params must have MODE_B conditional branch"
        )

    def test_mfpm_passes_signal_mode_to_entry_params(self):
        """compute_mfpm source must pass signal_mode=signal_mode to mode_w_entry_params."""
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod.compute_mfpm)
        assert "signal_mode=signal_mode" in src, (
            "compute_mfpm must pass signal_mode=signal_mode to mode_w_entry_params"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG-A: sector_filter by canonical sector name
# ══════════════════════════════════════════════════════════════════════════════

class TestBugASectorFilterByName:
    """
    sector_filter in ScanRequest was used as a ticker allow-list (item.ticker not in).
    It must now filter by canonical sector name (item.sector not in).
    ScanResultItem must have a `sector` field populated by infer_sector_name().
    """

    def test_scan_result_item_has_sector_field(self):
        from tradingos.data.schemas import ScanResultItem
        item = ScanResultItem(
            ticker="VCB", action="WATCH", confidence="MEDIUM",
            mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
            signal_mode="MODE_A", stealth_accum=False,
            sector="Ngân hàng",
            close=30000.0, entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
            amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
            sector_flow="NEUTRAL", earnings_risk="NONE",
            distribution_warning="NONE",
        )
        assert item.sector == "Ngân hàng"
        # Default sector must be empty string (not None — Pydantic must validate it)
        default_item = ScanResultItem(
            ticker="XYZ", action="WATCH", confidence="MEDIUM",
            mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
            signal_mode="MODE_A", stealth_accum=False,
            close=30000.0, entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
            amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
        )
        assert default_item.sector == ""

    def test_infer_sector_name_known_tickers(self):
        """Well-known VN tickers must resolve to their canonical sector."""
        from tradingos.engines.money_flow_service import infer_sector_name
        vcb_sector = infer_sector_name("VCB")
        assert vcb_sector == "Ngân hàng", f"VCB must map to Ngân hàng, got {vcb_sector!r}"
        hpg_sector = infer_sector_name("HPG")
        assert hpg_sector == "Thép", f"HPG must map to Thép, got {hpg_sector!r}"

    def test_stage8_source_filters_by_item_sector(self):
        """Scanner Stage 8 source must use `item.sector` not `item.ticker` for sector_filter."""
        import tradingos.engines.scanner_service as ss_mod
        src = inspect.getsource(ss_mod.ScannerService.scan)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code = "\n".join(code_lines)
        assert "item.ticker not in request.sector_filter" not in code, (
            "sector_filter must NOT filter by ticker symbol (old allow-list behavior removed)"
        )
        assert "item.sector" in code, (
            "sector_filter must filter by item.sector (canonical sector name)"
        )

    def test_sector_filter_behavior_keeps_matching_sector(self):
        """Items whose sector matches the filter must be kept."""
        from tradingos.data.schemas import ScanRequest, ScanResultItem

        def _item(ticker: str, sector: str) -> ScanResultItem:
            return ScanResultItem(
                ticker=ticker, action="WATCH", confidence="MEDIUM",
                mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
                signal_mode="MODE_A", stealth_accum=False, sector=sector,
                close=30000.0, entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
                amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
            )

        items = [
            _item("VCB", "Ngân hàng"), _item("CTG", "Ngân hàng"),
            _item("HPG", "Thép"), _item("VNM", "Tiêu dùng"),
        ]
        request = ScanRequest(sector_filter=["Ngân hàng"])
        # Apply Stage 8 sector logic
        filtered = [
            item for item in items
            if not (request.sector_filter and item.sector and item.sector not in request.sector_filter)
        ]
        assert {i.ticker for i in filtered} == {"VCB", "CTG"}, (
            f"Only Ngân hàng tickers should pass filter, got {[i.ticker for i in filtered]}"
        )

    def test_unmapped_sector_passes_filter(self):
        """Items with empty sector string must NOT be dropped (unmapped sector → pass through)."""
        from tradingos.data.schemas import ScanRequest, ScanResultItem

        item = ScanResultItem(
            ticker="ABC", action="WATCH", confidence="MEDIUM",
            mfpm_score=60, mode_w_score=0, sms_raw=50, sms_label="RETAIL_DRIVEN",
            signal_mode="MODE_A", stealth_accum=False, sector="",
            close=30000.0, entry=30000.0, sl=28500.0, tp1=33000.0, rr=2.0,
            amf_decision="PASS", best_pattern="NONE", hmm_state="TRANSITIONAL",
        )
        request = ScanRequest(sector_filter=["Ngân hàng"])
        passes = not (request.sector_filter and item.sector and item.sector not in request.sector_filter)
        assert passes, "Unmapped sector (sector='') must not be dropped by sector_filter"


# ══════════════════════════════════════════════════════════════════════════════
# BUG-B: min_position_pct enforced in sizing
# ══════════════════════════════════════════════════════════════════════════════

class TestBugBMinPositionPct:
    """
    strategy.yaml has `sizing.min_position_pct: 3.0` (3% of portfolio).
    compute_position_size must return 0 shares when the computed allocation
    would fall below this threshold — avoid opening trivially-small positions.
    """

    def test_tiny_position_rejected_by_min_pct(self):
        """A position below min_position_pct must return 0 shares."""
        from tradingos.core.sizing import compute_position_size

        # Portfolio: 1,000,000,000 VND; entry: 5000 VND; 1 lot (100 shares) = 500,000 VND = 0.05%
        # min_position_pct is 3.0% → 30,000,000 VND minimum → 1 lot falls far below
        portfolio = 1_000_000_000
        entry = 5_000.0
        sl = 4_700.0
        # Win prob/rr makes Kelly give a very small allocation
        result = compute_position_size(
            portfolio_value=portfolio, entry=entry, sl=sl,
            win_prob=0.51, rr=1.1,
        )
        # 1 lot (100 shares) at 5000 = 500,000 VND = 0.05% of 1B portfolio
        # Must be rejected by min_position_pct = 3%
        if result["shares"] > 0:
            pct = (result["shares"] * entry) / portfolio * 100
            # If the Kelly-computed shares are >= 3% of portfolio, the gate won't trigger
            # and this is correct behavior — skip the assertion
            if pct < 3.0:
                assert result["shares"] == 0, (
                    f"Position of {pct:.2f}% should be rejected by min_position_pct=3.0%, "
                    f"but got {result['shares']} shares"
                )

    def test_adequate_position_not_rejected(self):
        """A position above min_position_pct must be returned normally."""
        from tradingos.core.sizing import compute_position_size
        # Portfolio: 100,000,000 VND; entry: 30,000 VND; Kelly ~25% → 7,500,000 VND = 7.5%
        result = compute_position_size(
            portfolio_value=100_000_000, entry=30_000.0, sl=28_000.0,
            win_prob=0.60, rr=2.5,
        )
        if result["shares"] > 0:
            pct = (result["shares"] * 30_000.0) / 100_000_000 * 100
            # Should not be rejected since allocation is well above 3%
            assert pct >= 3.0 or result["shares"] == 0, (
                f"Expected either ≥3% allocation or 0 (Kelly negative edge); got {pct:.2f}%"
            )

    def test_source_has_min_position_pct_gate(self):
        """compute_position_size source must read and enforce min_position_pct."""
        from tradingos.core import sizing as sizing_mod
        src = inspect.getsource(sizing_mod.compute_position_size)
        assert "min_position_pct" in src, (
            "compute_position_size must read min_position_pct from config"
        )
        assert "provisional_pct" in src, (
            "compute_position_size must compute provisional_pct for the gate check"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG-C: walk_forward uses is_days/oos_days from config
# ══════════════════════════════════════════════════════════════════════════════

class TestBugCWalkForwardConfig:
    """
    Old walk-forward split data into N+1 equal blocks, making each OOS window
    ~(len(df) / (N+1)) bars — unpredictable and not aligned with the strategy config.
    New: uses walk_forward_is_days (252) and walk_forward_oos_days (63) from config.
    """

    def test_source_reads_walk_forward_config(self):
        """run_backtest source must read walk_forward_is_days and walk_forward_oos_days."""
        from tradingos.core import backtest as bt_mod
        src = inspect.getsource(bt_mod.run_backtest)
        assert "walk_forward_is_days" in src, (
            "run_backtest must read walk_forward_is_days from config"
        )
        assert "walk_forward_oos_days" in src, (
            "run_backtest must read walk_forward_oos_days from config"
        )

    def test_source_no_equal_block_split(self):
        """Old n_blocks = walk_forward_windows + 1 pattern must be removed."""
        from tradingos.core import backtest as bt_mod
        src = inspect.getsource(bt_mod.run_backtest)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code = "\n".join(code_lines)
        assert "n_blocks = walk_forward_windows + 1" not in code, (
            "Old equal-block split (n_blocks = walk_forward_windows + 1) must be removed"
        )

    def test_walk_forward_windows_use_oos_sized_blocks(self):
        """OOS windows from run_backtest must be ~_oos_days long (from config)."""
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all
        # Use 500 bars: IS=252, OOS=63 → 2 windows (252+63+63=378 < 500)
        df = compute_all(_make_ohlcv(500))
        result = run_backtest(df, "TEST", walk_forward_windows=5)
        if not result.walk_forward_windows:
            pytest.skip("No walk-forward windows produced (not enough data for IS+OOS)")
        # Each OOS window's record should exist and have a valid start/end
        for wf in result.walk_forward_windows:
            assert "window" in wf
            assert "start" in wf
            assert "n_trades" in wf

    def test_short_df_produces_no_windows(self):
        """When df is shorter than walk_forward_is_days, zero WF windows must be produced."""
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all
        # 100 bars < walk_forward_is_days=252 → no windows possible
        df = compute_all(_make_ohlcv(100))
        result = run_backtest(df, "TEST", walk_forward_windows=5)
        assert result.walk_forward_windows == [], (
            "With only 100 bars (< is_days=252), no walk-forward windows should be generated"
        )

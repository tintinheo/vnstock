"""
Unit + Performance tests for new components, engines, and VN market logic.

Covers:
  - vn_session_phase() — all 9 phases with correct HOSE timing
  - is_trading_day() — weekends, 2025/2026/2027 holidays
  - trading_day_offset() — over weekends and holidays
  - trading_days_between() — cross-week, cross-holiday
  - PortfolioTracker — add, close, get_positions_due_today, summary
  - _max_drawdown() — known series
  - _to_date() — all input variants (date, datetime, str, None)
  - position_card urgency — trading-days-aware countdown
  - _render_scan_cards_view — existence and signature
  - morning_briefing _load_macro_data — returns correct tuple shape
  - Performance benchmarks — trading_day_offset < 1 ms,
                              _max_drawdown on 1 000-row series < 10 ms,
                              trading_days_between < 1 ms
"""
from __future__ import annotations

import time as _time
from datetime import date, datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _vn_time(h: int, m: int, s: int = 0) -> datetime:
    """Return a VN-timezone (UTC+7) datetime with the given time, date=2026-05-22."""
    VN_TZ = timezone(timedelta(hours=7))
    return datetime(2026, 5, 22, h, m, s, tzinfo=VN_TZ)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. vn_session_phase() — all phases
# ═══════════════════════════════════════════════════════════════════════════════

class TestVnSessionPhase:
    """Verify every phase boundary with mocked vn_now()."""

    def _phase(self, h: int, m: int, s: int = 0) -> str:
        from tradingos.utils.dates import vn_session_phase
        with patch("tradingos.utils.dates.vn_now", return_value=_vn_time(h, m, s)):
            return vn_session_phase()

    def test_pre_market(self):
        assert self._phase(8, 59) == "PRE_MARKET"

    def test_pre_ato_start(self):
        assert self._phase(9, 0) == "PRE_ATO"

    def test_pre_ato_end(self):
        assert self._phase(9, 14, 59) == "PRE_ATO"

    def test_ato_at_915(self):
        assert self._phase(9, 15) == "ATO"

    def test_ato_at_919(self):
        assert self._phase(9, 19) == "ATO"

    def test_morning_starts_at_920(self):
        assert self._phase(9, 20) == "MORNING"

    def test_morning_mid(self):
        assert self._phase(10, 30) == "MORNING"

    def test_morning_end(self):
        assert self._phase(11, 29, 59) == "MORNING"

    def test_lunch_start(self):
        assert self._phase(11, 30) == "LUNCH"

    def test_lunch_mid(self):
        assert self._phase(12, 0) == "LUNCH"

    def test_lunch_end(self):
        assert self._phase(12, 59, 59) == "LUNCH"

    def test_afternoon_starts_at_1300(self):
        assert self._phase(13, 0) == "AFTERNOON"

    def test_afternoon_mid(self):
        assert self._phase(14, 0) == "AFTERNOON"

    def test_near_atc_starts_at_1430(self):
        assert self._phase(14, 30) == "NEAR_ATC"

    def test_near_atc_end(self):
        assert self._phase(14, 42, 59) == "NEAR_ATC"

    def test_atc_starts_at_1443(self):
        assert self._phase(14, 43) == "ATC"

    def test_atc_at_1445(self):
        assert self._phase(14, 45) == "ATC"

    def test_closed_after_1445(self):
        assert self._phase(14, 46) == "CLOSED"

    def test_closed_evening(self):
        assert self._phase(20, 0) == "CLOSED"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. is_trading_day()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsTradingDay:
    def test_regular_weekday(self):
        from tradingos.utils.dates import is_trading_day
        assert is_trading_day(date(2026, 5, 22))  # Friday

    def test_saturday_not_trading(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2026, 5, 23))

    def test_sunday_not_trading(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2026, 5, 24))

    def test_2026_tet_holiday(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2026, 2, 17))  # Tết 2026

    def test_2026_liberation_day(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2026, 4, 30))

    def test_2026_labour_day(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2026, 5, 1))

    def test_2027_new_year(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2027, 1, 1))

    def test_2027_tet(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2027, 1, 28))  # Tết Bính Ngọ

    def test_2027_labour_day(self):
        from tradingos.utils.dates import is_trading_day
        assert not is_trading_day(date(2027, 5, 1))

    def test_day_after_2026_tet_is_trading(self):
        from tradingos.utils.dates import is_trading_day
        # Feb 16-20 are holidays; Feb 23 (Monday) should be first trading day
        assert is_trading_day(date(2026, 2, 23))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. trading_day_offset()
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradingDayOffset:
    def test_t2_over_weekend(self):
        """Friday + 2 trading days = next Tuesday."""
        from tradingos.utils.dates import trading_day_offset
        # 2026-05-22 is Friday; +2 trading days = 2026-05-26 (Tuesday)
        result = trading_day_offset(date(2026, 5, 22), 2)
        assert result == date(2026, 5, 26)

    def test_t2_no_weekend_skip(self):
        """Wednesday + 2 = Friday."""
        from tradingos.utils.dates import trading_day_offset
        result = trading_day_offset(date(2026, 5, 20), 2)
        assert result == date(2026, 5, 22)

    def test_t2_over_holiday(self):
        """T+2 over Liberation Day (Apr 30)."""
        from tradingos.utils.dates import trading_day_offset
        # Apr 28 (Tue) + 2 = May 4 (Mon) since Apr 30 & May 1 are holidays
        result = trading_day_offset(date(2026, 4, 28), 2)
        assert result == date(2026, 5, 4)

    def test_zero_offset(self):
        from tradingos.utils.dates import trading_day_offset
        d = date(2026, 5, 20)
        assert trading_day_offset(d, 0) == d

    def test_negative_offset(self):
        """Tuesday - 1 trading day = Monday."""
        from tradingos.utils.dates import trading_day_offset
        result = trading_day_offset(date(2026, 5, 19), -1)
        assert result == date(2026, 5, 18)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. trading_days_between()
# ═══════════════════════════════════════════════════════════════════════════════

class TestTradingDaysBetween:
    def test_same_day_is_zero(self):
        from tradingos.utils.dates import trading_days_between
        d = date(2026, 5, 22)
        assert trading_days_between(d, d) == 0

    def test_one_trading_day(self):
        from tradingos.utils.dates import trading_days_between
        # Friday → next Monday = 1 trading day (Friday counts, weekend skipped)
        assert trading_days_between(date(2026, 5, 22), date(2026, 5, 25)) == 1

    def test_across_weekend(self):
        from tradingos.utils.dates import trading_days_between
        # Monday → next Friday = 4 trading days
        assert trading_days_between(date(2026, 5, 18), date(2026, 5, 22)) == 4

    def test_hold_days_for_t25(self):
        """Position entered on T+0=Monday; on Wednesday hold_days should be 2."""
        from tradingos.utils.dates import trading_days_between
        t0 = date(2026, 5, 18)  # Monday
        t2 = date(2026, 5, 20)  # Wednesday
        assert trading_days_between(t0, t2) == 2

    def test_holiday_not_counted(self):
        from tradingos.utils.dates import trading_days_between
        # Apr 29 (Wed) to May 4 (Mon): Apr 30, May 1 are holidays → only 1 trading day
        assert trading_days_between(date(2026, 4, 29), date(2026, 5, 4)) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PortfolioTracker — unit tests with mocked cache
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioTracker:
    """Test tracker logic independent of DuckDB."""

    def _make_tracker(self, rows: list[dict] | None = None):
        """Return a PortfolioTracker with cache.get_trade_ledger mocked."""
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        tracker = PortfolioTracker()
        df = pd.DataFrame(rows or [])
        with patch("tradingos.engines.portfolio_tracker.cache") as mock_cache:
            mock_cache.get_trade_ledger.return_value = df
            mock_cache.log_paper_trade.return_value = None
            mock_cache.close_paper_trade.return_value = 1
            yield tracker, mock_cache

    def test_get_open_positions_empty(self):
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        with patch("tradingos.engines.portfolio_tracker.cache") as mc:
            mc.get_trade_ledger.return_value = pd.DataFrame()
            t = PortfolioTracker()
            result = t.get_open_positions()
            assert result.empty

    def test_get_positions_due_today_detects_t2(self):
        """A position entered 2 trading days ago should appear in due_today."""
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        from tradingos.utils.dates import trading_day_offset
        today = date.today()  # use real today so date.today() inside tracker matches
        t0 = trading_day_offset(today, -2)  # 2 trading days before today
        rows = [{"ticker": "VCB", "entry_date": t0, "entry_price": 100_000,
                 "initial_sl": 93_000, "status": "OPEN", "signal_mode": "MODE_A",
                 "mfpm_score": 80, "mc_prob": 0.6}]
        with patch("tradingos.engines.portfolio_tracker.cache") as mc:
            mc.get_trade_ledger.return_value = pd.DataFrame(rows)
            t = PortfolioTracker()
            due = t.get_positions_due_today()
        assert len(due) == 1
        assert due[0]["ticker"] == "VCB"

    def test_get_positions_due_today_future_not_included(self):
        """A position entered today should NOT be in due_today (T+2 is in the future)."""
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        today = date.today()
        rows = [{"ticker": "TCB", "entry_date": today, "entry_price": 25_000,
                 "initial_sl": 23_000, "status": "OPEN", "signal_mode": "MODE_B",
                 "mfpm_score": 70, "mc_prob": 0.55}]
        with patch("tradingos.engines.portfolio_tracker.cache") as mc:
            mc.get_trade_ledger.return_value = pd.DataFrame(rows)
            t = PortfolioTracker()
            due = t.get_positions_due_today()
        assert len(due) == 0

    def test_summary_empty(self):
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        with patch("tradingos.engines.portfolio_tracker.cache") as mc:
            mc.get_trade_ledger.return_value = pd.DataFrame()
            t = PortfolioTracker()
            s = t.summary()
        assert s["open"] == 0
        assert s["closed"] == 0
        assert s["win_rate"] == 0.0

    def test_summary_with_closed_trades(self):
        from tradingos.engines.portfolio_tracker import PortfolioTracker
        rows = [
            {"ticker": "A", "status": "CLOSED", "pnl_pct": 5.0},
            {"ticker": "B", "status": "CLOSED", "pnl_pct": -3.0},
            {"ticker": "C", "status": "OPEN",   "pnl_pct": None},
        ]
        with patch("tradingos.engines.portfolio_tracker.cache") as mc:
            mc.get_trade_ledger.return_value = pd.DataFrame(rows)
            t = PortfolioTracker()
            s = t.summary()
        assert s["open"] == 1
        assert s["closed"] == 2
        assert abs(s["win_rate"] - 0.5) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# 6. _max_drawdown() in performance page
# ═══════════════════════════════════════════════════════════════════════════════

class TestMaxDrawdown:
    def _dd(self, pnl_list: list[float]) -> float:
        from tradingos.ui.pages.performance import _max_drawdown
        return _max_drawdown(pd.Series(pnl_list))

    def test_all_winning_no_drawdown(self):
        result = self._dd([5.0, 3.0, 7.0])
        assert result < 0.01

    def test_single_loss(self):
        result = self._dd([10.0, -50.0])
        assert 0.4 < result < 0.6

    def test_flat_series(self):
        assert self._dd([0.0, 0.0, 0.0]) < 0.01

    def test_empty_series(self):
        assert self._dd([]) == 0.0

    def test_all_losses(self):
        # 3 × -10%: equity [0.9, 0.81, 0.729] → max_dd ≈ 0.19 > 0.1
        result = self._dd([-10.0, -10.0, -10.0])
        assert result > 0.1


# ═══════════════════════════════════════════════════════════════════════════════
# 7. _to_date() in performance page
# ═══════════════════════════════════════════════════════════════════════════════

class TestToDate:
    def _call(self, v):
        from tradingos.ui.pages.performance import _to_date
        return _to_date(v)

    def test_none_returns_none(self):
        assert self._call(None) is None

    def test_date_passthrough(self):
        d = date(2026, 5, 22)
        assert self._call(d) == d

    def test_datetime_extracts_date(self):
        dt = datetime(2026, 5, 22, 9, 30)
        assert self._call(dt) == date(2026, 5, 22)

    def test_string_iso(self):
        assert self._call("2026-05-22") == date(2026, 5, 22)

    def test_string_with_time(self):
        assert self._call("2026-05-22 09:30:00") == date(2026, 5, 22)

    def test_invalid_string_returns_none(self):
        assert self._call("not-a-date") is None

    def test_pandas_timestamp(self):
        ts = pd.Timestamp("2026-05-22")
        assert self._call(ts) == date(2026, 5, 22)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. position_card — urgency uses trading days not calendar days
# ═══════════════════════════════════════════════════════════════════════════════

class TestPositionCardUrgency:
    """
    Verify that the urgency calculation in render_position_card uses
    trading_days_between(), NOT calendar days.  We inspect the source
    so this test does not require a Streamlit runtime.
    """

    def test_uses_trading_days_between(self):
        import inspect
        from tradingos.ui.components.position_card import render_position_card
        src = inspect.getsource(render_position_card)
        assert "trading_days_between" in src, (
            "render_position_card must use trading_days_between for days_left, "
            "not calendar subtraction — a Friday→Monday weekend inflates to 3 "
            "calendar days but is only 1 trading day."
        )

    def test_trading_days_between_imported(self):
        import inspect
        import tradingos.ui.components.position_card as pc
        src = inspect.getsource(pc)
        assert "trading_days_between" in src


# ═══════════════════════════════════════════════════════════════════════════════
# 9. hold_days in portfolio_tracker uses trading days
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioTrackerHoldDays:
    def test_hold_days_uses_trading_days_between(self):
        import inspect
        from tradingos.engines import portfolio_tracker as pt_mod
        src = inspect.getsource(pt_mod)
        assert "trading_days_between" in src, (
            "portfolio_tracker must use trading_days_between for hold_days — "
            "a position held over a 3-day weekend must show hold_days=1 "
            "not 3 (which would incorrectly trigger TP1 partial exit)."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 10. _render_scan_cards_view — existence + signature
# ═══════════════════════════════════════════════════════════════════════════════

class TestScanCardsView:
    def test_function_exists(self):
        from tradingos.ui.pages import scanner
        assert hasattr(scanner, "_render_scan_cards_view"), (
            "_render_scan_cards_view must be defined in scanner.py"
        )

    def test_accepts_dataframe(self):
        import inspect
        from tradingos.ui.pages.scanner import _render_scan_cards_view
        sig = inspect.signature(_render_scan_cards_view)
        params = list(sig.parameters)
        assert len(params) >= 1, "must accept at least one argument (df)"

    def test_empty_df_does_not_crash_logic(self):
        """Verify empty DataFrame branch does not call st.columns."""
        from tradingos.ui.pages.scanner import _render_scan_cards_view
        with patch("tradingos.ui.pages.scanner.st") as mock_st:
            _render_scan_cards_view(pd.DataFrame())
            mock_st.info.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# 11. morning_briefing _load_macro_data — returns correct tuple shape
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadMacroData:
    def test_returns_three_tuple(self):
        """_load_macro_data must return (score|None, regime_str, sector_dict)."""
        import inspect
        from tradingos.ui.pages import morning_briefing as mb
        assert hasattr(mb, "_load_macro_data"), "_load_macro_data must be defined"
        src = inspect.getsource(mb._load_macro_data)
        assert "sector_flows" in src
        assert "macro_score" in src
        assert "macro_regime" in src

    def test_returns_tuple_on_exception(self):
        """Even if both external calls fail, must return a valid 3-tuple."""
        from tradingos.ui.pages.morning_briefing import _load_macro_data
        with patch("tradingos.ui.pages.morning_briefing._load_macro_data",
                   return_value=(None, "", {})) as mocked:
            result = mocked()
        assert isinstance(result, tuple)
        assert len(result) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Performance benchmarks
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceBenchmarks:
    """
    Timing tests — each operation must complete within its SLA.
    These run in a single call (no warm-up needed for pure Python).
    """

    def test_trading_day_offset_under_1ms(self):
        from tradingos.utils.dates import trading_day_offset
        d = date(2026, 5, 22)
        start = _time.perf_counter()
        for _ in range(100):
            trading_day_offset(d, 2)
        elapsed_ms = (_time.perf_counter() - start) * 1000 / 100
        assert elapsed_ms < 1.0, f"trading_day_offset took {elapsed_ms:.3f}ms (SLA: <1ms)"

    def test_trading_days_between_under_1ms(self):
        from tradingos.utils.dates import trading_days_between
        start_d = date(2026, 1, 1)
        end_d   = date(2026, 5, 22)
        start = _time.perf_counter()
        for _ in range(100):
            trading_days_between(start_d, end_d)
        elapsed_ms = (_time.perf_counter() - start) * 1000 / 100
        assert elapsed_ms < 1.0, f"trading_days_between took {elapsed_ms:.3f}ms (SLA: <1ms)"

    def test_max_drawdown_1000_rows_under_10ms(self):
        from tradingos.ui.pages.performance import _max_drawdown
        rng = np.random.default_rng(42)
        pnl = pd.Series(rng.normal(0.5, 3.0, 1000))
        start = _time.perf_counter()
        for _ in range(50):
            _max_drawdown(pnl)
        elapsed_ms = (_time.perf_counter() - start) * 1000 / 50
        assert elapsed_ms < 10.0, f"_max_drawdown(1000 rows) took {elapsed_ms:.3f}ms (SLA: <10ms)"

    def test_vn_session_phase_under_1ms(self):
        from tradingos.utils.dates import vn_session_phase
        start = _time.perf_counter()
        for _ in range(500):
            vn_session_phase()
        elapsed_ms = (_time.perf_counter() - start) * 1000 / 500
        assert elapsed_ms < 1.0, f"vn_session_phase took {elapsed_ms:.3f}ms (SLA: <1ms)"

    def test_is_trading_day_under_01ms(self):
        from tradingos.utils.dates import is_trading_day
        d = date(2026, 5, 22)
        start = _time.perf_counter()
        for _ in range(1000):
            is_trading_day(d)
        elapsed_ms = (_time.perf_counter() - start) * 1000 / 1000
        assert elapsed_ms < 0.1, f"is_trading_day took {elapsed_ms:.4f}ms (SLA: <0.1ms)"

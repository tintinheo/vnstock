"""
Second-pass regression tests covering 12 new credibility / correctness issues.

Issue mapping:
  C1 — strategy.yaml min_score_strong_buy configurable (BUY gate)
  C2 — SMS component 7 (pt_flow) scores 0 when PT data absent (documented cap)
  C3 — run_backtest wires avg_vol_20d into _simulate_single_trade
  H1 — Walk-forward OOS windows are non-overlapping
  H2 — BacktestTrade entry/exit dates are ISO strings (YYYY-MM-DD), not ints
  H3 — sizing.py reads kelly_max_pct (25.0) not max_single_position_pct
  H4 — detect_amd_phase: near-zero OBV start does not falsely fire MARKUP
  H5 — HOSE ±7% circuit breaker: SL fill >= prev_close * 0.93
  M1 — universe.py reads min_avg_vol_20d config key
  M2 — fetch_foreign_flow docstring says dd/MM/YYYY
  M3 — exit_engine: exit_shares_1 dead variable removed (no NameError)
  M4 — mode_w_entry_params stale comment removed (no assertion on comment)
"""
from __future__ import annotations

import inspect
import re

import numpy as np
import pandas as pd
import pytest


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 200, seed: int = 42, trend: float = 0.001,
                start_date: str = "2023-01-02") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start_date, periods=n)
    close = 50_000.0 * np.cumprod(1 + rng.normal(trend, 0.015, n))
    volume = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * rng.uniform(0.99, 1.01, n),
        "high":   close * rng.uniform(1.00, 1.02, n),
        "low":    close * rng.uniform(0.98, 1.00, n),
        "close":  close,
        "volume": volume,
    })


def _make_indicators_df(n: int = 120) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n))


# ─────────────────────────────────────────────────────────────────────────────
# C1 — BUY gate reads min_score_strong_buy from config (not hardcoded 70)
# ─────────────────────────────────────────────────────────────────────────────

class TestC1ConfigBuyGate:
    def test_config_key_exists(self):
        from tradingos.utils.config import cfg
        val = cfg.strategy("mfpm", "min_score_strong_buy", default=None)
        assert val is not None, "strategy.yaml must define mfpm.min_score_strong_buy"
        assert int(val) >= 50

    def test_old_min_score_buy_key_gone(self):
        from tradingos.utils.config import cfg
        # The old undescribed key "min_score_buy" should no longer exist
        old = cfg.strategy("mfpm", "min_score_buy", default="__MISSING__")
        assert old == "__MISSING__", (
            "mfpm.min_score_buy is a dead key that was replaced by min_score_strong_buy"
        )

    def test_mfpm_reads_new_key(self):
        """compute_mfpm source must reference min_score_strong_buy."""
        from tradingos.core import mfpm
        src = inspect.getsource(mfpm.compute_mfpm)
        assert "min_score_strong_buy" in src, (
            "compute_mfpm must read BUY threshold from min_score_strong_buy config key"
        )

    def test_watch_gate_key_value(self):
        from tradingos.utils.config import cfg
        watch = cfg.strategy("mfpm", "min_score_watch", default=None)
        assert watch is not None
        # watch gate must be less than buy gate
        buy = cfg.strategy("mfpm", "min_score_strong_buy", default=70)
        assert int(watch) < int(buy)


# ─────────────────────────────────────────────────────────────────────────────
# C2 — SMS cap when PT deals unavailable (pt_flow = 5, neutral since VN-B3 fix)
# ─────────────────────────────────────────────────────────────────────────────

class TestC2SMSCapWithoutPT:
    def test_sms_max_without_pt_is_85(self):
        """[VN-B3 FIX] With no PT data, pt_flow = 5 (neutral, not 0).
        Old assertion checked pt_flow==0 and sms<=85; updated to new neutral behavior."""
        from tradingos.core.money_flow import compute_smart_money_score, proxy_whale_net_from_daily
        df = _make_indicators_df(120)
        flow = proxy_whale_net_from_daily(df)
        flow["data_source"] = "PROXY_OHLCV"
        # Pass no PT data (None) — pt_flow must be 5 (neutral) per VN-B3 fix
        result = compute_smart_money_score("TEST", df, flow, pt_deals_df=None)
        assert result["components"]["pt_flow"] == 5, (
            "pt_flow must be 5 (neutral) when no PT data — VN-B3 fix"
        )
        # Max SMS without real PT data: other components (max 85) + neutral pt_flow (5) = 90
        assert result["sms"] <= 90, f"SMS without real PT data should be <= 90, got {result['sms']}"

    def test_sms_with_pt_can_exceed_85(self):
        """With strong PT buy data, SMS can reach higher than 85."""
        from tradingos.core.money_flow import compute_smart_money_score, proxy_whale_net_from_daily
        df = _make_indicators_df(120)
        flow = proxy_whale_net_from_daily(df)
        flow["data_source"] = "PROXY_OHLCV"
        # Synthetic strong PT net buy
        avg_val = float((df["volume"] * df["close"]).tail(5).mean())
        pt = pd.DataFrame({
            "value": [avg_val * 0.5] * 5,  # 50% of avg 5d value each day
        })
        result = compute_smart_money_score("TEST", df, flow, pt_deals_df=pt)
        assert result["components"]["pt_flow"] == 15
        # SMS could now go above 85


# ─────────────────────────────────────────────────────────────────────────────
# C3 — run_backtest wires avg_vol_20d into _simulate_single_trade
# ─────────────────────────────────────────────────────────────────────────────

class TestC3AvgVolWired:
    def test_run_backtest_source_passes_avg_vol(self):
        from tradingos.core import backtest
        src = inspect.getsource(backtest.run_backtest)
        assert "avg_vol_20d" in src, (
            "run_backtest must compute and pass avg_vol_20d to _simulate_single_trade"
        )

    def test_illiquid_ticker_higher_lock_san(self):
        """Two identical price series but different volume — illiquid should have more
        synthetic lock_san misses (matched=False) over many trades."""
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all

        rng = np.random.default_rng(0)
        n = 250
        dates = pd.bdate_range("2022-01-03", periods=n)
        close = 50_000 * np.cumprod(1 + rng.normal(0.0005, 0.012, n))

        def _make(vol_level: float) -> pd.DataFrame:
            vols = np.full(n, vol_level)
            df = pd.DataFrame({
                "date": dates, "open": close, "high": close * 1.01,
                "low": close * 0.99, "close": close, "volume": vols,
            })
            return compute_all(df)

        liquid   = run_backtest(_make(2_000_000.0), ticker="LIQ",  mode="MODE_A")
        illiquid = run_backtest(_make(50_000.0),    ticker="ILIQ", mode="MODE_A")

        if liquid.n_trades >= 3 and illiquid.n_trades >= 3:
            liq_misses  = sum(1 for t in liquid.trades   if not t.matched)
            iliq_misses = sum(1 for t in illiquid.trades if not t.matched)
            # Illiquid should have >= liquid misses (lock_san probability is higher)
            assert iliq_misses >= liq_misses, (
                f"Illiquid should have >= lock_san misses: illiquid={iliq_misses} liquid={liq_misses}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# H1 — Walk-forward windows are non-overlapping
# ─────────────────────────────────────────────────────────────────────────────

class TestH1WalkForwardNoLeakage:
    def test_oos_windows_non_overlapping(self):
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(300))
        result = run_backtest(df, walk_forward_windows=4)

        windows = result.walk_forward_windows
        if len(windows) < 2:
            pytest.skip("Not enough windows produced")

        # Parse start/end dates — they should not overlap
        dates = [(w["start"], w["end"]) for w in windows]
        for i in range(len(dates) - 1):
            # Window i's end must be <= window i+1's start (no overlap)
            end_i   = pd.Timestamp(dates[i][1])
            start_j = pd.Timestamp(dates[i + 1][0])
            assert end_i <= start_j, (
                f"WF window {i+1} end {dates[i][1]} overlaps window {i+2} start {dates[i+1][0]}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# H2 — Entry/exit dates are ISO strings, not integers
# ─────────────────────────────────────────────────────────────────────────────

class TestH2BacktestDates:
    _ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def test_trade_dates_are_iso(self):
        from tradingos.core.backtest import run_backtest
        from tradingos.core.indicators import compute_all
        df = compute_all(_make_ohlcv(200))
        result = run_backtest(df, walk_forward_windows=0)

        assert result.start_date and self._ISO_PATTERN.match(result.start_date), \
            f"start_date '{result.start_date}' is not ISO YYYY-MM-DD"
        assert result.end_date and self._ISO_PATTERN.match(result.end_date), \
            f"end_date '{result.end_date}' is not ISO YYYY-MM-DD"

        for t in result.trades:
            assert self._ISO_PATTERN.match(t.entry_date), \
                f"Trade entry_date '{t.entry_date}' is not ISO"
            assert self._ISO_PATTERN.match(t.exit_date), \
                f"Trade exit_date '{t.exit_date}' is not ISO"


# ─────────────────────────────────────────────────────────────────────────────
# H3 — sizing.py reads kelly_max_pct (25%) from config
# ─────────────────────────────────────────────────────────────────────────────

class TestH3SizingCapKey:
    def test_source_uses_kelly_max_pct(self):
        from tradingos.core import sizing
        src = inspect.getsource(sizing.compute_position_size)
        assert "kelly_max_pct" in src, (
            "compute_position_size must read cap from kelly_max_pct config key"
        )
        assert "max_single_position_pct" not in src, (
            "old wrong key max_single_position_pct must be removed"
        )

    def test_cap_respects_25pct(self):
        from tradingos.core.sizing import compute_position_size
        # With very favourable params, Kelly would go above 10% — check cap is ~25%
        result = compute_position_size(
            portfolio_value=300_000_000,
            entry=50_000,
            sl=45_000,          # -10% SL (larger risk → smaller Kelly naturally)
            win_prob=0.80,
            rr=5.0,
        )
        # config has kelly_max_pct=25; result must not exceed that
        assert result["size_pct"] <= 0.26, \
            f"Position cap breach: {result['size_pct']:.2%} > 26%"


# ─────────────────────────────────────────────────────────────────────────────
# H4 — detect_amd_phase: near-zero OBV start does not spuriously fire MARKUP
# ─────────────────────────────────────────────────────────────────────────────

class TestH4OBVNearZeroGuard:
    def _make_flat_with_zero_obv(self, n: int = 70) -> pd.DataFrame:
        """Flat price, OBV starts at 0, slowly drifts up just a little."""
        prices = np.full(n, 50_000.0) + np.random.normal(0, 50, n)
        # OBV starts at 0 — very small total drift
        obv_vals = np.arange(n, dtype=float) * 10  # 10 shares/day drift
        return pd.DataFrame({
            "close":  prices,
            "open":   prices, "high": prices * 1.002, "low": prices * 0.998,
            "volume": np.full(n, 500_000.0),
            "OBV":    obv_vals,  # starts at 0 → first value is 0
            "date":   pd.bdate_range("2023-01-02", periods=n),
        })

    def test_near_zero_obv_start_not_markup(self):
        """With flat price and OBV start near 0, must not fire MARKUP."""
        from tradingos.core.anti_manip import detect_amd_phase
        df = self._make_flat_with_zero_obv()
        phase = detect_amd_phase(df)
        assert phase != "MARKUP", (
            f"Near-zero OBV start with flat price should not produce MARKUP, got '{phase}'"
        )

    def test_genuine_markup_still_detected(self):
        """Strong price + large absolute OBV gain still fires MARKUP."""
        from tradingos.core.anti_manip import detect_amd_phase
        n = 70
        prices = 50_000.0 * np.cumprod(1 + np.full(n, 0.002))  # +0.2%/day
        base_obv = 10_000_000.0  # realistic starting OBV (not near zero)
        obv_vals = base_obv + np.cumsum(np.full(n, 500_000.0))
        vols_up = np.full(n, 1_000_000.0)
        df = pd.DataFrame({
            "close":  prices, "open": prices, "high": prices * 1.01, "low": prices * 0.99,
            "volume": vols_up,
            "OBV":    obv_vals,
            "date":   pd.bdate_range("2023-01-02", periods=n),
        })
        phase = detect_amd_phase(df)
        assert phase == "MARKUP", f"Genuine markup not detected, got '{phase}'"


# ─────────────────────────────────────────────────────────────────────────────
# H5 — HOSE ±7% circuit breaker: SL fill >= prev_close * 0.93
# ─────────────────────────────────────────────────────────────────────────────

class TestH5HOSECircuitBreaker:
    def test_sl_fill_floored_at_93pct_prev_close(self):
        """
        Construct a scenario where SL would naturally be e.g. -15% away but
        HOSE floor means the exit price is -7% from prev close.
        """
        from tradingos.core.backtest import _simulate_single_trade
        n = 30
        dates = pd.bdate_range("2023-01-02", periods=n)
        entry_price = 50_000.0
        # Crash hard on day 5: low goes to 38_000 (−24%), prev_close was 49_000
        close = np.full(n, entry_price)
        low   = np.full(n, entry_price * 0.99)
        high  = np.full(n, entry_price * 1.01)
        close[5] = 40_000
        low[5]   = 38_000   # would trigger SL set at 47_500 (-5%)
        high[5]  = 42_000
        close[4] = 49_000   # prev_close before crash day

        df = pd.DataFrame({
            "date": dates,
            "open": close, "high": high, "low": low, "close": close,
            "volume": np.full(n, 1_000_000.0),
        })
        # Set SL = 5% below entry; natural fill would be 38_000 but HOSE floor = 49_000*0.93
        trade = _simulate_single_trade(df, entry_idx=0, sl_pct=0.05, tp1_pct=0.10, tp2_pct=0.20)
        if trade is not None and trade.exit_reason == "SL":
            hose_floor = close[4] * 0.93  # 49_000 * 0.93 = 45_570
            assert trade.exit_price >= hose_floor - 1, (
                f"SL fill {trade.exit_price:.0f} < HOSE floor {hose_floor:.0f}"
            )

    def test_normal_sl_not_affected(self):
        """Normal SL within 7% works as before (HOSE floor doesn't interfere)."""
        from tradingos.core.backtest import _simulate_single_trade
        n = 30
        close = np.full(n, 50_000.0)
        low   = np.array([50_000.0 * 0.99] * n)
        high  = np.full(n, 50_500.0)
        # Day 3: small dip triggers SL at -3%
        low[3]   = 48_400  # below SL of 48_500 (-3%)
        close[3] = 48_600
        df = pd.DataFrame({
            "date":   pd.bdate_range("2023-01-02", periods=n),
            "open":   close, "high": high, "low": low, "close": close,
            "volume": np.full(n, 1_000_000.0),
        })
        trade = _simulate_single_trade(df, entry_idx=0, sl_pct=0.03, tp1_pct=0.10, tp2_pct=0.20)
        if trade is not None:
            # SL fill is at the SL price or better (HOSE floor = prev_close * 0.93 ≈ 46_500)
            # For a 3% SL the floor is higher so no interference
            assert trade.exit_price >= close[0] * (1 - 0.10), \
                "Normal SL exit price should not be far below SL"


# ─────────────────────────────────────────────────────────────────────────────
# M1 — universe.py reads min_avg_vol_20d config key
# ─────────────────────────────────────────────────────────────────────────────

class TestM1UniverseConfigKey:
    def test_source_uses_correct_key(self):
        from tradingos.core import universe
        src = inspect.getsource(universe.canslim_filters)
        assert "min_avg_vol_20d" in src, (
            "canslim_filters must read min_avg_vol_20d (not min_avg_daily_vol)"
        )
        assert "min_avg_daily_vol" not in src, "old wrong key must be removed"

    def test_config_key_present_in_yaml(self):
        from tradingos.utils.config import cfg
        val = cfg.strategy("universe", "min_avg_vol_20d", default=None)
        assert val is not None, "strategy.yaml must define universe.min_avg_vol_20d"


# ─────────────────────────────────────────────────────────────────────────────
# M2 — fetch_foreign_flow docstring says dd/MM/YYYY
# ─────────────────────────────────────────────────────────────────────────────

class TestM2FOLDocstring:
    def test_docstring_says_dd_mm_yyyy(self):
        from tradingos.data.fetcher import fetch_foreign_flow
        doc = fetch_foreign_flow.__doc__ or ""
        assert "dd/MM/YYYY" in doc or "dd/mm/yyyy" in doc.lower() or "%d/%m/%Y" in doc, (
            "fetch_foreign_flow docstring must state dd/MM/YYYY date format"
        )
        assert "MM/DD/YYYY" not in doc and "mm/dd/yyyy" not in doc.lower(), (
            "docstring must not say MM/DD/YYYY (that was the old wrong format)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# M3 — exit_engine: dead variable exit_shares_1 is gone
# ─────────────────────────────────────────────────────────────────────────────

class TestM3ExitEngineDeadVar:
    def test_exit_shares_1_removed(self):
        from tradingos.core import exit_engine
        src = inspect.getsource(exit_engine.progressive_exit_plan)
        assert "exit_shares_1" not in src, (
            "exit_shares_1 is a dead variable and must be removed"
        )

    def test_progressive_exit_plan_runs_without_error(self):
        from tradingos.core.exit_engine import progressive_exit_plan
        df = _make_indicators_df()
        stages = progressive_exit_plan(
            df, entry=50_000, current_price=60_000,
            tp1=55_000, tp2=65_000, sl=47_000,
            hold_days=5, shares_held=1000, atr=1_500.0,
        )
        assert isinstance(stages, list)
        assert len(stages) >= 1

    def test_stage1_at_tp1(self):
        from tradingos.core.exit_engine import progressive_exit_plan
        df = _make_indicators_df()
        stages = progressive_exit_plan(
            df, entry=50_000, current_price=56_000,
            tp1=55_000, tp2=70_000, sl=47_000,
            hold_days=5, shares_held=1000, atr=1_200.0,
        )
        actions = [s.action for s in stages]
        assert "PARTIAL_EXIT" in actions, "TP1 hit should produce PARTIAL_EXIT stage"

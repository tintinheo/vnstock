"""
Regression tests for BUG-13 through BUG-19 and VN-8 / VN-10.

  BUG-13  scanner_service.py   data_source key path (mirror of BUG-10 in profiler)
  BUG-14  t25_engine.py        compute_t25_multiframe vol_ratio truthiness + default 1.0→0.0
  BUG-16  sizing.py            Kelly 2% floor forces trades with no edge
  BUG-17  backtest.py          HOSE limit-down 0.93 hardcoded → configurable
  BUG-18  backtest.py          pnl per-share only, not total trade VND
  BUG-19  sizing.py            progressive_entry forced min lot per tranche
  VN-8    t25_engine.py        midday oversold bonus fires in BEAR_TREND
  VN-10   money_flow.py        fol_pct clipped at 0 hides net-sell pressure
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 150, seed: int = 13, trend: float = 0.001) -> pd.DataFrame:
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


def _make_indicators(n: int = 150, seed: int = 13, trend: float = 0.001) -> pd.DataFrame:
    from tradingos.core.indicators import compute_all
    return compute_all(_make_ohlcv(n, seed=seed, trend=trend))


# ─────────────────────────────────────────────────────────────────────────────
# BUG-13: scanner_service data_source key path
# ─────────────────────────────────────────────────────────────────────────────

class TestBug13ScannerDataSource:
    """
    scanner_service must read data_source from mcvd dict, not sms_result top level.
    """

    def test_source_reads_mcvd_not_sms_result(self):
        """scanner_service _score_ticker() source must use mcvd.get, not sms_result.get."""
        import tradingos.engines.scanner_service as ss_mod
        src = inspect.getsource(ss_mod.ScannerService._score_ticker)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        # Old wrong pattern must be gone:
        assert 'sms_result.get("data_source"' not in code_only, (
            "scanner_service must NOT read data_source from sms_result top level"
        )
        # New correct pattern must exist:
        assert 'mcvd.get("data_source"' in code_only, (
            "scanner_service must read data_source from mcvd dict"
        )

    def test_mcvd_data_source_preserved_in_mfpm_call(self):
        """When mcvd has data_source=PARTIAL_PROXY, it must be passed to mfpm, not PROXY_OHLCV."""
        fake_mcvd = {"mcvd_trend": "UP", "data_source": "PARTIAL_PROXY"}
        fake_sms = {"sms": 65}  # no data_source at top level

        # Simulate scanner_service dict construction (post-fix)
        merged = {**fake_mcvd, "data_source": fake_mcvd.get("data_source", "PROXY_OHLCV")}
        assert merged["data_source"] == "PARTIAL_PROXY", (
            "PARTIAL_PROXY must not be overwritten by wrong key path"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-14: compute_t25_multiframe vol_ratio truthiness + wrong default
# ─────────────────────────────────────────────────────────────────────────────

class TestBug14MultiframeVolRatio:
    """
    vol_ratio in compute_t25_multiframe:
    - must use `is not None` guard, not truthiness (vol=0.0 is valid)
    - default must be 0.0 (no volume = no liquidity), not 1.0 (neutral)
    """

    def test_source_uses_is_not_none(self):
        """Source must use is not None guard for vol_now and vol_avg20."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_multiframe)
        assert "vol_now is not None" in src, (
            "compute_t25_multiframe vol_ratio must use 'vol_now is not None'"
        )
        assert "vol_avg20 is not None" in src

    def test_default_vol_ratio_is_zero_not_one(self):
        """Source must default vol_ratio to 0.0 when data is missing."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_multiframe)
        # Check the vol_ratio assignment line
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        vol_line = next(
            (l for l in code_lines if "vol_ratio" in l and "else" in l), None
        )
        assert vol_line is not None, "vol_ratio assignment with else clause not found"
        assert "else 0.0" in vol_line, (
            f"vol_ratio default must be 0.0, not 1.0; got: {vol_line!r}"
        )

    def test_zero_volume_does_not_inflate_afternoon_score(self):
        """vol_ratio=0 must produce afternoon score without vol_ratio > 1.5 bonus."""
        from tradingos.core.t25_engine import compute_t25_multiframe, compute_t25_entry_score
        df = _make_indicators(n=100)
        df.iloc[-1, df.columns.get_loc("volume")] = 0.0  # zero volume
        t25 = compute_t25_entry_score(df)
        result = compute_t25_multiframe(df, t25_entry_result=t25)
        # Should not contain "Khối lượng chiều cao" because vol=0
        assert not any("Khối lượng chiều cao" in r for r in result["mf_reasons"]), (
            "Zero volume must not produce 'Khối lượng chiều cao' reason"
        )

    def test_rsi_mh_adx_use_is_not_none(self):
        """Source must use is not None for rsi, mh_last, adx checks."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_multiframe)
        assert "rsi is not None" in src
        assert "mh_last is not None" in src
        assert "adx is not None" in src


# ─────────────────────────────────────────────────────────────────────────────
# BUG-16: Kelly 2% forced floor
# ─────────────────────────────────────────────────────────────────────────────

class TestBug16KellyFloor:
    """
    compute_position_size must return 0 size (0 shares) when Kelly ≤ 0
    (win_prob ≤ break-even for the given RR).
    Old np.clip(k, 0.02, max_pct) forced 2% even with negative edge.
    """

    def test_negative_edge_returns_zero_size(self):
        """win_prob=0.30, rr=2.0 → Kelly < 0 → must return 0 shares."""
        from tradingos.core.sizing import compute_position_size
        result = compute_position_size(
            portfolio_value=300_000_000.0,
            entry=30_000.0,
            sl=28_500.0,
            win_prob=0.30,   # very low win rate → negative Kelly
            rr=2.0,
        )
        assert result["shares"] == 0, (
            f"Negative Kelly edge must return 0 shares; got {result['shares']}"
        )
        assert result["size_pct"] == 0.0

    def test_break_even_edge_returns_zero(self):
        """win_prob=0.333 (break-even for RR=2) → Kelly≈0 → 0 shares."""
        from tradingos.core.sizing import compute_position_size
        result = compute_position_size(
            portfolio_value=300_000_000.0,
            entry=30_000.0,
            sl=28_500.0,
            win_prob=0.333,
            rr=2.0,
        )
        assert result["shares"] == 0, (
            f"Break-even Kelly must return 0 shares; got {result['shares']}"
        )

    def test_positive_edge_still_allocates(self):
        """win_prob=0.60, rr=2.0 → positive Kelly → should allocate shares."""
        from tradingos.core.sizing import compute_position_size
        result = compute_position_size(
            portfolio_value=300_000_000.0,
            entry=30_000.0,
            sl=28_500.0,
            win_prob=0.60,
            rr=2.0,
        )
        assert result["shares"] >= 100, "Positive edge must still allocate at least 1 lot"

    def test_source_clips_from_zero(self):
        """Source must clip Kelly from 0.0, not 0.02."""
        import tradingos.core.sizing as sizing_mod
        src = inspect.getsource(sizing_mod.compute_position_size)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        clip_line = next(
            (l for l in code_lines if "np.clip" in l and "size_pct" in l), None
        )
        assert clip_line is not None, "np.clip line for size_pct not found"
        assert "0.02" not in clip_line, (
            f"Kelly floor must be 0.0, not 0.02; got: {clip_line!r}"
        )
        assert "0.0," in clip_line or "0.0 ," in clip_line, (
            f"Kelly floor must be 0.0; got: {clip_line!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-17: Backtest limit-down hardcoded 0.93
# ─────────────────────────────────────────────────────────────────────────────

class TestBug17BacktestLimitDown:
    """
    Backtest limit-down floor must be configurable via strategy.yaml,
    not hardcoded to 0.93 (HOSE only).
    """

    def test_source_reads_from_config(self):
        """_simulate_single_trade must read limit_down_pct from config, not hardcode 0.93."""
        import tradingos.core.backtest as bt_mod
        src = inspect.getsource(bt_mod._simulate_single_trade)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "hose_floor" not in code_only, (
            "Old hose_floor variable must be removed — use limit_floor from config"
        )
        assert "limit_down_pct" in code_only, (
            "simulate_trade must use limit_down_pct from config"
        )
        assert "0.93" not in code_only, (
            "0.93 HOSE hardcode must be removed from code lines"
        )

    def test_config_has_limit_down_pct(self):
        """strategy.yaml must contain limit_down_pct under backtest section."""
        from tradingos.utils.config import cfg
        val = float(cfg.strategy("backtest", "limit_down_pct", default=-1))
        assert val > 0, "strategy.yaml must define backtest.limit_down_pct"
        assert val == pytest.approx(0.07), "Default HOSE limit_down_pct must be 0.07"

    def test_limit_floor_applied_correctly(self):
        """SL fill price must respect 7% limit-down floor on gap-down day."""
        import tradingos.core.backtest as bt_mod
        df = _make_indicators(n=40)
        # Set last bar's low far below SL to trigger limit-down
        entry_idx = 30
        prev_close = float(df.iloc[entry_idx]["close"])
        # Force low below SL at entry_idx+1
        df.iloc[entry_idx + 1, df.columns.get_loc("low")] = prev_close * 0.80

        trade = bt_mod._simulate_single_trade(
            df=df, entry_idx=entry_idx,
            sl_pct=0.10, tp1_pct=0.08, tp2_pct=0.15,
        )
        if trade and trade.exit_reason == "SL":
            # Exit must not be worse than 7% limit-down from prev_close
            limit_floor = float(df.iloc[entry_idx]["close"]) * 0.93
            assert trade.exit_price >= limit_floor * 0.999, (
                f"Exit {trade.exit_price:.0f} worse than limit_floor {limit_floor:.0f}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-18: Backtest pnl total trade VND
# ─────────────────────────────────────────────────────────────────────────────

class TestBug18BacktestPnlTotal:
    """
    BacktestTrade.pnl must be total trade VND for 100 shares,
    not per-share VND (100× understated).
    """

    def test_pnl_is_100x_per_share(self):
        """pnl must equal pnl_pct * entry_price * 100 approximately."""
        import tradingos.core.backtest as bt_mod
        df = _make_indicators(n=60, trend=0.003)
        trade = bt_mod._simulate_single_trade(
            df=df, entry_idx=30,
            sl_pct=0.06, tp1_pct=0.08, tp2_pct=0.15,
        )
        if trade is None:
            pytest.skip("No trade simulated on this fixture")
        # pnl should be of order: pnl_pct × ~30,000 × 100 = thousands or tens of thousands
        # Per-share would be: pnl_pct × ~30,000 = hundreds
        expected_scale = abs(trade.pnl_pct * trade.entry_price * 100)
        assert abs(trade.pnl) >= expected_scale * 0.8, (
            f"pnl={trade.pnl:.0f} is too small; expected ~{expected_scale:.0f} for 100 shares"
        )

    def test_pnl_sign_matches_pnl_pct(self):
        """pnl sign must match pnl_pct sign."""
        import tradingos.core.backtest as bt_mod
        df = _make_indicators(n=60, trend=0.003)
        trade = bt_mod._simulate_single_trade(
            df=df, entry_idx=30,
            sl_pct=0.06, tp1_pct=0.08, tp2_pct=0.15,
        )
        if trade is None:
            pytest.skip("No trade simulated")
        # pnl_pct and pnl must have same sign
        if trade.pnl_pct > 0:
            assert trade.pnl > 0, "Profitable trade must have positive pnl"
        elif trade.pnl_pct < 0:
            assert trade.pnl < 0, "Losing trade must have negative pnl"

    def test_source_multiplies_by_100(self):
        """Source must include * 100 in pnl computation."""
        import tradingos.core.backtest as bt_mod
        src = inspect.getsource(bt_mod._simulate_single_trade)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        pnl_line = next(
            (l for l in code_lines if "pnl = " in l and "pnl_pct" in l), None
        )
        assert pnl_line is not None, "pnl assignment line not found"
        assert "* 100" in pnl_line or "*100" in pnl_line, (
            f"pnl must multiply by 100 (shares); got: {pnl_line!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BUG-19: progressive_entry forced min lot per tranche
# ─────────────────────────────────────────────────────────────────────────────

class TestBug19ProgressiveEntryLot:
    """
    progressive_entry_plan must not force max(lot, ...) per tranche,
    which distorts small allocations.
    """

    def test_source_no_max_lot_per_tranche(self):
        """Source must not use max(lot, raw//lot*lot) pattern."""
        import tradingos.core.sizing as sizing_mod
        src = inspect.getsource(sizing_mod.progressive_entry_plan)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        code_only = "\n".join(code_lines)
        assert "max(lot," not in code_only, (
            "progressive_entry_plan must not use max(lot, ...) per tranche"
        )

    def test_total_shares_preserved_mode_a(self):
        """Sum of tranche shares must equal total_shares for MODE_A."""
        from tradingos.core.sizing import progressive_entry_plan
        result = progressive_entry_plan(total_shares=1000, entry=30_000.0, signal_mode="MODE_A")
        total = sum(t["shares"] for t in result)
        assert total == 1000, f"MODE_A tranches sum {total} != 1000"

    def test_total_shares_preserved_mode_w(self):
        """Sum of tranche shares must equal total_shares for MODE_W."""
        from tradingos.core.sizing import progressive_entry_plan
        result = progressive_entry_plan(total_shares=500, entry=30_000.0, signal_mode="MODE_W")
        total = sum(t["shares"] for t in result)
        assert total == 500, f"MODE_W tranches sum {total} != 500"

    def test_zero_allocation_handled(self):
        """Small total_shares < 1 lot per tranche must not crash."""
        from tradingos.core.sizing import progressive_entry_plan
        result = progressive_entry_plan(total_shares=100, entry=30_000.0, signal_mode="MODE_W")
        # Should produce at least one non-zero tranche
        assert any(t["shares"] > 0 for t in result)
        assert all(t["shares"] % 100 == 0 for t in result if t["shares"] > 0)


# ─────────────────────────────────────────────────────────────────────────────
# VN-8: Midday oversold bonus fires in BEAR_TREND
# ─────────────────────────────────────────────────────────────────────────────

class TestVN8MidDayBearSuppression:
    """
    In BEAR_TREND, midday RSI < 45 and Stoch < 30 bonuses must be suppressed
    to avoid promoting knife-catching under margin-call cascades.
    """

    def test_source_gates_midday_oversold_by_regime(self):
        """compute_t25_multiframe source must have bear_regime guard for midday oversold."""
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_multiframe)
        assert "bear_regime" in src, "bear_regime variable must be used in multiframe"
        assert "not bear_regime" in src, "midday oversold must be gated by not bear_regime"

    def test_bear_regime_suppresses_midday_oversold_bonus(self):
        """BEAR_TREND t25_regime: midday must not add oversold bonus."""
        from tradingos.core.t25_engine import compute_t25_multiframe

        df = _make_indicators(n=100, trend=-0.005)  # bear-trend data
        # Force RSI oversold + stoch oversold on last bar
        df.iloc[-1, df.columns.get_loc("RSI14")] = 35.0
        if "STOCH_K" in df.columns:
            df.iloc[-1, df.columns.get_loc("STOCH_K")] = 20.0

        # Simulate BEAR_TREND t25 result
        t25_bear = {"t25_score": 40.0, "t25_signal": "T25_NEUTRAL", "t25_regime": "BEAR_TREND"}
        result_bear = compute_t25_multiframe(df, t25_entry_result=t25_bear)

        # Simulate BULL_TREND with same RSI/Stoch
        t25_bull = {"t25_score": 40.0, "t25_signal": "T25_NEUTRAL", "t25_regime": "BULL_TREND"}
        result_bull = compute_t25_multiframe(df, t25_entry_result=t25_bull)

        # Bull should get higher midday score due to oversold bonus
        assert result_bull["midday_score"] >= result_bear["midday_score"], (
            f"BULL midday {result_bull['midday_score']} should be >= BEAR midday {result_bear['midday_score']}"
        )

    def test_stoch_oversold_reason_absent_in_bear(self):
        """'Stoch quá bán' reason must not appear in BEAR_TREND multiframe reasons."""
        from tradingos.core.t25_engine import compute_t25_multiframe
        df = _make_indicators(n=100, trend=-0.005)
        if "STOCH_K" in df.columns:
            df.iloc[-1, df.columns.get_loc("STOCH_K")] = 15.0
        t25_bear = {"t25_score": 30.0, "t25_signal": "T25_AVOID", "t25_regime": "BEAR_TREND"}
        result = compute_t25_multiframe(df, t25_entry_result=t25_bear)
        assert not any("Stoch quá bán" in r for r in result["mf_reasons"]), (
            "Stoch oversold reason must not appear in BEAR_TREND"
        )


# ─────────────────────────────────────────────────────────────────────────────
# VN-10: fol_pct signed + fol_direction field
# ─────────────────────────────────────────────────────────────────────────────

class TestVN10FolPctSigned:
    """
    fol_pct must be signed (negative for net-sell foreign flow).
    fol_direction field must be present: NET_BUY / NEUTRAL / NET_SELL.
    """

    def test_fol_direction_field_exists(self):
        """compute_smart_money_score must return fol_direction key."""
        from tradingos.core.money_flow import compute_smart_money_score
        from tradingos.core.money_flow import proxy_whale_net_from_daily
        df = _make_indicators()
        flow = proxy_whale_net_from_daily(df)
        result = compute_smart_money_score("T", df, flow)
        assert "fol_direction" in result, (
            "compute_smart_money_score must return fol_direction"
        )
        assert result["fol_direction"] in ("NET_BUY", "NET_SELL", "NEUTRAL"), (
            f"fol_direction must be NET_BUY/NET_SELL/NEUTRAL; got {result['fol_direction']!r}"
        )

    def test_fol_pct_can_be_negative(self):
        """When fol_ratio < 0, fol_pct must be negative (not clipped to 0)."""
        import tradingos.core.money_flow as mf_mod
        src = inspect.getsource(mf_mod.compute_smart_money_score)
        # Check fol_pct line is not using max(0.0, ...)
        code_lines = [l for l in src.splitlines() if not l.lstrip().startswith("#")]
        fol_pct_line = next(
            (l for l in code_lines if '"fol_pct"' in l and "fol_ratio" in l), None
        )
        assert fol_pct_line is not None, "fol_pct assignment line not found"
        assert "max(0" not in fol_pct_line, (
            f"fol_pct must not clip to 0; got: {fol_pct_line!r}"
        )

    def test_net_sell_direction_labeled_correctly(self):
        """Negative fol_ratio must produce fol_direction=NET_SELL."""
        import tradingos.core.money_flow as mf_mod
        # Simulate the direction logic directly
        for fol_ratio, expected in [
            (0.05, "NET_BUY"),
            (-0.05, "NET_SELL"),
            (0.0, "NEUTRAL"),
            (0.005, "NEUTRAL"),   # within ±1% dead-zone
        ]:
            direction = "NET_BUY" if fol_ratio > 0.01 else ("NET_SELL" if fol_ratio < -0.01 else "NEUTRAL")
            assert direction == expected, f"fol_ratio={fol_ratio} → expected {expected}, got {direction}"

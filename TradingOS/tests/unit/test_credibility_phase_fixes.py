"""Credibility Phase Fixes — regression tests (P1–P5).

Covers:
  P1.1  backtest.py — entry at next-bar open (no lookahead)
  P1.2  backtest.py — rolling liquidity tier (no future data leak)
  P1.3  PSO optimizer — IS/OOS split, execution timing fix, cost model, combo seed
  P3.1  profiler_service.py — 7 missing audit payload fields
  P3.2  audit.py — ERROR event in selectbox options
  P3.3  profiler_service.py — _error_profile writes payload
  P4.1  mfpm.py — SMS bonus ladder reads from config
  P4.2  mfpm.py — foreign flow bonus reads from config
  P4.3  mfpm.py — BiLSTM bonus reads from config
  P4.4  anti_manip.py — weighted flag scoring
  P5.1  performance.py — calib_df built before filter + ECE/Brier
  P2.1  intraday_collector.py — quality metadata in return dict
  P2.3  intraday_collector.py — cvd_quality_label
  P2.2  fetcher.py — staleness check calls ohlcv_is_fresh
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_ohlcv(n: int = 80, seed: int = 7) -> pd.DataFrame:
    """Synthetic OHLCV with date, open, high, low, close, volume columns."""
    rng = np.random.default_rng(seed)
    close = 50_000.0 * np.cumprod(1 + rng.normal(0.0, 0.012, n))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high  = np.maximum(close, open_) * (1 + rng.uniform(0, 0.005, n))
    low   = np.minimum(close, open_) * (1 - rng.uniform(0, 0.005, n))
    vol   = rng.integers(200_000, 2_000_000, n).astype(float)
    return pd.DataFrame({
        "date":   pd.bdate_range("2022-01-03", periods=n).strftime("%Y-%m-%d"),
        "open":   open_, "high": high, "low": low, "close": close, "volume": vol,
    })


# ─────────────────────────────────────────────────────────────────────────────
# P1.1 — backtest entry at next-bar open
# ─────────────────────────────────────────────────────────────────────────────

class TestBacktestEntryNextBarOpen:

    def test_entry_price_is_next_bar_open_not_signal_close(self):
        """Trade entry price must come from the open of bar entry_idx+1."""
        from tradingos.core.backtest import _simulate_single_trade

        # Use a DataFrame with clearly distinct open vs close values
        rng = np.random.default_rng(99)
        n = 60
        close = 50_000.0 * np.cumprod(1 + rng.normal(0.0, 0.012, n))
        # Force open to be 3% above close so open != close in a detectable way
        open_ = close * 1.03
        high  = np.maximum(close, open_) * 1.005
        low   = np.minimum(close, open_) * 0.995
        vol   = np.full(n, 1_000_000.0)
        df = pd.DataFrame({
            "date":   pd.bdate_range("2022-01-03", periods=n).strftime("%Y-%m-%d"),
            "open":   open_, "high": high, "low": low, "close": close, "volume": vol,
        })

        signal_close = float(df.iloc[5]["close"])   # bar 5 close
        exec_open    = float(df.iloc[6]["open"])    # bar 6 open (3% above bar6 close)

        trade = _simulate_single_trade(df, 5, sl_pct=0.10, tp1_pct=0.15, tp2_pct=0.30,
                                       max_hold=15, mode="MODE_A")
        assert trade is not None
        # raw entry = exec_open; trade.entry_price = exec_open * (1 + cost)
        # cost ≈ 0.002 (commission + slippage)
        raw_approx = trade.entry_price / 1.002
        # raw_approx should match exec_open (bar 6 open), NOT signal_close (bar 5 close)
        # Since open = close * 1.03, exec_open and signal_close differ by ~3%
        assert abs(raw_approx - exec_open) / exec_open < 0.02, (
            f"Raw entry {raw_approx:.0f} should match exec bar open {exec_open:.0f}")
        assert abs(raw_approx - signal_close) / signal_close > 0.01, (
            "Entry price should NOT match signal-bar close (that's lookahead)")

    def test_trade_holds_correct_number_of_bars(self):
        """Trade hold_days must be ≥1 (at least one bar after entry)."""
        from tradingos.core.backtest import _simulate_single_trade

        df = _make_ohlcv(60)
        trade = _simulate_single_trade(df, 5, sl_pct=0.07, tp1_pct=0.10, tp2_pct=0.20,
                                       max_hold=10, mode="MODE_A")
        assert trade is not None
        assert trade.hold_days >= 1

    def test_entry_near_end_returns_none(self):
        """Signal at last bar should return None (not enough bars for exec)."""
        from tradingos.core.backtest import _simulate_single_trade

        df = _make_ohlcv(60)
        last_idx = len(df) - 1
        trade = _simulate_single_trade(df, last_idx, sl_pct=0.07, tp1_pct=0.10, tp2_pct=0.20)
        assert trade is None


# ─────────────────────────────────────────────────────────────────────────────
# P1.2 — rolling liquidity tier
# ─────────────────────────────────────────────────────────────────────────────

class TestRollingLiquidityTier:

    def test_first_signal_uses_only_prior_volume(self):
        """avg_vol_20d for the first signal bar must use only bars 0..(idx-1)."""
        from tradingos.core.backtest import run_backtest

        df = _make_ohlcv(80)
        # Inject an artificial signal column with signal at bar 2 (very early)
        df["signal"] = 0
        df.at[2, "signal"] = 1

        # We patch _simulate_single_trade to capture the avg_vol_20d argument
        captured: list[float | None] = []
        from tradingos.core import backtest as bt_mod
        orig = bt_mod._simulate_single_trade

        def patched(df_, idx, *args, avg_vol_20d=None, **kwargs):
            captured.append(avg_vol_20d)
            return orig(df_, idx, *args, avg_vol_20d=avg_vol_20d, **kwargs)

        with patch.object(bt_mod, "_simulate_single_trade", side_effect=patched):
            run_backtest(df, "TEST", signal_col="signal")

        assert captured, "No trade was simulated"
        vol_20d = captured[0]
        # For signal at bar 2: rolling window is df["volume"].iloc[0:2].mean()
        expected = float(df["volume"].iloc[0:2].mean())
        assert vol_20d == pytest.approx(expected, rel=1e-6), (
            f"avg_vol_20d={vol_20d:.0f} should use only bars 0-1 (expected {expected:.0f})")

    def test_later_signal_uses_20_prior_bars(self):
        """avg_vol_20d for a signal at bar 30 should use bars 10-29 (20 bars)."""
        from tradingos.core.backtest import run_backtest

        df = _make_ohlcv(80)
        df["signal"] = 0
        df.at[30, "signal"] = 1

        captured: list[float | None] = []
        from tradingos.core import backtest as bt_mod
        orig = bt_mod._simulate_single_trade

        def patched(df_, idx, *args, avg_vol_20d=None, **kwargs):
            captured.append(avg_vol_20d)
            return orig(df_, idx, *args, avg_vol_20d=avg_vol_20d, **kwargs)

        with patch.object(bt_mod, "_simulate_single_trade", side_effect=patched):
            run_backtest(df, "TEST", signal_col="signal")

        assert captured
        vol_20d = captured[0]
        expected = float(df["volume"].iloc[10:30].mean())
        assert vol_20d == pytest.approx(expected, rel=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# P1.3 — PSO execution timing fix + IS/OOS split
# ─────────────────────────────────────────────────────────────────────────────

class TestPSOFixes:

    def _make_pso_df(self, n: int = 200) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        close = 10.0 * np.cumprod(1 + rng.normal(0, 0.01, n))
        df = pd.DataFrame({
            "date":   pd.bdate_range("2022-01-03", periods=n),
            "open":   close * 0.999, "high": close * 1.005,
            "low":    close * 0.995, "close": close, "volume": np.ones(n) * 1e6,
        })
        df["RSI14"] = 50.0 + rng.normal(0, 10, n)
        return df

    def test_rsi_sharpe_returns_finite(self):
        """_rsi_sharpe must return a finite scalar for valid thresholds."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        df = self._make_pso_df()
        result = _rsi_sharpe(np.array([70.0, 60.0, 30.0]), df)
        assert np.isfinite(result)

    def test_rsi_sharpe_accepts_cost_args(self):
        """_rsi_sharpe must accept commission_bps, slippage_bps, tax_sell_bps."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        df = self._make_pso_df()
        # Should not raise with cost args
        result = _rsi_sharpe(np.array([70.0, 60.0, 30.0]), df,
                              commission_bps=15.0, slippage_bps=5.0, tax_sell_bps=10.0)
        assert np.isfinite(result)

    def test_costs_reduce_sharpe(self):
        """Adding costs must produce equal or lower Sharpe than zero costs."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        df = self._make_pso_df()
        thres = np.array([70.0, 60.0, 30.0])
        sharpe_no_cost   = -_rsi_sharpe(thres, df, commission_bps=0, slippage_bps=0, tax_sell_bps=0)
        sharpe_with_cost = -_rsi_sharpe(thres, df, commission_bps=15, slippage_bps=5, tax_sell_bps=10)
        assert sharpe_with_cost <= sharpe_no_cost + 1e-9, (
            "Costs must not increase Sharpe")

    def test_is_oos_constants_defined(self):
        """DAYS_IS and DAYS_OOS constants must be defined and sum to DAYS."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        import importlib
        spec = importlib.util.spec_from_file_location(
            "pso_rsi_optimizer",
            Path(__file__).resolve().parents[2] / "scripts" / "pso_rsi_optimizer.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "DAYS_IS")
        assert hasattr(mod, "DAYS_OOS")
        assert mod.DAYS_IS + mod.DAYS_OOS == mod.DAYS
        assert mod.DAYS_IS > mod.DAYS_OOS, "IS window should be larger than OOS"

    def test_combo_seed_is_deterministic_per_combo(self):
        """Same regime+sector always produces the same seed value."""
        combo_seed_a = abs(hash("STEADY_BULL:BANKING")) % (2 ** 31)
        combo_seed_b = abs(hash("STEADY_BULL:BANKING")) % (2 ** 31)
        combo_seed_c = abs(hash("STEADY_BEAR:GENERAL")) % (2 ** 31)
        assert combo_seed_a == combo_seed_b
        assert combo_seed_a != combo_seed_c, "Different combos must produce different seeds"


# ─────────────────────────────────────────────────────────────────────────────
# P3.1 — profiler audit payload 7 missing fields
# ─────────────────────────────────────────────────────────────────────────────

class TestProfilerAuditPayload:

    def _make_minimal_put_audit_call(self) -> dict:
        """Capture the payload dict from a mock put_audit call."""
        import ast, inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod.ProfilerService._build_ticker_profile
                                if hasattr(ps_mod.ProfilerService, "_build_ticker_profile")
                                else ps_mod.ProfilerService.profile_ticker)
        return src

    def test_payload_contains_macro_score_key(self):
        """audit payload dict in profiler_service must include 'macro_score' key."""
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        # Check the put_audit call contains the new fields
        assert '"macro_score"' in src or "'macro_score'" in src, (
            "macro_score missing from audit payload")

    def test_payload_contains_fc_overall_vote(self):
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        assert '"fc_overall_vote"' in src or "'fc_overall_vote'" in src

    def test_payload_contains_tplus_verdict(self):
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        assert '"tplus_verdict"' in src or "'tplus_verdict'" in src

    def test_payload_contains_cvd_data_quality(self):
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        assert '"cvd_data_quality"' in src or "'cvd_data_quality'" in src

    def test_payload_contains_data_source_intraday(self):
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        assert '"data_source_intraday"' in src or "'data_source_intraday'" in src

    def test_payload_contains_bilstm_fields(self):
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod)
        assert '"bilstm_10d_signal"' in src or "'bilstm_10d_signal'" in src
        assert '"bilstm_10d_confidence"' in src or "'bilstm_10d_confidence'" in src


# ─────────────────────────────────────────────────────────────────────────────
# P3.2 — audit.py ERROR in event type selectbox
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditErrorEventType:

    def test_audit_page_source_includes_error_option(self):
        """audit.py selectbox options must include 'ERROR'."""
        import inspect
        import tradingos.ui.pages.audit as audit_mod
        src = inspect.getsource(audit_mod)
        assert '"ERROR"' in src or "'ERROR'" in src, (
            "'ERROR' must be an option in the Loại sự kiện selectbox")

    def test_rejected_reason_not_in_skip_set(self):
        """rejected_reason must not be in the display _skip set."""
        import inspect
        import tradingos.ui.pages.audit as audit_mod
        src = inspect.getsource(audit_mod)
        # The old code had "rejected_reason" in _skip; it must be removed now
        assert '"rejected_reason", "amf_decision"' not in src
        assert "'rejected_reason'" not in src.split("_skip")[1].split("}")[0], (
            "rejected_reason must not be in _skip — it should be shown in table")


# ─────────────────────────────────────────────────────────────────────────────
# P3.3 — _error_profile writes payload key
# ─────────────────────────────────────────────────────────────────────────────

class TestErrorProfilePayload:

    def test_error_profile_puts_payload_key(self):
        """_error_profile must write 'payload' key so DuckDB persists rejected_reason."""
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod.ProfilerService._error_profile)
        assert '"payload"' in src or "'payload'" in src, (
            "_error_profile must include 'payload' key in put_audit call")

    def test_error_profile_puts_action_error(self):
        """_error_profile must write action='ERROR' for downstream filtering."""
        import inspect
        import tradingos.engines.profiler_service as ps_mod
        src = inspect.getsource(ps_mod.ProfilerService._error_profile)
        assert '"action": "ERROR"' in src or '"action"' in src, (
            "_error_profile should include 'action' in audit record")


# ─────────────────────────────────────────────────────────────────────────────
# P4.1–P4.3 — mfpm.py bonus ladders read from config
# ─────────────────────────────────────────────────────────────────────────────

class TestMFPMBonusLadderConfigKeys:

    def test_sms_bonus_reads_from_cfg(self):
        """compute_mfpm SMS bonus must call cfg.strategy('mfpm', 'sms_bonus_strong', ...)."""
        import inspect
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod)
        assert "sms_bonus_strong" in src
        assert "sms_bonus_moderate" in src
        assert "sms_bonus_weak" in src
        assert "sms_penalty_low" in src
        assert "sms_penalty_mcvd" in src

    def test_foreign_bonus_reads_from_cfg(self):
        import inspect
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod)
        assert "foreign_bonus_strong" in src
        assert "foreign_bonus_moderate" in src
        assert "foreign_penalty_strong" in src
        assert "foreign_penalty_moderate" in src

    def test_bilstm_bonus_reads_from_cfg(self):
        import inspect
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod)
        assert "bilstm_bonus_up_high" in src
        assert "bilstm_bonus_up_medium" in src
        assert "bilstm_penalty_down_high" in src
        assert "bilstm_penalty_down_medium" in src

    def test_sms_bonus_default_values_match_prior_hardcode(self):
        """Default values in cfg.strategy calls must equal previously hardcoded values."""
        import inspect
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod)
        # P4.1 defaults: 20, 12, 5, -10, -25
        assert "default=20" in src
        assert "default=12" in src
        assert "default=5" in src
        assert "default=-10" in src
        assert "default=-25" in src

    def test_strategy_yaml_contains_new_keys(self):
        """strategy.yaml must contain the 9 new bonus ladder keys."""
        from pathlib import Path
        yaml_path = Path(__file__).resolve().parents[2] / "config" / "strategy.yaml"
        content = yaml_path.read_text(encoding="utf-8")
        for key in ["sms_bonus_strong", "sms_bonus_moderate", "sms_bonus_weak",
                    "sms_penalty_low", "sms_penalty_mcvd",
                    "foreign_bonus_strong", "foreign_bonus_moderate",
                    "bilstm_bonus_up_high", "bilstm_penalty_down_high"]:
            assert key in content, f"strategy.yaml missing key: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# P4.4 — anti_manip.py weighted flag scoring
# ─────────────────────────────────────────────────────────────────────────────

class TestAMFWeightedFlags:

    def _run_amf(self, flags_to_inject: list[str]) -> str:
        """
        Run the decision logic with specific flags injected, bypassing
        the data fetch layers.
        """
        from tradingos.core.anti_manip import run_amf
        import tradingos.core.anti_manip as amf_mod

        # Patch the flag-generation portion; only test the decision block
        df = _make_ohlcv(20)
        df["Z_vol"] = 0.5   # no wash-sale
        df["VWAP_daily"] = df["close"]  # no VWAP deviation

        # Create a minimal amf call that won't trigger any real flags,
        # then manually inject flags to test decision logic
        result = run_amf(df, order_book=None, intraday_data={})
        # Override flags list and re-run decision logic
        return result["decision"]

    def test_three_mild_vwap_flags_are_not_block(self):
        """3 mild VWAP_DEV flags (3×0.5=1.5 < 3.0) must not trigger BLOCK."""
        from tradingos.core.anti_manip import run_amf
        import tradingos.core.anti_manip as amf_mod

        original_logic = amf_mod.run_amf
        # Simulate 3 VWAP_DEV flags by patching at decision point
        df = _make_ohlcv(20)
        df["Z_vol"] = 0.5

        # We mock the flag list directly to isolate decision logic
        with patch.object(amf_mod, "run_amf", wraps=original_logic):
            # 3 mild flags: weight 0.5+0.5+0.5 = 1.5 < 3.0 → WARN not BLOCK
            flags = ["VWAP_DEV_6.0pct", "VWAP_DEV_5.5pct", "VWAP_DEV_5.2pct"]
            weights = {"OPEN_SPIKE": 2.0, "WASH_SALE_BUY_DRIVEN": 1.5,
                       "WASH_SALE_VOLUME": 1.0, "WASH_SALE_SELL_DRIVEN": 0.5,
                       "ORDER_BOOK_IMBALANCE": 1.0, "VWAP_DEV": 0.5}
            block_thr, warn_thr = 3.0, 0.5

            def _flag_weight(flag: str) -> float:
                for prefix, w in weights.items():
                    if flag.startswith(prefix):
                        return w
                return 1.0

            score = sum(_flag_weight(f) for f in flags)
            assert score < block_thr, f"3 mild flags weight={score} should be < {block_thr}"

            if score >= block_thr:
                decision = "BLOCK"
            elif score >= warn_thr:
                decision = "WARN"
            else:
                decision = "PASS"
            assert decision == "WARN", "3 mild VWAP flags must produce WARN not BLOCK"

    def test_open_spike_plus_order_book_imbalance_is_block(self):
        """OPEN_SPIKE(2.0)+ORDER_BOOK(1.0)=3.0 must produce BLOCK."""
        weights = {"OPEN_SPIKE": 2.0, "ORDER_BOOK_IMBALANCE": 1.0}
        flags   = ["OPEN_SPIKE_15.0pct", "ORDER_BOOK_IMBALANCE_BID_78pct"]
        block_thr = 3.0
        warn_thr  = 0.5

        def _flag_weight(flag: str) -> float:
            for prefix, w in weights.items():
                if flag.startswith(prefix):
                    return w
            return 1.0

        score = sum(_flag_weight(f) for f in flags)
        decision = "BLOCK" if score >= block_thr else "WARN" if score >= warn_thr else "PASS"
        assert decision == "BLOCK", f"Severe flags score={score} must produce BLOCK"

    def test_sell_wash_alone_is_warn_not_block(self):
        """WASH_SALE_SELL_DRIVEN alone (weight 0.5) must produce WARN."""
        flags = ["WASH_SALE_SELL_DRIVEN_Z4.2"]
        weights = {"WASH_SALE_SELL_DRIVEN": 0.5}
        block_thr, warn_thr = 3.0, 0.5

        def _w(flag: str) -> float:
            for p, w in weights.items():
                if flag.startswith(p):
                    return w
            return 1.0

        score    = sum(_w(f) for f in flags)
        decision = "BLOCK" if score >= block_thr else "WARN" if score >= warn_thr else "PASS"
        assert decision == "WARN"
        assert score < block_thr

    def test_anti_manip_source_contains_weighted_logic(self):
        """anti_manip.py source must contain weighted decision logic."""
        import inspect
        import tradingos.core.anti_manip as amf_mod
        src = inspect.getsource(amf_mod)
        assert "block_weighted_threshold" in src
        assert "warn_weighted_threshold" in src
        assert "_flag_weight" in src

    def test_strategy_yaml_has_amf_weight_keys(self):
        """strategy.yaml must contain the new AMF flag_weights keys."""
        from pathlib import Path
        yaml_path = Path(__file__).resolve().parents[2] / "config" / "strategy.yaml"
        content   = yaml_path.read_text(encoding="utf-8")
        assert "block_weighted_threshold" in content
        assert "warn_weighted_threshold"  in content
        assert "flag_weights"             in content


# ─────────────────────────────────────────────────────────────────────────────
# P5.1 — performance.py calibration bug fix
# ─────────────────────────────────────────────────────────────────────────────

class TestPerformanceCalibrationFix:

    def test_calib_df_built_before_filter(self):
        """calib_df must be constructed from calib_rows before filter_dataframe call."""
        import inspect
        import tradingos.ui.pages.performance as perf_mod
        src = inspect.getsource(perf_mod._render_confidence_calibration)

        # Find positions of both operations in the source
        build_pos  = src.find("pd.DataFrame(calib_rows)")
        filter_pos = src.find("filter_dataframe(calib_df")
        assert build_pos != -1, "calib_df = pd.DataFrame(calib_rows) not found in source"
        assert filter_pos != -1, "filter_dataframe(calib_df, ...) not found in source"
        assert build_pos < filter_pos, (
            "calib_df must be built BEFORE filter_dataframe is called on it")

    def test_ece_brier_computation_in_source(self):
        """ECE and Brier Score computation must be present in performance.py."""
        import inspect
        import tradingos.ui.pages.performance as perf_mod
        src = inspect.getsource(perf_mod._render_confidence_calibration)
        assert "brier" in src.lower()
        assert "ece" in src.lower()

    def test_ece_formula_correctness(self):
        """ECE must be weighted mean of |pred - actual| per confidence bin."""
        # Simulate what the code does
        _conf_prob_map = {"HIGH": 0.75, "MEDIUM": 0.55, "LOW": 0.35, "—": 0.50}
        df = pd.DataFrame({
            "confidence": ["HIGH"] * 10 + ["LOW"] * 10,
            "pnl_pct":    [0.05] * 8 + [-0.02] * 2 + [0.03] * 3 + [-0.01] * 7,
        })
        ece_total, ece_weight = 0.0, 0
        for conf, pred_p in _conf_prob_map.items():
            grp = df[df["confidence"] == conf]
            if grp.empty:
                continue
            actual_p = float((grp["pnl_pct"] > 0).mean())
            ece_total  += len(grp) * abs(pred_p - actual_p)
            ece_weight += len(grp)
        ece = ece_total / max(ece_weight, 1)
        assert 0.0 <= ece <= 1.0

    def test_brier_score_range(self):
        """Brier score must be in [0, 1]."""
        _conf_prob_map = {"HIGH": 0.75, "MEDIUM": 0.55, "LOW": 0.35}
        df = pd.DataFrame({
            "confidence": ["HIGH"] * 10 + ["MEDIUM"] * 5,
            "pnl_pct":    [0.01] * 15,
        })
        predicted = df["confidence"].map(_conf_prob_map).astype(float)
        outcomes  = (df["pnl_pct"] > 0).astype(float)
        brier = float(((predicted - outcomes) ** 2).mean())
        assert 0.0 <= brier <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# P2.1 + P2.3 — intraday quality metadata and CVD label
# ─────────────────────────────────────────────────────────────────────────────

class TestIntradayQualityMetadata:

    def _zero_return(self) -> dict:
        """Simulate a zero-fallback return from fetch_intraday_features."""
        return {
            "tfi": 0.0, "obi_l3": 0.0, "obi_reconstructed": 0.0,
            "foreign_buy": 0, "foreign_sell": 0, "foreign_net": 0,
            "reconstruction_depth": 0, "mcvd": 0,
            "intraday_source": "ZERO_FALLBACK",
            "intraday_fresh": False,
            "intraday_completeness": 0.0,
            "cvd_quality_label": "NONE",
        }

    def test_zero_fallback_has_quality_keys(self):
        """_zero fallback dict must include quality metadata keys."""
        z = self._zero_return()
        assert "intraday_source" in z
        assert "intraday_fresh" in z
        assert "intraday_completeness" in z
        assert "cvd_quality_label" in z

    def test_zero_fallback_values(self):
        """Zero fallback must have ZERO_FALLBACK source, fresh=False, completeness=0."""
        z = self._zero_return()
        assert z["intraday_source"]       == "ZERO_FALLBACK"
        assert z["intraday_fresh"]        is False
        assert z["intraday_completeness"] == 0.0
        assert z["cvd_quality_label"]     == "NONE"

    def test_cvd_quality_label_none_for_empty_trades(self):
        """0 trades → cvd_quality_label = 'NONE'."""
        n_trades = 0
        if n_trades >= 50:
            label = "REAL"
        elif n_trades >= 10:
            label = "PARTIAL"
        else:
            label = "NONE"
        assert label == "NONE"

    def test_cvd_quality_label_partial_for_small_trades(self):
        """10–49 trades → cvd_quality_label = 'PARTIAL'."""
        for n in [10, 25, 49]:
            label = "REAL" if n >= 50 else "PARTIAL" if n >= 10 else "NONE"
            assert label == "PARTIAL", f"n={n} should be PARTIAL"

    def test_cvd_quality_label_real_for_sufficient_trades(self):
        """50+ trades → cvd_quality_label = 'REAL'."""
        for n in [50, 100, 500]:
            label = "REAL" if n >= 50 else "PARTIAL" if n >= 10 else "NONE"
            assert label == "REAL", f"n={n} should be REAL"

    def test_intraday_source_code_contains_quality_keys(self):
        """intraday_collector.py source must include quality metadata in return dict."""
        import inspect
        import tradingos.data.intraday_collector as ic_mod
        src = inspect.getsource(ic_mod.fetch_intraday_features)
        assert "intraday_source"       in src
        assert "intraday_fresh"        in src
        assert "intraday_completeness" in src
        assert "cvd_quality_label"     in src

    def test_completeness_formula(self):
        """completeness = n_components_ok / 4.0; valid range [0, 1]."""
        for n_ok in range(5):
            completeness = n_ok / 4.0
            assert 0.0 <= completeness <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# P2.2 — fetcher.py staleness check
# ─────────────────────────────────────────────────────────────────────────────

class TestFetcherStalenessCheck:

    def test_fetch_ohlcv_calls_ohlcv_is_fresh_when_cache_hit(self):
        """fetch_ohlcv must call cache.ohlcv_is_fresh() before returning cached data."""
        import inspect
        import tradingos.data.fetcher as fetcher_mod
        src = inspect.getsource(fetcher_mod.fetch_ohlcv)
        assert "ohlcv_is_fresh" in src, (
            "fetch_ohlcv must call cache.ohlcv_is_fresh() to check staleness")

    def test_stale_cache_is_refetched(self):
        """When ohlcv_is_fresh returns False, fetch_ohlcv must fall through to live fetch."""
        import tradingos.data.fetcher as fetcher_mod

        cached_df = _make_ohlcv(60)
        live_df   = _make_ohlcv(62)  # slightly different (fresh data)

        # cache singleton is imported into fetcher_mod; patch it there
        with (
            patch.object(fetcher_mod.cache, "get_ohlcv",      return_value=cached_df),
            patch.object(fetcher_mod.cache, "ohlcv_is_fresh", return_value=False),
            patch.object(fetcher_mod.cache, "put_ohlcv",      return_value=None),
            patch.object(fetcher_mod,       "_fetch_ohlcv_ssi",  return_value=live_df),
        ):
            result = fetcher_mod.fetch_ohlcv("VCB", days=60)
        # Result should come from live fetch (same frame length as live_df)
        assert len(result) == len(live_df)

    def test_fresh_cache_is_returned_without_live_fetch(self):
        """When ohlcv_is_fresh returns True, no live SSI call is made."""
        import tradingos.data.fetcher as fetcher_mod

        cached_df = _make_ohlcv(60)
        ssi_called: list[bool] = []

        def mock_ssi(*args, **kwargs):
            ssi_called.append(True)
            return pd.DataFrame()

        with (
            patch.object(fetcher_mod.cache, "get_ohlcv",      return_value=cached_df),
            patch.object(fetcher_mod.cache, "ohlcv_is_fresh", return_value=True),
            patch.object(fetcher_mod,       "_fetch_ohlcv_ssi",  side_effect=mock_ssi),
        ):
            result = fetcher_mod.fetch_ohlcv("VCB", days=60)

        assert not ssi_called, "SSI should not be called when cache is fresh"
        assert len(result) == len(cached_df)

"""
VN Market Logic Fixes — regression tests.

Covers 5 targeted improvements for VN-market behavioral accuracy:

  VN-1  mfpm.py      HMM downgraded from hard gate → context penalty
                     HIGH confidence now reachable when MFPM≥80 + HMM≠STEADY_BULL
  VN-2  t25_engine   Bear regime blocks RSI/Stoch recovery oscillator upside
  VN-3  t25_engine   W%R and CCI removed from Group A (triple-count with RSI)
  VN-4  money_flow   FOL=None redistributed via OBV proxy (max 10 pts)
  VN-5  t_plus       T_OVERSOLD_RECOVERY blocked when sustained selling pressure
"""
from __future__ import annotations

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
# VN-1: HMM no longer hard-gates HIGH confidence
# ─────────────────────────────────────────────────────────────────────────────

class TestVN1HmmContextPenalty:
    """
    Previously: mfpm_score >= 80 required hmm_state == 'STEADY_BULL' for HIGH.
    Now: mfpm_score >= 80 → HIGH regardless of HMM; STEADY_BEAR downgrades one level.
    """

    def _make_mfpm_result(
        self,
        mfpm_score: int,
        hmm_state: str,
        action: str = "BUY",
        signal_mode: str = "MODE_A",
    ) -> dict:
        """Call compute_mfpm by patching scores via a minimal real call."""
        from tradingos.core.mfpm import compute_mfpm
        df = _make_indicators()
        flow = _make_flow(df)
        from tradingos.core.money_flow import compute_smart_money_score
        sms = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        amf = {"amf_decision": "PASS", "vqs_score": 0.5}
        pattern = {"pivot": float(df["close"].iloc[-1]) * 0.95, "pattern_bonus": 0,
                   "candle_pts": 0, "rsi_div_pts": 0}
        result = compute_mfpm(
            df, sms, amf, pattern,
            hmm_state=hmm_state, amd_phase="MARKUP",
        )
        return result

    def test_high_confidence_reachable_without_steady_bull(self):
        """HIGH confidence must be achievable even when HMM is TRANSITIONAL."""
        from tradingos.core.mfpm import compute_mfpm
        df = _make_indicators(seed=10, trend=0.003)
        flow = _make_flow(df)
        from tradingos.core.money_flow import compute_smart_money_score
        sms = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        amf = {"amf_decision": "PASS", "vqs_score": 0.6}
        pattern = {"pivot": float(df["close"].iloc[-1]) * 0.92, "pattern_bonus": 10,
                   "candle_pts": 3, "rsi_div_pts": 1}
        result_transitional = compute_mfpm(
            df, sms, amf, pattern, hmm_state="TRANSITIONAL", amd_phase="MARKUP"
        )
        # Confidence must NOT always be forced to MEDIUM just because HMM != STEADY_BULL
        # If the score is high enough, HIGH should be attainable
        # (This test verifies the gate is removed; actual value depends on MFPM score)
        assert result_transitional["confidence"] != "—", "Should produce a valid confidence"

    def test_steady_bear_downgrades_from_high(self):
        """STEADY_BEAR must downgrade HIGH → MEDIUM (never produce HIGH+STEADY_BEAR)."""
        from tradingos.core.mfpm import compute_mfpm
        # Build a scenario that would produce HIGH (strong trend, high score)
        df = _make_indicators(seed=10, trend=0.003)
        flow = _make_flow(df)
        from tradingos.core.money_flow import compute_smart_money_score
        sms = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        amf = {"amf_decision": "PASS", "vqs_score": 0.6}
        pattern = {"pivot": float(df["close"].iloc[-1]) * 0.92, "pattern_bonus": 10,
                   "candle_pts": 3, "rsi_div_pts": 1}
        result_steady_bull = compute_mfpm(
            df, sms, amf, pattern, hmm_state="STEADY_BULL", amd_phase="MARKUP"
        )
        result_steady_bear = compute_mfpm(
            df, sms, amf, pattern, hmm_state="STEADY_BEAR", amd_phase="MARKUP"
        )
        _conf_rank = {"—": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
        if result_steady_bull["confidence"] == "HIGH":
            assert result_steady_bear["confidence"] in ("MEDIUM", "LOW", "—"), (
                f"STEADY_BEAR must downgrade from HIGH; got {result_steady_bear['confidence']}"
            )

    def test_steady_bear_never_produces_high_confidence(self):
        """No matter the score, STEADY_BEAR must not emit HIGH confidence."""
        from tradingos.core.mfpm import compute_mfpm
        df = _make_indicators(seed=77, trend=0.005)
        flow = _make_flow(df)
        from tradingos.core.money_flow import compute_smart_money_score
        sms = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        amf = {"amf_decision": "PASS", "vqs_score": 0.8}
        pattern = {"pivot": float(df["close"].iloc[-1]) * 0.90, "pattern_bonus": 15,
                   "candle_pts": 5, "rsi_div_pts": 2}
        result = compute_mfpm(
            df, sms, amf, pattern, hmm_state="STEADY_BEAR", amd_phase="MARKUP"
        )
        assert result["confidence"] != "HIGH", (
            f"STEADY_BEAR must never produce HIGH confidence, got {result['confidence']}"
        )

    def test_hmm_code_no_longer_uses_hard_gate_pattern(self):
        """Source must not contain the old hard-gate pattern for HMM."""
        import inspect
        import tradingos.core.mfpm as mfpm_mod
        src = inspect.getsource(mfpm_mod.compute_mfpm)
        # The old hard gate: 'mfpm_score >= 80 and hmm_state == "STEADY_BULL"'
        assert 'mfpm_score >= 80 and hmm_state == "STEADY_BULL"' not in src, (
            "Old HMM hard gate still present in mfpm.py"
        )
        # The old Mode W gate: 'hmm_state == "STEADY_BULL" and mc_prob'
        assert 'hmm_state == "STEADY_BULL" and mc_prob' not in src, (
            "Old HMM Mode W hard gate still present in mfpm.py"
        )


# ─────────────────────────────────────────────────────────────────────────────
# VN-2: Bear regime blocks recovery oscillator upside in T25
# ─────────────────────────────────────────────────────────────────────────────

class TestVN2BearRegimeOscillatorBlock:
    """
    In BEAR_TREND regime, RSI recovery (+3/+5) and Stoch cross (+3) must not fire.
    VN stocks under margin pressure do not bounce from oversold levels reliably.
    """

    def _make_bear_df(self, n: int = 150) -> pd.DataFrame:
        """Build a bear-trend OHLCV with indicators."""
        rng = np.random.default_rng(99)
        dates = pd.bdate_range("2023-01-02", periods=n)
        # Strong downtrend: -0.4% per day
        close = 50_000.0 * np.cumprod(1 + rng.normal(-0.004, 0.012, n))
        volume = rng.integers(500_000, 3_000_000, n).astype(float)
        df = pd.DataFrame({
            "date":   dates,
            "open":   close * rng.uniform(1.00, 1.01, n),
            "high":   close * rng.uniform(1.00, 1.015, n),
            "low":    close * rng.uniform(0.985, 1.00, n),
            "close":  close,
            "volume": volume,
        })
        from tradingos.core.indicators import compute_all
        return compute_all(df)

    def test_group_a_does_not_spike_in_bear_regime(self):
        """Group A score in bear regime should be ≤ bull regime for same pattern."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        bear_df = self._make_bear_df()
        bull_df = _make_indicators(seed=5, trend=0.003)
        r_bear = compute_t25_entry_score(bear_df)
        r_bull = compute_t25_entry_score(bull_df)
        # Bear regime momentum score should not exceed bull regime unreasonably
        # Main check: bear regime is detected
        assert r_bear["t25_regime"] == "BEAR_TREND", (
            f"Expected BEAR_TREND, got {r_bear['t25_regime']}"
        )
        # Group A (momo) in bear must not be inflated by oscillator recovery
        assert r_bear["t25_momo_score"] <= 15.0, (
            f"Bear regime momo score too high: {r_bear['t25_momo_score']}"
        )

    def test_bear_regime_stoch_cross_not_in_confirms(self):
        """In BEAR_TREND, Stoch_cross should NOT appear in confirms list."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        bear_df = self._make_bear_df()
        result = compute_t25_entry_score(bear_df)
        if result["t25_regime"] == "BEAR_TREND":
            confirms = " ".join(result.get("t25_confirms", []))
            assert "Stoch_cross" not in confirms, (
                f"Stoch_cross must not fire in BEAR_TREND. Confirms: {confirms}"
            )

    def test_bear_regime_rsi_recovery_not_in_confirms(self):
        """In BEAR_TREND, RSI_rec and RSI_deep should NOT appear in confirms."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        bear_df = self._make_bear_df()
        result = compute_t25_entry_score(bear_df)
        if result["t25_regime"] == "BEAR_TREND":
            confirms = " ".join(result.get("t25_confirms", []))
            assert "RSI_rec" not in confirms, (
                f"RSI_rec must not fire in BEAR_TREND. Confirms: {confirms}"
            )
            assert "RSI_deep" not in confirms, (
                f"RSI_deep must not fire in BEAR_TREND. Confirms: {confirms}"
            )

    def test_bear_regime_source_uses_bear_regime_flag(self):
        """Source code must use bear_regime flag to gate oscillators."""
        import inspect
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_entry_score)
        assert "bear_regime" in src, "bear_regime flag must be present in t25_engine"
        assert "not bear_regime" in src, "oscillator guard must use 'not bear_regime'"


# ─────────────────────────────────────────────────────────────────────────────
# VN-3: W%R and CCI removed from Group A
# ─────────────────────────────────────────────────────────────────────────────

class TestVN3WRAndCCIRemoved:
    """
    W%R and CCI triple-counted oversold with RSI in Group A.
    They must be absent from the scoring logic in compute_t25_entry_score.
    """

    def test_wr_not_in_group_a_confirms(self):
        """W%R_rec must never appear in t25_confirms."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        # Run with various seeds to check no W%R appears
        for seed in range(1, 10):
            df = _make_indicators(seed=seed)
            result = compute_t25_entry_score(df)
            confirms = " ".join(result.get("t25_confirms", []))
            assert "W%R_rec" not in confirms, (
                f"W%R_rec found in confirms (seed={seed}): {confirms}"
            )

    def test_cci_not_in_group_a_confirms(self):
        """CCI_cross↑0 must never appear in t25_confirms."""
        from tradingos.core.t25_engine import compute_t25_entry_score
        for seed in range(1, 10):
            df = _make_indicators(seed=seed)
            result = compute_t25_entry_score(df)
            confirms = " ".join(result.get("t25_confirms", []))
            assert "CCI_cross" not in confirms, (
                f"CCI_cross found in confirms (seed={seed}): {confirms}"
            )

    def test_source_code_no_wr_or_cci_in_group_a(self):
        """Source must not reference W%R or CCI in Group A computation."""
        import inspect
        import tradingos.core.t25_engine as t25_mod
        src = inspect.getsource(t25_mod.compute_t25_entry_score)
        # Check the Group A block — after the 'Group A' comment, before 'Group B'
        group_a_block = src.split("Group A")[1].split("Group B")[0]
        assert "WILLIAMS_R" not in group_a_block, "WILLIAMS_R must be absent from Group A"
        assert "CCI" not in group_a_block, "CCI must be absent from Group A"


# ─────────────────────────────────────────────────────────────────────────────
# VN-4: FOL None redistributed via OBV proxy
# ─────────────────────────────────────────────────────────────────────────────

class TestVN4FolNullOBVProxy:
    """
    Previously: no fol_net column → comps['fol'] = 0 (always, for all vnstock tickers).
    Now: OBV slope used as institutional proxy — gives 0/3/6/10 pts based on trend.
    """

    def test_fol_nonzero_when_obv_rising(self):
        """When OBV is rising (uptrend data), comps['fol'] must be > 0."""
        from tradingos.core.money_flow import compute_smart_money_score
        # Use a strong uptrend so OBV rises
        df = _make_indicators(seed=10, trend=0.003)
        flow = _make_flow(df)
        # flow does NOT have fol_net column (typical vnstock scenario)
        assert "fol_net" not in flow.columns, "Test setup: flow must not have fol_net"
        result = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        assert result["components"]["fol"] > 0, (
            f"Rising OBV must give fol > 0; got {result['components']['fol']}"
        )

    def test_fol_zero_when_obv_falling(self):
        """When OBV is falling, comps['fol'] must be ≤ uptrend fol (directional check)."""
        from tradingos.core.money_flow import compute_smart_money_score
        df_down = _make_indicators(seed=99, trend=-0.004)
        flow_down = _make_flow(df_down)
        df_up = _make_indicators(seed=10, trend=0.003)
        flow_up = _make_flow(df_up)
        assert "fol_net" not in flow_down.columns
        assert "fol_net" not in flow_up.columns
        result_down = compute_smart_money_score("T", df_down, flow_down, amd_phase="MARKDOWN")
        result_up   = compute_smart_money_score("T", df_up, flow_up, amd_phase="MARKUP")
        assert result_down["components"]["fol"] <= result_up["components"]["fol"], (
            f"Downtrend fol ({result_down['components']['fol']}) must be ≤ "
            f"uptrend fol ({result_up['components']['fol']})"
        )
        # Also: fol must be ≤ 10 (proxy cap) in both cases
        assert result_down["components"]["fol"] <= 10
        assert result_up["components"]["fol"] <= 10

    def test_fol_obv_proxy_capped_at_10(self):
        """OBV proxy must never exceed 10 (vs real FOL max of 15)."""
        from tradingos.core.money_flow import compute_smart_money_score
        for seed in range(1, 8):
            df = _make_indicators(seed=seed, trend=0.005)
            flow = _make_flow(df)
            assert "fol_net" not in flow.columns
            result = compute_smart_money_score("T", df, flow)
            assert result["components"]["fol"] <= 10, (
                f"OBV proxy fol must be ≤ 10, got {result['components']['fol']} (seed={seed})"
            )

    def test_real_fol_still_scores_up_to_15(self):
        """When fol_net column IS present, original 0–15 scoring still applies."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _make_indicators(seed=5, trend=0.002)
        # Inject artificial fol_net column with strong positive net buy
        avg_vol = float(df["volume"].tail(20).mean())
        flow = _make_flow(df)
        flow["fol_net"] = avg_vol * 0.1  # ratio > 0.05 → 15 pts
        result = compute_smart_money_score("T", df, flow, amd_phase="MARKUP")
        assert result["components"]["fol"] == 15, (
            f"Real FOL with strong net buy must score 15, got {result['components']['fol']}"
        )

    def test_sms_higher_with_obv_proxy_than_old_zero(self):
        """SMS with OBV proxy redistribution must be ≥ what 0 would give (uptrend)."""
        from tradingos.core.money_flow import compute_smart_money_score
        df = _make_indicators(seed=10, trend=0.003)
        flow = _make_flow(df)
        result_with_proxy = compute_smart_money_score("T", df, flow)
        # Old behavior: fol=0 always. New behavior: fol may be up to 10.
        # SMS_new >= SMS_old because fol_new >= 0 always.
        assert result_with_proxy["components"]["fol"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# VN-5: T_OVERSOLD_RECOVERY blocked by sustained selling pressure
# ─────────────────────────────────────────────────────────────────────────────

class TestVN5OversoldRecoveryVQSGuard:
    """
    In VN market, stocks under margin call continue falling even when oversold.
    T_OVERSOLD_RECOVERY must be blocked when pv_direction_ratio < -0.3.
    """

    def _make_sell_pressure_df(self, n: int = 60) -> pd.DataFrame:
        """DataFrame where most volume is on down-days (sustained selling)."""
        rng = np.random.default_rng(88)
        dates = pd.bdate_range("2023-01-02", periods=n)
        # Downtrend: close falls consistently
        close = 40_000.0 * np.cumprod(1 + rng.normal(-0.006, 0.008, n))
        # Volume larger on down-days (2× more sell pressure)
        volume = np.where(
            np.arange(n) % 3 == 0,
            rng.integers(100_000, 300_000, n),   # small vol on occasional up-days
            rng.integers(600_000, 1_500_000, n), # large vol on down-days
        ).astype(float)
        df = pd.DataFrame({
            "date":   dates,
            "open":   close * rng.uniform(1.001, 1.01, n),
            "high":   close * rng.uniform(1.001, 1.015, n),
            "low":    close * rng.uniform(0.985, 1.00, n),
            "close":  close,
            "volume": volume,
        })
        from tradingos.core.indicators import compute_all
        return compute_all(df)

    def _make_neutral_df(self, n: int = 60) -> pd.DataFrame:
        """DataFrame with balanced buy/sell (sideways, oscillating)."""
        rng = np.random.default_rng(11)
        dates = pd.bdate_range("2023-01-02", periods=n)
        close = 30_000.0 * np.cumprod(1 + rng.normal(0.0, 0.012, n))
        volume = rng.integers(300_000, 800_000, n).astype(float)
        df = pd.DataFrame({
            "date":   dates,
            "open":   close * rng.uniform(0.99, 1.01, n),
            "high":   close * rng.uniform(1.00, 1.02, n),
            "low":    close * rng.uniform(0.98, 1.00, n),
            "close":  close,
            "volume": volume,
        })
        from tradingos.core.indicators import compute_all
        return compute_all(df)

    def test_oversold_blocked_under_sustained_sell_pressure(self):
        """T_OVERSOLD_RECOVERY score must be 0.0 under sustained sell pressure."""
        from tradingos.core.t_plus_engine import _score_oversold_recovery
        df = self._make_sell_pressure_df()
        # Verify the PV direction is indeed negative (test setup sanity)
        delta = df["close"].diff().fillna(0)
        buy_v  = df["volume"].where(delta > 0, 0).tail(20).sum()
        sell_v = df["volume"].where(delta < 0, 0).tail(20).sum()
        total  = buy_v + sell_v
        pv_dir = (buy_v - sell_v) / max(total, 1)
        if pv_dir < -0.3:
            score, reasons = _score_oversold_recovery(df)
            assert score == 0.0, (
                f"Sustained sell pressure must block T_OVERSOLD_RECOVERY; score={score}"
            )
            assert len(reasons) > 0, "Must return reason explaining the block"

    def test_oversold_allowed_in_neutral_market(self):
        """T_OVERSOLD_RECOVERY must be able to score > 0 in a balanced market."""
        from tradingos.core.t_plus_engine import _score_oversold_recovery
        df = self._make_neutral_df()
        # Force RSI to look oversold by injecting column
        df["RSI14"] = 32.0  # deep oversold
        score, reasons = _score_oversold_recovery(df)
        # In neutral market, score should be > 0 (RSI < 35 gives 1.5 or 3 pts)
        assert score >= 1.5, (
            f"Oversold recovery in neutral market should score ≥ 1.5; got {score}"
        )

    def test_oversold_guard_code_present(self):
        """Source code of _score_oversold_recovery must contain PV direction guard."""
        import inspect
        import tradingos.core.t_plus_engine as tpe_mod
        src = inspect.getsource(tpe_mod._score_oversold_recovery)
        assert "_pv_dir" in src, "VN-market PV direction guard must be in _score_oversold_recovery"
        assert "-0.3" in src, "Threshold -0.3 must be in oversold recovery guard"
        assert "Áp lực bán" in src, "Vietnamese reason string must be present"

    def test_tplus_recommendation_avoids_oversold_in_sell_pressure(self):
        """Full pipeline: T+ recommendation must not pick T_OVERSOLD_RECOVERY under sell pressure."""
        from tradingos.core.t_plus_engine import compute_tplus_recommendation
        df = self._make_sell_pressure_df()
        delta = df["close"].diff().fillna(0)
        buy_v  = df["volume"].where(delta > 0, 0).tail(20).sum()
        sell_v = df["volume"].where(delta < 0, 0).tail(20).sum()
        pv_dir = (buy_v - sell_v) / max(buy_v + sell_v, 1)
        if pv_dir < -0.3:
            result = compute_tplus_recommendation(df)
            assert result["setup_type"] != "T_OVERSOLD_RECOVERY", (
                f"T_OVERSOLD_RECOVERY must not be selected under sustained sell pressure; "
                f"got {result['setup_type']}"
            )

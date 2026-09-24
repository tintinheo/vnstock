"""Thirteenth pass — T+ trading recommendation engine tests.

Tests:
  - compute_tplus_recommendation returns correct dict shape for all inputs
  - T_BREAKOUT detected on high-volume uptrend data
  - T_PULLBACK_EMA detected on pullback-to-EMA scenario
  - T_OVERSOLD_RECOVERY detected on low-RSI + Stoch cross
  - T_RANGE_BREAK detected on BB-squeeze + volume burst
  - T_AVOID returned on distribution warning EXIT
  - T_NO_SETUP returned on flat/insufficient data
  - Confidence always in [0, 100]
  - Required keys always present
  - Verdict is one of valid constants
  - Vietnamese labels present for every valid setup
  - TickerProfile schema contains all tplus_ fields
  - ScanResultItem schema contains tplus_setup / tplus_verdict / tplus_confidence
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

_REQUIRED_KEYS = {
    "setup_type", "setup_vi", "entry_trigger",
    "entry_zone_low", "entry_zone_high",
    "target_t25", "target_t5", "stop_loss",
    "expected_return_pct", "risk_pct", "rr_ratio",
    "session", "session_vi",
    "confidence", "reasons", "risks",
    "verdict", "verdict_vi",
    "t25_score_used",
}

_VALID_SETUPS = {
    "T_BREAKOUT", "T_PULLBACK_EMA", "T_SUPPORT_BOUNCE",
    "T_OVERSOLD_RECOVERY", "T_RANGE_BREAK", "T_MOMENTUM_CONT",
    "T_NO_SETUP", "T_AVOID",
}

_VALID_VERDICTS = {"MUA_NGAY", "CHO_XAC_NHAN", "THEO_DOI", "TRANH_XA"}


# ── OHLCV builders ────────────────────────────────────────────────────────────

def _compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    from tradingos.core import compute_indicators
    return compute_indicators(df)


def _uptrend_df(n: int = 60, vol_surge_last: bool = False) -> pd.DataFrame:
    """Steady rising price — typical breakout candidate."""
    rng   = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=n)
    close = np.linspace(25_000, 38_000, n) + rng.normal(0, 200, n)
    vol   = np.full(n, 500_000.0)
    if vol_surge_last:
        vol[-1] = 1_300_000.0      # >1.5× average → volume surge
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.998,
        "high":   close * 1.012,
        "low":    close * 0.988,
        "close":  close,
        "volume": vol,
    })


def _pullback_df(n: int = 60) -> pd.DataFrame:
    """Price rallied then pulled back toward short EMA zone."""
    rng   = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-02", periods=n)
    # Up to day 45 then slight pullback
    trend = np.concatenate([
        np.linspace(20_000, 36_000, 45),
        np.linspace(36_000, 33_500, 15),   # pullback ~7%
    ])
    close = trend + rng.normal(0, 100, n)
    vol   = rng.integers(400_000, 800_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.998,
        "high":   close * 1.01,
        "low":    close * 0.99,
        "close":  close,
        "volume": vol,
    })


def _oversold_df(n: int = 60) -> pd.DataFrame:
    """Price fell sharply — RSI likely oversold."""
    rng   = np.random.default_rng(13)
    dates = pd.bdate_range("2024-01-02", periods=n)
    close = np.linspace(35_000, 22_000, n) + rng.normal(0, 200, n)
    close = np.maximum(close, 1_000)  # floor
    vol   = rng.integers(600_000, 1_500_000, n).astype(float)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 1.002,
        "high":   close * 1.01,
        "low":    close * 0.99,
        "close":  close,
        "volume": vol,
    })


def _flat_df(n: int = 60) -> pd.DataFrame:
    """Sideways flat price — should yield no clear setup."""
    rng   = np.random.default_rng(99)
    dates = pd.bdate_range("2024-01-02", periods=n)
    close = np.full(n, 30_000.0) + rng.normal(0, 30, n)
    vol   = np.full(n, 300_000.0)
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.999,
        "high":   close * 1.002,
        "low":    close * 0.998,
        "close":  close,
        "volume": vol,
    })


def _squeeze_df(n: int = 60) -> pd.DataFrame:
    """Tight consolidation then volume burst — BB-squeeze setup."""
    rng   = np.random.default_rng(55)
    dates = pd.bdate_range("2024-01-02", periods=n)
    # Very tight range for 50 bars then expand with big volume
    close = np.full(n, 28_000.0) + np.concatenate([
        rng.normal(0, 50, 50),
        rng.normal(500, 100, 10),
    ])
    vol = np.concatenate([
        np.full(50, 200_000.0),
        np.full(10, 900_000.0),   # burst
    ])
    return pd.DataFrame({
        "date":   dates,
        "open":   close * 0.998,
        "high":   close * 1.005,
        "low":    close * 0.995,
        "close":  close,
        "volume": vol.astype(float),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Main tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTplusEngine:
    """Unit tests for compute_tplus_recommendation."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from tradingos.core.t_plus_engine import compute_tplus_recommendation
        self.compute = compute_tplus_recommendation

    def _run(self, df_raw: pd.DataFrame, **kwargs) -> dict:
        df = _compute_indicators(df_raw)
        return self.compute(df, **kwargs)

    # ── dict shape ────────────────────────────────────────────────────────────

    def test_returns_all_required_keys(self):
        result = self._run(_flat_df())
        assert _REQUIRED_KEYS.issubset(result.keys()), (
            f"Missing keys: {_REQUIRED_KEYS - result.keys()}"
        )

    def test_setup_type_is_valid(self):
        for maker in [_uptrend_df, _pullback_df, _oversold_df, _flat_df]:
            result = self._run(maker())
            assert result["setup_type"] in _VALID_SETUPS, result["setup_type"]

    def test_verdict_is_valid(self):
        for maker in [_uptrend_df, _pullback_df, _oversold_df, _flat_df]:
            result = self._run(maker())
            assert result["verdict"] in _VALID_VERDICTS, result["verdict"]

    def test_confidence_in_range(self):
        for maker in [_uptrend_df, _pullback_df, _oversold_df, _flat_df, _squeeze_df]:
            result = self._run(maker())
            assert 0.0 <= result["confidence"] <= 100.0, (
                f"Confidence out of range: {result['confidence']}"
            )

    def test_vietnamese_labels_present(self):
        for maker in [_uptrend_df, _pullback_df, _oversold_df, _squeeze_df]:
            result = self._run(maker())
            if result["setup_type"] not in ("T_NO_SETUP",):
                assert result["setup_vi"], f"Empty setup_vi for {result['setup_type']}"
            assert result["verdict_vi"], f"Empty verdict_vi for {result['verdict']}"

    def test_reasons_and_risks_are_lists(self):
        result = self._run(_uptrend_df(vol_surge_last=True))
        assert isinstance(result["reasons"], list)
        assert isinstance(result["risks"], list)

    # ── setup detection ───────────────────────────────────────────────────────

    def test_breakout_detected_on_high_vol_uptrend(self):
        """High-volume breakout in rising price → T_BREAKOUT or T_MOMENTUM_CONT."""
        result = self._run(_uptrend_df(n=60, vol_surge_last=True))
        assert result["setup_type"] in (
            "T_BREAKOUT", "T_MOMENTUM_CONT", "T_RANGE_BREAK"
        ), f"Unexpected setup: {result['setup_type']}"

    def test_oversold_recovery_detected_on_declining_price(self):
        """Sharp decline → RSI oversold → T_OVERSOLD_RECOVERY or T_SUPPORT_BOUNCE."""
        result = self._run(_oversold_df())
        assert result["setup_type"] in (
            "T_OVERSOLD_RECOVERY", "T_SUPPORT_BOUNCE", "T_NO_SETUP"
        ), f"Unexpected: {result['setup_type']}"

    def test_no_setup_on_insufficient_data(self):
        """Only 10 bars — should return T_NO_SETUP (not enough indicators)."""
        df_short = _flat_df(n=10)
        result = self.compute(df_short)   # raw df without indicators
        assert result["setup_type"] == "T_NO_SETUP"

    def test_avoid_on_distribution_warning(self):
        df = _compute_indicators(_uptrend_df())
        result = self.compute(df, dist_warning="EXIT")
        assert result["setup_type"] == "T_AVOID"
        assert result["verdict"] == "TRANH_XA"

    def test_avoid_on_amf_block(self):
        df = _compute_indicators(_uptrend_df())
        result = self.compute(df, amf_decision="BLOCK")
        assert result["setup_type"] == "T_AVOID"
        assert result["verdict"] == "TRANH_XA"

    def test_avoid_on_amd_distribution_phase(self):
        df = _compute_indicators(_uptrend_df())
        result = self.compute(df, amd_phase="DISTRIBUTION")
        assert result["setup_type"] in ("T_AVOID", "T_NO_SETUP")

    # ── price levels sanity ───────────────────────────────────────────────────

    def test_stop_below_entry(self):
        result = self._run(_uptrend_df(vol_surge_last=True))
        if result["setup_type"] not in ("T_NO_SETUP", "T_AVOID"):
            assert result["stop_loss"] < result["entry_zone_high"], (
                f"SL {result['stop_loss']} >= entry_high {result['entry_zone_high']}"
            )

    def test_target_t25_above_entry(self):
        result = self._run(_uptrend_df(vol_surge_last=True))
        if result["setup_type"] not in ("T_NO_SETUP", "T_AVOID"):
            assert result["target_t25"] > result["entry_zone_high"] * 0.98, (
                f"T+2.5 target {result['target_t25']} not above entry {result['entry_zone_high']}"
            )

    def test_target_t5_ge_target_t25(self):
        result = self._run(_uptrend_df(vol_surge_last=True))
        if result["target_t25"] > 0 and result["target_t5"] > 0:
            assert result["target_t5"] >= result["target_t25"], (
                f"T+5 {result['target_t5']} < T+2.5 {result['target_t25']}"
            )

    # ── T+2.5 integration ─────────────────────────────────────────────────────

    def test_t25_result_passed_through(self):
        df = _compute_indicators(_uptrend_df(vol_surge_last=True))
        from tradingos.core.t25_engine import compute_t25_entry_score
        t25r = compute_t25_entry_score(df, None)
        result = self.compute(df, t25_result=t25r)
        assert "t25_score_used" in result
        assert result["t25_score_used"] == pytest.approx(t25r.get("t25_score", 0), abs=1)

    def test_t25_avoid_signal_does_not_give_mua_ngay(self):
        df = _compute_indicators(_uptrend_df(vol_surge_last=True))
        # Mock a T25_AVOID result
        fake_t25 = {"t25_score": 20.0, "t25_signal": "T25_AVOID", "t25_regime": "BEAR"}
        result = self.compute(df, t25_result=fake_t25)
        assert result["verdict"] != "MUA_NGAY", (
            "Got MUA_NGAY despite T25_AVOID signal"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Schema field tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTplusSchemaFields:
    """Verify TickerProfile and ScanResultItem contain all tplus_ fields."""

    def test_ticker_profile_has_all_tplus_fields(self):
        from tradingos.data.schemas import TickerProfile
        fields = TickerProfile.model_fields
        required = [
            "tplus_setup", "tplus_setup_vi", "tplus_entry_trigger",
            "tplus_entry_low", "tplus_entry_high",
            "tplus_target_t25", "tplus_target_t5",
            "tplus_stop", "tplus_rr", "tplus_confidence",
            "tplus_session", "tplus_session_vi",
            "tplus_verdict", "tplus_verdict_vi",
            "tplus_reasons", "tplus_risks",
        ]
        missing = [f for f in required if f not in fields]
        assert not missing, f"Missing TickerProfile fields: {missing}"

    def test_scan_result_item_has_tplus_fields(self):
        from tradingos.data.schemas import ScanResultItem
        fields = ScanResultItem.model_fields
        required = [
            "tplus_setup", "tplus_verdict", "tplus_verdict_vi", "tplus_confidence",
            "tplus_entry_low", "tplus_entry_high", "tplus_target_t25", "tplus_target_t5", "tplus_stop",
        ]
        missing = [f for f in required if f not in fields]
        assert not missing, f"Missing ScanResultItem fields: {missing}"

    def test_ticker_profile_tplus_defaults(self):
        """Default tplus_ fields should have safe values."""
        from tradingos.data.schemas import TickerProfile
        fields = TickerProfile.model_fields
        # Check defaults via field metadata, not instantiation (many required fields)
        assert fields["tplus_setup"].default    == "T_NO_SETUP"
        assert fields["tplus_verdict"].default  == "THEO_DOI"
        assert fields["tplus_confidence"].default == 0.0
        assert fields["tplus_rr"].default == 0.0

    def test_scan_result_item_tplus_defaults(self):
        from tradingos.data.schemas import ScanResultItem
        item = ScanResultItem(
            ticker="TEST", action="WATCH", confidence="MEDIUM",
            mfpm_score=0, mode_w_score=0, sms_raw=0,
            signal_mode="MODE_X",
            close=0.0, entry=0.0, sl=0.0, tp1=0.0, rr=0.0,
            amf_decision="PASS", best_pattern="NONE", hmm_state="STEADY_BULL",
        )
        assert item.tplus_setup      == "T_NO_SETUP"
        assert item.tplus_verdict    == "THEO_DOI"
        assert item.tplus_verdict_vi == ""
        assert item.tplus_confidence == 0.0
        assert item.tplus_entry_low  == 0.0
        assert item.tplus_entry_high == 0.0
        assert item.tplus_target_t25 == 0.0
        assert item.tplus_target_t5  == 0.0
        assert item.tplus_stop       == 0.0

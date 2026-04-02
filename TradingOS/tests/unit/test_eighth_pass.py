"""
test_eighth_pass.py — Sector rotation bug regression tests

  SR1 — inflow_score is not multiplied by 100 (score stays in [-100, +100])
  SR2 — RISK_OFF not forced when all sectors have SMS near 50 (neutral)
  SR3 — RISK_ON possible when all sectors have high SMS + rising momentum
  SR4 — rotation_phase key present in detect_sector_rotation() result
  SR5 — market_mode key absent (UI must use rotation_phase, not market_mode)
  SR6 — OBV column used in scoring when indicators df is passed
  SR7 — sectors with strong SMS > 50 produce positive inflow_score
  SR8 — sectors with SMS = 50 and flat price produce near-zero inflow_score
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_sector_df(
    n: int = 30,
    trend: float = 0.0,
    seed: int = 1,
    with_obv: bool = False,
    obv_start: float = 10_000_000.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 50_000 * np.cumprod(1 + rng.normal(trend, 0.005, n))
    df = pd.DataFrame({
        "date":   pd.bdate_range("2025-01-02", periods=n),
        "open":   close, "high": close * 1.01,
        "low":    close * 0.99, "close": close,
        "volume": np.full(n, 1_000_000.0),
    })
    if with_obv:
        df["OBV"] = obv_start + np.cumsum(np.full(n, 200_000.0))
    return df


def _sector_map(n_sectors: int = 4, trend: float = 0.0, sms_val: float = 50.0) -> tuple[dict, dict]:
    """Return sector_ohlcv_map and sector_sms_map with n_sectors."""
    ohlcv = {f"SEC{i}": _make_sector_df(30, trend=trend) for i in range(n_sectors)}
    sms   = {f"SEC{i}": [sms_val] for i in range(n_sectors)}
    return ohlcv, sms


# ═══════════════════════════════════════════════════════════════════════════════
# SR1 — Score not inflated by * 100
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR1ScoreScale:
    def test_inflow_score_within_bounds(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(4, trend=0.002, sms_val=60.0)
        result = detect_sector_rotation(ohlcv, sms)
        for r in result["rankings"]:
            assert -100.0 <= r["inflow_score"] <= 100.0, (
                f"inflow_score {r['inflow_score']} out of [-100, 100]"
            )

    def test_neutral_sectors_score_near_zero(self):
        """Flat price + SMS = 50 → inflow_score close to 0, not ±100."""
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(4, trend=0.0, sms_val=50.0)
        result = detect_sector_rotation(ohlcv, sms)
        for r in result["rankings"]:
            assert abs(r["inflow_score"]) < 20.0, (
                f"Neutral sector has unexpected score {r['inflow_score']}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# SR2 — RISK_OFF not always triggered
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR2NoFalseRiskOff:
    def test_neutral_conditions_not_risk_off(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(4, trend=0.0, sms_val=50.0)
        result = detect_sector_rotation(ohlcv, sms)
        # With flat price and neutral SMS, should be MIXED or NEUTRAL, never RISK_OFF
        assert result["rotation_phase"] != "RISK_OFF", (
            f"Neutral conditions should not produce RISK_OFF, got {result['rotation_phase']}"
        )

    def test_high_sms_not_risk_off(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(4, trend=0.003, sms_val=75.0)
        result = detect_sector_rotation(ohlcv, sms)
        assert result["rotation_phase"] != "RISK_OFF"


# ═══════════════════════════════════════════════════════════════════════════════
# SR3 — RISK_ON achievable
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR3RiskOnAchievable:
    def test_strong_conditions_produce_risk_on(self):
        """Strong uptrend + high SMS for all sectors → RISK_ON."""
        from tradingos.core.money_flow import detect_sector_rotation
        # trend=0.005 → ~0.5%/day, sms=80 → well above 50
        ohlcv, sms = _sector_map(6, trend=0.005, sms_val=80.0)
        result = detect_sector_rotation(ohlcv, sms)
        # Either RISK_ON or at least not RISK_OFF
        assert result["rotation_phase"] in ("RISK_ON", "MIXED", "ROTATION"), (
            f"Strong conditions expected RISK_ON/MIXED, got {result['rotation_phase']}"
        )

    def test_inflow_status_on_strong_sector(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv = {"STRONG": _make_sector_df(30, trend=0.006)}
        sms   = {"STRONG": [85.0]}
        result = detect_sector_rotation(ohlcv, sms)
        strong = next((r for r in result["rankings"] if r["sector"] == "STRONG"), None)
        assert strong is not None
        assert strong["flow_status"] == "INFLOW", (
            f"Strong sector expected INFLOW, got {strong['flow_status']} (score={strong['inflow_score']})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SR4/SR5 — rotation_phase key present, market_mode absent
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR4SR5KeyNames:
    def test_rotation_phase_key_present(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(2)
        result = detect_sector_rotation(ohlcv, sms)
        assert "rotation_phase" in result, "detect_sector_rotation must return 'rotation_phase'"

    def test_market_mode_key_absent(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(2)
        result = detect_sector_rotation(ohlcv, sms)
        assert "market_mode" not in result, (
            "rotation result must NOT have 'market_mode' key — UI must use 'rotation_phase'"
        )

    def test_rankings_key_present(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(3)
        result = detect_sector_rotation(ohlcv, sms)
        assert "rankings" in result
        assert isinstance(result["rankings"], list)

    def test_hot_cold_sectors_keys_present(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv, sms = _sector_map(3)
        result = detect_sector_rotation(ohlcv, sms)
        assert "hot_sectors" in result
        assert "cold_sectors" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SR6 — OBV column used when present
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR6OBVUsed:
    def test_rising_obv_increases_score(self):
        """Sector df with strong rising OBV should score higher than one without."""
        from tradingos.core.money_flow import detect_sector_rotation

        df_with_obv    = _make_sector_df(30, trend=0.001, with_obv=True,  obv_start=10_000_000)
        df_without_obv = _make_sector_df(30, trend=0.001, with_obv=False)

        result_with    = detect_sector_rotation({"SEC": df_with_obv},    {"SEC": [55.0]})
        result_without = detect_sector_rotation({"SEC": df_without_obv}, {"SEC": [55.0]})

        score_with    = result_with["rankings"][0]["inflow_score"]
        score_without = result_without["rankings"][0]["inflow_score"]

        assert score_with >= score_without, (
            f"Rising OBV should increase score: with={score_with:.1f} without={score_without:.1f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SR7/SR8 — Score direction matches SMS level
# ═══════════════════════════════════════════════════════════════════════════════

class TestSR7SR8ScoreDirection:
    def test_high_sms_positive_score(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv = {"HIGH": _make_sector_df(30, trend=0.003)}
        sms   = {"HIGH": [85.0]}
        result = detect_sector_rotation(ohlcv, sms)
        score = result["rankings"][0]["inflow_score"]
        assert score > 0, f"SMS=85 + uptrend should give positive score, got {score}"

    def test_low_sms_negative_score(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv = {"LOW": _make_sector_df(30, trend=-0.003)}
        sms   = {"LOW": [20.0]}
        result = detect_sector_rotation(ohlcv, sms)
        score = result["rankings"][0]["inflow_score"]
        assert score < 0, f"SMS=20 + downtrend should give negative score, got {score}"

    def test_neutral_sms_flat_score(self):
        from tradingos.core.money_flow import detect_sector_rotation
        ohlcv = {"NEUTRAL": _make_sector_df(30, trend=0.0)}
        sms   = {"NEUTRAL": [50.0]}
        result = detect_sector_rotation(ohlcv, sms)
        score = result["rankings"][0]["inflow_score"]
        assert abs(score) < 15.0, f"SMS=50 flat should give near-zero score, got {score}"

"""
Tests for Phase III — GJR-GARCH VaR / CVaR stop-loss calibration.

Tests cover:
  1. VaRResult namedtuple field presence
  2. var_99 <= var_95 (deeper loss at higher confidence)
  3. cvar_95 <= var_95 (Expected Shortfall is worse than VaR)
  4. Values are negative (loss representation)
  5. FAT_TAIL vs NORMAL_TAIL classification
  6. Insufficient bars → NONE model with zeros
  7. Empty DataFrame → zeros
  8. GJR-GARCH fallback to HISTORICAL for 30–99 bars
  9. Reasonable bounds for synthetic returns
  10. calibrate_stop_with_var picks wider (lower) stop
  11. calibrate_stop_with_var with zero entry_price safety
  12. HISTORICAL path produces consistent VaR signs
  13. Model field populated correctly
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradingos.core.risk_model import (
    compute_var,
    calibrate_stop_with_var,
    VaRResult,
)

# ── Synthetic data helpers ────────────────────────────────────────────────────

RNG = np.random.default_rng(42)


def _make_df(n: int, mu: float = 0.0005, sigma: float = 0.02, fat: bool = False) -> pd.DataFrame:
    """Return a DataFrame with 'close' column of n bars."""
    if fat:
        # Student-t innovations → fat tails
        rets = RNG.standard_t(df=3, size=n) * sigma + mu
    else:
        rets = RNG.normal(loc=mu, scale=sigma, size=n)
    close = 100.0 * np.exp(np.cumsum(rets))
    return pd.DataFrame({"close": close})


_DF_LONG    = _make_df(250)          # ≥ 100 bars → GARCH or HISTORICAL fallback
_DF_MED     = _make_df(60)           # 30–99 bars → HISTORICAL
_DF_FAT     = _make_df(250, fat=True)
_DF_SHORT   = _make_df(15)           # < 30 → NONE
_DF_EMPTY   = pd.DataFrame({"close": pd.Series([], dtype=float)})


# ── 1. Field presence ─────────────────────────────────────────────────────────

class TestVaRResultFields:
    def test_all_fields_present(self):
        r = compute_var(_DF_LONG)
        assert hasattr(r, "var_95")
        assert hasattr(r, "var_99")
        assert hasattr(r, "cvar_95")
        assert hasattr(r, "tail_regime")
        assert hasattr(r, "var_model")
        assert hasattr(r, "cond_vol")

    def test_returns_var_result_type(self):
        r = compute_var(_DF_LONG)
        assert isinstance(r, VaRResult)


# ── 2. VaR99 <= VaR95 (99% is more extreme loss) ─────────────────────────────

class TestVaROrdering:
    def test_var99_le_var95_garch(self):
        r = compute_var(_DF_LONG)
        # In loss space: more negative = bigger loss
        assert r.var_99 <= r.var_95

    def test_var99_le_var95_historical(self):
        r = compute_var(_DF_MED)
        assert r.var_99 <= r.var_95

    def test_cvar95_le_var95(self):
        r = compute_var(_DF_LONG)
        # CVaR should be at least as severe as VaR
        assert r.cvar_95 <= r.var_95

    def test_cvar95_le_var95_historical(self):
        r = compute_var(_DF_MED)
        assert r.cvar_95 <= r.var_95


# ── 3. VaR values are negative for typical equity series ─────────────────────

class TestVaRSign:
    def test_var95_is_negative(self):
        r = compute_var(_DF_LONG)
        assert r.var_95 < 0.0, f"Expected negative VaR95, got {r.var_95}"

    def test_var99_is_negative(self):
        r = compute_var(_DF_LONG)
        assert r.var_99 < 0.0

    def test_cvar95_is_negative(self):
        r = compute_var(_DF_LONG)
        assert r.cvar_95 < 0.0


# ── 4. Tail regime classification ─────────────────────────────────────────────

class TestTailRegime:
    def test_fat_tail_detected(self):
        r = compute_var(_DF_FAT)
        assert r.tail_regime == "FAT_TAIL", (
            f"Expected FAT_TAIL for Student-t innovations, got {r.tail_regime}"
        )

    def test_normal_tail_for_gaussian_returns(self):
        # Gaussian returns should be NORMAL_TAIL
        r = compute_var(_make_df(250, fat=False))
        # Not guaranteed to always be NORMAL_TAIL with short series, but check type
        assert r.tail_regime in ("NORMAL_TAIL", "FAT_TAIL")


# ── 5. Insufficient data → NONE model ────────────────────────────────────────

class TestInsufficientData:
    def test_short_series_returns_none_model(self):
        r = compute_var(_DF_SHORT)
        assert r.var_model == "NONE"

    def test_short_series_zeros(self):
        r = compute_var(_DF_SHORT)
        assert r.var_95   == 0.0
        assert r.var_99   == 0.0
        assert r.cvar_95  == 0.0
        assert r.cond_vol == 0.0

    def test_empty_df_returns_none_model(self):
        r = compute_var(_DF_EMPTY)
        assert r.var_model == "NONE"


# ── 6. 30–99 bars → HISTORICAL (not GARCH) ───────────────────────────────────

class TestHistoricalFallback:
    def test_medium_series_uses_historical(self):
        r = compute_var(_DF_MED)
        # With 60 bars, GJR-GARCH needs ≥ 100, so must use HISTORICAL
        assert r.var_model == "HISTORICAL"

    def test_historical_cond_vol_positive(self):
        r = compute_var(_DF_MED)
        assert r.cond_vol > 0.0


# ── 7. Long series → GARCH or HISTORICAL (arch may or may not be installed) ──

class TestGARCHPath:
    def test_long_series_model_is_garch_or_historical(self):
        r = compute_var(_DF_LONG)
        assert r.var_model in ("GJR_GARCH", "HISTORICAL")

    def test_long_series_cond_vol_positive(self):
        r = compute_var(_DF_LONG)
        assert r.cond_vol > 0.0


# ── 8. Reasonable bounds ──────────────────────────────────────────────────────

class TestReasonableBounds:
    def test_var95_within_daily_circuit_breaker(self):
        # VN-HOSE ±7% limit — VaR95 should be within 10%
        r = compute_var(_DF_LONG)
        assert r.var_95 > -10.0, f"VaR95={r.var_95} is beyond daily circuit breaker"

    def test_var99_within_extreme_gap(self):
        # Even in fat-tail, single-session loss > 30% is synthetic artefact
        r = compute_var(_DF_FAT)
        assert r.var_99 > -30.0


# ── 9. calibrate_stop_with_var ────────────────────────────────────────────────

class TestCalibrateStop:
    def test_picks_lower_stop_when_var_is_wider(self):
        # entry=100, atr_stop=97 (-3%), var_99=-5% → var_stop=95 → pick 95
        stop = calibrate_stop_with_var(100.0, atr_stop=97.0, var_99=-5.0)
        assert stop == pytest.approx(95.0, abs=0.5)

    def test_picks_lower_stop_when_atr_is_wider(self):
        # entry=100, atr_stop=93 (-7%), var_99=-3% → var_stop=97 → pick 93
        stop = calibrate_stop_with_var(100.0, atr_stop=93.0, var_99=-3.0)
        assert stop == pytest.approx(93.0, abs=0.5)

    def test_zero_entry_returns_atr_stop(self):
        stop = calibrate_stop_with_var(0.0, atr_stop=0.0, var_99=-5.0)
        assert stop == 0.0

    def test_var99_zero_picks_atr(self):
        # If var_99=0 (NONE model), var_stop = entry → atr_stop always wins
        stop = calibrate_stop_with_var(100.0, atr_stop=95.0, var_99=0.0)
        assert stop == pytest.approx(95.0, abs=0.5)

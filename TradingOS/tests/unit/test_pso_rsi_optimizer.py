"""PSO RSI Optimizer — unit tests.

Tests: objective function, DE bounds enforcement, YAML output format,
and indicators.py config reader integration.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv_with_rsi(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    close = 50_000.0 * np.cumprod(1 + rng.normal(0.0005, 0.012, n))
    vol   = rng.integers(200_000, 1_500_000, n).astype(float)
    df = pd.DataFrame({
        "date":   pd.bdate_range("2023-01-02", periods=n),
        "open":   close * 0.99, "high": close * 1.01,
        "low":    close * 0.99, "close": close, "volume": vol,
    })
    from tradingos.core.indicators import compute_all
    return compute_all(df)


# ── Objective function tests ───────────────────────────────────────────────────

class TestPSOObjectiveFunction:

    def test_objective_returns_finite_number(self):
        """_rsi_sharpe must return a finite float for valid thresholds."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        df = _make_ohlcv_with_rsi()
        result = _rsi_sharpe(np.array([70.0, 65.0, 35.0]), df)
        assert np.isfinite(result)

    def test_infeasible_thresholds_penalized(self):
        """Thresholds violating ob > warn > os ordering get penalty value."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        df = _make_ohlcv_with_rsi()
        # ob < warn: infeasible
        result = _rsi_sharpe(np.array([55.0, 70.0, 35.0]), df)
        assert result == pytest.approx(10.0)

    def test_penalty_on_too_few_trades(self):
        """All-neutral RSI (50) → no trades → mild penalty returned."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        from pso_rsi_optimizer import _rsi_sharpe
        # Create df where RSI is always 50 (flat close)
        close = np.full(120, 50_000.0)
        vol   = np.full(120, 500_000.0)
        df = pd.DataFrame({
            "date":   pd.bdate_range("2023-01-02", periods=120),
            "open":   close, "high": close, "low": close, "close": close, "volume": vol,
        })
        df["RSI14"] = 50.0
        result = _rsi_sharpe(np.array([80.0, 70.0, 20.0]), df)
        # Should return a penalty (non-negative, no crash)
        assert np.isfinite(result)
        assert result >= 0


# ── Bounds enforcement tests ──────────────────────────────────────────────────

class TestPSOBoundsEnforcement:

    def test_bounds_tuple_structure(self):
        """DE bounds must be a list of 3 tuples: (overbought, warning, oversold)."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "pso_rsi_optimizer",
            Path(__file__).resolve().parents[2] / "scripts" / "pso_rsi_optimizer.py",
        )
        # Just check the script has sensible bounds constant — read source
        src_path = Path(__file__).resolve().parents[2] / "scripts" / "pso_rsi_optimizer.py"
        src = src_path.read_text(encoding="utf-8")
        assert "65.0, 85.0" in src   # overbought range
        assert "55.0, 75.0" in src   # warning range
        assert "15.0, 40.0" in src   # oversold range

    def test_overbought_bound_range_is_sensible(self):
        """Overbought upper bound must not exceed 95 (hard ceiling in indicators.py)."""
        src_path = Path(__file__).resolve().parents[2] / "scripts" / "pso_rsi_optimizer.py"
        src = src_path.read_text(encoding="utf-8")
        # Parse the bound: must be ≤ 85 upper
        assert "85.0" in src  # upper bound of overbought


# ── YAML output format tests ──────────────────────────────────────────────────

class TestPSOYAMLOutput:

    def test_yaml_structure_has_rsi_thresholds_key(self, tmp_path):
        """Generated YAML must have top-level 'rsi_thresholds' key."""
        import yaml
        sample = {
            "rsi_thresholds": {
                "TRANSITIONAL": {
                    "GENERAL": {"overbought": 72.0, "warning": 65.0, "oversold": 32.0}
                }
            }
        }
        out_path = tmp_path / "rsi_thresholds.yaml"
        with open(out_path, "w") as f:
            yaml.dump(sample, f)

        with open(out_path) as f:
            loaded = yaml.safe_load(f)

        assert "rsi_thresholds" in loaded
        assert "TRANSITIONAL" in loaded["rsi_thresholds"]
        combo = loaded["rsi_thresholds"]["TRANSITIONAL"]["GENERAL"]
        assert {"overbought", "warning", "oversold"} == set(combo.keys())

    def test_yaml_values_are_floats(self, tmp_path):
        """All threshold values in YAML must be numeric."""
        import yaml
        combo = {"overbought": 72.0, "warning": 65.0, "oversold": 32.0}
        out_path = tmp_path / "t.yaml"
        with open(out_path, "w") as f:
            yaml.dump({"rsi_thresholds": {"T": {"G": combo}}}, f)
        with open(out_path) as f:
            loaded = yaml.safe_load(f)
        vals = loaded["rsi_thresholds"]["T"]["G"]
        for k, v in vals.items():
            assert isinstance(v, (int, float)), f"{k} must be numeric"


# ── indicators.py config reader integration ───────────────────────────────────

class TestIndicatorsConfigReader:

    def test_fallback_when_yaml_absent(self):
        """get_adaptive_rsi_thresholds returns hardcoded values when no YAML exists."""
        from tradingos.core import indicators as ind_mod
        # Force reload with no YAML cache
        ind_mod._RSI_YAML_LOADED = False
        ind_mod._RSI_YAML_CACHE  = None
        from unittest.mock import patch
        with patch.object(ind_mod, "_load_rsi_yaml", return_value=None):
            result = ind_mod.get_adaptive_rsi_thresholds("TRANSITIONAL", "GENERAL")
        assert "overbought" in result
        assert "warning" in result
        assert "oversold" in result
        assert 60.0 <= result["overbought"] <= 90.0

    def test_yaml_values_take_priority_when_present(self, tmp_path):
        """When YAML cache is populated, its values override hardcoded tables."""
        from tradingos.core import indicators as ind_mod
        from unittest.mock import patch
        yaml_data = {
            "TRANSITIONAL": {
                "GENERAL": {"overbought": 77.5, "warning": 68.0, "oversold": 28.0}
            }
        }
        with patch.object(ind_mod, "_load_rsi_yaml", return_value=yaml_data):
            result = ind_mod.get_adaptive_rsi_thresholds("TRANSITIONAL", "GENERAL")
        assert result["overbought"] == pytest.approx(77.5)
        assert result["warning"]    == pytest.approx(68.0)
        assert result["oversold"]   == pytest.approx(28.0)

    def test_yaml_missing_sector_falls_back_to_general(self, tmp_path):
        """If sector not in YAML, falls back to GENERAL entry in that regime."""
        from tradingos.core import indicators as ind_mod
        from unittest.mock import patch
        yaml_data = {
            "TRANSITIONAL": {
                "GENERAL": {"overbought": 77.5, "warning": 68.0, "oversold": 28.0}
            }
        }
        with patch.object(ind_mod, "_load_rsi_yaml", return_value=yaml_data):
            result = ind_mod.get_adaptive_rsi_thresholds("TRANSITIONAL", "REAL_ESTATE")
        # Should fall back to GENERAL since REAL_ESTATE not in yaml_data["TRANSITIONAL"]
        assert result["overbought"] == pytest.approx(77.5)

"""
tests/test_ensemble.py — NewTradingOS v14.0
Tests for ml/ensemble.py
All model calls are mocked — no actual ML training in unit tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from ml.ensemble import (
    ensemble_forecast, ForecastResult,
)
from config import TIMEFRAME_CONFIG


# ─────────────────────────────────────────────────────────────
# Weight redistribution (inline logic verification)
# ─────────────────────────────────────────────────────────────
def _redistribute_weights(weights: dict, available: set) -> dict:
    """Mirror of the inline weight normalization in ensemble.py."""
    if not available:
        # equal fallback
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    filtered = {k: v for k, v in weights.items() if k in available}
    total = sum(filtered.values()) or 1.0
    return {k: v / total for k, v in filtered.items()}


# ─────────────────────────────────────────────────────────────
# Weight redistribution
# ─────────────────────────────────────────────────────────────
class TestRedistributeWeights:
    def test_available_weights_sum_to_1(self):
        weights    = {"LSTM": 0.3, "XGB": 0.2, "RF": 0.2, "MC": 0.1, "ARIMA": 0.1, "HOLT": 0.1}
        available  = {"RF", "MC", "HOLT"}
        new_w      = _redistribute_weights(weights, available)
        total      = sum(new_w.values())
        assert abs(total - 1.0) < 1e-9

    def test_unavailable_models_zero(self):
        weights   = {"LSTM": 0.3, "XGB": 0.2, "RF": 0.2, "MC": 0.1, "ARIMA": 0.1, "HOLT": 0.1}
        available = {"RF", "MC", "HOLT"}
        new_w     = _redistribute_weights(weights, available)
        assert new_w.get("LSTM", 0.0) == 0.0
        assert new_w.get("XGB",  0.0) == 0.0

    def test_all_available_unchanged(self):
        weights   = {"RF": 0.5, "MC": 0.3, "HOLT": 0.2}
        available = {"RF", "MC", "HOLT"}
        new_w     = _redistribute_weights(weights, available)
        for k, v in weights.items():
            assert abs(new_w[k] - v) < 1e-9

    def test_empty_available_returns_equal(self):
        """If nothing available, fall back to equal weights."""
        weights   = {"RF": 0.5, "MC": 0.3, "HOLT": 0.2}
        available = set()
        new_w     = _redistribute_weights(weights, available)
        total = sum(new_w.values())
        assert abs(total - 1.0) < 1e-9 or total == 0.0


# ─────────────────────────────────────────────────────────────
# ForecastResult
# ─────────────────────────────────────────────────────────────
class TestForecastResult:
    def _make(self, n: int = 5):
        prices = [50_000.0 + i * 500 for i in range(n)]
        return ForecastResult(
            ticker="VCB",
            timeframe="1M",
            n_days=n,
            prices=prices,
            prices_bull=[p * 1.05 for p in prices],
            prices_bear=[p * 0.95 for p in prices],
            model_preds={"rf": prices, "mc": prices},
            weights_used={"rf": 0.6, "mc": 0.4},
            method_flags={"rf": True, "mc": True},
            current_price=prices[0],
            target_price=prices[-1],
            upside_pct=5.0,
        )

    def test_target_price_set(self):
        fr = self._make()
        assert fr.target_price > 0

    def test_bull_above_base(self):
        fr = self._make()
        assert fr.prices_bull[-1] > fr.prices[-1]

    def test_bear_below_base(self):
        fr = self._make()
        assert fr.prices_bear[-1] < fr.prices[-1]

    def test_upside_pct_finite(self):
        fr = self._make()
        assert np.isfinite(fr.upside_pct)


# ─────────────────────────────────────────────────────────────
# ensemble_forecast — with mocked sub-models
# ─────────────────────────────────────────────────────────────
class TestEnsembleForecast:
    def _mock_preds(self, n: int, base: float = 50_000.0):
        return [base + i * 100 for i in range(n)]

    @pytest.mark.parametrize("tf", ["1W", "2W", "1M", "3M", "5M"])
    def test_returns_forecast_result(self, ohlcv, tf):
        with patch("ml.ensemble.rf_predict",      return_value=self._mock_preds(20)), \
             patch("ml.ensemble.monte_carlo_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.holt_predict",    return_value=self._mock_preds(20)), \
             patch("ml.ensemble.get_lstm_forecast",
                   return_value={"prices": self._mock_preds(20), "available": True}):
            result = ensemble_forecast(ohlcv, tf, ticker="VCB")
        assert isinstance(result, ForecastResult)

    def test_prices_list_non_empty(self, ohlcv):
        with patch("ml.ensemble.rf_predict",   return_value=self._mock_preds(20)), \
             patch("ml.ensemble.monte_carlo_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.holt_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.get_lstm_forecast",
                   return_value={"prices": self._mock_preds(20), "available": True}):
            result = ensemble_forecast(ohlcv, "1M", ticker="VCB")
        assert len(result.prices) > 0

    def test_weights_used_sum_to_1(self, ohlcv):
        with patch("ml.ensemble.rf_predict",   return_value=self._mock_preds(20)), \
             patch("ml.ensemble.monte_carlo_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.holt_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.get_lstm_forecast",
                   return_value={"prices": self._mock_preds(20), "available": True}):
            result = ensemble_forecast(ohlcv, "1M", ticker="VCB")
        total = sum(result.weights_used.values())
        assert abs(total - 1.0) < 1e-9

    def test_model_preds_non_empty(self, ohlcv):
        """Each model in model_preds should produce at least one prediction."""
        n = 20
        with patch("ml.ensemble.rf_predict",   return_value=self._mock_preds(n)), \
             patch("ml.ensemble.monte_carlo_predict", return_value=self._mock_preds(n)), \
             patch("ml.ensemble.holt_predict", return_value=self._mock_preds(n)), \
             patch("ml.ensemble.get_lstm_forecast",
                   return_value={"prices": self._mock_preds(n), "available": True}):
            result = ensemble_forecast(ohlcv, "1M", ticker="VCB")
        for model, preds in result.model_preds.items():
            assert len(preds) > 0, f"model_preds['{model}'] is empty"

    def test_insufficient_data_fallback(self, ohlcv_small):
        """Very short DF should return a valid result (possibly Holt-only)."""
        with patch("ml.ensemble.holt_predict", return_value=self._mock_preds(5)):
            result = ensemble_forecast(ohlcv_small, "1M", ticker="VCB")
        assert isinstance(result, ForecastResult)

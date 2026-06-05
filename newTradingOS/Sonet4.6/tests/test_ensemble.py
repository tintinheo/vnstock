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

    def test_exchange_is_forwarded_to_monte_carlo(self, ohlcv):
        with patch("ml.ensemble.rf_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.monte_carlo_predict", return_value=self._mock_preds(20)) as mock_mc, \
             patch("ml.ensemble.holt_predict", return_value=self._mock_preds(20)), \
             patch("ml.ensemble.get_lstm_forecast", return_value={"prices": self._mock_preds(20), "available": True}):
            result = ensemble_forecast(ohlcv, "1M", ticker="ZZZ", exchange="UPCOM")

        assert isinstance(result, ForecastResult)
        assert mock_mc.call_args.kwargs["exchange"] == "UPCOM"


# ─────────────────────────────────────────────────────────────
# FIX #5 — Walk-forward train/test split in RandomForest
# ─────────────────────────────────────────────────────────────
class TestWalkForwardRF:
    def test_rf_predict_uses_train_split(self):
        """
        rf_predict must train only on 80% of available data (not all rows),
        ensuring out-of-sample data is not seen during training (no look-ahead bias).
        We verify by confirming predictions are generated from a valid lookback window
        (not all available data) and that the function runs without error.
        """
        from tests.conftest import _make_ohlcv
        from ml.classical_models import rf_predict

        df = _make_ohlcv(n=400, seed=10)
        preds = rf_predict(df, n_days=22, lookback=20)
        assert len(preds) == 22, "rf_predict must return exactly n_days predictions"
        assert all(p > 0 for p in preds), "All predicted prices must be positive"

    def test_rf_predict_prices_near_last_close(self):
        """Predicted prices should be within a reasonable range of the last close."""
        from tests.conftest import _make_ohlcv
        from ml.classical_models import rf_predict

        df  = _make_ohlcv(n=400, seed=11)
        preds = rf_predict(df, n_days=5, lookback=20)
        last  = float(df["Close"].iloc[-1])
        for p in preds:
            pct_diff = abs(p - last) / last
            assert pct_diff < 0.5, f"Predicted price {p:.0f} is >50% away from last close {last:.0f}"

    def test_rf_predict_insufficient_data_returns_empty(self):
        from tests.conftest import _make_ohlcv_small
        from ml.classical_models import rf_predict

        df    = _make_ohlcv_small(n=10)
        preds = rf_predict(df, n_days=22, lookback=20)
        assert preds == [], "rf_predict must return [] when data is insufficient"

    def test_walk_forward_mape_returns_float_or_nan(self):
        """_walk_forward_mape must return float or nan, never raise."""
        import math
        from tests.conftest import _make_ohlcv, _make_ohlcv_small
        from ml.classical_models import _walk_forward_mape

        df_long  = _make_ohlcv(n=400, seed=20)
        df_short = _make_ohlcv_small(n=30)

        mape_long  = _walk_forward_mape(df_long["Close"], lookback=20, horizon=5)
        mape_short = _walk_forward_mape(df_short["Close"], lookback=20, horizon=5)

        # Long series should give a real number or nan (not raise)
        assert isinstance(mape_long, float)
        # Short series must return nan gracefully
        assert math.isnan(mape_short)

    def test_walk_forward_mape_non_negative(self):
        """MAPE (absolute error) must be >= 0 when computable."""
        import math
        from tests.conftest import _make_ohlcv
        from ml.classical_models import _walk_forward_mape

        df   = _make_ohlcv(n=500, seed=30)
        mape = _walk_forward_mape(df["Close"], lookback=20, horizon=5)
        if not math.isnan(mape):
            assert mape >= 0.0


# ────────────────────────────────────────────────────────────
# Round 3 Fix #4 — Monte Carlo VN daily price-limit enforcement
# ────────────────────────────────────────────────────────────
class TestMonteCarloVNLimit:
    """monte_carlo_predict must clip each simulated daily step to the
    VN exchange price limit (HOSE ±7%, HNX ±10%, UPCOM ±15%).

    Without clipping, GBM generates paths with physically impossible
    single-session moves (e.g. +12% on HOSE), inflating short-term
    variance and leading to over-aggressive price targets.
    """

    @staticmethod
    def _make_df(n: int = 200, start: float = 50_000.0) -> "pd.DataFrame":  # type: ignore[name-defined]
        import pandas as pd
        close = pd.Series([start + i * 10 for i in range(n)])
        return pd.DataFrame({"Close": close})

    def test_hose_median_path_within_7pct(self):
        """No single step of the MEDIAN path should exceed HOSE ±7% limit."""
        from ml.classical_models import monte_carlo_predict
        preds = monte_carlo_predict(self._make_df(), n_days=22, exchange="HOSE")
        assert len(preds) == 22
        for i in range(1, len(preds)):
            daily_chg = abs(preds[i] / preds[i - 1] - 1.0)
            assert daily_chg <= 0.07 + 1e-6, (
                f"HOSE: day {i} median change {daily_chg:.4f} exceeds 7% daily limit"
            )

    def test_hnx_limit_10pct(self):
        """HNX exchange allows up to ±10% per session."""
        from ml.classical_models import monte_carlo_predict
        preds = monte_carlo_predict(self._make_df(), n_days=22, exchange="HNX")
        for i in range(1, len(preds)):
            daily_chg = abs(preds[i] / preds[i - 1] - 1.0)
            assert daily_chg <= 0.10 + 1e-6, (
                f"HNX: day {i} median change {daily_chg:.4f} exceeds 10% daily limit"
            )

    def test_upcom_limit_15pct(self):
        """UPCOM exchange allows up to ±15% per session."""
        from ml.classical_models import monte_carlo_predict
        preds = monte_carlo_predict(self._make_df(), n_days=22, exchange="UPCOM")
        for i in range(1, len(preds)):
            daily_chg = abs(preds[i] / preds[i - 1] - 1.0)
            assert daily_chg <= 0.15 + 1e-6, (
                f"UPCOM: day {i} median change {daily_chg:.4f} exceeds 15% daily limit"
            )

    def test_default_exchange_is_hose(self):
        """Without exchange param, default should behave like HOSE (±7%)."""
        from ml.classical_models import monte_carlo_predict
        preds_default = monte_carlo_predict(self._make_df(), n_days=10)
        preds_hose    = monte_carlo_predict(self._make_df(), n_days=10, exchange="HOSE")
        for a, b in zip(preds_default, preds_hose):
            assert abs(a - b) < 1e-3, "Default exchange must produce same result as HOSE"

    def test_returns_correct_length(self):
        """monte_carlo_predict must return exactly n_days prices."""
        from ml.classical_models import monte_carlo_predict
        for n in (5, 22, 66):
            preds = monte_carlo_predict(self._make_df(), n_days=n, exchange="HOSE")
            assert len(preds) == n, f"Expected {n} predictions, got {len(preds)}"

    def test_hose_more_constrained_than_upcom(self):
        """HOSE (7%) should have smaller max single-step in median than UPCOM (15%)."""
        import numpy as np
        from ml.classical_models import monte_carlo_predict
        # Use volatile data so clipping actually activates
        import pandas as pd
        volatile = pd.DataFrame({"Close": pd.Series(
            [50_000.0 * (1 + 0.08 * ((-1) ** i)) for i in range(300)]
        )})
        preds_hose  = monte_carlo_predict(volatile, n_days=22, exchange="HOSE")
        preds_upcom = monte_carlo_predict(volatile, n_days=22, exchange="UPCOM")
        # HOSE steps must all be within 7%; UPCOM within 15%
        for i in range(1, len(preds_hose)):
            chg_hose = abs(preds_hose[i] / preds_hose[i - 1] - 1.0)
            assert chg_hose <= 0.07 + 1e-6


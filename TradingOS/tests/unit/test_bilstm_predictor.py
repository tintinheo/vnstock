"""BiLSTM Predictor — unit tests (model-file-free, mock-based).

All tests run without requiring models/bilstm_direction_10d.keras.
Tests verify: NO_MODEL path, confidence thresholds, feature engineering shape,
and graceful degradation on various error conditions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ohlcv_with_indicators(n: int = 150) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 50_000.0 * np.cumprod(1 + rng.normal(0.001, 0.012, n))
    vol   = rng.integers(300_000, 2_000_000, n).astype(float)
    df = pd.DataFrame({
        "date":   pd.bdate_range("2023-01-02", periods=n),
        "open":   close * 0.99, "high": close * 1.01,
        "low":    close * 0.99, "close": close, "volume": vol,
    })
    from tradingos.core.indicators import compute_all
    return compute_all(df)


# ── NO_MODEL path tests ───────────────────────────────────────────────────────

class TestBiLSTMNoModelPath:

    def test_returns_no_model_when_file_absent(self, tmp_path):
        """BiLSTMPredictor with non-existent model path returns NO_MODEL."""
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        df = _make_ohlcv_with_indicators()
        result = predictor.predict(df)
        assert result["signal"] == "NO_MODEL"
        assert result["confidence"] == "NONE"
        assert result["up_prob"] == pytest.approx(0.5)

    def test_predict_returns_valid_keys(self, tmp_path):
        """predict() always returns all required keys."""
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        result = predictor.predict(_make_ohlcv_with_indicators())
        required = {"signal", "up_prob", "down_prob", "flat_prob", "confidence"}
        assert required.issubset(result.keys())

    def test_predict_no_model_probs_sum_approximately_one(self, tmp_path):
        """NO_MODEL result: up+down+flat probabilities are consistent."""
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        result = predictor.predict(_make_ohlcv_with_indicators())
        total = result["up_prob"] + result["down_prob"] + result["flat_prob"]
        # NO_MODEL returns up=0.5, down=0.5, flat=0.0 → total=1.0
        assert total == pytest.approx(1.0, abs=0.01)

    def test_empty_df_returns_no_model(self, tmp_path):
        """Empty DataFrame → NO_MODEL gracefully."""
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        result = predictor.predict(pd.DataFrame())
        assert result["signal"] == "NO_MODEL"

    def test_insufficient_data_returns_no_model(self, tmp_path):
        """DataFrame with fewer than SEQ_LEN+10 rows → NO_MODEL."""
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        df = _make_ohlcv_with_indicators(n=30)  # SEQ_LEN=60, need 70+
        result = predictor.predict(df)
        assert result["signal"] == "NO_MODEL"


# ── Confidence threshold tests ────────────────────────────────────────────────

class TestBiLSTMConfidenceThresholds:
    """Mock model.predict() to test confidence classification logic."""

    def _make_predictor_with_mock_model(self, tmp_path) -> "BiLSTMPredictor":
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        # Inject a mock model
        mock_model = MagicMock()
        predictor._model = mock_model
        return predictor, mock_model

    def test_high_confidence_when_max_prob_above_065(self, tmp_path):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        mock_model = MagicMock()
        # Index 2 = UP with prob 0.70 (HIGH)
        mock_model.predict.return_value = np.array([[0.15, 0.15, 0.70]])
        predictor._model = mock_model
        result = predictor.predict(_make_ohlcv_with_indicators())
        assert result["signal"] == "UP"
        assert result["confidence"] == "HIGH"

    def test_medium_confidence_when_max_prob_055_to_065(self, tmp_path):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        mock_model = MagicMock()
        # Index 0 = DOWN with prob 0.60 (MEDIUM)
        mock_model.predict.return_value = np.array([[0.60, 0.25, 0.15]])
        predictor._model = mock_model
        result = predictor.predict(_make_ohlcv_with_indicators())
        assert result["signal"] == "DOWN"
        assert result["confidence"] == "MEDIUM"

    def test_low_confidence_when_max_prob_below_055(self, tmp_path):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        mock_model = MagicMock()
        # Index 1 = FLAT with prob 0.45 (LOW)
        mock_model.predict.return_value = np.array([[0.30, 0.45, 0.25]])
        predictor._model = mock_model
        result = predictor.predict(_make_ohlcv_with_indicators())
        assert result["signal"] == "FLAT"
        assert result["confidence"] == "LOW"

    def test_model_predict_exception_returns_no_model(self, tmp_path):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        predictor = BiLSTMPredictor(model_path=tmp_path / "nonexistent.keras")
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("GPU out of memory")
        predictor._model = mock_model
        result = predictor.predict(_make_ohlcv_with_indicators())
        assert result["signal"] == "NO_MODEL"


# ── Feature engineering shape tests ──────────────────────────────────────────

class TestBiLSTMFeatureEngineering:

    def test_build_features_returns_correct_shape(self):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor, _SEQ_LEN, _FEATURES
        df = _make_ohlcv_with_indicators()
        feat = BiLSTMPredictor._build_features(df)
        assert feat is not None
        assert feat.shape == (_SEQ_LEN, _FEATURES)

    def test_build_features_returns_none_on_insufficient_data(self):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        df = _make_ohlcv_with_indicators(n=30)
        feat = BiLSTMPredictor._build_features(df)
        assert feat is None

    def test_build_features_all_finite(self):
        from tradingos.core.bilstm_predictor import BiLSTMPredictor
        df = _make_ohlcv_with_indicators()
        feat = BiLSTMPredictor._build_features(df)
        assert feat is not None
        assert np.all(np.isfinite(feat)), "Feature matrix must not contain NaN/Inf"

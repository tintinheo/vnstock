"""BiLSTM 10-Day Directional Predictor — TF/Keras inference module.

Predicts the 10-session directional outcome (UP / DOWN / FLAT) for a single
ticker using a Bidirectional LSTM model trained on VN market OHLCV data.

Model file: models/bilstm_direction_10d.keras
If the file is absent, all calls return NO_MODEL gracefully.

Training: see scripts/train_bilstm.py
Label convention:
    UP   — close(t+10) / close(t) > 1.03  (+3% or more)
    DOWN — close(t+10) / close(t) < 0.97  (-3% or more)
    FLAT — otherwise

Confidence:
    HIGH   — argmax softmax prob > 0.65
    MEDIUM — argmax softmax prob > 0.55
    LOW    — argmax softmax prob <= 0.55
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..utils.logging import get_logger

if TYPE_CHECKING:
    pass  # keep imports lazy to avoid mandatory TF import at module load

log = get_logger("bilstm_predictor")

# Resolve model path relative to the project root (two levels up from this file)
_SRC_DIR    = Path(__file__).resolve().parents[2]          # …/src/  (parents[2] of core/bilstm_predictor.py)
_PROJ_ROOT  = _SRC_DIR.parent                              # …/TradingOS/  (one level above src/)
_MODEL_PATH = _PROJ_ROOT / "models" / "bilstm_direction_10d.keras"

_SEQ_LEN    = 60   # look-back window (trading days)
_FEATURES   = 6    # close_ret, vol_z, rsi14, macd_norm, atr_norm, obv_norm
_LABELS     = ["DOWN", "FLAT", "UP"]  # class indices: 0, 1, 2
_CONF_HIGH  = 0.65
_CONF_MED   = 0.55

_NO_MODEL_RESULT = {
    "signal":     "NO_MODEL",
    "up_prob":    0.5,
    "down_prob":  0.5,
    "flat_prob":  0.0,
    "confidence": "NONE",
}


class BiLSTMPredictor:
    """
    Singleton-friendly inference wrapper.

    Usage:
        predictor = BiLSTMPredictor()          # loads model once
        result    = predictor.predict(df)      # returns dict

    Thread-safety: Keras model.predict() is not thread-safe with the default
    TF session. For single-threaded profiler use this is fine.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        self._model = None
        self._path  = Path(model_path) if model_path else _MODEL_PATH
        self._load_model()

    def _load_model(self) -> None:
        if not self._path.exists():
            log.debug(f"BiLSTM model not found at {self._path} — running in NO_MODEL mode")
            return
        try:
            # Lazy import so TF is not imported if model file is absent
            import tensorflow as tf  # noqa: F401
            from tensorflow import keras  # type: ignore
            self._model = keras.models.load_model(str(self._path), compile=False)
            log.info(f"BiLSTM model loaded from {self._path}")
        except Exception as e:
            log.warning(f"BiLSTM model load failed: {e}")
            self._model = None

    # ── Feature engineering ───────────────────────────────────────────────────

    @staticmethod
    def _build_features(df: pd.DataFrame) -> np.ndarray | None:
        """
        Build normalised feature matrix of shape (seq_len, n_features).

        Features (all computed from OHLCV + indicators):
            0  close_ret      — 1-day log return
            1  vol_z          — volume z-score (20-day rolling)
            2  rsi14          — RSI-14 (0–100 scaled to 0–1)
            3  macd_norm      — MACD_line / ATR14 (avoids price-scale dependence)
            4  atr_norm       — ATR14 / close (normalised volatility)
            5  obv_norm       — OBV slope normalised by recent OBV range

        Returns None if insufficient data.
        """
        if df is None or len(df) < _SEQ_LEN + 10:
            return None

        tail = df.tail(_SEQ_LEN + 20).copy()

        # 0. Close return
        close_ret = tail["close"].pct_change().fillna(0.0)

        # 1. Volume z-score
        vol_mean = tail["volume"].rolling(20).mean()
        vol_std  = tail["volume"].rolling(20).std().replace(0, 1)
        vol_z    = ((tail["volume"] - vol_mean) / vol_std).fillna(0.0).clip(-3, 3)

        # 2. RSI-14 (normalised 0–1)
        if "RSI14" in tail.columns:
            rsi = tail["RSI14"].fillna(50.0) / 100.0
        else:
            rsi = pd.Series(0.5, index=tail.index)

        # 3. MACD normalised by ATR
        if "MACD_line" in tail.columns and "ATR14" in tail.columns:
            atr_safe = tail["ATR14"].replace(0, np.nan).ffill().fillna(1)
            macd_norm = (tail["MACD_line"].fillna(0.0) / atr_safe).clip(-3, 3)
        else:
            macd_norm = pd.Series(0.0, index=tail.index)

        # 4. ATR / close (normalised volatility)
        if "ATR14" in tail.columns:
            atr_norm = (tail["ATR14"] / tail["close"].replace(0, np.nan)).fillna(0.0).clip(0, 0.2) / 0.2
        else:
            atr_norm = pd.Series(0.0, index=tail.index)

        # 5. OBV slope (normalised)
        if "OBV" in tail.columns:
            obv = tail["OBV"]
            obv_range = obv.abs().max() or 1
            obv_slope = obv.diff().fillna(0.0) / obv_range
            obv_norm  = obv_slope.clip(-1, 1)
        else:
            obv_norm = pd.Series(0.0, index=tail.index)

        feat = np.column_stack([
            close_ret.values,
            vol_z.values,
            rsi.values,
            macd_norm.values,
            atr_norm.values,
            obv_norm.values,
        ])

        # Take the last _SEQ_LEN rows
        feat = feat[-_SEQ_LEN:]
        if feat.shape != (_SEQ_LEN, _FEATURES):
            return None

        # Per-feature rolling normalisation: (x - mean) / std over the window
        mean = feat.mean(axis=0)
        std  = feat.std(axis=0)
        std[std == 0] = 1.0
        feat = (feat - mean) / std

        return feat.astype(np.float32)

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(self, df: pd.DataFrame) -> dict:
        """
        Predict 10-day directional outcome for a single ticker.

        Returns dict:
            signal     : "UP" | "DOWN" | "FLAT" | "NO_MODEL"
            up_prob    : float  [0, 1]
            down_prob  : float  [0, 1]
            flat_prob  : float  [0, 1]
            confidence : "HIGH" | "MEDIUM" | "LOW" | "NONE"
        """
        if self._model is None:
            return dict(_NO_MODEL_RESULT)

        try:
            feat = self._build_features(df)
            if feat is None:
                return dict(_NO_MODEL_RESULT)

            # Add batch dimension: (1, seq_len, n_features)
            x = feat[np.newaxis, ...]
            probs = self._model.predict(x, verbose=0)[0]  # shape (3,)

            max_idx   = int(np.argmax(probs))
            max_prob  = float(probs[max_idx])
            signal    = _LABELS[max_idx]

            if max_prob >= _CONF_HIGH:
                confidence = "HIGH"
            elif max_prob >= _CONF_MED:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            return {
                "signal":     signal,
                "up_prob":    round(float(probs[2]), 4),
                "down_prob":  round(float(probs[0]), 4),
                "flat_prob":  round(float(probs[1]), 4),
                "confidence": confidence,
            }
        except Exception as e:
            log.warning(f"BiLSTM prediction failed: {e}")
            return dict(_NO_MODEL_RESULT)

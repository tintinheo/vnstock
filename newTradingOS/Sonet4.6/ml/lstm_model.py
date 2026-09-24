"""
ml/lstm_model.py — NewTradingOS v14.0
LSTM price forecasting — TensorFlow/Keras optional.
Falls back to a simple Holt's Exponential Smoothing if TF is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from ml.features import build_lstm_features, make_sequences, inverse_log_price

logger = logging.getLogger("TradingOS.lstm")

# ─── optional TensorFlow ──────────────────────────────────────
try:
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    TF_AVAILABLE = True
    logger.info("TensorFlow %s available — LSTM enabled.", tf.__version__)
except ImportError:
    TF_AVAILABLE = False
    logger.info("TensorFlow not installed — LSTM will use Holt's fallback.")


# ─────────────────────────────────────────────────────────────
# LSTM MODEL
# ─────────────────────────────────────────────────────────────
def _build_lstm(n_features: int, lookback: int) -> "tf.keras.Model":  # type: ignore[name-defined]
    model = Sequential([
        Input(shape=(lookback, n_features)),
        LSTM(64, return_sequences=True),
        Dropout(0.2),
        LSTM(32),
        Dropout(0.2),
        Dense(16, activation="relu"),
        Dense(1),
    ])
    model.compile(optimizer=Adam(learning_rate=0.001), loss="huber")
    return model


def train_lstm(
    df: pd.DataFrame,
    lookback: int = 30,
    horizon: int = 5,
    epochs: int = 80,
    batch_size: int = 16,
    val_split: float = 0.15,
    foreign_flow: pd.Series | None = None,
) -> tuple | None:
    """
    Train LSTM on OHLCV data.

    Returns
    -------
    (model, scaler, col_names, last_sequence) or None if insufficient data.
    """
    if not TF_AVAILABLE:
        return None

    feat_df = build_lstm_features(df, foreign_flow)
    if len(feat_df) < lookback + horizon + 20:
        logger.warning("LSTM: insufficient data (%d rows)", len(feat_df))
        return None

    X, y, cols, scaler = make_sequences(feat_df, lookback, horizon)
    if len(X) < 30:
        return None

    split      = max(int(len(X) * (1 - val_split)), 20)
    X_tr, X_v = X[:split], X[split:]
    y_tr, y_v = y[:split], y[split:]

    model = _build_lstm(X.shape[2], lookback)
    callbacks = [
        EarlyStopping(patience=12, restore_best_weights=True, verbose=0),
        ReduceLROnPlateau(factor=0.5, patience=6, verbose=0),
    ]

    model.fit(
        X_tr, y_tr,
        validation_data=(X_v, y_v) if len(X_v) > 0 else None,
        epochs=epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        verbose=0,
    )

    # Build last sequence from feat_df (most recent `lookback` rows)
    from sklearn.preprocessing import MinMaxScaler as _MMS
    scaler2 = _MMS(feature_range=(0, 1))
    scaled  = scaler2.fit_transform(feat_df.values)
    last_seq = scaled[-lookback:].reshape(1, lookback, len(cols))

    return model, scaler, cols, last_seq


def predict_lstm(
    model,
    scaler: MinMaxScaler,
    col_names: list[str],
    last_seq: np.ndarray,
    n_days: int,
) -> list[float]:
    """
    Auto-regressive multi-step prediction.

    Returns list of n_days price forecasts.
    """
    if not TF_AVAILABLE or model is None:
        return []

    t_idx    = col_names.index("log_price") if "log_price" in col_names else 0
    seq      = last_seq.copy()   # (1, lookback, n_features)
    preds    = []

    for _ in range(n_days):
        scaled_pred = float(model.predict(seq, verbose=0)[0, 0])
        preds.append(scaled_pred)
        new_step          = seq[0, -1, :].copy()
        new_step[t_idx]   = scaled_pred
        seq               = np.append(seq[:, 1:, :],
                                       new_step.reshape(1, 1, -1), axis=1)

    return inverse_log_price(np.array(preds), scaler, col_names).tolist()


# ─────────────────────────────────────────────────────────────
# FALLBACK: Holt's Exponential Smoothing
# ─────────────────────────────────────────────────────────────
def _holt_predict(df: pd.DataFrame, n_days: int) -> list[float]:
    """
    Double exponential smoothing fallback when TF is unavailable.
    """
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        close = df["Close"].dropna()
        if len(close) < 20:
            last = float(close.iloc[-1])
            return [last] * n_days
        model = ExponentialSmoothing(
            close, trend="add", seasonal=None, initialization_method="estimated"
        ).fit(optimized=True)
        return model.forecast(n_days).tolist()
    except Exception:
        last = float(df["Close"].iloc[-1])
        trend = float(df["Close"].pct_change(5).iloc[-1] or 0)
        return [last * (1 + trend) ** i for i in range(1, n_days + 1)]


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────
def get_lstm_forecast(
    df: pd.DataFrame,
    n_days: int,
    lookback: int = 30,
    horizon: int | None = None,
    epochs: int = 60,
    cache_key: str | None = None,
    foreign_flow: pd.Series | None = None,
) -> dict:
    """
    High-level LSTM forecast API.

    Returns
    -------
    {
        'prices':  list[float],   # predicted prices for n_days
        'method':  'lstm'|'holt',
        'n_days':  int,
    }
    """
    h = horizon or max(n_days, 5)

    if TF_AVAILABLE and len(df) >= lookback + h + 20:
        result = train_lstm(df, lookback=lookback, horizon=h, epochs=epochs,
                            foreign_flow=foreign_flow)
        if result is not None:
            model, scaler, cols, last_seq = result
            prices = predict_lstm(model, scaler, cols, last_seq, n_days)
            if prices:
                return {"prices": prices, "method": "lstm", "n_days": n_days}

    # Fallback
    prices = _holt_predict(df, n_days)
    return {"prices": prices, "method": "holt", "n_days": n_days}

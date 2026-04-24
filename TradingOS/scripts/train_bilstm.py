"""BiLSTM Training Script — offline model training for 10-day directional prediction.

Usage:
    python scripts/train_bilstm.py
    python scripts/train_bilstm.py --tickers VCB,VHM,FPT,HPG --epochs 50

Downloads 5 years of OHLCV for the specified ticker list via vnstock, builds
training sequences, and saves the trained model to models/bilstm_direction_10d.keras.

Label convention:
    UP   — close(t+10) / close(t) > 1.03  (+3% threshold)
    DOWN — close(t+10) / close(t) < 0.97  (-3% threshold)
    FLAT — otherwise

Architecture:
    Input(60, 6)
    → Bidirectional(LSTM(64, return_sequences=True)) → Dropout(0.2)
    → Bidirectional(LSTM(32))                        → Dropout(0.2)
    → Dense(32, relu) → Dense(3, softmax)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Path setup ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJ_ROOT  = _SCRIPT_DIR.parent
_SRC_DIR    = _PROJ_ROOT / "src"
sys.path.insert(0, str(_SRC_DIR))

_MODEL_DIR  = _PROJ_ROOT / "models"
_MODEL_PATH = _MODEL_DIR / "bilstm_direction_10d.keras"

# ── Constants ─────────────────────────────────────────────────────────────────
SEQ_LEN    = 60     # look-back window (trading days)
N_FEATURES = 6
N_CLASSES  = 3
HORIZON    = 10     # predict 10 sessions ahead
UP_THR     = 0.03   # +3% threshold
DOWN_THR   = -0.03  # -3% threshold

DEFAULT_TICKERS = [
    "VCB", "BID", "CTG", "MBB", "ACB",            # Banking
    "VHM", "VIC", "NVL", "KDH", "DXG",            # Real Estate
    "FPT", "CMG", "VGI",                           # Technology
    "HPG", "NKG", "HSG",                           # Steel
    "VHC", "MPC", "ANV",                           # Seafood (proxy for general market)
    "VNM", "MSN", "SAB",                           # FMCG
    "GAS", "PLX", "PVT",                           # Oil & Gas
    "TCB", "SSI", "VND",                           # Securities
]

# ── Data loading ──────────────────────────────────────────────────────────────

def _load_ohlcv(ticker: str, years: int = 5) -> pd.DataFrame | None:
    """Download OHLCV via vnstock and compute basic indicators."""
    try:
        from tradingos.data.fetcher import fetch_ohlcv
        from tradingos.core import compute_indicators
        df = fetch_ohlcv(ticker, days=years * 252)
        if df is None or len(df) < SEQ_LEN + HORIZON + 30:
            print(f"  [{ticker}] insufficient data ({len(df) if df is not None else 0} bars)")
            return None
        df = compute_indicators(df)
        print(f"  [{ticker}] loaded {len(df)} bars")
        return df
    except Exception as e:
        print(f"  [{ticker}] fetch failed: {e}")
        return None


# ── Feature engineering ───────────────────────────────────────────────────────

def _build_sequences(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Build (X, y) training arrays from a single ticker's DataFrame.
    X shape: (n_samples, SEQ_LEN, N_FEATURES)
    y shape: (n_samples,) int labels 0=DOWN 1=FLAT 2=UP
    """
    close   = df["close"].values.astype(np.float32)
    vol     = df["volume"].values.astype(np.float32)

    rsi     = df["RSI14"].fillna(50.0).values.astype(np.float32) / 100.0 if "RSI14" in df.columns else np.full(len(df), 0.5, dtype=np.float32)
    macd    = df["MACD_line"].fillna(0.0).values.astype(np.float32) if "MACD_line" in df.columns else np.zeros(len(df), dtype=np.float32)
    atr     = df["ATR14"].fillna(0.0).values.astype(np.float32) if "ATR14" in df.columns else np.zeros(len(df), dtype=np.float32)
    obv     = df["OBV"].fillna(0.0).values.astype(np.float32) if "OBV" in df.columns else np.zeros(len(df), dtype=np.float32)

    # Derived features
    close_ret = np.diff(np.log(np.maximum(close, 1e-6)), prepend=np.log(close[0]))
    vol_mean  = pd.Series(vol).rolling(20, min_periods=1).mean().values
    vol_std   = pd.Series(vol).rolling(20, min_periods=1).std().fillna(1).values
    vol_z     = np.clip((vol - vol_mean) / np.maximum(vol_std, 1), -3, 3)
    atr_safe  = np.where(atr > 0, atr, 0.001)
    atr_norm  = np.clip(atr / np.maximum(close, 1), 0, 0.2) / 0.2
    macd_atr  = np.clip(macd / atr_safe, -3, 3)
    obv_range = np.abs(obv).max() or 1.0
    obv_slope = np.diff(obv, prepend=obv[0]) / obv_range
    obv_norm  = np.clip(obv_slope, -1, 1)

    feat_matrix = np.column_stack([close_ret, vol_z, rsi, macd_atr, atr_norm, obv_norm])

    X_list, y_list = [], []
    n = len(close)
    for i in range(SEQ_LEN, n - HORIZON):
        window = feat_matrix[i - SEQ_LEN : i]
        # Per-window normalisation
        mean = window.mean(axis=0)
        std  = window.std(axis=0)
        std[std == 0] = 1.0
        window = (window - mean) / std

        # Label
        ret_10 = close[i + HORIZON] / close[i] - 1.0
        if ret_10 > UP_THR:
            label = 2   # UP
        elif ret_10 < DOWN_THR:
            label = 0   # DOWN
        else:
            label = 1   # FLAT

        X_list.append(window)
        y_list.append(label)

    if not X_list:
        return np.empty((0, SEQ_LEN, N_FEATURES)), np.empty(0, dtype=int)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)


# ── Model definition ──────────────────────────────────────────────────────────

def _build_model() -> "keras.Model":  # type: ignore
    from tensorflow import keras
    from tensorflow.keras import layers  # type: ignore

    inp = keras.Input(shape=(SEQ_LEN, N_FEATURES), name="ohlcv_seq")
    x   = layers.Bidirectional(layers.LSTM(64, return_sequences=True))(inp)
    x   = layers.Dropout(0.2)(x)
    x   = layers.Bidirectional(layers.LSTM(32))(x)
    x   = layers.Dropout(0.2)(x)
    x   = layers.Dense(32, activation="relu")(x)
    out = layers.Dense(N_CLASSES, activation="softmax", name="direction")(x)
    model = keras.Model(inp, out)
    model.compile(
        optimizer="adam",
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


# ── Main ───────────────────────────────────────────────────────────────────────

def main(tickers: list[str], epochs: int, batch_size: int) -> None:
    import tensorflow as tf  # noqa: F401 — validate TF available early
    from tensorflow import keras

    print(f"\nBiLSTM Training — {len(tickers)} tickers, {epochs} epochs\n")

    all_X, all_y = [], []
    for t in tickers:
        df = _load_ohlcv(t)
        if df is None:
            continue
        X, y = _build_sequences(df)
        if len(X) > 0:
            all_X.append(X)
            all_y.append(y)

    if not all_X:
        print("No training data collected. Aborting.")
        sys.exit(1)

    X = np.concatenate(all_X, axis=0)
    y = np.concatenate(all_y, axis=0)
    print(f"\nTotal sequences: {len(X)}  Label dist: DOWN={np.sum(y==0)} FLAT={np.sum(y==1)} UP={np.sum(y==2)}")

    # Shuffle + split
    rng = np.random.default_rng(42)
    idx = rng.permutation(len(X))
    X, y = X[idx], y[idx]
    split = int(len(X) * 0.8)
    X_train, y_train = X[:split], y[:split]
    X_val,   y_val   = X[split:], y[split:]

    # Class weights to handle imbalance
    from sklearn.utils.class_weight import compute_class_weight  # type: ignore
    cw = compute_class_weight("balanced", classes=np.unique(y_train), y=y_train)
    class_weights = dict(enumerate(cw))

    model = _build_model()
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(patience=5, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=3, verbose=1),
    ]

    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1,
    )

    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(_MODEL_PATH))
    print(f"\nModel saved to {_MODEL_PATH}")

    # Quick evaluation
    loss, acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"Val loss={loss:.4f}  Val accuracy={acc:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train BiLSTM directional model")
    parser.add_argument("--tickers", default=",".join(DEFAULT_TICKERS),
                        help="Comma-separated ticker list")
    parser.add_argument("--epochs",     type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=64)
    args = parser.parse_args()
    main(
        tickers    = [t.strip().upper() for t in args.tickers.split(",") if t.strip()],
        epochs     = args.epochs,
        batch_size = args.batch_size,
    )

#!/usr/bin/env python3
"""
train_lstm.py  —  Offline LSTM Training Script
════════════════════════════════════════════════
Trains a small LSTM per ticker to predict 5-day forward returns.
Saves weights to  data/models/{TICKER}_lstm.keras
The Streamlit UI (Quant_Profiler_ui.py) loads these weights at inference
time via forecast_engine.py.  If no weights exist, falls back to Ridge.

Requirements:
    pip install tensorflow scikit-learn

Usage:
    # Train using the default Quant_Profiler OHLCV pipeline
    python train_lstm.py HPG
    python train_lstm.py HPG VNM TCH ACB --days 600 --epochs 30
    python train_lstm.py --watchlist data/watchlist.txt --epochs 20

Architecture:
    Input  (20 timesteps × 5 features)
    LSTM   (64 units, return_sequences=True)
    Dropout(0.2)
    LSTM   (32 units)
    Dropout(0.2)
    Dense  (1)   → predicted 5-day return (%)
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# ─── Path setup ──────────────────────────────────────────────────────────────
_DIR = Path(__file__).parent
sys.path.insert(0, str(_DIR))
_MODELS_DIR = _DIR / "data" / "models"
_MODELS_DIR.mkdir(parents=True, exist_ok=True)

from forecast_engine import prepare_lstm_features, _SEQ_LEN, _FEATURES

# ─── Import core data pipeline from Quant_Profiler ───────────────────────────
try:
    from Quant_Profiler import fetch_ohlcv, calculate_indicators, HISTORY_DAYS
except ImportError as e:
    print(f"ERROR: Cannot import Quant_Profiler.py: {e}")
    sys.exit(1)

# ─── Keras (required for training) ───────────────────────────────────────────
try:
    import keras
    from keras import layers, callbacks
    _KERAS_OK = True
except ImportError:
    _KERAS_OK = False
    print("WARNING: keras not installed. Install with: pip install tensorflow")


# ═══════════════════════════════════════════════════════════════════════════════
#  Feature Builder (training version — builds full dataset from history)
# ═══════════════════════════════════════════════════════════════════════════════

def build_training_dataset(df: pd.DataFrame, forward_days: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """
    Slide a SEQ_LEN window over the full history to build X, y pairs.
    X: (N, SEQ_LEN, FEATURES)  float32
    y: (N,)                    float32 — forward_days return (%)
    """
    if df is None or len(df) < _SEQ_LEN + forward_days + 5:
        return np.empty((0, _SEQ_LEN, _FEATURES), dtype=np.float32), np.empty(0, dtype=np.float32)

    needed = ("Close", "Volume", "RSI", "MACD_Hist", "ATR", "Vol_MA20")
    for col in needed:
        if col not in df.columns:
            return np.empty((0, _SEQ_LEN, _FEATURES), dtype=np.float32), np.empty(0, dtype=np.float32)

    close   = df["Close"].values.astype(float)
    vol     = df["Volume"].values.astype(float)
    rsi     = df["RSI"].values.astype(float)
    mh      = df["MACD_Hist"].values.astype(float)
    atr_arr = df["ATR"].values.astype(float)
    vol_ma  = df["Vol_MA20"].values.astype(float)

    n   = len(close)
    Xs  = []
    ys  = []

    for end in range(_SEQ_LEN + 1, n - forward_days):
        # Slice: [end - SEQ_LEN - 1 : end + 1] gives SEQ_LEN+1 bars
        sl = slice(end - _SEQ_LEN - 1, end + 1)
        c_ = close[sl]
        v_ = vol[sl]
        r_ = rsi[sl]
        m_ = mh[sl]
        a_ = atr_arr[sl]
        vm_= vol_ma[sl]

        # Skip if any NaN in window
        if np.any(np.isnan(c_)) or np.any(np.isnan(r_)) or c_[0] <= 0:
            continue

        close_ret  = np.diff(c_)  / (c_[:-1] + 1e-9) * 100
        vol_ratio  = v_[1:]       / (vm_[1:] + 1e-9)
        rsi_n      = np.clip(r_[1:] / 100.0, 0, 1)
        mh_n       = np.clip(m_[1:] / (c_[1:] + 1e-9) * 100, -5, 5)
        atr_pct    = a_[1:] / (c_[1:] + 1e-9) * 100

        seq = np.stack([close_ret, vol_ratio, rsi_n, mh_n, atr_pct], axis=1)
        seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)

        # Forward return label
        future_price = close[end + forward_days]
        if future_price <= 0 or close[end] <= 0:
            continue
        fwd_ret = (future_price - close[end]) / close[end] * 100

        Xs.append(seq)
        ys.append(fwd_ret)

    if not Xs:
        return np.empty((0, _SEQ_LEN, _FEATURES), dtype=np.float32), np.empty(0, dtype=np.float32)

    return np.array(Xs, dtype=np.float32), np.array(ys, dtype=np.float32)


# ═══════════════════════════════════════════════════════════════════════════════
#  Model Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_model(seq_len: int = _SEQ_LEN, n_features: int = _FEATURES) -> "keras.Model":
    """
    Small LSTM: Input → LSTM(64) → Dropout → LSTM(32) → Dropout → Dense(1).
    Regression: predicts 5-day return %.
    """
    inp = keras.Input(shape=(seq_len, n_features), name="price_seq")
    x   = layers.LSTM(64, return_sequences=True, name="lstm_1")(inp)
    x   = layers.Dropout(0.2, name="drop_1")(x)
    x   = layers.LSTM(32, return_sequences=False, name="lstm_2")(x)
    x   = layers.Dropout(0.2, name="drop_2")(x)
    out = layers.Dense(1, name="output")(x)
    model = keras.Model(inputs=inp, outputs=out, name="lstm_quant")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="huber",
        metrics=["mae"],
    )
    return model


# ═══════════════════════════════════════════════════════════════════════════════
#  Training Pipeline per Ticker
# ═══════════════════════════════════════════════════════════════════════════════

def train_ticker(
    ticker: str,
    days: int = HISTORY_DAYS,
    epochs: int = 30,
    batch_size: int = 32,
    force_retrain: bool = False,
) -> dict:
    """
    Full training pipeline for one ticker.
    Returns metrics dict.
    """
    model_path = _MODELS_DIR / f"{ticker.upper()}_lstm.keras"

    if model_path.exists() and not force_retrain:
        print(f"  [{ticker}] Model exists → skip (use --force to retrain)")
        return {"ticker": ticker, "status": "skipped"}

    print(f"\n[{ticker}] Fetching {days}-day OHLCV...")
    df, src = fetch_ohlcv(ticker, days=days, verbose=False)
    if df is None or df.empty:
        print(f"  [{ticker}] FAILED: no data")
        return {"ticker": ticker, "status": "no_data"}

    df = calculate_indicators(df)
    print(f"  [{ticker}] {len(df)} bars from {src}")

    X, y = build_training_dataset(df, forward_days=5)
    if len(X) < 50:
        print(f"  [{ticker}] Insufficient samples ({len(X)}) — skip")
        return {"ticker": ticker, "status": "too_few_samples", "n": len(X)}

    print(f"  [{ticker}] Building dataset: {len(X)} samples")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, shuffle=False,
    )

    model = build_model()
    cb_list = [
        callbacks.EarlyStopping(patience=7, restore_best_weights=True, monitor="val_loss"),
        callbacks.ReduceLROnPlateau(patience=4, factor=0.5, min_lr=1e-5, monitor="val_loss"),
    ]

    print(f"  [{ticker}] Training {epochs} epochs  (train={len(X_train)}, val={len(X_test)})...")
    hist = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=cb_list,
        verbose=0,
    )

    preds = model.predict(X_test, verbose=0).flatten()
    mae   = float(mean_absolute_error(y_test, preds))
    rmse  = float(np.sqrt(mean_squared_error(y_test, preds)))
    dir_acc = float(np.mean(np.sign(preds) == np.sign(y_test)) * 100)

    print(f"  [{ticker}] MAE={mae:.3f}%  RMSE={rmse:.3f}%  DirAcc={dir_acc:.1f}%")

    model.save(str(model_path))
    print(f"  [{ticker}] Saved → {model_path}")

    return {
        "ticker":   ticker,
        "status":   "trained",
        "n_train":  len(X_train),
        "n_test":   len(X_test),
        "mae":      mae,
        "rmse":     rmse,
        "dir_acc":  dir_acc,
        "epochs_done": len(hist.history["loss"]),
        "model_path": str(model_path),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Offline LSTM training for Quant Profiler forecast engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train_lstm.py HPG
  python train_lstm.py HPG VNM TCH ACB --epochs 40 --days 600
  python train_lstm.py --watchlist watchlist.txt --force
        """,
    )
    parser.add_argument("tickers",     nargs="*",          help="Ticker symbols to train")
    parser.add_argument("--watchlist", type=str,           help="File with one ticker per line")
    parser.add_argument("--days",      type=int, default=HISTORY_DAYS, help="History days to fetch")
    parser.add_argument("--epochs",    type=int, default=30,           help="Max training epochs")
    parser.add_argument("--batch",     type=int, default=32,           help="Batch size")
    parser.add_argument("--force",     action="store_true",            help="Force retrain even if model exists")
    args = parser.parse_args()

    if not _KERAS_OK:
        print("ERROR: tensorflow/keras not installed.")
        print("Install:  pip install tensorflow")
        sys.exit(1)

    tickers = [t.upper() for t in args.tickers]

    if args.watchlist:
        wl_path = Path(args.watchlist)
        if not wl_path.exists():
            wl_path = _DIR / args.watchlist
        with open(wl_path) as f:
            for line in f:
                t = line.strip().upper()
                if t and not t.startswith("#") and t not in tickers:
                    tickers.append(t)

    if not tickers:
        # Default: common liquid tickers
        tickers = ["HPG", "VNM", "VCB", "TCH", "ACB", "MBB", "FPT", "MSN"]
        print(f"No tickers specified — training defaults: {tickers}")

    print(f"\n{'═'*60}")
    print(f"  QUANT PROFILER — LSTM Offline Training")
    print(f"  Tickers : {', '.join(tickers)}")
    print(f"  Days    : {args.days}")
    print(f"  Epochs  : {args.epochs}")
    print(f"  Output  : {_MODELS_DIR}")
    print(f"{'═'*60}")

    results = []
    for ticker in tickers:
        result = train_ticker(
            ticker,
            days=args.days,
            epochs=args.epochs,
            batch_size=args.batch,
            force_retrain=args.force,
        )
        results.append(result)

    # Summary
    print(f"\n{'─'*60}")
    print(f"  TRAINING SUMMARY")
    print(f"{'─'*60}")
    for r in results:
        st = r["status"]
        if st == "trained":
            print(f"  ✅ {r['ticker']:6s}  MAE={r['mae']:.2f}%  DirAcc={r['dir_acc']:.1f}%  epochs={r['epochs_done']}")
        elif st == "skipped":
            print(f"  ⏭  {r['ticker']:6s}  (skipped — model exists)")
        else:
            print(f"  ❌ {r['ticker']:6s}  {st}")
    print(f"{'─'*60}")


if __name__ == "__main__":
    main()

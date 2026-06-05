"""
ml/features.py — NewTradingOS v14.0
Feature engineering for ML models (LSTM, XGBoost, RandomForest).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from core.indicators import (
    rsi, macd, bb_percent_b, volume_ratio,
    atr, adx, roc, obv, money_flow_index,
)


# ─────────────────────────────────────────────────────────────
# SHARED FEATURE BUILDERS
# ─────────────────────────────────────────────────────────────
def build_base_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build ~25 base technical features from OHLCV.
    Returns a new DataFrame aligned to df.index.
    """
    close  = df["Close"]
    high   = df.get("High",   close)
    low    = df.get("Low",    close)
    volume = df.get("Volume", pd.Series(0, index=close.index))

    feat = pd.DataFrame(index=df.index)

    # ── Returns
    feat["ret_1d"]  = close.pct_change(1)
    feat["ret_3d"]  = close.pct_change(3)
    feat["ret_5d"]  = close.pct_change(5)
    feat["ret_10d"] = close.pct_change(10)
    feat["ret_20d"] = close.pct_change(20)
    feat["log_ret"] = np.log(close / close.shift(1))

    # ── Price position
    for w in (5, 10, 20, 50):
        sma_w = close.rolling(w, min_periods=1).mean()
        feat[f"price_vs_sma{w}"] = (close - sma_w) / sma_w.replace(0, np.nan)

    # ── RSI multi-period
    for p in (7, 14, 21):
        feat[f"rsi_{p}"] = rsi(close, p)

    # ── MACD histogram (standard)
    _, _, hist = macd(close, 12, 26, 9)
    feat["macd_hist"] = hist

    # ── Bollinger %B
    feat["bb_pctb_20"] = bb_percent_b(close, 20)
    feat["bb_pctb_10"] = bb_percent_b(close, 10)

    # ── ATR (normalised)
    atr_14 = atr(high, low, close, 14)
    feat["atr_norm"] = atr_14 / close.replace(0, np.nan)

    # ── Volume
    feat["vol_ratio_5"]  = volume_ratio(volume, 5)
    feat["vol_ratio_20"] = volume_ratio(volume, 20)

    # ── ADX
    feat["adx_14"] = adx(high, low, close, 14)

    # ── ROC
    feat["roc_5"]  = roc(close, 5)
    feat["roc_10"] = roc(close, 10)

    # ── MFI
    feat["mfi_14"] = money_flow_index(high, low, close, volume, 14)

    # ── Candle patterns
    feat["body_size"]   = (close - df.get("Open", close)).abs() / atr_14.replace(0, np.nan)
    feat["upper_shadow"] = (high - pd.concat([close, df.get("Open", close)], axis=1).max(axis=1)) \
                           / atr_14.replace(0, np.nan)
    feat["lower_shadow"] = (pd.concat([close, df.get("Open", close)], axis=1).min(axis=1) - low) \
                           / atr_14.replace(0, np.nan)

    return feat


def build_lstm_features(
    df: pd.DataFrame,
    foreign_flow: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Build feature matrix for LSTM.
    8–10 carefully chosen features (quality over quantity for LSTM).
    """
    close  = df["Close"]
    high   = df.get("High",   close)
    low    = df.get("Low",    close)
    volume = df.get("Volume", pd.Series(0, index=close.index))

    feat = pd.DataFrame(index=df.index)

    feat["log_price"]   = np.log(close)                       # target base
    feat["ret_1d"]      = close.pct_change(1)
    feat["ret_5d"]      = close.pct_change(5)
    feat["rsi_14"]      = rsi(close, 14)
    _, _, hist          = macd(close, 12, 26, 9)
    feat["macd_hist"]   = hist
    feat["bb_pctb"]     = bb_percent_b(close, 20)
    feat["vol_ratio"]   = volume_ratio(volume, 20)
    feat["atr_norm"]    = atr(high, low, close, 14) / close.replace(0, np.nan)

    if foreign_flow is not None:
        ff_abs = foreign_flow.abs().rolling(20).mean().replace(0, np.nan)
        feat["foreign_norm"] = foreign_flow / ff_abs
    else:
        feat["foreign_norm"] = 0.0

    return feat.dropna()


def build_xgb_features(
    df: pd.DataFrame,
    regime: str = "sideways",
    macro_dict: dict | None = None,
) -> pd.DataFrame:
    """
    Rich feature set for XGBoost (30+ features + regime/macro encoding).
    """
    base = build_base_features(df)

    # Regime encoding
    base["regime_bull"]    = 1 if regime == "bull" else 0
    base["regime_bear"]    = 1 if regime == "bear" else 0
    base["regime_neutral"] = 1 if regime == "sideways" else 0

    # Macro features
    if macro_dict:
        base["dxy_trend"]    = _encode_dxy(macro_dict.get("dxy_trend", "neutral"))
        base["vix_level"]    = _encode_vix(macro_dict.get("vix_level", "normal"))
        base["ad_ratio"]     = macro_dict.get("ad_ratio", 0.5)
        ff_net               = macro_dict.get("foreign_flow", {}).get("net_buy", 0)
        base["ff_norm"]      = np.sign(ff_net)  # -1, 0, +1
    else:
        base["dxy_trend"]  = 0.0
        base["vix_level"]  = 0.0
        base["ad_ratio"]   = 0.5
        base["ff_norm"]    = 0.0

    return base.dropna()


def _encode_dxy(trend: str) -> float:
    return {"strong_up": -2, "up": -1, "neutral": 0, "down": 1, "strong_down": 2}.get(
        trend, 0
    )


def _encode_vix(level: str) -> float:
    return {"fear": -2, "elevated": -1, "normal": 0}.get(level, 0)


# ─────────────────────────────────────────────────────────────
# SEQUENCE BUILDER FOR LSTM
# ─────────────────────────────────────────────────────────────
def make_sequences(
    feat_df: pd.DataFrame,
    lookback: int = 30,
    horizon: int = 5,
    target_col: str = "log_price",
) -> tuple[np.ndarray, np.ndarray, list[str], MinMaxScaler]:
    """
    Build (X, y) sequences for LSTM training.

    Returns
    -------
    X        : shape (n_samples, lookback, n_features)
    y        : shape (n_samples,)  — future log_price
    col_names: list of feature column names
    scaler   : fitted MinMaxScaler
    """
    scaler  = MinMaxScaler(feature_range=(0, 1))
    scaled  = scaler.fit_transform(feat_df.values)
    cols    = list(feat_df.columns)
    t_idx   = cols.index(target_col) if target_col in cols else 0

    X_list, y_list = [], []
    for i in range(lookback, len(scaled) - horizon + 1):
        X_list.append(scaled[i - lookback: i])
        y_list.append(scaled[i + horizon - 1, t_idx])

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    return X, y, cols, scaler


def inverse_log_price(
    scaled_pred: float | np.ndarray,
    scaler: MinMaxScaler,
    col_names: list[str],
    target_col: str = "log_price",
) -> float | np.ndarray:
    """
    Inverse-transform scaled log_price predictions back to price.
    """
    t_idx   = col_names.index(target_col) if target_col in col_names else 0
    n_cols  = len(col_names)

    if np.isscalar(scaled_pred):
        dummy = np.zeros((1, n_cols))
        dummy[0, t_idx] = scaled_pred
        log_p = scaler.inverse_transform(dummy)[0, t_idx]
        return float(np.exp(log_p))

    dummy = np.zeros((len(scaled_pred), n_cols))
    dummy[:, t_idx] = scaled_pred
    log_p = scaler.inverse_transform(dummy)[:, t_idx]
    return np.exp(log_p)

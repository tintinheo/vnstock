"""
ml/classical_models.py — NewTradingOS v14.0
Classical ML models: XGBoost, RandomForest, SVR, ARIMA, Prophet, Monte Carlo.
All wrapped with a uniform predict(df, n_days, **kwargs) interface.
"""
from __future__ import annotations

import logging
import warnings
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
logger = logging.getLogger("TradingOS.classical")

# ─── optional imports ────────────────────────────────────────
try:
    from xgboost import XGBRegressor
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from statsmodels.tsa.arima.model import ARIMA as _ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False

try:
    from prophet import Prophet as _Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

try:
    from sklearn.svm import SVR
    SVR_AVAILABLE = True
except ImportError:
    SVR_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
# HELPER — rolling window targets
# ─────────────────────────────────────────────────────────────
def _make_xy(close: pd.Series, lookback: int = 20,
             horizon: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Sliding window X (lookback returns) → y (horizon return)."""
    rets = close.pct_change().dropna().values
    X, y = [], []
    for i in range(lookback, len(rets) - horizon):
        X.append(rets[i - lookback: i])
        y.append(rets[i: i + horizon].sum())   # cumulative return over horizon
    return np.array(X), np.array(y)


def _predict_price(last_price: float, cumret: float) -> float:
    return last_price * (1 + cumret)


# ─────────────────────────────────────────────────────────────
# RANDOM FOREST
# ─────────────────────────────────────────────────────────────
def rf_predict(
    df: pd.DataFrame,
    n_days: int,
    n_estimators: int = 200,
    lookback: int = 20,
) -> list[float]:
    close = df["Close"].dropna()
    if len(close) < lookback + n_days + 10:
        return []
    X, y  = _make_xy(close, lookback, n_days)
    if len(X) < 20:
        return []
    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42,
                                   n_jobs=-1, max_depth=8)
    model.fit(X, y)
    last_window = close.pct_change().dropna().values[-lookback:]
    pred_cumret = float(model.predict([last_window])[0])
    last_price  = float(close.iloc[-1])
    # Linearly interpolate to n_days daily predictions
    daily_ret   = (1 + pred_cumret) ** (1 / n_days) - 1
    return [last_price * (1 + daily_ret) ** i for i in range(1, n_days + 1)]


# ─────────────────────────────────────────────────────────────
# XGBoost
# ─────────────────────────────────────────────────────────────
def xgb_predict(
    df: pd.DataFrame,
    n_days: int,
    lookback: int = 20,
    regime: str = "sideways",
    macro_dict: dict | None = None,
) -> list[float]:
    if not XGB_AVAILABLE:
        return rf_predict(df, n_days, lookback=lookback)

    from ml.features import build_xgb_features
    try:
        feat_df = build_xgb_features(df, regime, macro_dict)
        close   = df["Close"].dropna()
        if len(feat_df) < 40:
            return []
        target  = close.pct_change(n_days).shift(-n_days).reindex(feat_df.index)
        valid   = target.dropna()
        X       = feat_df.loc[valid.index]
        y       = valid

        split   = max(int(len(X) * 0.8), 20)
        X_tr, X_v = X.iloc[:split], X.iloc[split:]
        y_tr, y_v = y.iloc[:split], y.iloc[split:]

        model = XGBRegressor(
            n_estimators=300, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            objective="reg:squarederror", random_state=42, n_jobs=-1,
        )
        eval_data = [(X_v.values, y_v.values)] if len(X_v) >= 5 else None
        model.fit(X_tr.values, y_tr.values,
                  eval_set=eval_data, verbose=False)

        last_feat   = feat_df.iloc[-1:].values
        pred_cumret = float(model.predict(last_feat)[0])
        last_price  = float(close.iloc[-1])
        daily_ret   = (1 + pred_cumret) ** (1 / n_days) - 1
        return [last_price * (1 + daily_ret) ** i for i in range(1, n_days + 1)]
    except Exception as exc:
        logger.warning("XGBoost predict failed: %s", exc)
        return rf_predict(df, n_days, lookback=lookback)


# ─────────────────────────────────────────────────────────────
# ARIMA
# ─────────────────────────────────────────────────────────────
def arima_predict(
    df: pd.DataFrame,
    n_days: int,
    order: tuple = (2, 1, 2),
) -> list[float]:
    if not ARIMA_AVAILABLE:
        return []
    close = df["Close"].dropna()
    if len(close) < 50:
        return []
    try:
        model  = _ARIMA(close, order=order)
        result = model.fit()
        forecast = result.forecast(steps=n_days)
        return list(forecast.values if hasattr(forecast, "values") else forecast)
    except Exception as exc:
        logger.debug("ARIMA: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────
# PROPHET
# ─────────────────────────────────────────────────────────────
def prophet_predict(
    df: pd.DataFrame,
    n_days: int,
    include_holidays: bool = True,
) -> list[float]:
    if not PROPHET_AVAILABLE:
        return []
    close = df["Close"].dropna().reset_index()
    close.columns = ["ds", "y"]
    close["ds"]   = pd.to_datetime(close["ds"])
    if len(close) < 30:
        return []
    try:
        m = _Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.1,
            interval_width=0.8,
        )
        if include_holidays:
            m.add_country_holidays(country_name="VN")
        m.fit(close)
        future  = m.make_future_dataframe(periods=n_days, freq="B")
        forecast = m.predict(future)
        preds   = forecast["yhat"].values[-n_days:]
        return list(np.maximum(preds, 0))
    except Exception as exc:
        logger.debug("Prophet: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────
# MONTE CARLO
# ─────────────────────────────────────────────────────────────
def monte_carlo_predict(
    df: pd.DataFrame,
    n_days: int,
    n_simulations: int = 2000,
    percentile_central: float = 50,
) -> list[float]:
    """
    GBM Monte Carlo simulation.
    Returns median path over n_days.
    """
    close = df["Close"].dropna()
    if len(close) < 30:
        return []
    log_rets   = np.log(close / close.shift(1)).dropna()
    mu         = float(log_rets.mean())
    sigma      = float(log_rets.std())
    last_price = float(close.iloc[-1])

    dt      = 1.0
    rng     = np.random.default_rng(seed=42)
    shocks  = rng.normal(
        loc=(mu - 0.5 * sigma**2) * dt,
        scale=sigma * np.sqrt(dt),
        size=(n_simulations, n_days),
    )
    paths   = last_price * np.exp(np.cumsum(shocks, axis=1))
    median  = np.percentile(paths, percentile_central, axis=0)
    return list(median)


# ─────────────────────────────────────────────────────────────
# HOLT'S EXPONENTIAL SMOOTHING  (simple trend baseline)
# ─────────────────────────────────────────────────────────────
def holt_predict(df: pd.DataFrame, n_days: int) -> list[float]:
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        close = df["Close"].dropna()
        if len(close) < 20:
            last = float(close.iloc[-1])
            return [last] * n_days
        model = ExponentialSmoothing(
            close, trend="add", seasonal=None,
            initialization_method="estimated",
        ).fit(optimized=True)
        return list(model.forecast(n_days))
    except Exception as exc:
        logger.debug("Holt: %s", exc)
        last  = float(df["Close"].iloc[-1])
        trend = float(df["Close"].pct_change(5).iloc[-1] or 0.0)
        return [last * (1 + trend) ** i for i in range(1, n_days + 1)]

"""
ml/ensemble.py — NewTradingOS v14.0
Weighted ensemble combiner — timeframe-specific weights.
Gracefully handles missing models by redistributing weights.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import TIMEFRAME_CONFIG
from ml.lstm_model import get_lstm_forecast, TF_AVAILABLE
from ml.classical_models import (
    rf_predict, xgb_predict, arima_predict,
    prophet_predict, monte_carlo_predict, holt_predict,
    XGB_AVAILABLE, ARIMA_AVAILABLE, PROPHET_AVAILABLE,
)

logger = logging.getLogger("TradingOS.ensemble")


@dataclass
class ForecastResult:
    ticker:        str
    timeframe:     str
    n_days:        int
    prices:        list[float]          # ensemble median prices
    prices_bull:   list[float]          # optimistic (75th pct)
    prices_bear:   list[float]          # pessimistic (25th pct)
    model_preds:   dict = field(default_factory=dict)  # {model: [prices]}
    weights_used:  dict = field(default_factory=dict)
    method_flags:  dict = field(default_factory=dict)  # {model: True/False}
    current_price: float = 0.0
    target_price:  float = 0.0   # ensemble median at end of horizon
    upside_pct:    float = 0.0   # (target - current) / current * 100


def ensemble_forecast(
    df: pd.DataFrame,
    tf: str,
    ticker: str = "UNKNOWN",
    regime: str = "sideways",
    macro_dict: dict | None = None,
    foreign_flow: pd.Series | None = None,
    n_lstm_epochs: int = 60,
) -> ForecastResult:
    """
    Run all available models and combine predictions using timeframe weights.

    Parameters
    ----------
    df         : OHLCV DataFrame
    tf         : '1W' | '2W' | '1M' | '3M' | '5M'
    ticker     : symbol label
    regime     : market regime from RegimeResult
    macro_dict : from macro_data.fetch_macro_indicators()
    foreign_flow: pd.Series of daily net foreign buy values
    n_lstm_epochs: LSTM training epochs (reduce for faster iteration)
    """
    cfg    = TIMEFRAME_CONFIG[tf]
    n_days = cfg["hold_sessions"]
    base_w = cfg["ml_weights"].copy()  # {model: weight}

    method_flags = {
        "lstm":    TF_AVAILABLE,
        "xgb":     XGB_AVAILABLE,
        "rf":      True,
        "prophet": PROPHET_AVAILABLE,
        "arima":   ARIMA_AVAILABLE,
        "mc":      True,
    }

    # ─── run models ───────────────────────────────────────────
    model_preds: dict[str, list[float]] = {}

    # LSTM
    if method_flags["lstm"]:
        try:
            res = get_lstm_forecast(df, n_days, epochs=n_lstm_epochs,
                                     foreign_flow=foreign_flow)
            if res["prices"]:
                model_preds["lstm"] = res["prices"]
        except Exception as exc:
            logger.warning("LSTM failed: %s", exc)
            method_flags["lstm"] = False

    # XGBoost
    if method_flags["xgb"]:
        try:
            preds = xgb_predict(df, n_days, regime=regime, macro_dict=macro_dict)
            if preds:
                model_preds["xgb"] = preds
        except Exception as exc:
            logger.warning("XGBoost failed: %s", exc)
            method_flags["xgb"] = False

    # Random Forest (always available via sklearn)
    try:
        preds = rf_predict(df, n_days)
        if preds:
            model_preds["rf"] = preds
    except Exception as exc:
        logger.warning("RF failed: %s", exc)

    # Prophet
    if method_flags["prophet"]:
        try:
            preds = prophet_predict(df, n_days)
            if preds:
                model_preds["prophet"] = preds
        except Exception as exc:
            logger.warning("Prophet failed: %s", exc)
            method_flags["prophet"] = False

    # ARIMA
    if method_flags["arima"]:
        try:
            preds = arima_predict(df, n_days)
            if preds:
                model_preds["arima"] = preds
        except Exception as exc:
            logger.warning("ARIMA failed: %s", exc)
            method_flags["arima"] = False

    # Monte Carlo (always available)
    try:
        preds = monte_carlo_predict(df, n_days)
        if preds:
            model_preds["mc"] = preds
    except Exception as exc:
        logger.warning("MC failed: %s", exc)

    # ─── fallback: Holt's if everything else fails ───────────
    if not model_preds:
        preds = holt_predict(df, n_days)
        model_preds["holt"] = preds
        base_w = {"holt": 1.0}

    # ─── normalise weights for available models ───────────────
    active_w  = {m: w for m, w in base_w.items() if m in model_preds and w > 0}
    total_w   = sum(active_w.values())
    if total_w == 0:
        active_w = {m: 1.0 / len(model_preds) for m in model_preds}
        total_w  = 1.0
    norm_w    = {m: w / total_w for m, w in active_w.items()}

    # ─── pad all predictions to n_days ───────────────────────
    def _pad(lst: list[float]) -> np.ndarray:
        arr = np.array(lst, dtype=float)
        if len(arr) < n_days:
            arr = np.pad(arr, (0, n_days - len(arr)), mode="edge")
        return arr[:n_days]

    # ─── weighted ensemble (median across models, weighted) ───
    # Build weighted prediction matrix: (n_models, n_days)
    mat   = []
    ws    = []
    for m, w in norm_w.items():
        mat.append(_pad(model_preds[m]))
        ws.append(w)

    mat_arr = np.array(mat)   # (n_models, n_days)
    ws_arr  = np.array(ws)

    # Weighted median: repeat rows by relative weight
    rep_counts = np.maximum(1, (ws_arr * 100).astype(int))
    repeated   = np.repeat(mat_arr, rep_counts, axis=0)

    ensemble_median = np.median(repeated, axis=0)
    ensemble_p75    = np.percentile(repeated, 75, axis=0)
    ensemble_p25    = np.percentile(repeated, 25, axis=0)

    current_price = float(df["Close"].iloc[-1])
    target_price  = float(ensemble_median[-1])
    upside_pct    = (target_price - current_price) / current_price * 100 \
                    if current_price > 0 else 0.0

    return ForecastResult(
        ticker=ticker,
        timeframe=tf,
        n_days=n_days,
        prices=ensemble_median.tolist(),
        prices_bull=ensemble_p75.tolist(),
        prices_bear=ensemble_p25.tolist(),
        model_preds=model_preds,
        weights_used=norm_w,
        method_flags=method_flags,
        current_price=current_price,
        target_price=round(target_price, 0),
        upside_pct=round(upside_pct, 2),
    )

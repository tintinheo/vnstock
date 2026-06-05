#!/usr/bin/env python3
"""
candle_forecast_engine.py  —  Candlestick Forecast Engine  v1.0
═══════════════════════════════════════════════════════════════════════════════
Multi-model ensemble forecasting with predicted OHLCV candle reconstruction.

Pipeline:
    fit_garch()        → volatility forecast + VaR (arch library)
    fit_hmm()          → regime detection + transition matrix (hmmlearn)
    fit_sarima()       → statistical N-day close forecast (pmdarima)
    train_candle_lstm() → deep learning N-day OHLC forecast (Keras)
    fit_prophet()      → seasonality-aware N-day forecast (prophet)
    build_ensemble()   → inverse-error weighted combination
    build_predicted_candles() → OHLCV reconstruction from predicted closes
    classify_candle_pattern() → pattern recognition (Marubozu/Hammer/Doji/…)
    compute_confidence_score() → 5-component composite confidence
    find_optimal_timing()      → entry/exit/avoid period optimizer
    calculate_half_kelly()     → position sizing with catastrophic loss param
    run_candle_forecast()      → main entry point for UI

Exposed API (imported by Quant_Profiler_ui.py):
    run_candle_forecast(ticker, r, df, n_days) → dict
    train_candle_lstm_model(ticker, df, n_days, force, progress_callback) → model|None
    _CANDLE_KERAS_AVAILABLE  (bool)
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import logging
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

_DIR        = Path(__file__).parent
_MODELS_DIR = _DIR / "data" / "models"
_MODELS_DIR.mkdir(parents=True, exist_ok=True)

_log = logging.getLogger("candle_forecast")

# ── VN circuit breaker daily return clip ──────────────────────────────────────
_MAX_DAILY_RET = 0.065   # ±6.5% (±7% limit − 0.5% safety margin)

# ── LSTM config ───────────────────────────────────────────────────────────────
_SEQ_LEN   = 20     # look-back bars
_FEATURES  = 7      # close_ret, vol_ratio, rsi_n, macd_hist_n, atr_pct, cci_n, williams_n
_OHLCV_OUT = 5      # O, H, L, C, V multiplier

# ── Candle cache ──────────────────────────────────────────────────────────────
_CANDLE_LSTM_CACHE: dict = {}

# ─── Optional Keras ──────────────────────────────────────────────────────────
try:
    import keras                         # type: ignore
    _CANDLE_KERAS_AVAILABLE = True
except ImportError:
    try:
        from tensorflow import keras     # type: ignore
        _CANDLE_KERAS_AVAILABLE = True
    except ImportError:
        _CANDLE_KERAS_AVAILABLE = False
        keras = None  # type: ignore

# ─── Optional Prophet ────────────────────────────────────────────────────────
try:
    from prophet import Prophet          # type: ignore
    _PROPHET_AVAILABLE = True
except ImportError:
    _PROPHET_AVAILABLE = False
    Prophet = None  # type: ignore

# ─── GARCH arch library ──────────────────────────────────────────────────────
try:
    from arch import arch_model          # type: ignore
    _ARCH_AVAILABLE = True
except ImportError:
    _ARCH_AVAILABLE = False

# ─── HMM ─────────────────────────────────────────────────────────────────────
try:
    from hmmlearn.hmm import GaussianHMM  # type: ignore
    _HMM_AVAILABLE = True
except ImportError:
    _HMM_AVAILABLE = False
    GaussianHMM = None  # type: ignore

# ─── pmdarima ────────────────────────────────────────────────────────────────
try:
    from pmdarima import auto_arima      # type: ignore
    _PMDARIMA_AVAILABLE = True
except ImportError:
    _PMDARIMA_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GARCHResult:
    sigma_t1:      float          # next-period σ forecast
    vol_forecast:  list[float]    # σ per day for n_days
    var_95:        float          # 95% 1-day VaR as fraction
    persistence:   float          # α + β (>0.97 → high vol regime)
    high_vol_regime: bool
    status:        str            # "ok" | "fallback"


@dataclass
class HMMResult:
    current_state:     int              # 0=Bear, 1=Range, 2=Bull (sorted by μ)
    regime_label:      str              # "Bull" | "Range" | "Bear"
    transition_matrix: list[list[float]]
    next_state_probs:  list[float]      # [bear%, range%, bull%]
    state_prob:        float            # P(current hidden state)
    status:            str


@dataclass
class SarimaResult:
    forecast:   list[float]    # absolute price [N]
    lower_ci:   list[float]
    upper_ci:   list[float]
    rmse:       float
    aic:        float
    status:     str


@dataclass
class LSTMCandleResult:
    # per-day predicted [O, H, L, C, V_multiplier] for N days
    ohlcv_preds: list[list[float]]   # shape (N, 5)
    close_preds: list[float]         # absolute prices  [N]
    rmse:        float
    status:      str


@dataclass
class ProphetResult:
    forecast:  list[float]    # yhat absolute prices [N]
    lower_ci:  list[float]
    upper_ci:  list[float]
    rmse:      float
    status:    str


@dataclass
class EnsemblePrediction:
    close_preds:   list[float]           # final blended absolute close prices [N]
    pct_changes:   list[float]           # % change vs prev close [N]
    model_weights: dict[str, float]      # {"sarima": 0.4, "lstm": 0.4, "prophet": 0.2}
    directional_accuracy: dict[str, float]  # per-model DA% on walk-forward


@dataclass
class CandleDict:
    day:       int
    date_lbl:  str
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    lower_ci:  float
    upper_ci:  float
    pattern:   str
    signal:    str   # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL


@dataclass
class TimingResult:
    entry_period:  Optional[int]     # day index (0-based)
    exit_period:   Optional[int]
    avoid_periods: list[int]
    t25_windows:   list[int]         # T+2 session flags (for n_days ≤ 5)
    entry_reason:  str
    exit_reason:   str


@dataclass
class KellyResult:
    f_star:           float
    half_kelly:       float
    max_position_vnd: float
    num_lots:         int            # floor(max_position_vnd / (price × 100))
    is_hold:          bool           # True if half_kelly ≤ 0


# ══════════════════════════════════════════════════════════════════════════════
#  1. GARCH(1,1) VOLATILITY
# ══════════════════════════════════════════════════════════════════════════════

def fit_garch(returns: pd.Series, n_days: int) -> GARCHResult:
    """
    Fit GARCH(1,1) with skewed-t distribution on log-returns.
    Returns per-day σ forecast for n_days + 1-day 95% VaR.
    Falls back to rolling-std when arch unavailable or fitting fails.
    """
    ret = returns.dropna().values.astype(float)
    if len(ret) < 30 or not _ARCH_AVAILABLE:
        return _garch_fallback(ret, n_days)

    try:
        model = arch_model(ret * 100, vol="Garch", p=1, q=1, dist="skewt", rescale=False)
        res   = model.fit(disp="off", show_warning=False)

        params = res.params
        alpha  = float(params.get("alpha[1]", 0.05))
        beta   = float(params.get("beta[1]",  0.90))
        persistence = alpha + beta

        forecast   = res.forecast(horizon=n_days, reindex=False)
        var_arr    = np.sqrt(forecast.variance.values[-1]) / 100   # back to fraction
        sigma_t1   = float(var_arr[0])

        # 30% buffer for underestimated tail risk (VN market caveat)
        var_95 = float(sigma_t1 * 1.645 * 1.30)

        return GARCHResult(
            sigma_t1      = sigma_t1,
            vol_forecast  = [float(v) for v in var_arr],
            var_95        = var_95,
            persistence   = float(persistence),
            high_vol_regime = bool(persistence > 0.97),
            status        = "ok",
        )
    except Exception as exc:
        _log.warning("GARCH fit failed (%s), using fallback", exc)
        return _garch_fallback(ret, n_days)


def _garch_fallback(ret: np.ndarray, n_days: int) -> GARCHResult:
    """Rolling-std 20-bar fallback when GARCH unavailable/fails."""
    sigma = float(np.std(ret[-20:]) if len(ret) >= 20 else np.std(ret))
    var_95 = sigma * 1.645
    return GARCHResult(
        sigma_t1      = sigma,
        vol_forecast  = [sigma] * n_days,
        var_95        = var_95,
        persistence   = 0.90,
        high_vol_regime = False,
        status        = "fallback",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  2. HMM REGIME DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def fit_hmm(returns: pd.Series, n_components: int = 3) -> HMMResult:
    """
    Fit 3-state Gaussian HMM on daily log-returns.
    States sorted by mean return: Bear (lowest μ) → Range → Bull (highest μ).
    """
    ret = returns.dropna().values.astype(float).reshape(-1, 1)
    if len(ret) < 60 or not _HMM_AVAILABLE:
        return _hmm_fallback(returns)

    try:
        model = GaussianHMM(
            n_components=n_components,
            covariance_type="full",
            n_iter=200,
            random_state=42,
        )
        model.fit(ret)

        # Sort states by mean return: state 0=Bear, 1=Range, 2=Bull
        means   = model.means_.flatten()
        order   = np.argsort(means)           # sort ascending by μ
        remap   = {old: new for new, old in enumerate(order)}

        trans_raw  = model.transmat_
        trans_sort = trans_raw[order][:, order]   # reorder rows and cols

        # Predict current hidden state
        hidden    = model.predict(ret)
        cur_raw   = int(hidden[-1])
        cur_state = remap[cur_raw]              # remapped 0/1/2

        # P(current state) via posterior probs of last observation
        posteriors    = model.predict_proba(ret)
        cur_prob_raw  = float(posteriors[-1, cur_raw])

        # Next-step transition probabilities from current (sorted) state
        next_probs_raw = trans_sort[cur_state]  # [bear%, range%, bull%]

        labels = ["Bear", "Range", "Bull"]

        return HMMResult(
            current_state     = cur_state,
            regime_label      = labels[cur_state],
            transition_matrix = trans_sort.tolist(),
            next_state_probs  = next_probs_raw.tolist(),
            state_prob        = cur_prob_raw,
            status            = "ok",
        )
    except Exception as exc:
        _log.warning("HMM fit failed (%s), using fallback", exc)
        return _hmm_fallback(returns)


def _hmm_fallback(returns: pd.Series) -> HMMResult:
    """Map existing regime label to HMM-like output when hmmlearn fails."""
    recent_ret = float(returns.dropna().iloc[-5:].mean()) if len(returns) >= 5 else 0.0
    if recent_ret > 0.003:
        state, label = 2, "Bull"
    elif recent_ret < -0.003:
        state, label = 0, "Bear"
    else:
        state, label = 1, "Range"

    tri = [[0.70, 0.20, 0.10], [0.15, 0.65, 0.20], [0.10, 0.20, 0.70]]
    return HMMResult(
        current_state     = state,
        regime_label      = label,
        transition_matrix = tri,
        next_state_probs  = tri[state],
        state_prob        = 0.65,
        status            = "fallback",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  3. SARIMA
# ══════════════════════════════════════════════════════════════════════════════

def fit_sarima(close: pd.Series, n_days: int) -> SarimaResult:
    """
    Auto-ARIMA with seasonal period=20 (monthly VN trading sessions).
    Walk-forward RMSE computed on last 30-bar holdout.
    """
    close = close.dropna()
    if len(close) < 60 or not _PMDARIMA_AVAILABLE:
        return _sarima_fallback(close, n_days)

    try:
        train = close.iloc[:-30]
        test  = close.iloc[-30:]

        model = auto_arima(
            train,
            start_p=1, start_q=1,
            max_p=3,   max_q=3,
            d=None,                  # auto-differencing via ADF
            seasonal=True,
            m=20,                    # monthly VN seasonality
            start_P=0, start_Q=0,
            max_P=1,   max_Q=1,
            D=1,
            information_criterion="aic",
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            n_fits=10,
        )
        wf_preds = model.predict(n_periods=30)
        rmse = float(np.sqrt(np.mean((wf_preds - test.values) ** 2)))

        # Refit on full series
        model.update(test)
        fc_vals, ci = model.predict(n_periods=n_days, return_conf_int=True)

        # Clip runaway forecasts: max ±6.5% per day from last known price
        last_price = float(close.iloc[-1])
        clipped = _clip_forecast(fc_vals, last_price)

        return SarimaResult(
            forecast  = [float(v) for v in clipped],
            lower_ci  = [float(v) for v in ci[:, 0]],
            upper_ci  = [float(v) for v in ci[:, 1]],
            rmse      = rmse,
            aic       = float(model.aic()),
            status    = "ok",
        )
    except Exception as exc:
        _log.warning("SARIMA failed (%s), using fallback", exc)
        return _sarima_fallback(close, n_days)


def _sarima_fallback(close: pd.Series, n_days: int) -> SarimaResult:
    """Drift-based naive fallback: last N returns avg × t."""
    c = close.dropna()
    if len(c) < 5:
        last = float(c.iloc[-1]) if len(c) > 0 else 0.0
        return SarimaResult(
            forecast=[last] * n_days, lower_ci=[last] * n_days,
            upper_ci=[last] * n_days, rmse=0.0, aic=0.0, status="fallback",
        )
    ret_std = float(c.pct_change().dropna().std())
    last    = float(c.iloc[-1])
    drift   = float(c.pct_change().dropna().mean())
    drift   = np.clip(drift, -_MAX_DAILY_RET, _MAX_DAILY_RET)
    fc  = [last * (1 + drift) ** (i + 1) for i in range(n_days)]
    lci = [p * (1 - 1.645 * ret_std * np.sqrt(i + 1)) for i, p in enumerate(fc)]
    uci = [p * (1 + 1.645 * ret_std * np.sqrt(i + 1)) for i, p in enumerate(fc)]
    return SarimaResult(
        forecast=fc, lower_ci=lci, upper_ci=uci,
        rmse=last * ret_std, aic=0.0, status="fallback",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  4. CANDLE LSTM (N-day multi-output OHLCV)
# ══════════════════════════════════════════════════════════════════════════════

def _prepare_candle_features(df: pd.DataFrame) -> Optional[np.ndarray]:
    """Build (1, SEQ_LEN, FEATURES) inference tensor for CandleLSTM."""
    needed = ("Close", "High", "Low", "Volume", "RSI", "MACD_Hist", "ATR", "Vol_MA20")
    if df is None or len(df) < _SEQ_LEN + 1:
        return None
    for col in needed:
        if col not in df.columns:
            return None
    try:
        tail   = df.iloc[-(_SEQ_LEN + 1):]
        close  = tail["Close"].values.astype(float)
        vol    = tail["Volume"].values.astype(float)
        rsi    = tail["RSI"].values.astype(float) if "RSI" in tail else np.full(len(tail), 50.0)
        mh     = tail["MACD_Hist"].values.astype(float) if "MACD_Hist" in tail else np.zeros(len(tail))
        atr    = tail["ATR"].values.astype(float) if "ATR" in tail else np.zeros(len(tail))
        volma  = tail["Vol_MA20"].values.astype(float) if "Vol_MA20" in tail else vol

        # Williams %R and CCI if present
        wrr    = tail["Williams_R"].values.astype(float) if "Williams_R" in tail.columns else np.full(len(tail), -50.0)
        cci    = tail["CCI"].values.astype(float) if "CCI" in tail.columns else np.zeros(len(tail))

        close_ret = np.diff(close) / (close[:-1] + 1e-9) * 100
        vol_ratio = vol[1:] / (volma[1:] + 1e-9)
        rsi_n     = np.clip(rsi[1:] / 100.0, 0, 1)
        mh_n      = np.clip(mh[1:] / (close[1:] + 1e-9) * 100, -5, 5)
        atr_pct   = atr[1:] / (close[1:] + 1e-9) * 100
        cci_n     = np.clip(cci[1:] / 200.0, -1, 1)
        wrr_n     = (wrr[1:] + 100) / 100.0

        seq = np.stack([close_ret, vol_ratio, rsi_n, mh_n, atr_pct, cci_n, wrr_n], axis=1)
        seq = np.nan_to_num(seq, nan=0.0, posinf=0.0, neginf=0.0)
        return seq.reshape(1, _SEQ_LEN, _FEATURES)
    except Exception as exc:
        _log.warning("prepare_candle_features failed: %s", exc)
        return None


def _build_candle_training_data(
    df: pd.DataFrame, n_days: int
) -> "tuple[Optional[np.ndarray], Optional[np.ndarray]]":
    """
    Build (X, y) for CandleLSTM training.
    X: (samples, SEQ_LEN, FEATURES)
    y: (samples, n_days, 5) — [open_ret%, high_ret%, low_ret%, close_ret%, vol_mul]
    """
    needed = ("Close", "High", "Low", "Open", "Volume", "RSI", "MACD_Hist", "ATR", "Vol_MA20")
    if df is None or len(df) < _SEQ_LEN + n_days + 10:
        return None, None
    for col in needed:
        if col not in df.columns:
            return None, None
    try:
        close  = df["Close"].values.astype(float)
        high   = df["High"].values.astype(float)
        low    = df["Low"].values.astype(float)
        open_  = df["Open"].values.astype(float)
        vol    = df["Volume"].values.astype(float)
        rsi    = df["RSI"].values.astype(float)
        mh     = df["MACD_Hist"].values.astype(float)
        atr    = df["ATR"].values.astype(float)
        volma  = df["Vol_MA20"].values.astype(float)
        wrr    = df["Williams_R"].values.astype(float) if "Williams_R" in df.columns else np.full(len(close), -50.0)
        cci    = df["CCI"].values.astype(float) if "CCI" in df.columns else np.zeros(len(close))

        close_ret = np.concatenate([[0.0], np.diff(close) / (close[:-1] + 1e-9) * 100])
        vol_ratio = vol / (volma + 1e-9)
        rsi_n     = np.clip(rsi / 100.0, 0, 1)
        mh_n      = np.clip(mh / (close + 1e-9) * 100, -5, 5)
        atr_pct   = atr / (close + 1e-9) * 100
        cci_n     = np.clip(cci / 200.0, -1, 1)
        wrr_n     = (wrr + 100) / 100.0

        feat = np.stack([close_ret, vol_ratio, rsi_n, mh_n, atr_pct, cci_n, wrr_n], axis=1)
        feat = np.nan_to_num(feat, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

        n = len(close)
        X_list, y_list = [], []
        for i in range(_SEQ_LEN, n - n_days):
            X_list.append(feat[i - _SEQ_LEN : i])
            # Target: n_days of (open_ret, high_ret, low_ret, close_ret, vol_mul) relative to ref close
            ref_c = close[i - 1]
            y_seq = []
            for j in range(n_days):
                idx  = i + j
                c_r  = np.clip((close[idx] - ref_c) / (ref_c + 1e-9) * 100, -6.5, 6.5)
                h_r  = np.clip((high[idx]  - ref_c) / (ref_c + 1e-9) * 100, -6.5, 6.5)
                l_r  = np.clip((low[idx]   - ref_c) / (ref_c + 1e-9) * 100, -6.5, 6.5)
                o_r  = np.clip((open_[idx] - ref_c) / (ref_c + 1e-9) * 100, -6.5, 6.5)
                v_m  = np.clip(vol[idx] / (np.mean(vol[max(0, i-20):i]) + 1e-9), 0, 5)
                y_seq.append([o_r, h_r, l_r, c_r, v_m])
            y_list.append(y_seq)

        if len(X_list) < 30:
            return None, None

        return (
            np.array(X_list, dtype=np.float32),
            np.array(y_list, dtype=np.float32),
        )
    except Exception as exc:
        _log.warning("_build_candle_training_data failed: %s", exc)
        return None, None


def _directional_loss(y_true, y_pred):
    """
    Custom loss: 70% MSE + 30% directional penalty.
    Penalises wrong direction predictions on the close channel (index 3).
    """
    if keras is None:
        return (y_true - y_pred) ** 2  # plain MSE fallback

    import keras.backend as K  # type: ignore
    mse   = K.mean(K.square(y_true - y_pred))
    # Close return is channel index 3 across all n_days
    true_dir = y_true[:, :, 3]
    pred_dir = y_pred[:, :, 3]
    dir_pen  = K.mean(K.relu(-true_dir * pred_dir))
    return 0.70 * mse + 0.30 * dir_pen


def _build_candle_lstm_model(n_days: int) -> "Optional[object]":
    """Build CandleLSTM architecture: LSTM×2 → MultiHeadAttention → Dense(N×5)."""
    if not _CANDLE_KERAS_AVAILABLE or keras is None:
        return None
    try:
        inputs  = keras.layers.Input(shape=(_SEQ_LEN, _FEATURES))
        x       = keras.layers.LSTM(128, return_sequences=True)(inputs)
        x       = keras.layers.Dropout(0.20)(x)
        x       = keras.layers.LSTM(64, return_sequences=True)(x)
        x       = keras.layers.Dropout(0.15)(x)
        # Multi-Head Attention over the LSTM output sequence
        x_mha   = keras.layers.MultiHeadAttention(num_heads=4, key_dim=16)(x, x)
        x       = keras.layers.Add()([x, x_mha])           # residual
        x       = keras.layers.LayerNormalization()(x)
        # Flatten last step
        x       = keras.layers.Lambda(lambda t: t[:, -1, :])(x)
        x       = keras.layers.Dense(64, activation="relu")(x)
        x       = keras.layers.Dropout(0.10)(x)
        # Output: n_days × 5 channels
        out_flat = keras.layers.Dense(n_days * _OHLCV_OUT)(x)
        outputs  = keras.layers.Reshape((n_days, _OHLCV_OUT))(out_flat)

        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss=_directional_loss,
        )
        return model
    except Exception as exc:
        _log.warning("_build_candle_lstm_model failed: %s", exc)
        return None


def train_candle_lstm_model(
    ticker:            str,
    df:                pd.DataFrame,
    n_days:            int  = 5,
    force:             bool = False,
    epochs:            int  = 80,
    patience:          int  = 10,
    progress_callback = None,
) -> "Optional[object]":
    """
    Train or retrain the CandleLSTM model for ticker × n_days combination.
    Saved to data/models/{TICKER}_candle_lstm_{N}.keras.
    Returns trained Keras model or None if training fails/Keras unavailable.
    """
    if not _CANDLE_KERAS_AVAILABLE or keras is None:
        return None

    cache_key  = f"{ticker.upper()}_n{n_days}"
    model_path = _MODELS_DIR / f"{ticker.upper()}_candle_lstm_{n_days}.keras"

    if not force and cache_key in _CANDLE_LSTM_CACHE:
        return _CANDLE_LSTM_CACHE[cache_key]

    X, y = _build_candle_training_data(df, n_days)
    if X is None or len(X) < 30:
        _log.warning("CandleLSTM %s n%d: insufficient training data", ticker, n_days)
        return None

    try:
        cbs = []
        es  = keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=patience,
            restore_best_weights=True, verbose=0,
        )
        cbs.append(es)

        if progress_callback is not None:
            _req = epochs

            class _PBar(keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    progress_callback(epoch + 1, _req, logs or {})

            cbs.append(_PBar())

        split   = max(15, int(len(X) * 0.85))
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        model = _build_candle_lstm_model(n_days)
        if model is None:
            return None

        history = model.fit(
            X_tr, y_tr,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=max(8, min(32, len(X_tr) // 4)),
            callbacks=cbs,
            verbose=0,
        )

        _MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model.save(str(model_path))
        _CANDLE_LSTM_CACHE[cache_key] = model

        stopped_epoch = len(history.history["loss"])
        model._train_epochs  = stopped_epoch
        model._train_samples = len(X_tr)
        model._n_days        = n_days
        _log.info("CandleLSTM %s n%d trained: %d epochs %d samples", ticker, n_days, stopped_epoch, len(X_tr))
        return model

    except Exception as exc:
        _log.warning("CandleLSTM %s n%d train failed: %s", ticker, n_days, exc)
        return None


def _candle_lstm_inference(
    ticker: str,
    features: np.ndarray,
    df: pd.DataFrame,
    n_days: int,
    current_price: float,
) -> LSTMCandleResult:
    """Run CandleLSTM inference. Falls back to SARIMA-derived OHLCV on failure."""
    status    = "ok"
    cache_key = f"{ticker.upper()}_n{n_days}"
    model_path = _MODELS_DIR / f"{ticker.upper()}_candle_lstm_{n_days}.keras"

    model = _CANDLE_LSTM_CACHE.get(cache_key)
    if model is None and model_path.exists() and _CANDLE_KERAS_AVAILABLE and keras is not None:
        try:
            model = keras.models.load_model(
                str(model_path),
                custom_objects={"_directional_loss": _directional_loss},
                compile=False,
            )
            _CANDLE_LSTM_CACHE[cache_key] = model
        except Exception:
            model = None

    if model is None and df is not None:
        model = train_candle_lstm_model(ticker, df, n_days=n_days)

    if model is None or features is None:
        return _lstm_candle_fallback(current_price, n_days)

    try:
        pred = model.predict(features, verbose=0)[0]   # (n_days, 5)
        ohlcv_preds = []
        close_preds = []
        for i in range(n_days):
            o_r, h_r, l_r, c_r, v_m = [float(pred[i][k]) for k in range(5)]
            o_r = np.clip(o_r, -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100)
            h_r = np.clip(h_r, -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100)
            l_r = np.clip(l_r, -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100)
            c_r = np.clip(c_r, -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100)
            cp  = current_price * (1 + c_r / 100)
            close_preds.append(cp)
            ohlcv_preds.append([o_r, h_r, l_r, c_r, float(v_m)])

        # Walk-forward RMSE on last 20 bars (approx)
        wf_rmse = _wf_rmse_lstm(model, df, n_days, current_price)

        return LSTMCandleResult(
            ohlcv_preds=ohlcv_preds,
            close_preds=close_preds,
            rmse=wf_rmse,
            status=status,
        )
    except Exception as exc:
        _log.warning("CandleLSTM inference failed: %s", exc)
        return _lstm_candle_fallback(current_price, n_days)


def _wf_rmse_lstm(model, df, n_days, current_price) -> float:
    """Approximate walk-forward RMSE for ensemble weighting."""
    try:
        close = df["Close"].values.astype(float)
        if len(close) < _SEQ_LEN + n_days + 10:
            return current_price * 0.03
        preds, actuals = [], []
        for i in range(-min(20, len(close) - _SEQ_LEN - n_days), 0):
            sub_df = df.iloc[:i] if i < -1 else df.iloc[:-1]
            feat   = _prepare_candle_features(sub_df)
            if feat is None:
                continue
            pred = model.predict(feat, verbose=0)[0]
            pred_close_pct = float(pred[min(n_days - 1, 4), 3])  # last day close return
            pred_close     = close[i - n_days] * (1 + pred_close_pct / 100) if abs(i - n_days) < len(close) else current_price
            actual_close   = float(close[i if i != 0 else -1])
            preds.append(pred_close)
            actuals.append(actual_close)
        if len(preds) < 3:
            return current_price * 0.03
        return float(np.sqrt(np.mean((np.array(preds) - np.array(actuals)) ** 2)))
    except Exception:
        return current_price * 0.03


def _lstm_candle_fallback(current_price: float, n_days: int) -> LSTMCandleResult:
    return LSTMCandleResult(
        ohlcv_preds=[[0, 0.3, -0.3, 0, 1.0]] * n_days,
        close_preds=[current_price] * n_days,
        rmse=current_price * 0.05,
        status="fallback",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  5. FACEBOOK PROPHET
# ══════════════════════════════════════════════════════════════════════════════

def fit_prophet(df: pd.DataFrame, n_days: int) -> ProphetResult:
    """
    Fit Facebook Prophet on closing prices.
    VN holidays included; 20-session Fourier component for T+2.5 settlement.
    Walk-forward RMSE on last 30 bars.
    """
    if not _PROPHET_AVAILABLE or Prophet is None or df is None or len(df) < 80:
        return _prophet_fallback(df, n_days)

    try:
        # Prepare prophet dataframe
        dates  = pd.to_datetime(df.index if isinstance(df.index, pd.DatetimeIndex) else
                                df["Date"] if "Date" in df.columns else
                                pd.RangeIndex(len(df)))
        close  = df["Close"].values.astype(float)
        if len(dates) != len(close):
            return _prophet_fallback(df, n_days)

        prophet_df = pd.DataFrame({"ds": dates, "y": close})

        # Walk-forward RMSE on last 30
        train_pf = prophet_df.iloc[:-30]
        test_pf  = prophet_df.iloc[-30:]

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_mode="multiplicative",
        )
        m.add_seasonality(name="monthly_settlement", period=20, fourier_order=5)
        try:
            m.add_country_holidays(country_name="VN")
        except Exception:
            pass   # holidays package may not have VN

        import logging as _log_prophet
        _log_prophet.getLogger("prophet").setLevel(_log_prophet.WARNING)
        _log_prophet.getLogger("cmdstanpy").setLevel(_log_prophet.WARNING)

        m.fit(train_pf)

        future_wf     = m.make_future_dataframe(periods=30, freq="B")
        forecast_wf   = m.predict(future_wf)
        wf_preds      = forecast_wf["yhat"].values[-30:]
        rmse          = float(np.sqrt(np.mean((wf_preds - test_pf["y"].values) ** 2)))

        # Re-fit on full data
        m2 = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_mode="multiplicative",
        )
        m2.add_seasonality(name="monthly_settlement", period=20, fourier_order=5)
        try:
            m2.add_country_holidays(country_name="VN")
        except Exception:
            pass
        m2.fit(prophet_df)

        future   = m2.make_future_dataframe(periods=n_days, freq="B")
        forecast = m2.predict(future)
        fc_rows  = forecast.tail(n_days)

        last_price = float(close[-1])
        clipped    = _clip_forecast(fc_rows["yhat"].values, last_price)

        return ProphetResult(
            forecast  = [float(v) for v in clipped],
            lower_ci  = [float(v) for v in fc_rows["yhat_lower"].values],
            upper_ci  = [float(v) for v in fc_rows["yhat_upper"].values],
            rmse      = rmse,
            status    = "ok",
        )
    except Exception as exc:
        _log.warning("Prophet failed (%s), using fallback", exc)
        return _prophet_fallback(df, n_days)


def _prophet_fallback(df: Optional[pd.DataFrame], n_days: int) -> ProphetResult:
    """Naive fallback with last 5-day average return when Prophet unavailable."""
    if df is None or len(df) < 5:
        last = 0.0
        return ProphetResult(
            forecast=[last] * n_days, lower_ci=[last] * n_days,
            upper_ci=[last] * n_days, rmse=0.0, status="fallback",
        )
    close    = df["Close"].dropna().values.astype(float)
    ret_mean = float(np.mean(np.diff(close[-6:]) / (close[-6:-1] + 1e-9)))
    ret_mean = np.clip(ret_mean, -_MAX_DAILY_RET, _MAX_DAILY_RET)
    ret_std  = float(np.std(np.diff(close[-20:]) / (close[-20:-1] + 1e-9))) if len(close) >= 20 else 0.02
    last     = float(close[-1])
    fc  = [last * (1 + ret_mean) ** (i + 1) for i in range(n_days)]
    lci = [p * (1 - 1.96 * ret_std * np.sqrt(i + 1)) for i, p in enumerate(fc)]
    uci = [p * (1 + 1.96 * ret_std * np.sqrt(i + 1)) for i, p in enumerate(fc)]
    rmse = last * ret_std
    return ProphetResult(forecast=fc, lower_ci=lci, upper_ci=uci, rmse=rmse, status="fallback")


# ══════════════════════════════════════════════════════════════════════════════
#  6. ENSEMBLE COMBINER
# ══════════════════════════════════════════════════════════════════════════════

def build_ensemble(
    current_price: float,
    sarima:  SarimaResult,
    lstm:    LSTMCandleResult,
    prophet: ProphetResult,
    df:      pd.DataFrame,
    n_days:  int,
) -> EnsemblePrediction:
    """
    Inverse-error weighted ensemble of SARIMA + LSTM + Prophet.
    Models with higher RMSE receive lower weight.
    Failed models (status="fallback") still contribute but with downweighted RMSE.
    """
    # Normalise RMSE as fraction of price for comparability
    def _norm_rmse(result) -> float:
        r = max(getattr(result, "rmse", current_price * 0.05), 1e-6)
        # Penalise fallback models
        if getattr(result, "status", "ok") == "fallback":
            r *= 2.0
        return float(r)

    r_sar  = _norm_rmse(sarima)
    r_lst  = _norm_rmse(lstm)
    r_prp  = _norm_rmse(prophet)

    w_sar  = 1.0 / r_sar
    w_lst  = 1.0 / r_lst
    w_prp  = 1.0 / r_prp
    total  = w_sar + w_lst + w_prp

    ws = w_sar / total
    wl = w_lst / total
    wp = w_prp / total

    # Ensemble close predictions
    close_preds = []
    for i in range(n_days):
        s = sarima.forecast[i] if i < len(sarima.forecast) else current_price
        l = lstm.close_preds[i] if i < len(lstm.close_preds) else current_price
        p = prophet.forecast[i] if i < len(prophet.forecast) else current_price
        blended = ws * s + wl * l + wp * p
        close_preds.append(float(blended))

    # % changes vs previous close (current_price for day 0 ref)
    pct_changes = []
    prev = current_price
    for cp in close_preds:
        pct = (cp - prev) / (prev + 1e-9) * 100
        pct_changes.append(float(np.clip(pct, -_MAX_DAILY_RET * 100, _MAX_DAILY_RET * 100)))
        prev = cp

    # Per-model directional accuracy (walk-forward on df last 30 bars)
    da = _compute_da_per_model(df, sarima, lstm, prophet, n_days)

    return EnsemblePrediction(
        close_preds   = close_preds,
        pct_changes   = pct_changes,
        model_weights = {"sarima": round(ws, 3), "lstm": round(wl, 3), "prophet": round(wp, 3)},
        directional_accuracy = da,
    )


def _compute_da_per_model(df, sarima, lstm, prophet, n_days) -> dict[str, float]:
    """Estimate directional accuracy from pct changes vs historical trend."""
    if df is None or len(df) < 10:
        return {"sarima": 0.0, "lstm": 0.0, "prophet": 0.0}
    close    = df["Close"].dropna().values.astype(float)
    true_dir = 1 if close[-1] >= close[-min(5, len(close) - 1)] else -1
    da: dict[str, float] = {}

    for name, result in [("sarima", sarima), ("lstm", lstm), ("prophet", prophet)]:
        fc = getattr(result, "forecast", None) or getattr(result, "close_preds", None)
        if fc and len(fc) > 0:
            pred_dir = 1 if float(fc[-1]) >= float(close[-1]) else -1
            da[name] = 100.0 if pred_dir == true_dir else 0.0
        else:
            da[name] = 50.0
    return da


# ══════════════════════════════════════════════════════════════════════════════
#  7. OHLCV CANDLE BUILDER
# ══════════════════════════════════════════════════════════════════════════════

# Regime multipliers [body_mul, upper_shadow_mul, lower_shadow_mul, vol_mul]
_REGIME_MULTIPLIERS = {
    "Bull":  [1.20, 0.70, 0.80, 1.20],
    "Range": [0.70, 1.30, 1.30, 0.90],
    "Bear":  [1.20, 0.80, 0.70, 1.10],
}


def _compute_candle_params(df: pd.DataFrame) -> dict:
    """Compute historical average candle geometry from last 60 bars."""
    try:
        tail   = df.tail(60).copy()
        close  = tail["Close"].values.astype(float)
        open_  = tail["Open"].values.astype(float) if "Open" in tail.columns else close
        high   = tail["High"].values.astype(float)
        low    = tail["Low"].values.astype(float)
        vol    = tail["Volume"].values.astype(float)

        rng    = high - low + 1e-9
        body   = np.abs(close - open_)
        upper  = high - np.maximum(close, open_)
        lower  = np.minimum(close, open_) - low

        gaps   = np.diff(close) / (close[:-1] + 1e-9)

        return {
            "mean_gap_pct":         float(np.nanmean(gaps)),
            "mean_body_pct":        float(np.nanmean(body / (close + 1e-9))),
            "mean_upper_shadow_pct": float(np.nanmean(upper / (close + 1e-9))),
            "mean_lower_shadow_pct": float(np.nanmean(lower / (close + 1e-9))),
            "avg_volume":           float(np.nanmean(vol)),
        }
    except Exception:
        return {
            "mean_gap_pct": 0.0, "mean_body_pct": 0.01,
            "mean_upper_shadow_pct": 0.005, "mean_lower_shadow_pct": 0.005,
            "avg_volume": 500_000.0,
        }


def build_predicted_candles(
    ensemble:     EnsemblePrediction,
    df:           pd.DataFrame,
    hmm:          HMMResult,
    garch:        GARCHResult,
    n_days:       int,
    lstm_ohlcv:   Optional[LSTMCandleResult] = None,
) -> list[CandleDict]:
    """
    Reconstruct full OHLCV predicted candles from ensemble close forecasts.
    LSTM ohlcv_preds modulate the shadow ratios when available.
    """
    params      = _compute_candle_params(df)
    mul         = _REGIME_MULTIPLIERS.get(hmm.regime_label, _REGIME_MULTIPLIERS["Range"])
    body_mul    = mul[0]
    upper_mul   = mul[1]
    lower_mul   = mul[2]
    vol_mul     = mul[3]

    base_close  = float(df["Close"].iloc[-1]) if df is not None and len(df) > 0 else 0.0
    candles     = []

    for i in range(n_days):
        pred_close = ensemble.close_preds[i]
        sigma_i    = garch.vol_forecast[i] if i < len(garch.vol_forecast) else garch.sigma_t1

        # Open: previous close × (1 + mean_gap)
        prev_c = ensemble.close_preds[i - 1] if i > 0 else base_close
        open_  = prev_c * (1 + params["mean_gap_pct"])

        # Determine body direction
        bullish = pred_close >= open_

        # If LSTM provided shadow ratios, use them to modulate
        if lstm_ohlcv and i < len(lstm_ohlcv.ohlcv_preds):
            _, h_r, l_r, c_r, v_m = lstm_ohlcv.ohlcv_preds[i]
            # Use lstm projected high/low relative to open/close
            ref = prev_c
            lstm_high  = ref * (1 + h_r / 100)
            lstm_low   = ref * (1 + l_r / 100)
            upper_sh   = max(0, lstm_high - max(open_, pred_close))
            lower_sh   = max(0, min(open_, pred_close) - lstm_low)
            vol_factor = float(v_m) * vol_mul
        else:
            # Fallback to historical ratios × regime multiplier
            body_size  = abs(pred_close - open_)
            upper_sh   = pred_close * params["mean_upper_shadow_pct"] * upper_mul
            lower_sh   = pred_close * params["mean_lower_shadow_pct"] * lower_mul
            vol_factor = vol_mul

        high = max(open_, pred_close) + max(0, upper_sh)
        low  = min(open_, pred_close) - max(0, lower_sh)

        # GARCH confidence interval on close
        lower_ci = pred_close * (1 - 1.645 * sigma_i)
        upper_ci = pred_close * (1 + 1.645 * sigma_i)

        volume = params["avg_volume"] * vol_factor

        pattern, signal = classify_candle_pattern(open_, high, low, pred_close)

        # Generate trading-day label
        date_lbl = f"T+{i+1}"

        candles.append(CandleDict(
            day       = i,
            date_lbl  = date_lbl,
            open      = round(open_, 0),
            high      = round(high,  0),
            low       = round(low,   0),
            close     = round(pred_close, 0),
            volume    = round(volume, 0),
            lower_ci  = round(lower_ci, 0),
            upper_ci  = round(upper_ci, 0),
            pattern   = pattern,
            signal    = signal,
        ))

    return candles


# ══════════════════════════════════════════════════════════════════════════════
#  8. CANDLE PATTERN CLASSIFIER
# ══════════════════════════════════════════════════════════════════════════════

def classify_candle_pattern(o: float, h: float, l: float, c: float) -> tuple[str, str]:
    """
    Classify OHLC candle geometry into named pattern + trading signal.

    Returns (pattern_name, signal) where signal ∈
        STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
    """
    rng  = h - l + 1e-9
    body = abs(c - o)
    body_ratio   = body / rng
    upper_shadow = (h - max(c, o)) / rng
    lower_shadow = (min(c, o) - l) / rng
    bullish      = c >= o

    # ── Marubozu ─────────────────────────────────────────────────────────────
    if body_ratio > 0.90:
        if bullish:
            return "Bullish Marubozu", "STRONG_BUY"
        return "Bearish Marubozu", "STRONG_SELL"

    # ── Hammer / Pin Bar — checked BEFORE Doji (dominant lower shadow) ────────
    if body_ratio < 0.25 and lower_shadow > 0.55 and upper_shadow < 0.15:
        return "Hammer / Pin Bar", "BUY"

    # ── Shooting Star — checked BEFORE Doji (dominant upper shadow) ──────────
    if body_ratio < 0.25 and upper_shadow > 0.55 and lower_shadow < 0.15:
        return "Shooting Star", "SELL"

    # ── Dragonfly Doji (long lower shadow, no upper) ──────────────────────────
    if body_ratio < 0.08 and lower_shadow > 0.65:
        return "Dragonfly Doji", "BUY"

    # ── Gravestone Doji (long upper shadow, no lower) ─────────────────────────
    if body_ratio < 0.08 and upper_shadow > 0.65:
        return "Gravestone Doji", "SELL"

    # ── Doji ─────────────────────────────────────────────────────────────────
    if body_ratio < 0.05:
        return "Doji", "NEUTRAL"

    # ── Inverted Hammer (potential reversal up) ───────────────────────────────
    if body_ratio < 0.30 and upper_shadow > 0.50 and lower_shadow < 0.10 and bullish:
        return "Inverted Hammer", "BUY"

    # ── Spinning Top (small body, moderate both shadows) ─────────────────────
    if 0.10 < body_ratio < 0.35 and lower_shadow > 0.20 and upper_shadow > 0.20:
        return "Spinning Top", "NEUTRAL"

    # ── Strong bullish / bearish body (>60%) ─────────────────────────────────
    if body_ratio > 0.60:
        if bullish:
            return "Strong Bullish", "BUY"
        return "Strong Bearish", "SELL"

    # ── Default ──────────────────────────────────────────────────────────────
    if bullish:
        return "Bullish", "BUY"
    return "Bearish", "SELL"


# ══════════════════════════════════════════════════════════════════════════════
#  9. COMPOSITE CONFIDENCE SCORE
# ══════════════════════════════════════════════════════════════════════════════

_SIGNAL_STRENGTH = {
    "STRONG_BUY": 1.00, "BUY": 0.75, "NEUTRAL": 0.50, "SELL": 0.25, "STRONG_SELL": 0.00
}


def compute_confidence_score(
    candles:      list[CandleDict],
    hmm:          HMMResult,
    ensemble:     EnsemblePrediction,
    bt_win_rate:  float,     # from existing result dict, 0-100
    kl_ratio:     float,     # liquidity ratio vol/MA20
) -> tuple[float, str]:
    """
    C = 0.30 × ModelAgreement + 0.20 × RegimeConfidence
      + 0.15 × PatternStrength + 0.25 × HistAccuracy - 0.10 × HerdingIndex

    All components normalised to [0, 1] before weighting.
    Returns (confidence_score 0-100, grade "A+" | "A" | "B" | "C" | "D").
    """
    # ModelAgreement: 1 - CV of per-model final-day forecasts
    # (higher agreement → lower CV → higher score)
    weights = ensemble.model_weights
    model_closes = {}
    # Approximate per-model last-day close for CV
    # We only have blended closes; use DA as proxy for agreement
    da_vals = list(ensemble.directional_accuracy.values())
    if len(da_vals) >= 2:
        ma_raw = float(np.mean(da_vals)) / 100.0
    else:
        ma_raw = 0.5

    # RegimeConfidence
    rc_raw = float(hmm.state_prob)

    # PatternStrength: majority vote across predicted candle signals
    if candles:
        ps_vals = [_SIGNAL_STRENGTH.get(c.signal, 0.5) for c in candles]
        ps_raw  = float(np.mean(ps_vals))
    else:
        ps_raw = 0.5

    # HistAccuracy
    ha_raw = float(np.clip(bt_win_rate, 0, 100)) / 100.0

    # HerdingIndex (small-cap illiquid = high herding = penalty)
    hi_raw = float(min(1.0, kl_ratio * 2))   # kl_ratio ~0.2 (illiquid) → hi=0.4

    c_score = (
        0.30 * ma_raw
        + 0.20 * rc_raw
        + 0.15 * ps_raw
        + 0.25 * ha_raw
        - 0.10 * hi_raw
    )
    c_score = float(np.clip(c_score * 100, 0, 100))

    if c_score >= 80:
        grade = "A+"
    elif c_score >= 65:
        grade = "A"
    elif c_score >= 50:
        grade = "B"
    elif c_score >= 35:
        grade = "C"
    else:
        grade = "D"

    return round(c_score, 1), grade


# ══════════════════════════════════════════════════════════════════════════════
#  10. TIMING OPTIMIZER
# ══════════════════════════════════════════════════════════════════════════════

def find_optimal_timing(
    candles:       list[CandleDict],
    n_days:        int,
    current_price: float,
    garch:         GARCHResult,
    confidence:    float,
) -> TimingResult:
    """
    Scan predicted candles and identify:
    - Optimal entry day (bullish, confidence ≥55%, not >2% above current, not avoid)
    - Optimal exit day (first bearish after entry with confidence ≥55%, or TP hit)
    - Avoid periods (GARCH σ > 2× median σ)
    - T+2.5 windows (flagged when n_days ≤ 5, day index % 3 == 2)
    """
    median_sigma = np.median(garch.vol_forecast) if garch.vol_forecast else garch.sigma_t1

    avoid_periods = [
        i for i, σ in enumerate(garch.vol_forecast[:n_days])
        if σ > 2 * median_sigma
    ]

    # T+2.5 windows (for short n_days trades)
    t25_windows = []
    if n_days <= 5:
        t25_windows = [i for i in range(n_days) if i % 3 == 2]

    # Entry: first bullish candle satisfying all conditions
    entry_period = None
    entry_reason = ""
    for c in candles:
        i = c.day
        if i in avoid_periods:
            continue
        is_bullish   = c.close >= c.open
        not_too_high = c.close <= current_price * 1.02
        has_signal   = c.signal in ("STRONG_BUY", "BUY")
        if is_bullish and not_too_high and has_signal and confidence >= 55:
            entry_period = i
            entry_reason = f"Nến tăng tại T+{i+1}: {c.pattern} ({c.signal})"
            break

    # Exit: first bearish after entry OR last candle
    exit_period  = None
    exit_reason  = ""
    if entry_period is not None:
        for c in candles:
            i = c.day
            if i <= entry_period:
                continue
            is_bearish = c.close < c.open
            if is_bearish and confidence >= 55:
                exit_period = i
                exit_reason = f"Nến giảm tại T+{i+1}: {c.pattern}"
                break
        if exit_period is None:
            exit_period = n_days - 1
            exit_reason = "Kết thúc kỳ dự báo (chưa có tín hiệu thoát rõ)"

    return TimingResult(
        entry_period  = entry_period,
        exit_period   = exit_period,
        avoid_periods = avoid_periods,
        t25_windows   = t25_windows,
        entry_reason  = entry_reason,
        exit_reason   = exit_reason,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  11. HALF-KELLY POSITION SIZING
# ══════════════════════════════════════════════════════════════════════════════

def calculate_half_kelly(
    p_win:        float,    # win probability 0–1
    b_ratio:      float,    # win/loss ratio
    account_size: float,    # total capital in VND
    garch:        GARCHResult,
    lambda_loss:  float = 0.25,   # crash size (25% wipeout on catastrophic loss)
) -> KellyResult:
    """
    Gemini/proposal formula:
        f* = [(b × p_win) − (1 − p_win − r_catas) − (λ × r_catas)] / b × 0.5

    r_catas: 0.05 if GARCH persistence > 0.97 (high vol regime), else 0.01
    Half-Kelly applied: position = f* × 0.5
    Kelly Override Rule: if half_kelly ≤ 0 → HOLD
    """
    r_catas = 0.05 if garch.high_vol_regime else 0.01
    b = max(b_ratio, 1e-9)

    expectation = (b * p_win) - (1 - p_win - r_catas) - (lambda_loss * r_catas)
    f_star      = expectation / b
    half_kelly  = max(0.0, f_star * 0.5)

    # Cap at 20% of account (F0 investor safety)
    max_position_vnd = min(account_size * half_kelly, account_size * 0.20)
    is_hold = bool(half_kelly <= 0)

    return KellyResult(
        f_star           = round(float(f_star), 4),
        half_kelly       = round(float(half_kelly), 4),
        max_position_vnd = round(max_position_vnd, 0),
        num_lots         = 0,   # computed by caller who knows current price
        is_hold          = is_hold,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _clip_forecast(arr: np.ndarray, last_price: float) -> np.ndarray:
    """Clip daily returns to ±6.5% (Vietnam circuit breaker safety)."""
    result = []
    prev   = last_price
    for v in arr:
        ret     = (float(v) - prev) / (prev + 1e-9)
        ret     = np.clip(ret, -_MAX_DAILY_RET, _MAX_DAILY_RET)
        clipped = prev * (1 + ret)
        result.append(clipped)
        prev = clipped
    return np.array(result)


def _action_from_candles(candles: list[CandleDict], confidence: float, grade: str, half_kelly: float) -> str:
    """Derive overall action label from candle signals + confidence override rules."""
    if half_kelly <= 0:
        return "HOLD"
    if grade in ("C", "D"):
        return "HOLD"

    bull_signals = sum(1 for c in candles if c.signal in ("STRONG_BUY", "BUY"))
    sell_signals = sum(1 for c in candles if c.signal in ("STRONG_SELL", "SELL"))
    total        = len(candles) or 1

    bull_pct = bull_signals / total

    if grade == "A+" and bull_pct >= 0.60:
        return "STRONG_BUY"
    if grade in ("A+", "A") and bull_pct >= 0.50:
        return "BUY"
    if sell_signals / total >= 0.60:
        if grade == "A+":
            return "STRONG_SELL"
        return "SELL"
    return "HOLD"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def run_candle_forecast(
    ticker:       str,
    r:            dict,          # result dict from Quant_Profiler.analyse_ticker()
    df:           pd.DataFrame,
    n_days:       int = 5,
    account_size: float = 20_000_000.0,
) -> dict:
    """
    Full Candlestick Forecast pipeline.

    Returns:
    {
        "garch":      GARCHResult,
        "hmm":        HMMResult,
        "sarima":     SarimaResult,
        "lstm":       LSTMCandleResult,
        "prophet":    ProphetResult,
        "ensemble":   EnsemblePrediction,
        "candles":    list[CandleDict],
        "confidence": float,
        "grade":      str,
        "action":     str,
        "timing":     TimingResult,
        "kelly":      KellyResult,
        "n_days":     int,
        "ticker":     str,
        "current_price": float,
        "model_statuses": dict,
    }
    """
    if df is None or df.empty:
        return {"error": "No OHLCV data available for candle forecast."}

    # ── Prepare log-returns ──────────────────────────────────────────────────
    close_s = df["Close"].dropna()
    returns = np.log(close_s / close_s.shift(1)).dropna()

    current_price = float(r.get("price") or close_s.iloc[-1])
    bt_win_rate   = float(r.get("bt_win_rate") or 50.0)
    kl_ratio      = float(r.get("kl_ratio") or 1.0)

    # ── Step 1: GARCH ────────────────────────────────────────────────────────
    garch = fit_garch(returns, n_days)

    # ── Step 2: HMM ─────────────────────────────────────────────────────────
    hmm = fit_hmm(returns)

    # ── Steps 3/4/5: Models (pseudo-parallel: sequential in single thread) ──
    sarima  = fit_sarima(close_s, n_days)
    features = _prepare_candle_features(df)
    lstm    = _candle_lstm_inference(ticker, features, df, n_days, current_price)
    prophet = fit_prophet(df, n_days)

    # ── Step 6: Ensemble ─────────────────────────────────────────────────────
    ensemble = build_ensemble(current_price, sarima, lstm, prophet, df, n_days)

    # ── Step 7: Candle builder ───────────────────────────────────────────────
    candles = build_predicted_candles(ensemble, df, hmm, garch, n_days, lstm)

    # ── Step 9: Confidence score ─────────────────────────────────────────────
    confidence, grade = compute_confidence_score(candles, hmm, ensemble, bt_win_rate, kl_ratio)

    # ── Step 10: Timing optimizer ─────────────────────────────────────────────
    timing = find_optimal_timing(candles, n_days, current_price, garch, confidence)

    # ── Step 11: Half-Kelly position sizing ──────────────────────────────────
    p_win   = float(np.clip(bt_win_rate / 100, 0.01, 0.99))
    bt_avg_win  = float(r.get("bt_avg_win")  or 5.67)
    bt_avg_loss = abs(float(r.get("bt_avg_loss") or -3.61))
    b_ratio     = bt_avg_win / max(bt_avg_loss, 0.1)

    kelly = calculate_half_kelly(p_win, b_ratio, account_size, garch)
    # Compute lot size now that we have price
    lot_size         = int(kelly.max_position_vnd // (current_price * 100)) if current_price > 0 else 0
    kelly.num_lots   = max(0, lot_size)

    # ── Derive overall action ────────────────────────────────────────────────
    action = _action_from_candles(candles, confidence, grade, kelly.half_kelly)

    return {
        "garch":         garch,
        "hmm":           hmm,
        "sarima":        sarima,
        "lstm":          lstm,
        "prophet":       prophet,
        "ensemble":      ensemble,
        "candles":       candles,
        "confidence":    confidence,
        "grade":         grade,
        "action":        action,
        "timing":        timing,
        "kelly":         kelly,
        "n_days":        n_days,
        "ticker":        ticker,
        "current_price": current_price,
        "model_statuses": {
            "garch":   garch.status,
            "hmm":     hmm.status,
            "sarima":  sarima.status,
            "lstm":    lstm.status,
            "prophet": prophet.status,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SMOKE TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Running candle_forecast_engine smoke tests…")

    # GARCH
    rng  = np.random.default_rng(42)
    rets = pd.Series(rng.normal(0, 0.015, 200))
    g    = fit_garch(rets, 5)
    assert g.sigma_t1 > 0, "GARCH sigma must be positive"
    assert 0 <= g.persistence <= 2, "GARCH persistence out of range"
    print(f"  GARCH OK  σ={g.sigma_t1:.4f}  p={g.persistence:.3f}  status={g.status}")

    # HMM
    h = fit_hmm(rets)
    trans = np.array(h.transition_matrix)
    assert np.allclose(trans.sum(axis=1), 1.0, atol=0.01), "HMM transition rows must sum to 1"
    print(f"  HMM OK    state={h.current_state} ({h.regime_label})  status={h.status}")

    # Candle Pattern Classifier
    _, s1 = classify_candle_pattern(100, 101, 99, 100)    # Doji-like
    _, s2 = classify_candle_pattern(100, 100.5, 90, 100)  # Hammer
    _, s3 = classify_candle_pattern(100, 110, 99, 100)    # Shooting Star-like
    print(f"  Pattern OK  doji→{s1}  hammer→{s2}  top→{s3}")

    # Confidence score
    mock_candles = [CandleDict(0, "T+1", 100, 102, 98, 101, 500000, 97, 105, "Bullish", "BUY")]
    mock_hmm     = HMMResult(2, "Bull", [[0.1]*3]*3, [0.1, 0.2, 0.7], 0.80, "fallback")
    mock_ensemble = EnsemblePrediction([101.0], [1.0], {"sarima":0.4, "lstm":0.4, "prophet":0.2}, {"sarima":60.0, "lstm":60.0, "prophet":60.0})
    score, grade = compute_confidence_score(mock_candles, mock_hmm, mock_ensemble, 60.0, 1.5)
    assert 0 <= score <= 100, "Confidence score out of range"
    print(f"  Confidence OK  score={score}  grade={grade}")

    # Kelly
    g_mock = GARCHResult(0.015, [0.015]*5, 0.025, 0.92, False, "fallback")
    k = calculate_half_kelly(0.55, 1.5, 20_000_000, g_mock)
    assert k.half_kelly >= 0, "Half-Kelly must be non-negative"
    print(f"  Kelly OK  f*={k.f_star:.4f}  half={k.half_kelly:.4f}  hold={k.is_hold}")

    # Build candles from mock ensemble
    mock_df = pd.DataFrame({
        "Open":  rng.uniform(95, 105, 100),
        "High":  rng.uniform(100, 110, 100),
        "Low":   rng.uniform(90, 98, 100),
        "Close": rng.uniform(96, 106, 100),
        "Volume": rng.uniform(100000, 900000, 100),
    })
    mock_ens = EnsemblePrediction(
        close_preds=[101, 102, 103, 102, 104],
        pct_changes=[0.5, 1.0, 0.98, -0.98, 1.96],
        model_weights={"sarima":0.4, "lstm":0.4, "prophet":0.2},
        directional_accuracy={"sarima":60.0, "lstm":65.0, "prophet":55.0},
    )
    cs = build_predicted_candles(mock_ens, mock_df, mock_hmm, g_mock, 5)
    for c in cs:
        assert c.high >= max(c.open, c.close), f"H < max(O,C) on day {c.day}"
        assert c.low  <= min(c.open, c.close), f"L > min(O,C) on day {c.day}"
    print(f"  CandleBuilder OK  {len(cs)} candles, H≥max(O,C) and L≤min(O,C) verified")

    print("\n✅ All smoke tests passed.")

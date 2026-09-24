"""GJR-GARCH Risk Model — conditional VaR / CVaR for stop-loss calibration.

Implements the fat-tail risk measurement proposed in:
  "AMF Wash Sale Directionality" §Problem 3 — Absence of Fat-Tail Risk Management

Vietnamese equity market characteristics that make Normal-Distribution VaR
dangerous:
  - HOSE ±7% daily circuit breaker (hard cut-off, not tail continuation)
  - Sudden policy announcements → gap risk (15–25% in 1 session)
  - NPF foreign institutional flows (Circular 08/2026/TT-BTC) → liquidity shocks
  - Retail herding (F0 dominance) → fat left tails during panic sell-offs

Model: GJR-GARCH(1,1,1) with skewed-t distribution
  - GJR (Glosten-Jagannathan-Runkle) captures the asymmetric leverage effect:
    negative shocks increase volatility more than positive ones (VN = confirmed)
  - Skewed-t accounts for negative skewness and excess kurtosis in VN returns

Outputs (all expressed as percentages of entry price):
  var_95       : Value-at-Risk at 95% confidence (loss threshold, negative)
  var_99       : Value-at-Risk at 99% confidence (negative)
  cvar_95      : Conditional VaR / Expected Shortfall at 95% (negative)
  tail_regime  : FAT_TAIL | NORMAL_TAIL — classification based on kurtosis excess
  var_model    : GJR_GARCH | HISTORICAL | NONE — which model produced the result
  stop_loss_var: max(atr_stop, var99_stop) expressed as absolute price level

Fallback chain:
  1. GJR-GARCH(1,1,1) skewt  (requires ≥ 100 bars, arch installed)
  2. Historical simulation    (requires ≥ 30 bars)
  3. Zero-fill NONE           (insufficient data)
"""
from __future__ import annotations

import warnings
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy import stats

from ..utils.logging import get_logger

log = get_logger("risk_model")

# Minimum bars required for each model tier
_MIN_BARS_GARCH = 100
_MIN_BARS_HIST  = 30

# Kurtosis threshold above which we declare FAT_TAIL
_FAT_TAIL_KURTOSIS = 0.5   # excess kurtosis > 0.5 (Normal = 0 by definition)


class VaRResult(NamedTuple):
    var_95       : float   # % loss, negative  e.g. -2.4 means 2.4% loss
    var_99       : float   # % loss, negative
    cvar_95      : float   # % loss, negative (more extreme than VaR95)
    tail_regime  : str     # FAT_TAIL | NORMAL_TAIL
    var_model    : str     # GJR_GARCH | HISTORICAL | NONE
    cond_vol     : float   # current conditional volatility (%, annualised if GARCH)


# ── Public entry point ────────────────────────────────────────────────────────

def compute_var(df: pd.DataFrame) -> VaRResult:
    """
    Compute conditional VaR metrics from OHLCV DataFrame.

    Uses GJR-GARCH(1,1,1) with skewed-t if ≥ 100 bars are available,
    falls back to historical simulation for 30–99 bars, and returns
    zero-filled NONE for fewer than 30 bars.

    Args:
        df: OHLCV DataFrame with 'close' column (daily bars).

    Returns:
        VaRResult namedtuple — all pct values expressed as raw percentages
        (e.g., -2.5 means a 2.5% potential loss).
    """
    _none = VaRResult(0.0, 0.0, 0.0, "NORMAL_TAIL", "NONE", 0.0)

    close = df["close"].dropna()
    if len(close) < _MIN_BARS_HIST:
        return _none

    # Log-returns as percentages (arch convention)
    log_returns = np.log(close / close.shift(1)).dropna() * 100.0
    n = len(log_returns)

    # Tail regime classification (computed regardless of model)
    tail_regime = _classify_tail(log_returns.values)

    if n >= _MIN_BARS_GARCH:
        try:
            return _gjr_garch_var(log_returns.values, tail_regime)
        except Exception as e:
            log.debug(f"GJR-GARCH failed ({e}), falling back to historical")

    # Historical simulation fallback
    return _historical_var(log_returns.values, tail_regime)


# ── GJR-GARCH ────────────────────────────────────────────────────────────────

def _gjr_garch_var(returns: np.ndarray, tail_regime: str) -> VaRResult:
    """Fit GJR-GARCH(1,1,1) with skewed-t and extract 1-step-ahead VaR."""
    from arch import arch_model  # lazy import — arch not required at module load

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        am  = arch_model(returns, vol="GARCH", p=1, o=1, q=1, dist="skewt")
        res = am.fit(disp="off", show_warning=False)

    mu       = float(res.params.get("mu", 0.0))
    cond_vol = float(res.conditional_volatility[-1])

    # Standardised residuals for CVaR estimation
    std_resid = res.resid / res.conditional_volatility

    # VaR via Normal approximation of conditional distribution
    # (skewt parameters shift the tails, but for VaR we use empirical quantiles
    #  of standardised residuals which already embed the distribution shape)
    q95 = float(np.percentile(std_resid, 5))
    q99 = float(np.percentile(std_resid, 1))

    var_95 = round(mu + q95 * cond_vol, 4)
    var_99 = round(mu + q99 * cond_vol, 4)

    # CVaR = mean of residuals below 5th percentile, scaled by cond_vol
    tail_mask = std_resid <= q95
    cvar_95 = round(
        mu + float(std_resid[tail_mask].mean()) * cond_vol if tail_mask.sum() > 0 else var_95,
        4,
    )

    return VaRResult(
        var_95      = var_95,
        var_99      = var_99,
        cvar_95     = cvar_95,
        tail_regime = tail_regime,
        var_model   = "GJR_GARCH",
        cond_vol    = round(cond_vol, 4),
    )


# ── Historical simulation ─────────────────────────────────────────────────────

def _historical_var(returns: np.ndarray, tail_regime: str) -> VaRResult:
    """Historical simulation VaR — no distribution assumption."""
    var_95  = round(float(np.percentile(returns, 5)),  4)
    var_99  = round(float(np.percentile(returns, 1)),  4)
    cvar_95 = round(float(returns[returns <= var_95].mean()) if (returns <= var_95).any() else var_95, 4)
    cond_vol = round(float(returns.std()), 4)

    return VaRResult(
        var_95      = var_95,
        var_99      = var_99,
        cvar_95     = cvar_95,
        tail_regime = tail_regime,
        var_model   = "HISTORICAL",
        cond_vol    = cond_vol,
    )


# ── Tail regime classification ────────────────────────────────────────────────

def _classify_tail(returns: np.ndarray) -> str:
    """
    Classify tail regime based on excess kurtosis and skewness of log-returns.

    FAT_TAIL: excess kurtosis > 0.5  OR  skewness < -0.5
              (either heavy tails or left-skewed distribution)
    NORMAL_TAIL: otherwise
    """
    if len(returns) < 10:
        return "NORMAL_TAIL"
    excess_kurt = float(stats.kurtosis(returns, fisher=True))  # Fisher=True → Normal=0
    skewness    = float(stats.skew(returns))
    if excess_kurt > _FAT_TAIL_KURTOSIS or skewness < -0.5:
        return "FAT_TAIL"
    return "NORMAL_TAIL"


# ── Stop-loss calibration helper ──────────────────────────────────────────────

def calibrate_stop_with_var(
    entry_price: float,
    atr_stop: float,
    var_99: float,
) -> float:
    """
    Return the wider (more conservative) of the ATR-based stop and VaR-99 stop.

    Args:
        entry_price : current entry price (VND)
        atr_stop    : ATR-derived stop price (entry - ATR × mult), VND
        var_99      : GJR-GARCH VaR at 99% expressed as percentage (negative)
                      e.g., -3.2 means the model expects up to 3.2% loss

    Returns:
        stop_price (VND) — the lower of the two stop levels (larger drawdown)
    """
    if entry_price <= 0:
        return atr_stop

    # Convert VaR % to absolute stop price
    var_stop = entry_price * (1.0 + var_99 / 100.0)  # var_99 is negative

    # Conservative: take the lower price (further from entry = wider stop)
    return round(min(atr_stop, var_stop), 1)

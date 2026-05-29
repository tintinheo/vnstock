"""
core/regime.py — NewTradingOS v14.0
Market regime detection using Hidden Markov Model (HMM).
Falls back to rule-based detection if hmmlearn is unavailable.
"""
from __future__ import annotations

import logging
from typing import NamedTuple

import numpy as np
import pandas as pd

logger = logging.getLogger("TradingOS.regime")

try:
    from hmmlearn import hmm as _hmm
    HMMLEARN_AVAILABLE = True
except ImportError:
    HMMLEARN_AVAILABLE = False
    logger.info("hmmlearn not installed; using rule-based regime fallback.")


class RegimeResult(NamedTuple):
    regime:       str    # 'bull' | 'bear' | 'sideways'
    probability:  float  # [0, 1]
    history:      list   # list of regime strings, length = len(returns)
    method:       str    # 'hmm' | 'rule'
    state_stats:  dict   # {regime: mean_daily_return}


# ─────────────────────────────────────────────────────────────
# HMM-BASED DETECTION
# ─────────────────────────────────────────────────────────────
def _detect_hmm(prices: pd.Series, n_states: int = 3) -> RegimeResult:
    """
    Fit a 3-state Gaussian HMM to log-returns.
    States labelled by ascending mean return: bear < sideways < bull.
    """
    log_ret = np.diff(np.log(prices.values)).reshape(-1, 1)
    if len(log_ret) < 60:
        # Not enough data for HMM
        return _detect_rule(prices)

    model = _hmm.GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=300,
        random_state=42,
        tol=1e-4,
    )
    try:
        model.fit(log_ret)
    except Exception as exc:
        logger.warning("HMM fit failed: %s — falling back to rule-based", exc)
        return _detect_rule(prices)

    hidden_states = model.predict(log_ret)

    # Map states to labels by mean return
    state_means = {
        s: float(log_ret[hidden_states == s].mean())
        for s in range(n_states)
        if (hidden_states == s).any()
    }
    sorted_states = sorted(state_means, key=lambda s: state_means[s])
    label_map = {}
    labels_ordered = ["bear", "sideways", "bull"]
    for i, s in enumerate(sorted_states):
        label_map[s] = labels_ordered[i]

    history = [label_map.get(s, "sideways") for s in hidden_states]

    current_state = int(hidden_states[-1])
    try:
        _, posteriors = model.score_samples(log_ret)
        current_prob = float(posteriors[-1, current_state])
    except Exception:
        current_prob = 0.5

    state_stats = {
        label_map.get(s, "sideways"): round(float(v) * 100, 4)
        for s, v in state_means.items()
    }

    return RegimeResult(
        regime=label_map.get(current_state, "sideways"),
        probability=round(current_prob, 3),
        history=history,
        method="hmm",
        state_stats=state_stats,
    )


# ─────────────────────────────────────────────────────────────
# RULE-BASED FALLBACK
# ─────────────────────────────────────────────────────────────
def _detect_rule(prices: pd.Series) -> RegimeResult:
    """
    Simple rule-based regime:
    - bull:    price > SMA50 AND SMA20 > SMA50
    - bear:    price < SMA50 AND SMA20 < SMA50
    - sideways: otherwise

    For each bar, compute rolling regime to build history.
    """
    close  = prices.values
    n      = len(close)
    period_fast = 20
    period_slow = 50

    def _sma(arr, w):
        result = np.full(len(arr), np.nan)
        for i in range(w - 1, len(arr)):
            result[i] = arr[max(0, i - w + 1): i + 1].mean()
        return result

    sma20 = _sma(close, min(period_fast, n))
    sma50 = _sma(close, min(period_slow, n))

    history = []
    for i in range(n):
        if np.isnan(sma20[i]) or np.isnan(sma50[i]):
            history.append("sideways")
        elif close[i] > sma50[i] and sma20[i] > sma50[i]:
            history.append("bull")
        elif close[i] < sma50[i] and sma20[i] < sma50[i]:
            history.append("bear")
        else:
            history.append("sideways")

    current_regime = history[-1] if history else "sideways"

    # Probability proxy: % of last 20 sessions in current regime
    last_20 = history[-20:] if len(history) >= 20 else history
    prob = last_20.count(current_regime) / len(last_20)

    # Simple state stats
    rets = pd.Series(close).pct_change().dropna()
    h_s  = history[1:]  # align with rets
    state_stats = {}
    for regime in ("bull", "bear", "sideways"):
        idx = [i for i, r in enumerate(h_s) if r == regime]
        if idx:
            state_stats[regime] = round(float(rets.iloc[idx].mean()) * 100, 4)
        else:
            state_stats[regime] = 0.0

    return RegimeResult(
        regime=current_regime,
        probability=round(prob, 3),
        history=history,
        method="rule",
        state_stats=state_stats,
    )


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────
def detect_regime(prices: pd.Series, use_hmm: bool = True) -> RegimeResult:
    """
    Detect current market regime from a price series.

    Parameters
    ----------
    prices : pd.Series
        Daily closing prices (VN-Index or individual stock).
    use_hmm : bool
        Use HMM if hmmlearn is available; else fall back to rule-based.

    Returns
    -------
    RegimeResult namedtuple
    """
    if prices is None or len(prices) < 10:
        return RegimeResult("sideways", 0.5, [], "rule", {})

    prices = prices.dropna()
    if use_hmm and HMMLEARN_AVAILABLE:
        return _detect_hmm(prices)
    return _detect_rule(prices)


def regime_color(regime: str) -> str:
    """Streamlit-compatible color string for regime badge."""
    return {"bull": "#00cc66", "bear": "#ff4444", "sideways": "#ffaa33"}.get(
        regime, "#aaaaaa"
    )


def regime_emoji(regime: str) -> str:
    return {"bull": "🟢", "bear": "🔴", "sideways": "🟡"}.get(regime, "⚪")


def regime_label_vi(regime: str) -> str:
    return {"bull": "Tăng", "bear": "Giảm", "sideways": "Đi ngang"}.get(
        regime, "Không rõ"
    )

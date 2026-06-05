"""Macro Engine — Vietnam macro-regime scoring for top-down overlay (SRS §3.11).

Computes a continuous MacroScore (-100 to +100) and maps it to a MacroRegime.
Three primary inputs for the Vietnamese market:
  1. USD/VND exchange rate momentum + proximity to SBV ceiling
  2. SBV OMO / T-bill net injection (proxy: broad money M2 weekly change)
  3. VN 10-year Government Bond yield momentum

The MacroScore acts as a "throttle valve":
  - ACCOMMODATIVE (score > 30): allow full kelly sizing, loosen BUY gate
  - NEUTRAL (-30 ≤ score ≤ 30): normal operation
  - RESTRICTIVE (score < -30): reduce kelly max, tighten BUY gate

Key design choices:
  - Score is CONTINUOUS (not discrete step function) to avoid regime flip-flopping.
  - Hysteresis band ±10pts prevents oscillation at regime boundaries.
  - Staleness penalty: score decays 5pts/day after 3 days without fresh data.
  - Fallback: returns NEUTRAL with confidence=LOW when all sources fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..utils.config import cfg
from ..utils.logging import get_logger

log = get_logger("macro")

# ── Regime thresholds (readable from strategy.yaml) ─────────────────────────
# [BUG-24 FIX] These were hardcoded at ±30, but config has accommodative_min=15
# and restrictive_max=-15.  Using hardcoded ±30 meant the macro regime would
# switch 2× too late (score had to be twice as extreme as the config specifies).
# Now _regime_from_score() reads from config at call time so strategy.yaml is
# the single source of truth.  Module-level constants kept only as fallbacks.
_ACCOMMODATIVE_THRESHOLD = 15   # fallback; real value comes from config
_RESTRICTIVE_THRESHOLD   = -15  # fallback; real value comes from config
_HYSTERESIS              = 10   # must cross threshold by this much to change regime


# ── Data Containers ───────────────────────────────────────────────────────────

@dataclass
class MacroIndicator:
    """A single macro data point with staleness tracking."""
    name        : str
    value       : float
    as_of_date  : date
    source      : str
    contrib     : float = 0.0   # contribution to MacroScore after scoring


@dataclass
class MacroResult:
    """Full macro regime output returned from compute_macro_regime()."""
    macro_score       : float                        # -100 to +100 continuous
    macro_regime      : str                          # ACCOMMODATIVE | NEUTRAL | RESTRICTIVE
    macro_confidence  : str                          # HIGH | MEDIUM | LOW
    macro_staleness_days : int                       # days since freshest data point
    indicators        : list[MacroIndicator] = field(default_factory=list)
    warnings          : list[str]            = field(default_factory=list)
    as_of_date        : Optional[date]       = None

    def to_dict(self) -> dict:
        return {
            "macro_score":            round(self.macro_score, 1),
            "macro_regime":           self.macro_regime,
            "macro_confidence":       self.macro_confidence,
            "macro_staleness_days":   self.macro_staleness_days,
            "macro_warnings":         self.warnings,
            "macro_as_of":            str(self.as_of_date) if self.as_of_date else "",
        }


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _score_usdvnd(df: pd.DataFrame) -> tuple[float, str]:
    """
    Score USD/VND based on:
    - 20-day momentum (rate rising = market stress = negative)
    - Proximity to perceived SBV ceiling (configurable, default 26,000)
    Returns (contribution: -40 to +40, detail_str).
    """
    if df.empty or len(df) < 10:
        return 0.0, "USDVND: no data"

    close = df["close"].values
    rate_now  = float(close[-1])
    rate_20d  = float(close[max(-20, -len(close))])
    momentum  = (rate_now - rate_20d) / max(rate_20d, 1)

    sbv_ceiling = float(cfg.strategy("macro", "sbv_usdvnd_ceiling", default=26_000))

    # Proximity: 0 = far from ceiling, 1 = at ceiling
    proximity   = max(0.0, (rate_now - sbv_ceiling * 0.97) / (sbv_ceiling * 0.03))
    proximity   = float(np.clip(proximity, 0.0, 1.0))

    # Momentum score: -30 to +30 (negative momentum = tỷ giá giảm = tích cực)
    mom_score   = float(np.clip(-momentum * 20 / 0.03, -30, 30))

    # Ceiling proximity: adds up to -10 penalty near ceiling
    ceiling_pen = -proximity * 10

    total = mom_score + ceiling_pen
    total = float(np.clip(total, -40, 40))

    detail = (f"USDVND {rate_now:,.0f} | 20d momentum {momentum:+.2%} | "
              f"ceiling proximity {proximity:.1%}")
    return total, detail


def _score_sbv_omo(net_injection_7d: float, avg_vol_ref: float) -> tuple[float, str]:
    """
    Score SBV net injection from OMO / T-bill operations.
    Positive net_injection (bơm ròng) → positive signal.
    Negative (hút ròng) → negative signal.
    net_injection_7d: sum of 7-day net injection (VND billion).
    avg_vol_ref    : reference average weekly volume (VND billion).
    Returns (contribution: -30 to +30, detail_str).
    """
    if avg_vol_ref <= 0:
        return 0.0, "SBV OMO: no reference volume"

    normalized = net_injection_7d / max(avg_vol_ref, 1)
    score = float(np.clip(normalized * 30, -30, 30))
    detail = (f"SBV OMO 7d net {net_injection_7d:+,.0f}B | "
              f"normalized {normalized:+.2f} → score {score:+.1f}")
    return score, detail


def _score_bond_yield(df: pd.DataFrame) -> tuple[float, str]:
    """
    Score VN 10Y Government Bond yield momentum.
    Rising yield = tightening = negative for equities.
    Returns (contribution: -30 to +30, detail_str).
    """
    if df.empty or len(df) < 5:
        return 0.0, "Bond yield: no data"

    yields = df["yield"].values
    dy_20d = float(yields[-1]) - float(yields[max(-20, -len(yields))])  # absolute bps-like change

    # Each 0.5% (50bps) rise → -30 contribution
    score = float(np.clip(-dy_20d * 60, -30, 30))
    detail = (f"VN10Y yield {yields[-1]:.2f}% | 20d Δ {dy_20d:+.2f}% → score {score:+.1f}")
    return score, detail


def _staleness_penalty(staleness_days: int) -> float:
    """Reduce score magnitude by cfg-driven pts/day after grace period."""
    # [BUG-26 FIX] Read staleness constants from config (strategy.yaml macro section)
    # instead of hardcoding 3, 5, 40.  Values happen to be identical but must flow
    # through a single source of truth per SRS §9.4.
    grace    = int(cfg.strategy("macro", "staleness_grace_days",  default=3))
    pts_day  = float(cfg.strategy("macro", "staleness_pts_per_day", default=5))
    cap      = float(cfg.strategy("macro", "staleness_cap_pts",     default=40))
    if staleness_days <= grace:
        return 0.0
    return float(min((staleness_days - grace) * pts_day, cap))


def _regime_from_score(score: float, prev_regime: str = "NEUTRAL") -> str:
    """Map continuous score to regime with hysteresis."""
    # [BUG-24 FIX] Read thresholds from config so strategy.yaml is the sole
    # source of truth.  Old module constants were ±30; config specifies ±15.
    acc_thr  = float(cfg.strategy("macro", "accommodative_min", default=_ACCOMMODATIVE_THRESHOLD))
    rest_thr = float(cfg.strategy("macro", "restrictive_max",   default=_RESTRICTIVE_THRESHOLD))
    hyst     = float(_HYSTERESIS)
    # Hysteresis: only change regime when crossing threshold by hyst
    if prev_regime == "ACCOMMODATIVE":
        if score < acc_thr - hyst:
            return "NEUTRAL"
    elif prev_regime == "RESTRICTIVE":
        if score > rest_thr + hyst:
            return "NEUTRAL"

    if score > acc_thr:
        return "ACCOMMODATIVE"
    elif score < rest_thr:
        return "RESTRICTIVE"
    return "NEUTRAL"


def _confidence_from_staleness(staleness_days: int, n_sources: int) -> str:
    if staleness_days > 5 or n_sources == 0:
        return "LOW"
    if staleness_days > 2 or n_sources == 1:
        return "MEDIUM"
    return "HIGH"


# ── Public API ────────────────────────────────────────────────────────────────

def compute_macro_regime(
    usdvnd_df: pd.DataFrame | None = None,
    bond_yield_df: pd.DataFrame | None = None,
    sbv_net_injection_7d: float | None = None,
    sbv_avg_vol_ref: float = 10_000.0,   # VND billion reference
    prev_regime: str = "NEUTRAL",
    as_of: date | None = None,
) -> MacroResult:
    """
    Compute macro regime from available data sources.

    Parameters
    ----------
    usdvnd_df          : DataFrame with columns [date, close] — USD/VND interbank rate.
    bond_yield_df      : DataFrame with columns [date, yield] — VN 10Y G-Bond yield (%).
    sbv_net_injection_7d: Net SBV OMO injection over the last 7 days (VND billion).
                          Positive = bơm ròng, Negative = hút ròng.
    sbv_avg_vol_ref    : Average weekly OMO volume for normalisation (VND billion).
    prev_regime        : Previous regime (for hysteresis).
    as_of              : The reference date (defaults to today).

    Returns
    -------
    MacroResult with macro_score, macro_regime, macro_confidence, staleness_days.
    """
    as_of    = as_of or date.today()
    warnings : list[str] = []
    indicators: list[MacroIndicator] = []
    total_score  = 0.0
    n_sources    = 0
    freshest_date: date | None = None

    # ── Component 1: USD/VND ─────────────────────────────────────────────
    if usdvnd_df is not None and not usdvnd_df.empty:
        contrib, detail = _score_usdvnd(usdvnd_df)
        last_date = pd.to_datetime(usdvnd_df["date"].iloc[-1]).date()
        indicators.append(MacroIndicator(
            name="USDVND", value=float(usdvnd_df["close"].iloc[-1]),
            as_of_date=last_date, source="SSI/VCB", contrib=contrib
        ))
        total_score += contrib
        n_sources   += 1
        if freshest_date is None or last_date > freshest_date:
            freshest_date = last_date
        log.debug(detail)
    else:
        warnings.append("USDVND data unavailable — component skipped")

    # ── Component 2: SBV OMO ─────────────────────────────────────────────
    if sbv_net_injection_7d is not None:
        contrib, detail = _score_sbv_omo(sbv_net_injection_7d, sbv_avg_vol_ref)
        indicators.append(MacroIndicator(
            name="SBV_OMO", value=sbv_net_injection_7d,
            as_of_date=as_of, source="SBV", contrib=contrib
        ))
        total_score += contrib
        n_sources   += 1
        if freshest_date is None or as_of > freshest_date:
            freshest_date = as_of
        log.debug(detail)
    else:
        warnings.append("SBV OMO data unavailable — component skipped")

    # ── Component 3: VN10Y Bond Yield ────────────────────────────────────
    if bond_yield_df is not None and not bond_yield_df.empty:
        contrib, detail = _score_bond_yield(bond_yield_df)
        last_date = pd.to_datetime(bond_yield_df["date"].iloc[-1]).date()
        indicators.append(MacroIndicator(
            name="VN10Y_YIELD", value=float(bond_yield_df["yield"].iloc[-1]),
            as_of_date=last_date, source="HNX", contrib=contrib
        ))
        total_score += contrib
        n_sources   += 1
        if freshest_date is None or last_date > freshest_date:
            freshest_date = last_date
        log.debug(detail)
    else:
        warnings.append("VN10Y bond yield data unavailable — component skipped")

    # ── Staleness penalty ────────────────────────────────────────────────
    staleness_days = 0
    if freshest_date:
        staleness_days = max(0, (as_of - freshest_date).days)
    penalty = _staleness_penalty(staleness_days)
    if penalty > 0:
        # Pull score toward 0 (neutral) proportionally
        total_score = total_score * (1 - penalty / 100)
        warnings.append(f"Data stale {staleness_days}d — score dampened by {penalty:.0f}pts")

    total_score = float(np.clip(total_score, -100, 100))

    # ── Regime + confidence ──────────────────────────────────────────────
    regime     = _regime_from_score(total_score, prev_regime)
    confidence = _confidence_from_staleness(staleness_days, n_sources)

    if n_sources == 0:
        warnings.append("All macro sources unavailable — defaulting to NEUTRAL/LOW")

    return MacroResult(
        macro_score=total_score,
        macro_regime=regime,
        macro_confidence=confidence,
        macro_staleness_days=staleness_days,
        indicators=indicators,
        warnings=warnings,
        as_of_date=as_of,
    )


# ── Sizing adjustment from macro ─────────────────────────────────────────────

def macro_sizing_multiplier(macro_result: MacroResult) -> float:
    """
    Return a multiplier (0.32–1.0) to apply to kelly_max_pct.
    Reads multipliers from strategy.yaml (macro section).
    """
    # [BUG-25 FIX] Hardcoded NEUTRAL=0.75 and RESTRICTIVE=0.40 disagree with config
    # sizing_neutral=0.65 and sizing_restrictive=0.32.  Read from config so all
    # threshold changes flow through a single source of truth per SRS §9.4.
    if macro_result is None:
        return 1.0
    acc_mult  = float(cfg.strategy("macro", "sizing_accommodative", default=1.00))
    neu_mult  = float(cfg.strategy("macro", "sizing_neutral",       default=0.65))
    rest_mult = float(cfg.strategy("macro", "sizing_restrictive",   default=0.32))
    regime_mult = {
        "ACCOMMODATIVE": acc_mult,
        "NEUTRAL":       neu_mult,
        "RESTRICTIVE":   rest_mult,
    }.get(macro_result.macro_regime, neu_mult)

    confidence_mult = {
        "HIGH":   1.00,
        "MEDIUM": 0.90,
        "LOW":    0.80,
    }.get(macro_result.macro_confidence, 0.90)

    return regime_mult * confidence_mult


def macro_score_gate_adjustment(macro_result: MacroResult) -> int:
    """
    Return additive delta for min_score_strong_buy gate.

    RESTRICTIVE  → +10 (require higher score to trigger BUY — tighter gate)
    NEUTRAL      → 0
    ACCOMMODATIVE → -5 (relax slightly when macro is supportive)
    """
    if macro_result is None:
        return 0
    return {
        "ACCOMMODATIVE": -5,
        "NEUTRAL":        0,
        "RESTRICTIVE":   +10,
    }.get(macro_result.macro_regime, 0)


def build_macro_regime_series(
    trading_dates: pd.Series | list,
    usdvnd_df: pd.DataFrame | None = None,
    bond_yield_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a daily macro regime series aligned to trading dates for backtests.

    Uses only historical series that are actually available by date. If one source
    is missing, the series still builds from the remaining source(s).
    """
    if trading_dates is None or len(trading_dates) == 0:
        return pd.DataFrame(columns=["date", "macro_score", "macro_regime"])

    dates = pd.to_datetime(pd.Series(trading_dates), errors="coerce").dropna().dt.date.drop_duplicates().sort_values()
    if dates.empty:
        return pd.DataFrame(columns=["date", "macro_score", "macro_regime"])

    usdvnd = usdvnd_df.copy() if usdvnd_df is not None else pd.DataFrame(columns=["date", "close"])
    bond = bond_yield_df.copy() if bond_yield_df is not None else pd.DataFrame(columns=["date", "yield"])
    if not usdvnd.empty:
        usdvnd["date"] = pd.to_datetime(usdvnd["date"], errors="coerce").dt.date
        usdvnd = usdvnd.sort_values("date")
    if not bond.empty:
        bond["date"] = pd.to_datetime(bond["date"], errors="coerce").dt.date
        bond = bond.sort_values("date")

    prev_regime = "NEUTRAL"
    rows: list[dict] = []
    for current_date in dates.tolist():
        usd_slice = usdvnd[usdvnd["date"] <= current_date].tail(60) if not usdvnd.empty else pd.DataFrame(columns=["date", "close"])
        bond_slice = bond[bond["date"] <= current_date].tail(60) if not bond.empty else pd.DataFrame(columns=["date", "yield"])
        result = compute_macro_regime(
            usdvnd_df=usd_slice,
            bond_yield_df=bond_slice,
            sbv_net_injection_7d=None,
            prev_regime=prev_regime,
            as_of=current_date,
        )
        prev_regime = result.macro_regime
        rows.append({
            "date": current_date,
            "macro_score": result.macro_score,
            "macro_regime": result.macro_regime,
        })

    return pd.DataFrame(rows)

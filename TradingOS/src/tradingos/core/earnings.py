"""Earnings / BCTC risk engine — Phase 2.

Purpose
-------
Detect upcoming earnings-publication windows and adjust the exit plan accordingly.
Vietnamese listed companies must publish quarterly BCTC (financial statements)
by regulatory deadlines (Circular 96/2020/TT-BTC). The 5–14 days *before* the
publication deadline are a high-risk window: institutions often reduce positions
to avoid earnings surprise risk, causing abnormal sell pressure ("earnings
rollover effect").

This module:
  1. Computes `EarningsRisk` for a given ticker / trade entry date.
  2. Provides an `earnings_stop_tightener` multiplier for the trailing stop.
  3. Provides `earnings_gate_adjustment` — raises the minimum SMS score
     threshold when a publication is imminent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

import pandas as pd

from ..utils.config import cfg
from ..utils.logging import log


# ── Enums ─────────────────────────────────────────────────────────────────────

class EarningsRolloverRisk(str, Enum):
    SAFE       = "SAFE"        # No upcoming publication within caution window
    CAUTION    = "CAUTION"     # Within caution window (default: 14 days)
    HIGH_RISK  = "HIGH_RISK"   # Within high-risk window (default: 5 days)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class EarningsRisk:
    """Earnings rollover risk for an open position."""
    ticker:              str
    rollover_risk:       EarningsRolloverRisk = EarningsRolloverRisk.SAFE
    days_to_next_event:  int | None           = None   # calendar days to next publication
    next_fiscal_quarter: str                  = ""
    next_pub_date:       date | None          = None
    stop_tightener:      float                = 1.0    # multiply ATR multiplier (< 1 → tighter)
    gate_delta:          float                = 0.0    # additive delta on SMS entry gate


# ── Main computation ──────────────────────────────────────────────────────────

def compute_earnings_risk(
    ticker: str,
    current_date: date | None = None,
    earnings_df: pd.DataFrame | None = None,
) -> EarningsRisk:
    """
    Compute earnings rollover risk for a ticker.

    Parameters
    ----------
    ticker       : VN stock ticker (e.g. 'VNM', 'HPG')
    current_date : reference date (defaults to today)
    earnings_df  : pre-fetched earnings calendar (from fetch_earnings_calendar).
                   If None, one is fetched automatically.

    Returns
    -------
    EarningsRisk with rollover_risk, days_to_next_event, stop_tightener,
    and gate_delta fields populated.
    """
    if current_date is None:
        # [BUG-11 FIX] Using VN timezone (UTC+7) instead of the system clock.
        # A UTC server past 17:00 UTC would return the next calendar day,
        # shifting CAUTION/HIGH_RISK windows incorrectly by one day.
        current_date = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()

    # Thresholds from strategy.yaml (with sensible defaults)
    caution_days   = int(cfg.strategy("earnings", "caution_days_before",   default=14))
    high_risk_days = int(cfg.strategy("earnings", "high_risk_days_before", default=5))

    # [BUG-EARN FIX] Only lazy-fetch when earnings_df was NOT provided at all.
    # Previously, an explicitly-passed empty DataFrame still triggered a live fetch,
    # which returned CAUTION from the real fiscal calendar even when the caller
    # intended "no upcoming events" (e.g., tests or offline contexts).
    if earnings_df is None:
        try:
            from ..data.fetcher import fetch_earnings_calendar
            earnings_df = fetch_earnings_calendar(ticker, lookforward_days=caution_days + 5)
        except Exception as e:
            log.debug(f"Earnings fetch failed for {ticker}: {e}")
            earnings_df = pd.DataFrame()

    if earnings_df is None or earnings_df.empty:
        return EarningsRisk(ticker=ticker)

    # Only consider future publication dates (expected or confirmed)
    future = earnings_df[
        pd.to_datetime(earnings_df["expected_publication_date"]).dt.date >= current_date
    ].copy()

    if future.empty:
        return EarningsRisk(ticker=ticker)

    # Nearest upcoming publication
    future = future.sort_values("expected_publication_date")
    next_row = future.iloc[0]
    next_pub = pd.to_datetime(next_row["expected_publication_date"]).date()
    days_to  = (next_pub - current_date).days
    quarter  = str(next_row.get("fiscal_quarter") or "")

    # Classify risk level
    if days_to <= high_risk_days:
        risk  = EarningsRolloverRisk.HIGH_RISK
        tighten, gate_delta = _earnings_high_risk_params()
    elif days_to <= caution_days:
        risk  = EarningsRolloverRisk.CAUTION
        tighten, gate_delta = _earnings_caution_params()
    else:
        risk  = EarningsRolloverRisk.SAFE
        tighten, gate_delta = 1.0, 0.0

    return EarningsRisk(
        ticker              = ticker,
        rollover_risk       = risk,
        days_to_next_event  = days_to,
        next_fiscal_quarter = quarter,
        next_pub_date       = next_pub,
        stop_tightener      = tighten,
        gate_delta          = gate_delta,
    )


def earnings_stop_tightener(risk: EarningsRisk) -> float:
    """
    Returns ATR multiplier reduction for trailing stop.
    Multiply the normal trailing-stop ATR multiplier by this value.
      SAFE      → 1.00  (no change)
      CAUTION   → 0.80  (20% tighter)
      HIGH_RISK → 0.60  (40% tighter — lock profits aggressively)
    """
    return risk.stop_tightener


def earnings_gate_adjustment(risk: EarningsRisk) -> float:
    """
    Returns additive delta for SMS entry gate threshold.
    Positive values raise the bar (harder to enter near earnings).
      SAFE      →  0.0
      CAUTION   → +5.0  (require 5 more points on SMS score)
      HIGH_RISK → +10.0 (require 10 more points — essentially block new entries)
    """
    return risk.gate_delta


# ── Internal helpers ──────────────────────────────────────────────────────────

def _earnings_caution_params() -> tuple[float, float]:
    tighten    = float(cfg.strategy("earnings", "caution_stop_tightener",    default=0.80))
    gate_delta = float(cfg.strategy("earnings", "caution_gate_delta",        default=5.0))
    return tighten, gate_delta


def _earnings_high_risk_params() -> tuple[float, float]:
    tighten    = float(cfg.strategy("earnings", "high_risk_stop_tightener",  default=0.60))
    gate_delta = float(cfg.strategy("earnings", "high_risk_gate_delta",      default=10.0))
    return tighten, gate_delta

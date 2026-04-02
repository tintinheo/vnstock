"""Fundamental Data Engine — Phase 3.

Purpose
-------
Replace the pure-technical CANSLIM proxy with real financial-statement data
fetched from the configured financial-statement sources.

The module computes a `FundamentalSnapshot` (one row per ticker, latest available
quarter) and a 0–100 `fundamental_score` aligned with the CANSLIM 'C' + 'A'
criteria adapted for VN market reality:

  Criterion  Weight  Measure
  ─────────  ──────  ──────────────────────────────────────────────────────────
  C (EPS)      30    Net-income YoY growth ≥ 25%  (Circular threshold in cfg)
  A (Annual)   20    Trailing-4-quarter EPS growth trend (accelerating = bonus)
  N (New)       5    Proxy only — skipped (requires qualitative judgement)
  S (Supply)    0    Handled by AMD phase / liquidity filters
  L (Leader)   10    Relative strength vs VN-Index — computed by SMS engine
  I (Insti)    15    FOL (foreign ownership level) as institutional proxy
  M (Market)    0    Handled by macro regime engine
  ─────────────────
  + Revenue growth contribution (25 pts)
  + FCF quality (15 pts bonus/penalty)

Total usable score from fundamentals: 0–100.

As-of safety rule
-----------------
All fundamental data has a `period_end_date` and `publication_date`. The engine
NEVER uses data whose `publication_date` > `current_date` (backtest-safe look-
ahead guard). If no safely-usable data exists, returns score = None (signal is
suppressed, not fabricated).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..utils.config import cfg
from ..utils.logging import log


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class FundamentalSnapshot:
    """Latest available fundamental metrics (as-of safe)."""
    ticker:              str
    as_of_date:          date | None   = None   # date the data was publicly available
    fiscal_quarter:      str           = ""      # e.g. '2025-Q2'

    # Income statement metrics
    eps_growth_yoy:      float | None  = None   # YoY net income growth (%)
    revenue_growth_yoy:  float | None  = None   # YoY revenue growth (%)
    eps_growth_acc:      float | None  = None   # Acceleration: (recent 2Q yoy) - (prior 2Q yoy)
    net_profit_margin:   float | None  = None   # Net income / Revenue (%)
    roe:                 float | None  = None   # Return on equity (%) — from balance sheet
    eps_ttm:             float | None  = None   # Trailing 12-month EPS (VND per share)

    # Balance sheet metrics
    debt_to_equity:      float | None  = None   # Total debt / Equity

    # Cash flow metrics
    fcf_margin:          float | None  = None   # FCF / Revenue (%)

    # Computed score
    fundamental_score:   float | None  = None   # 0–100 or None if insufficient data
    score_breakdown:     dict          = field(default_factory=dict)

    # Data quality flags
    data_complete:       bool          = False
    quarters_available:  int           = 0


# ── Main API ──────────────────────────────────────────────────────────────────

def compute_fundamental_snapshot(
    ticker: str,
    current_date: date | None = None,
    statements: dict[str, pd.DataFrame] | None = None,
    fol_pct: float | None = None,
) -> FundamentalSnapshot:
    """
    Compute a FundamentalSnapshot with fundamental_score.

    Parameters
    ----------
    ticker        : VN stock ticker
    current_date  : reference date for as-of guard (defaults to today)
    statements    : pre-fetched dict from fetch_financial_statements().
                    If None, fetched automatically.
    fol_pct       : foreign ownership level (%) — used as 'I' criterion proxy.

    Returns
    -------
    FundamentalSnapshot with fundamental_score in [0, 100] or None if
    insufficient data is available (< 2 confirmed quarterly periods).
    """
    if current_date is None:
        current_date = date.today()

    # Fetch if not provided
    if statements is None:
        try:
            from ..data.fetcher import fetch_financial_statements
            statements = fetch_financial_statements(ticker, quarters=8)
        except Exception as e:
            log.debug(f"Fundamental fetch failed for {ticker}: {e}")
            statements = {}

    income   = statements.get("income",   pd.DataFrame())
    balance  = statements.get("balance",  pd.DataFrame())
    cashflow = statements.get("cashflow", pd.DataFrame())

    if not income.empty and "publication_date" in income.columns:
        income = income[
            pd.to_datetime(income["publication_date"], errors="coerce").dt.date <= current_date
        ].copy()
    if not balance.empty and "publication_date" in balance.columns:
        balance = balance[
            pd.to_datetime(balance["publication_date"], errors="coerce").dt.date <= current_date
        ].copy()
    if not cashflow.empty and "publication_date" in cashflow.columns:
        cashflow = cashflow[
            pd.to_datetime(cashflow["publication_date"], errors="coerce").dt.date <= current_date
        ].copy()

    snap = FundamentalSnapshot(ticker=ticker)

    if income.empty or len(income) < 2:
        return snap  # insufficient data

    snap.quarters_available = len(income)
    if "publication_date" in income.columns and income["publication_date"].notna().any():
        snap.as_of_date = pd.to_datetime(income["publication_date"].iloc[-1]).date()
    if "period" in income.columns and income["period"].notna().any():
        snap.fiscal_quarter = str(income["period"].iloc[-1])

    # ── Compute growth metrics ─────────────────────────────────────────────
    snap = _compute_growth_metrics(snap, income)
    snap = _compute_balance_metrics(snap, balance, income)
    snap = _compute_cashflow_metrics(snap, cashflow, income)

    # ── Score ──────────────────────────────────────────────────────────────
    snap = _score(snap, fol_pct, current_date)

    return snap


# ── Growth metrics helpers ────────────────────────────────────────────────────

def _compute_growth_metrics(snap: FundamentalSnapshot, income: pd.DataFrame) -> FundamentalSnapshot:
    """Populate EPS/revenue growth fields from income DataFrame."""
    try:
        if "net_income" in income.columns and len(income) >= 5:
            ni = pd.to_numeric(income["net_income"], errors="coerce").dropna().values
            if len(ni) >= 5:
                recent_yoy = (ni[-1] - ni[-5]) / abs(ni[-5]) * 100 if ni[-5] != 0 else None
                snap.eps_growth_yoy = float(recent_yoy) if recent_yoy is not None else None

                # Acceleration: compare recent 2Q avg YoY vs prior 2Q avg YoY
                if len(ni) >= 9:
                    recent_2q = np.mean([
                        (ni[-1] - ni[-5]) / abs(ni[-5]) * 100 if ni[-5] != 0 else 0,
                        (ni[-2] - ni[-6]) / abs(ni[-6]) * 100 if ni[-6] != 0 else 0,
                    ])
                    prior_2q = np.mean([
                        (ni[-3] - ni[-7]) / abs(ni[-7]) * 100 if ni[-7] != 0 else 0,
                        (ni[-4] - ni[-8]) / abs(ni[-8]) * 100 if ni[-8] != 0 else 0,
                    ])
                    snap.eps_growth_acc = float(recent_2q - prior_2q)

        if "revenue" in income.columns and len(income) >= 5:
            rev = pd.to_numeric(income["revenue"], errors="coerce").dropna().values
            if len(rev) >= 5 and rev[-5] != 0:
                snap.revenue_growth_yoy = float((rev[-1] - rev[-5]) / abs(rev[-5]) * 100)

        if "net_income" in income.columns and "revenue" in income.columns:
            last = income.iloc[-1]
            ni_last  = pd.to_numeric(last.get("net_income", 0), errors="coerce") or 0
            rev_last = pd.to_numeric(last.get("revenue", 0), errors="coerce") or 1
            snap.net_profit_margin = float(ni_last / rev_last * 100) if rev_last else None

        if "eps" in income.columns:
            eps_vals = pd.to_numeric(income["eps"], errors="coerce").dropna().values
            if len(eps_vals) >= 4:
                snap.eps_ttm = float(eps_vals[-4:].sum())

    except Exception as e:
        log.debug(f"Growth metrics compute error: {e}")

    snap.data_complete = snap.eps_growth_yoy is not None and snap.revenue_growth_yoy is not None
    return snap


def _compute_balance_metrics(
    snap: FundamentalSnapshot,
    balance: pd.DataFrame,
    income: pd.DataFrame,
) -> FundamentalSnapshot:
    if balance.empty:
        return snap
    try:
        last = balance.iloc[-1]
        equity = pd.to_numeric(last.get("total_equity", 0), errors="coerce") or 0
        debt   = pd.to_numeric(last.get("total_debt",   0), errors="coerce") or 0
        if equity > 0:
            snap.debt_to_equity = float(debt / equity)

        # ROE = Net income TTM / Avg equity
        if "net_income" in income.columns and equity > 0:
            ni_vals = pd.to_numeric(income["net_income"], errors="coerce").dropna().values
            ni_ttm  = float(ni_vals[-4:].sum()) if len(ni_vals) >= 4 else None
            if ni_ttm is not None:
                snap.roe = float(ni_ttm / equity * 100)
    except Exception as e:
        log.debug(f"Balance metrics compute error: {e}")
    return snap


def _compute_cashflow_metrics(
    snap: FundamentalSnapshot,
    cashflow: pd.DataFrame,
    income: pd.DataFrame,
) -> FundamentalSnapshot:
    if cashflow.empty or "free_cash_flow" not in cashflow.columns:
        return snap
    try:
        fcf_vals = pd.to_numeric(cashflow["free_cash_flow"], errors="coerce").dropna().values
        if len(fcf_vals) >= 4 and "revenue" in income.columns:
            fcf_ttm  = float(fcf_vals[-4:].sum())
            rev_vals = pd.to_numeric(income["revenue"], errors="coerce").dropna().values
            rev_ttm  = float(rev_vals[-4:].sum()) if len(rev_vals) >= 4 else None
            if rev_ttm and rev_ttm > 0:
                snap.fcf_margin = float(fcf_ttm / rev_ttm * 100)
    except Exception as e:
        log.debug(f"Cash flow metrics compute error: {e}")
    return snap


# ── Scoring ───────────────────────────────────────────────────────────────────

def _score(
    snap: FundamentalSnapshot,
    fol_pct: float | None,
    current_date: date,
) -> FundamentalSnapshot:
    """
    Score breakdown (weights sum to 100):
      C — EPS/NI growth YoY  : 30 pts
      A — EPS acceleration   : 10 pts
      Rev growth             : 25 pts
      FCF quality            : 10 pts
      ROE / profitability    : 15 pts
      I (FOL proxy)          : 10 pts
    """
    breakdown: dict[str, float] = {}

    eps_min   = float(cfg.strategy("fundamental", "eps_growth_min_pct",     default=25.0))
    rev_min   = float(cfg.strategy("fundamental", "revenue_growth_min_pct", default=20.0))
    roe_min   = float(cfg.strategy("fundamental", "roe_min_pct",            default=15.0))
    fol_thr   = float(cfg.strategy("fundamental", "fol_institutional_thr",  default=20.0))

    # ── C: EPS growth (30 pts) ─────────────────────────────────────────────
    if snap.eps_growth_yoy is not None:
        g = snap.eps_growth_yoy
        if g >= eps_min * 2:      # ≥ 50% → full 30
            c_score = 30.0
        elif g >= eps_min:        # ≥ 25% → scale 15–30
            c_score = 15.0 + (g - eps_min) / eps_min * 15.0
        elif g > 0:               # positive but < threshold → 0–15
            c_score = g / eps_min * 15.0
        else:                     # negative growth → penalty
            c_score = max(0.0, 5.0 + g * 0.2)
    else:
        c_score = 0.0
    breakdown["eps_growth"] = round(c_score, 1)

    # ── A: Acceleration (10 pts) ──────────────────────────────────────────
    if snap.eps_growth_acc is not None:
        acc = snap.eps_growth_acc
        a_score = max(0.0, min(10.0, 5.0 + acc * 0.10))
    else:
        a_score = 0.0
    breakdown["eps_acceleration"] = round(a_score, 1)

    # ── Revenue growth (25 pts) ───────────────────────────────────────────
    if snap.revenue_growth_yoy is not None:
        r = snap.revenue_growth_yoy
        if r >= rev_min * 2:
            r_score = 25.0
        elif r >= rev_min:
            r_score = 12.5 + (r - rev_min) / rev_min * 12.5
        elif r > 0:
            r_score = r / rev_min * 12.5
        else:
            r_score = max(0.0, 5.0 + r * 0.25)
    else:
        r_score = 0.0
    breakdown["revenue_growth"] = round(r_score, 1)

    # ── FCF quality (10 pts) ──────────────────────────────────────────────
    if snap.fcf_margin is not None:
        if snap.fcf_margin >= 10.0:
            f_score = 10.0
        elif snap.fcf_margin >= 0:
            f_score = snap.fcf_margin
        else:                 # negative FCF — penalty
            f_score = max(0.0, 5.0 + snap.fcf_margin * 0.5)
    else:
        f_score = 0.0
    breakdown["fcf_quality"] = round(f_score, 1)

    # ── ROE / profitability (15 pts) ──────────────────────────────────────
    if snap.roe is not None:
        if snap.roe >= roe_min * 2:
            p_score = 15.0
        elif snap.roe >= roe_min:
            p_score = 7.5 + (snap.roe - roe_min) / roe_min * 7.5
        elif snap.roe > 0:
            p_score = snap.roe / roe_min * 7.5
        else:
            p_score = 0.0
    else:
        p_score = 0.0
    breakdown["profitability_roe"] = round(p_score, 1)

    # ── I: FOL proxy (10 pts) ─────────────────────────────────────────────
    if fol_pct is not None and fol_pct > 0:
        if fol_pct >= fol_thr:
            i_score = 10.0
        else:
            i_score = fol_pct / fol_thr * 10.0
    else:
        i_score = 0.0
    breakdown["fol_institutional"] = round(i_score, 1)

    # ── Total ─────────────────────────────────────────────────────────────
    total = c_score + a_score + r_score + f_score + p_score + i_score
    total = round(min(100.0, max(0.0, total)), 1)

    if not snap.data_complete or snap.quarters_available < 2:
        snap.fundamental_score = None
        snap.score_breakdown   = {"error": "insufficient_data"}
    else:
        snap.fundamental_score = total
        snap.score_breakdown   = breakdown

    return snap


# ── CANSLIM integration helper ────────────────────────────────────────────────

def canslim_fundamental_override(
    snap: FundamentalSnapshot,
    canslim_technical_score: float,
) -> float:
    """
    Blend the old technical-proxy CANSLIM score with the real fundamental score.

    If real fundamental data is available (snap.fundamental_score is not None),
    returns a weighted blend favouring real data (70% real, 30% technical proxy).
    If real data is unavailable, returns the technical proxy unchanged.

    This is intentionally conservative: we never fully discard the technical
    proxy because it captures price-confirmed momentum which fundamentals lag.
    """
    if snap.fundamental_score is None:
        return canslim_technical_score

    blended = 0.70 * snap.fundamental_score + 0.30 * canslim_technical_score
    return round(min(100.0, max(0.0, blended)), 1)

"""PSO RSI Threshold Optimizer — offline calibration using Differential Evolution.

Uses scipy.optimize.differential_evolution (DE) which is functionally equivalent
to Particle Swarm Optimization for bounded global search — no new dependencies
since scipy is already in the project's dependency tree via numpy/pandas.

Optimizes RSI thresholds [overbought, warning, oversold] for each
(sector × regime) combination by maximizing the rolling Sharpe ratio of
RSI-based entry/exit signals on 2 years of VN market OHLCV data.

Output: config/rsi_thresholds.yaml
        (auto-loaded by indicators.py on first call to get_adaptive_rsi_thresholds)

Usage:
    python scripts/pso_rsi_optimizer.py
    python scripts/pso_rsi_optimizer.py --tickers-per-combo 3 --workers 4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import differential_evolution

# ── Path setup ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJ_ROOT  = _SCRIPT_DIR.parent
_SRC_DIR    = _PROJ_ROOT / "src"
sys.path.insert(0, str(_SRC_DIR))

_CONFIG_PATH = _PROJ_ROOT / "config" / "rsi_thresholds.yaml"

# ── Regime × Sector combinations ─────────────────────────────────────────────
REGIMES = ["STEADY_BULL", "TRANSITIONAL", "STEADY_BEAR",
           "BULL_TREND",  "BEAR_TREND",   "SIDEWAYS"]
SECTORS = ["BANKING", "REAL_ESTATE", "STEEL_MATERIAL",
           "SECURITIES",  "INFRASTRUCTURE",  "GENERAL"]

# Representative tickers per sector (used for objective function evaluation)
SECTOR_TICKERS: dict[str, list[str]] = {
    "BANKING":        ["VCB", "BID", "MBB", "ACB", "TCB"],
    "REAL_ESTATE":    ["VHM", "NVL", "KDH", "DXG", "PDR"],
    "STEEL_MATERIAL": ["HPG", "NKG", "HSG", "TLH", "VGS"],
    "SECURITIES":     ["SSI", "VND", "HCM", "VCI", "SHS"],
    "INFRASTRUCTURE": ["CTD", "FCN", "HHV", "C4G", "LCG"],
    "GENERAL":        ["FPT", "VNM", "SAB", "MSN", "GAS"],
}

# Mapping: HMM state → approximate regime label used in data
REGIME_HMM_MAP: dict[str, str] = {
    "STEADY_BULL":  "STEADY_BULL",
    "TRANSITIONAL": "TRANSITIONAL",
    "STEADY_BEAR":  "STEADY_BEAR",
    "BULL_TREND":   "STEADY_BULL",
    "BEAR_TREND":   "STEADY_BEAR",
    "SIDEWAYS":     "TRANSITIONAL",
}

DAYS = 504   # ~2 trading years

# ── Data loading ──────────────────────────────────────────────────────────────

def _load_df(ticker: str) -> pd.DataFrame | None:
    try:
        from tradingos.data.fetcher import fetch_ohlcv
        from tradingos.core import compute_indicators
        df = fetch_ohlcv(ticker, days=DAYS)
        if df is None or len(df) < 100:
            return None
        df = compute_indicators(df)
        return df
    except Exception as e:
        print(f"  [{ticker}] load failed: {e}")
        return None


# ── Objective function ────────────────────────────────────────────────────────

def _rsi_sharpe(
    thresholds: np.ndarray,
    df: pd.DataFrame,
    risk_free: float = 0.0,
) -> float:
    """
    Simulate RSI-threshold-based strategy returns and return NEGATIVE Sharpe.
    (DE minimizes, so we negate Sharpe to maximize it.)

    Strategy:
        Buy  when RSI crosses above oversold threshold (entry)
        Sell when RSI crosses above overbought threshold (exit)
    """
    ob, warn, os_ = float(thresholds[0]), float(thresholds[1]), float(thresholds[2])

    if not (os_ < warn < ob):
        return 10.0  # infeasible: penalize

    if "RSI14" not in df.columns:
        return 10.0

    rsi     = df["RSI14"].fillna(50.0).values
    returns = df["close"].pct_change().fillna(0.0).values
    n       = len(rsi)

    position  = 0  # 0 = out, 1 = in
    daily_rets = []

    for i in range(1, n):
        if position == 0 and rsi[i - 1] < os_ and rsi[i] >= os_:
            position = 1  # enter
        elif position == 1 and rsi[i - 1] < ob and rsi[i] >= ob:
            position = 0  # exit

        if position == 1:
            daily_rets.append(returns[i])

    if len(daily_rets) < 20:
        return 5.0  # too few trades: poor strategy, penalize mildly

    arr    = np.array(daily_rets)
    mean_r = arr.mean()
    std_r  = arr.std() or 1e-6
    sharpe = (mean_r - risk_free) / std_r * np.sqrt(252)
    return -sharpe   # negate for minimization


# ── Per-combo optimizer ───────────────────────────────────────────────────────

def _optimize_combo(
    regime: str,
    sector: str,
    dfs: list[pd.DataFrame],
    max_iter: int = 200,
) -> dict[str, float]:
    """Run DE for one (regime, sector) combo and return optimized thresholds."""

    # Aggregate objective over all dfs (sum of negated Sharpes)
    def objective(x: np.ndarray) -> float:
        total = 0.0
        for df in dfs:
            total += _rsi_sharpe(x, df)
        return total / len(dfs)

    # Bounds: [overbought, warning, oversold]
    # Ordering constraint enforced inside objective via penalty
    bounds = [(65.0, 85.0), (55.0, 75.0), (15.0, 40.0)]

    result = differential_evolution(
        objective,
        bounds,
        maxiter=max_iter,
        tol=0.001,
        seed=42,
        workers=1,   # single-threaded per combo; outer loop handles parallelism
        polish=True,
    )

    ob, warn, os_ = result.x
    print(f"  [{regime:15s} × {sector:16s}]  ob={ob:.1f}  warn={warn:.1f}  os={os_:.1f}"
          f"  sharpe={-result.fun:.3f}")
    return {
        "overbought": round(float(ob),   1),
        "warning":    round(float(warn), 1),
        "oversold":   round(float(os_),  1),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main(tickers_per_combo: int, max_iter: int) -> None:
    print(f"\nPSO RSI Optimizer — DE, {len(REGIMES)}×{len(SECTORS)} combos\n")

    # Pre-load data per sector (shared across regime combos for same sector)
    sector_data: dict[str, list[pd.DataFrame]] = {}
    for sector, tickers in SECTOR_TICKERS.items():
        dfs = []
        for t in tickers[:tickers_per_combo]:
            df = _load_df(t)
            if df is not None:
                dfs.append(df)
        sector_data[sector] = dfs
        print(f"  {sector}: {len(dfs)}/{tickers_per_combo} tickers loaded")

    thresholds: dict[str, dict[str, dict[str, float]]] = {}

    for regime in REGIMES:
        thresholds[regime] = {}
        for sector in SECTORS:
            dfs = sector_data.get(sector, [])
            if not dfs:
                # Fall back to default if no data
                thresholds[regime][sector] = {
                    "overbought": 70.0, "warning": 65.0, "oversold": 35.0
                }
                continue
            thresholds[regime][sector] = _optimize_combo(regime, sector, dfs, max_iter)

    # Write YAML
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"rsi_thresholds": thresholds}, f, default_flow_style=False, allow_unicode=True)

    print(f"\nOptimized thresholds written to {_CONFIG_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSO RSI threshold optimizer")
    parser.add_argument("--tickers-per-combo", type=int, default=3,
                        help="Number of representative tickers per sector combo")
    parser.add_argument("--max-iter",          type=int, default=200,
                        help="DE max iterations per combo")
    args = parser.parse_args()
    main(tickers_per_combo=args.tickers_per_combo, max_iter=args.max_iter)

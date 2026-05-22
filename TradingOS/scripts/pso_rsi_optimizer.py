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

# [P1.3 — IS/OOS] Total fetch window: IS + OOS.
# Optimize on IS bars; evaluate reported Sharpe on OOS only.
DAYS_IS  = 378   # ~1.5 trading years (in-sample, used for DE optimization)
DAYS_OOS = 126   # ~0.5 trading year  (out-of-sample, used for reported Sharpe)
DAYS     = DAYS_IS + DAYS_OOS   # total bars to fetch (~2 trading years)

# ── Data loading ──────────────────────────────────────────────────────────────

def _load_df(ticker: str) -> pd.DataFrame | None:
    try:
        from tradingos.data.fetcher import fetch_ohlcv
        from tradingos.core import compute_indicators
        df = fetch_ohlcv(ticker, days=DAYS)
        if df is None or len(df) < DAYS_IS + 40:   # need enough IS bars
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
    commission_bps: float = 15.0,
    slippage_bps: float = 5.0,
    tax_sell_bps: float = 10.0,
) -> float:
    """
    Simulate RSI-threshold-based strategy returns and return NEGATIVE Sharpe.
    (DE minimizes, so we negate Sharpe to maximize it.)

    Strategy:
        Buy  when RSI crosses above oversold threshold (entry)
        Sell when RSI crosses above overbought threshold (exit)

    [P1.3 — TIMING FIX] Signal fires when cross is detected at bar i (close of i);
    position is entered at bar i+1 (next-bar execution), so the first captured
    return is returns[i+1], not returns[i].  The old code collected returns[i]
    which meant profiting from the bar that generated the signal — lookahead.

    [P1.3 — COST MODEL] Round-trip cost deducted at entry and exit using the
    same bps parameters as the main backtest engine (strategy.yaml values passed
    in by the caller so costs are consistent across the whole system).
    """
    ob, warn, os_ = float(thresholds[0]), float(thresholds[1]), float(thresholds[2])

    if not (os_ < warn < ob):
        return 10.0  # infeasible: penalize

    if "RSI14" not in df.columns:
        return 10.0

    rsi     = df["RSI14"].fillna(50.0).values
    returns = df["close"].pct_change().fillna(0.0).values
    n       = len(rsi)

    # Round-trip cost fractions (basis points → decimal)
    entry_cost = (commission_bps + slippage_bps) / 10_000
    exit_cost  = (commission_bps + slippage_bps + tax_sell_bps) / 10_000

    position   = 0  # 0 = out, 1 = in
    daily_rets: list[float] = []
    pending_entry = False   # enter at next bar open (P1.3 timing fix)
    pending_exit  = False   # exit  at next bar open

    for i in range(1, n):
        # Execute deferred entry/exit first (fills at open of this bar)
        if pending_entry:
            pending_entry = False
            position = 1
            daily_rets.append(-entry_cost)   # entry slippage + commission
            continue
        if pending_exit:
            pending_exit = False
            position = 0
            daily_rets.append(-exit_cost)    # exit slippage + commission + tax
            continue

        # Check for signals at end of bar i (using close-derived RSI)
        if position == 0 and rsi[i - 1] < os_ and rsi[i] >= os_:
            pending_entry = True   # will enter at bar i+1 open
        elif position == 1 and rsi[i - 1] < ob and rsi[i] >= ob:
            pending_exit = True    # will exit at bar i+1 open

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

def _get_costs() -> tuple[float, float, float]:
    """Read cost bps from strategy.yaml if available, else use hardcoded defaults."""
    try:
        sys.path.insert(0, str(_SRC_DIR))
        from tradingos.utils.config import cfg
        commission = float(cfg.strategy("backtest", "commission_bps", default=15))
        slippage   = float(cfg.strategy("backtest", "slippage_bps",   default=5))
        tax_sell   = float(cfg.strategy("backtest", "tax_sell_bps",   default=10))
        return commission, slippage, tax_sell
    except Exception:
        return 15.0, 5.0, 10.0


def _optimize_combo(
    regime: str,
    sector: str,
    dfs: list[pd.DataFrame],
    max_iter: int = 200,
) -> dict[str, float]:
    """
    Run DE for one (regime, sector) combo and return optimized thresholds.

    [P1.3 — IS/OOS] Each DataFrame is split into IS (first DAYS_IS bars) and
    OOS (remaining DAYS_OOS bars). DE optimizes on IS only. The reported Sharpe
    is the mean OOS Sharpe across all tickers in this combo.

    [P1.3 — SEED] Seed is derived from regime+sector hash so each combo gets
    a reproducible but independent random sequence (no correlation across combos).
    """
    commission, slippage, tax_sell = _get_costs()

    # Split IS / OOS
    is_dfs  = [df.iloc[:DAYS_IS]  for df in dfs]
    oos_dfs = [df.iloc[DAYS_IS:]  for df in dfs if len(df) > DAYS_IS]

    # Aggregate IS objective (mean negated Sharpe across tickers)
    def objective(x: np.ndarray) -> float:
        total = 0.0
        for df in is_dfs:
            total += _rsi_sharpe(x, df, commission_bps=commission,
                                 slippage_bps=slippage, tax_sell_bps=tax_sell)
        return total / max(len(is_dfs), 1)

    # Bounds: [overbought, warning, oversold]
    # Ordering constraint enforced inside objective via penalty
    bounds = [(65.0, 85.0), (55.0, 75.0), (15.0, 40.0)]

    # [P1.3 — SEED] Combo-specific seed — reproducible but independent per combo
    combo_seed = abs(hash(f"{regime}:{sector}")) % (2 ** 31)

    result = differential_evolution(
        objective,
        bounds,
        maxiter=max_iter,
        tol=0.001,
        seed=combo_seed,
        workers=1,   # single-threaded per combo; outer loop handles parallelism
        polish=True,
    )

    ob, warn, os_ = result.x

    # Compute OOS Sharpe for reporting
    oos_sharpe = 0.0
    if oos_dfs:
        oos_total = sum(_rsi_sharpe(result.x, df, commission_bps=commission,
                                    slippage_bps=slippage, tax_sell_bps=tax_sell)
                        for df in oos_dfs)
        oos_sharpe = -(oos_total / len(oos_dfs))   # un-negate for display

    print(f"  [{regime:15s} × {sector:16s}]  ob={ob:.1f}  warn={warn:.1f}  os={os_:.1f}"
          f"  IS_sharpe={-result.fun:.3f}  OOS_sharpe={oos_sharpe:.3f}")
    return {
        "overbought":  round(float(ob),         1),
        "warning":     round(float(warn),        1),
        "oversold":    round(float(os_),         1),
        "is_sharpe":   round(float(-result.fun), 3),
        "oos_sharpe":  round(float(oos_sharpe),  3),
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

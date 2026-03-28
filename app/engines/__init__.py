"""
engines/ — barrel re-exports for all VN-Swing Alpha analysis engines.

This package exposes every public symbol from the engine modules at root level,
so callers can optionally import via:

    from engines import analyse_ticker, T25ExitManager, train_lstm_model

instead of knowing which specific module owns each symbol.

Engine files remain at the app root to preserve all existing import paths.
This package is purely additive — no existing code needs to change.
"""
from __future__ import annotations

import sys
import os

# Ensure app root is on sys.path so engine modules are always findable
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

# ─── Core analysis engine ─────────────────────────────────────────────────────
from Quant_Profiler import (
    analyse_ticker,
    fetch_ohlcv,
    async_fetch_many,
    fetch_ssi_realtime,
    calculate_indicators,
    compute_rolling_beta_20d,
    compute_market_breadth,
    compute_t25_score,
    detect_vwap_divergence,
    detect_rsi_divergence,
    detect_candlestick_patterns,
    calculate_csad,
    save_profiler_audit,
    HISTORY_DAYS,
)

# ─── Portfolio & T+2.5 engine ─────────────────────────────────────────────────
from portfolio_engine import (
    T25ExitManager,
    calculate_fractional_kelly,
    generate_t_plus_recommendation,
    compute_t_plus_multiframe,
    compute_ssi_score,
    parse_portfolio_csv,
    calculate_performance,
    build_portfolio_summary,
    is_vn_trading_day,
    calculate_t2_settlement,
    classify_settlement_status,
)

# ─── Multi-horizon forecast engine ───────────────────────────────────────────
from forecast_engine import (
    multi_horizon_forecast,
    monte_carlo_projection,
    promethee_ii_ranking,
    train_lstm_model,
    prepare_lstm_features,
)

# ─── Microstructure / intraday ────────────────────────────────────────────────
from microstructure import (
    compute_vwap_intraday,
    compute_realized_volatility,
)

# ─── Screening / CANSLIM ─────────────────────────────────────────────────────
from screening import (
    filter_canslim,
    get_pivot_breakout,
    compute_manipulation_score,
    detect_pump_dump_advanced,
    detect_false_breakout,
)

# ─── Smart money / Wyckoff ────────────────────────────────────────────────────
from smart_money_engine import (
    forecast_weekly_direction,
    detect_vsa_patterns,
)

# ─── Trend warning ───────────────────────────────────────────────────────────
from trend_warning_engine import (
    compute_trend_warning,
)

# ─── Candle ensemble forecast ────────────────────────────────────────────────
from candle_forecast_engine import (
    run_candle_forecast,
)

# ─── NL explainer ────────────────────────────────────────────────────────────
from nl_explainer import (
    generate_nl_explanation,
)

__all__ = [
    # Core
    "analyse_ticker", "fetch_ohlcv", "async_fetch_many", "fetch_ssi_realtime",
    "calculate_indicators", "compute_rolling_beta_20d", "compute_market_breadth",
    "compute_t25_score", "detect_vwap_divergence", "detect_rsi_divergence",
    "detect_candlestick_patterns", "calculate_csad", "save_profiler_audit",
    "HISTORY_DAYS",
    # Portfolio
    "T25ExitManager", "calculate_fractional_kelly", "generate_t_plus_recommendation",
    "compute_t_plus_multiframe", "compute_ssi_score", "parse_portfolio_csv",
    "calculate_performance", "build_portfolio_summary", "is_vn_trading_day",
    "calculate_t2_settlement", "classify_settlement_status",
    # Forecast
    "multi_horizon_forecast", "monte_carlo_projection", "promethee_ii_ranking",
    "train_lstm_model", "prepare_lstm_features",
    # Microstructure
    "compute_vwap_intraday", "compute_realized_volatility",
    # Screening
    "filter_canslim", "get_pivot_breakout", "compute_manipulation_score",
    "detect_pump_dump_advanced", "detect_false_breakout",
    # Smart money
    "forecast_weekly_direction", "detect_vsa_patterns",
    # Trend
    "compute_trend_warning",
    # Candle
    "run_candle_forecast",
    # NL
    "generate_nl_explanation",
]

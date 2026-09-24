"""TradingOS core engines."""
from .indicators import compute_all as compute_indicators
from .anti_manip import run_amf, detect_amd_phase, volume_quality_score
from .money_flow import (
    compute_smart_money_score,
    detect_stealth_accumulation,
    detect_sector_rotation,
    mode_w_entry_params,
    detect_whale_distribution,
)
from .patterns import detect_all as detect_patterns
from .gmo import detect_hmm_state, compute_omega, compute_vn30f_basis
from .mfpm import compute_mfpm
from .sizing import compute_position_size, progressive_entry_plan, compute_atr_position_size
from .gap_vwap import (
    detect_gaps,
    compute_vwap_result,
    compute_vwap_intraday_result,
    compute_monthly_pivots,
    compute_fibonacci_levels,
)
from .t25_engine import t25_exit_check, compute_t25_entry_score, compute_t25_multiframe
from .exit_engine import progressive_exit_plan, compute_trailing_stop
from .nlp import generate_signal_text, generate_exit_advisory_text, generate_indicator_explanation, generate_summary_headline, generate_f0_explanation
from .backtest import run_backtest, compare_modes
from .universe import build_universe, compute_universe_rs
from .execution_advisory import advise_entry_window, advise_exit_window
from .macro import compute_macro_regime, macro_sizing_multiplier, macro_score_gate_adjustment
from .earnings import compute_earnings_risk, earnings_stop_tightener, earnings_gate_adjustment
from .fundamental import compute_fundamental_snapshot, canslim_fundamental_override
from .trend_warning import compute_trend_warning
from .horizon_forecast import compute_multi_horizon_forecast
from .t_plus_engine import compute_tplus_recommendation
from .intraday_cvd import compute_intraday_cvd
from .orderbook import compute_order_book_imbalance
from .risk_model import compute_var, calibrate_stop_with_var

__all__ = [
    "compute_indicators",
    "run_amf", "detect_amd_phase", "volume_quality_score",
    "compute_smart_money_score", "detect_stealth_accumulation",
    "detect_sector_rotation", "mode_w_entry_params", "detect_whale_distribution",
    "detect_patterns",
    "detect_hmm_state", "compute_omega", "compute_vn30f_basis",
    "compute_mfpm",
    "compute_position_size", "progressive_entry_plan", "compute_atr_position_size",
    "detect_gaps", "compute_vwap_result", "compute_vwap_intraday_result",
    "compute_monthly_pivots", "compute_fibonacci_levels",
    "t25_exit_check", "compute_t25_entry_score", "compute_t25_multiframe",
    "progressive_exit_plan", "compute_trailing_stop",
    "generate_signal_text", "generate_exit_advisory_text",
    "generate_indicator_explanation", "generate_summary_headline",
    "generate_f0_explanation",
    "run_backtest", "compare_modes",
    "build_universe", "compute_universe_rs",
    "advise_entry_window", "advise_exit_window",
    "compute_macro_regime", "macro_sizing_multiplier", "macro_score_gate_adjustment",
    "compute_earnings_risk", "earnings_stop_tightener", "earnings_gate_adjustment",
    "compute_fundamental_snapshot", "canslim_fundamental_override",
    "compute_trend_warning",
    "compute_multi_horizon_forecast",
    "compute_tplus_recommendation",
    "compute_intraday_cvd",
    "compute_order_book_imbalance",
    "compute_var", "calibrate_stop_with_var",
]

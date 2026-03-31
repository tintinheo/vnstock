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
from .sizing import compute_position_size, progressive_entry_plan
from .t25_engine import t25_exit_check
from .exit_engine import progressive_exit_plan, compute_trailing_stop
from .nlp import generate_signal_text, generate_exit_advisory_text
from .backtest import run_backtest, compare_modes
from .universe import build_universe, compute_universe_rs
from .execution_advisory import advise_entry_window, advise_exit_window

__all__ = [
    "compute_indicators",
    "run_amf", "detect_amd_phase", "volume_quality_score",
    "compute_smart_money_score", "detect_stealth_accumulation",
    "detect_sector_rotation", "mode_w_entry_params", "detect_whale_distribution",
    "detect_patterns",
    "detect_hmm_state", "compute_omega", "compute_vn30f_basis",
    "compute_mfpm",
    "compute_position_size", "progressive_entry_plan",
    "t25_exit_check",
    "progressive_exit_plan", "compute_trailing_stop",
    "generate_signal_text", "generate_exit_advisory_text",
    "run_backtest", "compare_modes",
    "build_universe", "compute_universe_rs",
    "advise_entry_window", "advise_exit_window",
]

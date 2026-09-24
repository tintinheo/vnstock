"""
data_layer/ — DuckDB persistence layer for VN-Swing Alpha apps.

Re-exports everything from db_cache at root so callers can use either:
    from db_cache import get_ohlcv, put_ohlcv          # existing style
    from data_layer import get_ohlcv, put_ohlcv        # new package style
"""
from __future__ import annotations
import sys, os

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from db_cache import (
    get_ohlcv,
    put_ohlcv,
    get_scan_result,
    put_scan_result,
    get_all_scan_results,
    append_signal_history,
    get_signal_history,
    db_stats,
    vacuum,
    OHLCV_TODAY_TTL,
    OHLCV_HISTORY_TTL,
    SCAN_RESULT_TTL,
    SIGNAL_HISTORY_MAX_ROWS,
)

__all__ = [
    "get_ohlcv", "put_ohlcv",
    "get_scan_result", "put_scan_result", "get_all_scan_results",
    "append_signal_history", "get_signal_history",
    "db_stats", "vacuum",
    "OHLCV_TODAY_TTL", "OHLCV_HISTORY_TTL", "SCAN_RESULT_TTL", "SIGNAL_HISTORY_MAX_ROWS",
]

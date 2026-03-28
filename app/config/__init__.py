"""
config/ — VN-Swing Alpha configuration constants.

Re-exports everything from qp_config at root so callers can use either:
    from qp_config import CANSLIM_EPS_GROWTH_MIN      # existing style (no change needed)
    from config import CANSLIM_EPS_GROWTH_MIN          # new package style
"""
from __future__ import annotations
import sys, os

_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from qp_config import (
    CANSLIM_EPS_GROWTH_MIN,
    CANSLIM_ROE_MIN,
    CANSLIM_PIVOT_BARS,
    CANSLIM_VOL_CONFIRM_X,
    MANIP_VOL_ZSCORE_THRESH,
    MANIP_REVERSAL_BARS,
    VWAP_DIV_SWING_WINDOW,
    VWAP_INTRADAY_RESOLUTION,
    T25_WINDOW_START,
    T25_WINDOW_END,
    SSI_DEVICE_ID,
    VN30_TICKERS,
)

__all__ = [
    "CANSLIM_EPS_GROWTH_MIN", "CANSLIM_ROE_MIN", "CANSLIM_PIVOT_BARS",
    "CANSLIM_VOL_CONFIRM_X", "MANIP_VOL_ZSCORE_THRESH", "MANIP_REVERSAL_BARS",
    "VWAP_DIV_SWING_WINDOW", "VWAP_INTRADAY_RESOLUTION",
    "T25_WINDOW_START", "T25_WINDOW_END",
    "SSI_DEVICE_ID", "VN30_TICKERS",
]

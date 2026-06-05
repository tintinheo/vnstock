import pandas as pd
import numpy as np
from enum import Enum
from datetime import date

class ExitSignal(Enum):
    HOLD = "HOLD"
    T25_FORCED_EXIT = "T25_FORCED_EXIT"
    ATC_EXIT_T2 = "ATC_EXIT_T2"
    RSI_CLIMAX_EXIT = "RSI_CLIMAX_EXIT"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    SL_HIT = "SL_HIT"
    TRAILING_STOP_HIT = "TRAILING_STOP_HIT"

def is_t2_of_position(entry_date: date, current_date: date, holidays: list = []) -> bool:
    """
    Calculates if the current date is exactly T+2 from the entry date.
    Uses numpy busday_count to skip weekends. In production, provide the VN holidays list.
    """
    if entry_date > current_date:
        return False
    # Count business days between entry and current
    trading_days_passed = np.busday_count(entry_date, current_date, holidays=holidays)
    return trading_days_passed == 2

def is_t25_window(current_time: str) -> bool:
    """Checks if current time is within the T+2.5 danger window (12:45 - 13:15)."""
    return "12:45:00" <= current_time <= "13:15:00"

def t25_exit_check(
    position_entry_date: date, 
    current_date: date, 
    current_time: str, 
    current_bar: pd.Series, 
    rsi_series: pd.Series, 
    mav20: float, 
    holidays: list = []
) -> ExitSignal:
    """
    Evaluates market conditions against T+2.5 settlement pressure.
    """
    is_t2 = is_t2_of_position(position_entry_date, current_date, holidays)

    rsi_now = current_bar.get('RSI14', 50)
    rsi_3ago = rsi_series.iloc[-4] if len(rsi_series) >= 4 else rsi_now
    rsi_prev = rsi_series.iloc[-2] if len(rsi_series) >= 2 else rsi_now

    # 1. Danger window check (12:45–13:15 on T+2)
    if is_t2 and is_t25_window(current_time):
        rsi_declining = rsi_now < rsi_3ago
        volume_spike = current_bar.get('Volume', 0) > mav20 * 2.0
        below_vwap = current_bar.get('Close', 0) < current_bar.get('VWAP', float('inf'))
        
        if rsi_declining and volume_spike and below_vwap:
            return ExitSignal.T25_FORCED_EXIT

    # 2. Afternoon T+2 exit (14:00–14:45 on T+2)
    if is_t2 and current_time >= "14:00:00":
        if rsi_now > 70 and rsi_now < rsi_prev:
            return ExitSignal.ATC_EXIT_T2

    # 3. RSI Climax exit (any day)
    if rsi_now > 80 and rsi_now < rsi_prev:
        return ExitSignal.RSI_CLIMAX_EXIT

    return ExitSignal.HOLD
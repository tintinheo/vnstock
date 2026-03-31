# File: scripts/test_t25.py

import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Dynamically add the 'src' directory to the Python path so imports work perfectly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from tradingos.core.t25_engine import t25_exit_check, ExitSignal

def run_t25_test():
    tickers = ["HPG", "SSI", "VND"]
    
    # Simulate today and a T+2 entry date (assuming no weekends for this simple test)
    today = date.today()
    entry_date = today - timedelta(days=2) 
    
    print("="*60)
    print(f"🚀 TRADINGOS ALPHA: T+2.5 ENGINE TEST ({today})")
    print("="*60)

    for ticker in tickers:
        # ---------------------------------------------------------
        # SCENARIO 1: HPG - Caught in the 13:00 Danger Window 
        # (Price below VWAP, Volume Spike, RSI dropping)
        # ---------------------------------------------------------
        if ticker == "HPG":
            current_time = "13:05:00"  # Inside the 12:45-13:15 window
            current_bar = pd.Series({"Close": 28000, "VWAP": 28500, "Volume": 2500000, "RSI14": 45})
            rsi_series = pd.Series([60, 55, 50, 48, 45]) # Declining RSI
            mav20 = 500000 # Massive volume spike (5x average)

        # ---------------------------------------------------------
        # SCENARIO 2: SSI - RSI Climax Exit (Overbought & Reversing)
        # ---------------------------------------------------------
        elif ticker == "SSI":
            current_time = "10:30:00"  # Morning session
            current_bar = pd.Series({"Close": 35000, "VWAP": 34500, "Volume": 1000000, "RSI14": 82})
            rsi_series = pd.Series([70, 75, 80, 88, 82]) # RSI crossed > 80, but now dropping (88 -> 82)
            mav20 = 800000

        # ---------------------------------------------------------
        # SCENARIO 3: VND - Healthy Uptrend (Hold)
        # ---------------------------------------------------------
        elif ticker == "VND":
            current_time = "14:15:00"  # Afternoon session
            current_bar = pd.Series({"Close": 22000, "VWAP": 21800, "Volume": 1200000, "RSI14": 65})
            rsi_series = pd.Series([50, 55, 60, 62, 65]) # Steadily rising
            mav20 = 1000000

        # Run the engine
        result = t25_exit_check(
            position_entry_date=entry_date,
            current_date=today,
            current_time=current_time,
            current_bar=current_bar,
            rsi_series=rsi_series,
            mav20=mav20
        )

        # Print the result
        print(f"[{ticker}] Time: {current_time:<8} | RSI: {current_bar['RSI14']:<4} | Action: {result.name}")

    print("="*60)

if __name__ == "__main__":
    run_t25_test()
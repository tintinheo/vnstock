import pandas as pd
import numpy as np

def find_swing_highs_and_lows(df: pd.DataFrame, lookback: int = 50) -> list:
    """Helper to find local pivots for VCP detection."""
    swings = []
    # Simplified pivot detection for structural layout
    for i in range(2, len(df)-2):
        if df['High'].iloc[i] == max(df['High'].iloc[i-2:i+3]):
            swings.append({'type': 'high', 'idx': i, 'val': df['High'].iloc[i]})
        elif df['Low'].iloc[i] == min(df['Low'].iloc[i-2:i+3]):
            swings.append({'type': 'low', 'idx': i, 'val': df['Low'].iloc[i]})
    return swings[-lookback:]

def detect_vcp(df: pd.DataFrame, min_contractions: int = 2, lookback: int = 50) -> bool:
    """Detects Volatility Contraction Pattern (VCP) with adaptive ATR thresholds."""
    if len(df) < lookback:
        return False
        
    c = df.iloc[-1]
    atr_ratio = c.get('ATR14', (df['High'] - df['Low']).tail(14).mean()) / c['Close']
    
    # Adaptive threshold: high volatility VN midcaps get relaxed thresholds
    price_thr = 0.70 if atr_ratio <= 0.02 else 0.80
    vol_thr = 0.75 if atr_ratio <= 0.02 else 0.85
    
    # Mocking contraction counting for structural completeness
    # In production, iterate through 'swings' to compare range_i / range_im1
    contractions = 0
    recent_vols = df['Volume'].tail(lookback).values
    recent_ranges = (df['High'] - df['Low']).tail(lookback).values
    
    # Simulate finding sequential drops in volume and price range
    for i in range(1, len(recent_ranges)):
        if recent_ranges[i] < recent_ranges[i-1] * price_thr and recent_vols[i] < recent_vols[i-1] * vol_thr:
            contractions += 1
            
    return contractions >= min_contractions

def detect_spring(df: pd.DataFrame, lookback: int = 20) -> bool:
    """Detects standard Wyckoff Spring."""
    if len(df) < lookback + 1:
        return False
        
    historical_low = df['Low'].iloc[-lookback:-1].min()
    avg_vol = df['Volume'].iloc[-lookback:].mean()
    c = df.iloc[-1]

    is_spring = (
        c['Low'] < historical_low and   
        c['Close'] > historical_low and 
        c['Volume'] < avg_vol * 0.85 and 
        c['Close'] > c['Open']             
    )
    return is_spring

def detect_cup_with_handle(df: pd.DataFrame, cup_min_bars: int = 30, cup_max_bars: int = 120) -> dict:
    """Detects O'Neil Cup with Handle pattern."""
    close = df['Close']
    n = len(close)
    if n < cup_min_bars + 10:
        return {"detected": False}

    window = close.iloc[-cup_max_bars:]
    left_rim = window.iloc[0]
    cup_bottom = window.min()
    right_rim = window.iloc[-15] # 15 bars before current = handle start

    depth = (left_rim - cup_bottom) / left_rim
    rim_symmetry = abs(right_rim - left_rim) / left_rim

    valid_cup = (0.12 <= depth <= 0.35) and (rim_symmetry <= 0.05)
    
    if not valid_cup:
        return {"detected": False}

    handle_window = close.iloc[-15:]
    handle_low = handle_window.min()
    handle_depth = (right_rim - handle_low) / right_rim
    handle_vol_shrink = df['Volume'].iloc[-15:].mean() < df['Volume'].iloc[-30:-15].mean() * 0.80

    valid_handle = handle_depth <= 0.15 and handle_vol_shrink
    pivot = float(right_rim)

    return {
        "detected": valid_cup and valid_handle,
        "cup_depth": round(depth, 3),
        "handle_depth": round(handle_depth, 3),
        "pivot": pivot,
        "pattern": "CUP_WITH_HANDLE",
    }
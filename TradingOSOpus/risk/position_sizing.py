"""risk/position_sizing.py – ATR-based and Kelly Criterion position sizing."""
import numpy as np

def atr_position_size(capital, atr_value, risk_per_trade=0.02, atr_multiplier=2.0):
    if atr_value <= 0: return {"shares":0,"position_value":0,"risk_amount":0,"stop_distance":0}
    risk_amount = capital * risk_per_trade; stop_distance = atr_value * atr_multiplier
    shares = int(risk_amount / stop_distance)
    return {"shares":shares,"position_value":shares*atr_value*10,"risk_amount":risk_amount,"stop_distance":stop_distance}

def kelly_criterion(win_rate, avg_win, avg_loss):
    if avg_loss == 0 or win_rate <= 0 or win_rate >= 1: return 0.0
    b = abs(avg_win / avg_loss); kelly = (win_rate * b - (1-win_rate)) / b
    return max(min(kelly/2, 0.25), 0.0)

def fixed_fraction_size(capital, price, fraction=0.10, max_pct=0.20):
    val = capital * min(fraction, max_pct)
    return int(val / price) if price > 0 else 0

"""risk/stop_loss.py – Stop-loss management: fixed, trailing, ATR-based, time-based."""
class StopLossManager:
    def __init__(self, method="atr", atr_multiplier=2.0, fixed_pct=0.05, trailing_pct=0.03, max_hold_days=30):
        self.method=method; self.atr_multiplier=atr_multiplier; self.fixed_pct=fixed_pct
        self.trailing_pct=trailing_pct; self.max_hold_days=max_hold_days

    def calculate_stop_loss(self, entry_price, current_price, atr_value=0, highest_since_entry=0, days_held=0):
        stop_level, reason = 0, ""
        if self.method == "fixed":
            stop_level = entry_price * (1 - self.fixed_pct); reason = f"Fixed {self.fixed_pct:.0%}"
        elif self.method == "atr" and atr_value > 0:
            stop_level = entry_price - self.atr_multiplier * atr_value; reason = f"ATR x{self.atr_multiplier}"
        elif self.method == "trailing":
            if highest_since_entry <= 0: highest_since_entry = max(entry_price, current_price)
            stop_level = highest_since_entry * (1 - self.trailing_pct); reason = f"Trailing {self.trailing_pct:.0%}"
        elif self.method == "time":
            stop_level = entry_price * (1 - self.fixed_pct)
            if days_held >= self.max_hold_days:
                return {"stop_level":stop_level,"is_stopped":True,"method":"time","reason":f"Time stop {days_held}d"}
        return {"stop_level":round(stop_level,2),"is_stopped":current_price<=stop_level,"method":self.method,"reason":reason}

    def calculate_take_profit(self, entry_price, atr_value=0, risk_reward=2.5):
        if self.method == "atr" and atr_value > 0:
            return entry_price + self.atr_multiplier * atr_value * risk_reward
        return entry_price * (1 + self.fixed_pct * risk_reward)

def update_trailing_stop(entry_price: float, current_sl: float, peak_price_since_entry: float) -> float:
    """
    Calculates the dynamic trailing stop.
    Rules:
    1. Activate only after position reaches +7% gain.
    2. new_sl = max(current_sl, peak_price * 0.95)
    3. Never set sl below break-even once +7% achieved.
    4. Floor: entry * 0.965 (max -3.5% floor for low-ATR stocks).
    """
    floor_sl = entry_price * 0.965
    
    # Check if +7% threshold has been breached at least once
    if peak_price_since_entry >= entry_price * 1.07:
        new_sl = max(current_sl, peak_price_since_entry * 0.95, entry_price)
        return max(new_sl, floor_sl)
        
    return max(current_sl, floor_sl)

def calculate_progressive_exit(total_qty_original: int, current_qty: int, current_price: float, tp1: float, tp2: float, current_sl: float) -> dict:
    """
    Handles the 40% -> 40% -> 20% (Trailing) scale-out mechanism.
    """
    # Force 100-lot rounding on VN markets
    tp1_qty = int(total_qty_original * 0.40)
    tp1_qty = (tp1_qty // 100) * 100

    tp2_qty = int(total_qty_original * 0.40)
    tp2_qty = (tp2_qty // 100) * 100
    
    trailing_qty = total_qty_original - tp1_qty - tp2_qty

    # Check Stop Loss first
    if current_price <= current_sl:
        return {"action": "SELL", "qty": current_qty, "reason": "SL_HIT"}

    # Check TP2 (If we are holding more than the final 20% trailing tranche)
    if current_price >= tp2 and current_qty > trailing_qty:
        # Calculate exactly how much to sell to leave only the trailing_qty
        sell_qty = current_qty - trailing_qty
        sell_qty = (sell_qty // 100) * 100
        if sell_qty > 0:
            return {"action": "SELL", "qty": sell_qty, "reason": "TP2_HIT"}

    # Check TP1 (If we are still holding the full original amount)
    if current_price >= tp1 and current_qty == total_qty_original:
        if tp1_qty > 0:
            return {"action": "SELL", "qty": tp1_qty, "reason": "TP1_HIT"}

    return {"action": "HOLD", "qty": 0, "reason": "HOLD"}

def margin_call_protection(positions: list, margin_ratio: float, safety_threshold: float = 1.50) -> dict:
    """
    If broker margin drops below safety threshold, identify the position with the highest 
    unrealized loss for a partial emergency liquidation.
    """
    if margin_ratio >= safety_threshold:
        return {"action": "SAFE"}
        
    if not positions:
        return {"action": "SAFE"}

    # Sort positions by unrealized PnL ascending (worst losers first)
    worst_position = sorted(positions, key=lambda x: x.get('unrealized_pnl_pct', 0))[0]
    
    return {
        "action": "LIQUIDATE_PARTIAL",
        "ticker": worst_position['ticker'],
        "reason": f"MARGIN_RATIO_CRITICAL_{margin_ratio}"
    }
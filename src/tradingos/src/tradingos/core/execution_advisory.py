def calculate_ecp(order_book: dict) -> float:
    """
    Calculates the Expected Closing Price (ECP) from the ATC order book.
    In a real scenario, this involves finding the price that maximizes matched volume.
    For this implementation, we extract the pre-calculated ECP if provided by the SSI EP-4 payload.
    """
    # Assuming 'ecp' or 'matchedPrice' is returned by the broker API during ATC
    return float(order_book.get('ecp', order_book.get('matchedPrice', 0.0)))

def smart_atc_router(position: dict, order_book: dict, current_time: str, last_continuous_price: float, breakout_signal: bool = False) -> dict:
    """
    Decides the optimal ATC execution strategy and guards against end-of-day manipulation.
    """
    ecp = calculate_ecp(order_book)
    if ecp == 0.0:
        ecp = last_continuous_price

    # 1. Anti-Manipulation Gate: ECP deviation > 2.5% vs continuous session
    if last_continuous_price > 0 and abs(ecp - last_continuous_price) / last_continuous_price > 0.025:
        return {"status": "CANCEL_ALL", "reason": "ATC_MANIPULATION_DETECTED"}

    # 2. Aggressive SELL (Take profit / Cut loss)
    # Target 14:43:00 to ensure time priority before the 14:45:00 close
    if position.get('unrealized_pnl_pct', 0) >= position.get('target_pct', 999) and current_time >= "14:43:00":
        return {"status": "SUBMIT_ATC_SELL", "reason": "PROFIT_TARGET_MET"}

    # 3. Aggressive BUY (Catching a breakout in the ATC session)
    atc_bid_vol = sum(level.get('vol', 0) for level in order_book.get('bids', []))
    atc_ask_vol = sum(level.get('vol', 0) for level in order_book.get('asks', []))
    atc_total = max(atc_bid_vol + atc_ask_vol, 1)
    imbalance = (atc_bid_vol - atc_ask_vol) / atc_total

    if breakout_signal and ecp < last_continuous_price and imbalance > 0.30:
        if "14:40:00" <= current_time < "14:44:30":
            return {"status": "SUBMIT_ATC_BUY", "reason": "BREAKOUT_ANTICIPATION"}

    return {"status": "MONITOR", "reason": "NO_ACTION_REQUIRED"}

def validate_mtl_order(side: str, qty: int, avg_vol_5m: float) -> dict:
    """
    KRX MTL (Market-to-Limit) Order Validation.
    Prevents fat fingers and calculates estimated price impact.
    """
    if qty < 100 or qty % 100 != 0:
        return {"valid": False, "reason": "INVALID_LOT_SIZE"}

    # Fat-finger Protection
    if qty > avg_vol_5m * 5:
        return {"valid": False, "reason": f"FAT_FINGER_BLOCKED: Qty {qty} > 5x avg 5m vol"}

    # Estimate price impact (Rough proxy: assuming standard depth)
    price_impact_est = qty / max(avg_vol_5m, 1) * 0.002 
    if price_impact_est > 0.015:
        return {"valid": False, "reason": f"PRICE_IMPACT_HIGH: Est {price_impact_est*100:.2f}%"}

    return {"valid": True, "type": "MTL", "side": side, "qty": qty}
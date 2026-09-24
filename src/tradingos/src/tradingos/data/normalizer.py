import pandas as pd

def round_to_tick(price: float) -> int:
    """
    Rounds a target price to the nearest valid VN tick size (HOSE/HNX).
    < 10,000      : 10 VND
    10,000-49,950 : 50 VND
    >= 50,000     : 100 VND
    """
    if price < 10000:
        tick = 10
    elif price < 50000:
        tick = 50
    else:
        tick = 100
    
    return int(round(price / tick) * tick)

def round_lot(qty: float) -> int:
    """
    Rounds quantity down to the nearest 100-lot multiple (VN market standard).
    """
    if qty < 100:
        return 0
    return int((qty // 100) * 100)

def apply_ex_dividend_adjustment(df: pd.DataFrame, corp_actions: list) -> pd.DataFrame:
    """
    Adjusts historical OHLCV data for stock splits and dividends.
    Requires data from SSI EP-11 (corporate-actions).
    This is a structural placeholder; in production, calculate the adjustment ratio 
    by walking backward from the present.
    """
    df = df.copy()
    df['adjusted_close'] = df['Close'] # Default mapping

    if not corp_actions:
        return df

    # Simulated adjustment logic:
    # 1. Sort corp_actions by ex_date descending.
    # 2. Maintain a cumulative adjustment_factor (starts at 1.0).
    # 3. For each event (cash dividend or stock split), update the factor.
    # 4. Multiply historical prices prior to ex_date by the factor.
    
    adjustment_factor = 1.0
    for action in sorted(corp_actions, key=lambda x: x['ex_date'], reverse=True):
        ex_date = action['ex_date']
        
        if action['type'] == 'CASH_DIVIDEND':
            # Factor = 1 - (Dividend / Price_Before_Ex)
            pass 
        elif action['type'] == 'STOCK_SPLIT':
            # Factor *= (Old_Shares / New_Shares)
            pass

        # Apply to all rows before the ex_date
        # mask = df.index < ex_date
        # df.loc[mask, 'adjusted_close'] *= adjustment_factor
        
    return df
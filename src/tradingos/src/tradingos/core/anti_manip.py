import pandas as pd

def compute_ofi(order_book: dict) -> float:
    """Calculates Order Flow Imbalance from the EP-4 order book snapshot."""
    def _extract_vol(level: dict) -> float:
        for key in ('vol', 'volume', 'totalVol', 'qtty', 'Qtty'):
            if key in level: return float(level[key])
        return 0.0

    def _extract_levels(book: dict, side: str) -> list:
        for key in (side, side + 's', side + 'List'):
            if key in book: return book[key]
        return []

    bids = _extract_levels(order_book, 'bid')[:3]
    asks = _extract_levels(order_book, 'ask')[:3]

    if not bids or not asks: return 0.0

    bid_vol = sum(_extract_vol(b) for b in bids)
    ask_vol = sum(_extract_vol(a) for a in asks)
    total = bid_vol + ask_vol
    return (bid_vol - ask_vol) / total if total > 0 else 0.0

def volume_quality_score(df: pd.DataFrame, order_book: dict) -> dict:
    """Evaluates the structural quality of volume to detect wash trading or distribution."""
    flags = []
    
    ofi = compute_ofi(order_book)
    z_vol = df['Z_vol'].iloc[-1] if 'Z_vol' in df.columns else 0

    if z_vol > 1.5 and abs(ofi) < 0.10:
        flags.append("WASH_TRADING_SUSPECT")
        ofi_score = -0.5
    elif ofi > 0.30: ofi_score = +1.0
    elif ofi < -0.30: ofi_score = -1.0
    else: ofi_score = ofi * 2

    obv_5d_change = (df['OBV'].iloc[-1] - df['OBV'].iloc[-6]) / abs(df['OBV'].iloc[-6] + 1e-9) if len(df) >= 6 else 0
    if obv_5d_change > 0.05: obv_score = +1.0
    elif obv_5d_change < -0.05:
        obv_score = -1.0
        flags.append("OBV_DIVERGENCE")
    else: obv_score = 0.0

    price_up = df['Close'].iloc[-1] > df['Close'].iloc[-2]
    vol_up = df['Volume'].iloc[-1] > df['Volume'].iloc[-2]
    
    if price_up and vol_up: pv_score = +1.0
    elif not price_up and vol_up:
        pv_score = -0.5
        flags.append("DISTRIBUTION_VOLUME")
    else: pv_score = 0.0

    vqs = (ofi_score + obv_score + pv_score) / 3.0
    return {"vqs_score": round(vqs, 3), "flags": flags, "ofi": ofi}

def detect_spring_quality(df: pd.DataFrame, lookback: int = 20) -> tuple[bool, str]:
    """Distinguishes between a real Wyckoff Spring and a retail trap Fake Spring."""
    if len(df) < lookback + 1:
        return False, "INSUFFICIENT_DATA"

    historical_low = df['Low'].iloc[-lookback:-1].min()
    avg_vol = df['Volume'].iloc[-lookback:].mean()
    c = df.iloc[-1]

    basic_spring = c['Low'] < historical_low and c['Close'] > historical_low and c['Close'] > c['Open']
    if not basic_spring:
        return False, "NO_SPRING"

    low_volume_break = c['Volume'] < avg_vol * 0.85
    high_volume_break = c['Volume'] > avg_vol * 1.50
    obv_stable = df['OBV'].iloc[-1] >= df['OBV'].iloc[-3] * 0.97 if len(df) >= 3 else True

    if low_volume_break and obv_stable:
        return True, "SPRING_REAL"
    elif high_volume_break:
        return False, "SPRING_FAKE_SELL"
    elif not obv_stable:
        return False, "SPRING_FAKE_OBV"
    else:
        return True, "SPRING_WEAK"
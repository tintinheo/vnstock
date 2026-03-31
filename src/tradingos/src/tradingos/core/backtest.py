import pandas as pd
from typing import Callable, List, Dict

class VNBacktestConstraints:
    T0_SAME_DAY_SELL = False
    T2_SELL_START = "13:00"
    MIN_LOT_SIZE = 100
    BUY_COMMISSION = 0.0015  # 0.15% SSI
    SELL_COMMISSION = 0.0025 # 0.25% SSI
    MIN_COMMISSION_VND = 1000
    SELL_TAX = 0.001         # 0.1% Tax
    ATC_SLIPPAGE_VN30 = 0.001
    ATC_SLIPPAGE_MIDCAP = 0.003
    LOCK_SAN_PROB = 0.02     # Synthetic stress test probability

def calculate_trade_pnl(entry_price: float, exit_price: float, qty: int, is_vn30: bool = False) -> dict:
    """Calculates net PnL after VN-specific commissions and taxes."""
    buy_value = entry_price * qty
    buy_fee = max(buy_value * VNBacktestConstraints.BUY_COMMISSION, VNBacktestConstraints.MIN_COMMISSION_VND)
    
    # Simulate slippage on exit
    slippage = VNBacktestConstraints.ATC_SLIPPAGE_VN30 if is_vn30 else VNBacktestConstraints.ATC_SLIPPAGE_MIDCAP
    actual_exit = exit_price * (1 - slippage)
    
    sell_value = actual_exit * qty
    sell_fee = max(sell_value * VNBacktestConstraints.SELL_COMMISSION, VNBacktestConstraints.MIN_COMMISSION_VND)
    sell_tax = sell_value * VNBacktestConstraints.SELL_TAX
    
    net_pnl = sell_value - buy_value - buy_fee - sell_fee - sell_tax
    pnl_pct = net_pnl / (buy_value + buy_fee)
    
    return {"net_pnl_vnd": net_pnl, "pnl_pct": pnl_pct, "actual_exit_price": actual_exit}

def walk_forward_backtest(strategy_fn: Callable, full_df: pd.DataFrame, train_years: int = 2, test_months: int = 6) -> List[Dict]:
    """
    Walk-Forward Validation to prevent bull-bias from the 2020-2025 era.
    1. Train on 2 years (In-Sample) -> Calibrate
    2. Test on 6 months (Out-Of-Sample) -> Measure
    3. Shift window forward.
    """
    trading_days_year = 252
    train_size = train_years * trading_days_year
    test_size = test_months * 21 # ~21 sessions per month
    
    results = []
    start = 0
    
    while start + train_size + test_size <= len(full_df):
        train_df = full_df.iloc[start : start + train_size]
        test_df = full_df.iloc[start + train_size : start + train_size + test_size]
        
        # Step 1: Calibrate parameters on training data
        params = {"mfpm_threshold": 50, "sms_threshold": 60} # Mocked calibration output
        
        # Step 2: Run Out-Of-Sample
        oos_result = strategy_fn(test_df, params)
        
        # Step 3: Check Overfitting (Target: OOS win rate >= IS win rate * 0.85)
        is_win_rate = 0.60 # Mocked IS result
        oos_win_rate = oos_result.get("win_rate", 0.0)
        overfit_flag = oos_win_rate < (is_win_rate * 0.85)
        
        results.append({
            "start_idx": start,
            "oos_win_rate": oos_win_rate,
            "overfit_flag": overfit_flag,
            "trades": oos_result.get("num_trades", 0)
        })
        
        start += test_size
        
    return results
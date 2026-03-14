import pandas as pd
import numpy as np
from vnstock import stock_historical_data

def run_portfolio_smoke_test(tickers):
    """
    Thực hiện Smoke Test để đảm bảo data nguồn sạch và sẵn sàng.
    """
    print(f"--- Đang thực hiện Smoke Test cho {len(tickers)} mã ---")
    results = {}
    for ticker in tickers:
        try:
            df = stock_historical_data(ticker, "2025-01-01", "2026-03-14", "1D")
            if df.empty or len(df) < 20:
                results[ticker] = "FAIL: Thiếu dữ liệu"
            else:
                results[ticker] = "PASS"
        except Exception as e:
            results[ticker] = f"ERROR: {str(e)}"
    return results

def get_correlation_matrix(tickers):
    """
    Tính toán ma trận tương quan dựa trên lợi nhuận log (Log Returns).
    """
    combined_df = pd.DataFrame()
    for ticker in tickers:
        df = stock_historical_data(ticker, "2025-06-01", "2026-03-14", "1D")
        df['Log_Ret'] = np.log(df['close'] / df['close'].shift(1))
        combined_df[ticker] = df['Log_Ret']
    
    return combined_df.corr()

# Danh sách mã từ Portfolio SSI và mã "tím" tuần qua
my_watchlist = ['HPG', 'TCH', 'CII', 'HHV', 'DIG', 'SCR', 'HVN', 'VIP', 'PDV']

# Thực thi
# correlation_matrix = get_correlation_matrix(my_watchlist)
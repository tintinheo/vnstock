import pandas as pd
import numpy as np
from vnstock import stock_historical_data, Trading, Quote
import datetime
import time

# Danh sách cổ phiếu mục tiêu
TICKERS = ["CII","TCH","MSN","BSR","VRE"]

def get_realtime_signals(ticker):
    """
    Phân tích kỹ thuật thời gian thực cho một mã cổ phiếu cụ thể.
    Sử dụng dữ liệu lịch sử để tính toán các ngưỡng hỗ trợ/kháng cự 
    và dữ liệu bảng giá để xác định trạng thái hiện tại.
    """
    try:
        # 1. Lấy dữ liệu lịch sử (6 tháng gần nhất) để tính các chỉ báo xu hướng
        end_date = datetime.datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime('%Y-%m-%d')
        
        df = stock_historical_data(symbol=ticker, start_date=start_date, end_date=end_date)
        if df.empty:
            return None

        # 2. Tính toán các chỉ báo kỹ thuật
        # Simple Moving Averages
        df = df['close'].rolling(window=20).mean()
        df = df['close'].rolling(window=50).mean()
        
        # Relative Strength Index (RSI)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df = 100 - (100 / (1 + rs))
        
        # Pivot Points cho phiên hiện tại
        prev_day = df.iloc[-2]
        high, low, close = prev_day['high'], prev_day['low'], prev_day['close']
        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        
        # 3. Lấy giá real-time từ bảng giá
        # Lưu ý: Trading(source='KBS') yêu cầu kết nối ổn định đến API nguồn
        rt_price = Trading(source='KBS').price_board([ticker])
        current_price = rt_price['Giá'].iloc if not rt_price.empty else df.iloc[-1]['close']
        
        # 4. Logic xác định tín hiệu
        last_rsi = df.iloc[-1]
        last_sma20 = df.iloc[-1]
        
        signal = "THEO DÕI"
        if last_rsi < 30:
            signal = "MUA (QUÁ BÁN)"
        elif last_rsi > 70:
            signal = "BÁN (QUÁ MUA)"
        elif current_price > last_sma20 and df['close'].iloc[-2] <= last_sma20:
            signal = "MUA (BREAKOUT SMA20)"
            
        return {
            'Ticker': ticker,
            'Price': current_price,
            'RSI': round(last_rsi, 2),
            'SMA20': round(last_sma20, 0),
            'Pivot': round(pp, 0),
            'R1': round(r1, 0),
            'S1': round(s1, 0),
            'Action': signal
        }
    except Exception as e:
        print(f"Lỗi khi phân tích {ticker}: {e}")
        return None

def main_analysis_loop():
    print("--- Khởi động Hệ thống Phân tích Kỹ thuật Real-time 2026 ---")
    while True:
        results = []
        for t in TICKERS:
            data = get_realtime_signals(t)
            if data:
                results.append(data)
        
        if results:
            analysis_df = pd.DataFrame(results)
            print("\n" + "="*50)
            print(f"Cập nhật lúc: {datetime.datetime.now().strftime('%H:%M:%S')}")
            print(analysis_df.to_markdown(index=False))
            print("="*50)
        
        # Nghỉ 60 giây trước chu kỳ cập nhật tiếp theo
        time.sleep(60)

if __name__ == "__main__":
    main_analysis_loop()
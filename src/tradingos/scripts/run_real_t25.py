import sys
import os
import time
import requests
import pandas as pd
from datetime import date, datetime, timedelta

# Dynamically add 'src' to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from tradingos.core.t25_engine import t25_exit_check

def fetch_real_data(ticker: str, days: int = 60) -> pd.DataFrame:
    """
    Fetches real historical OHLCV data using the DNSE Fallback API.
    """
    end_time = int(time.time())
    start_time = end_time - (days * 24 * 3600)
    
    url = f"https://services.entrade.com.vn/chart-api/v2/history?symbol={ticker}&resolution=D&from={start_time}&to={end_time}"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if 'c' not in data or not data['c']:
            return pd.DataFrame()

        df = pd.DataFrame({
            'Close': data['c'],
            'Open': data['o'],
            'High': data['h'],
            'Low': data['l'],
            'Volume': data['v']
        })
        
        # Calculate Indicators
        # 1. VWAP (Daily Typical Price proxy for this test)
        df['VWAP'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # 2. MAV20 (20-day Moving Average Volume)
        df['MAV20'] = df['Volume'].rolling(window=20).mean()
        
        # 3. RSI 14 (Wilder's Smoothing)
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI14'] = 100 - (100 / (1 + rs))
        
        return df.dropna().reset_index(drop=True)

    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

def run_real_test(ticker_file: str):
    if not os.path.exists(ticker_file):
        print(f"❌ Error: File '{ticker_file}' not found.")
        return

    with open(ticker_file, 'r') as f:
        tickers = [line.strip().upper() for line in f if line.strip()]

    # Simulate a position entered 2 business days ago
    today = date.today()
    entry_date = today - timedelta(days=2) 
    
    # We will use the actual current system time to test the danger window logic
    current_time_str = datetime.now().strftime("%H:%M:%S")

    print("="*80)
    print(f"🚀 TRADINGOS ALPHA: LIVE T+2.5 ENGINE TEST")
    print(f"Date: {today} | Current Time: {current_time_str}")
    print(f"Simulating Entry Date: {entry_date} (T+2)")
    print("="*80)
    print(f"{'TICKER':<8} | {'PRICE':<8} | {'RSI(14)':<8} | {'VOL/MAV20':<12} | {'ACTION':<20}")
    print("-" * 80)

    for ticker in tickers:
        df = fetch_real_data(ticker)
        
        if df.empty:
            print(f"{ticker:<8} | --- Data Unavailable ---")
            continue

        # Extract the latest data points to feed the engine
        current_bar = df.iloc[-1].copy()
        mav20 = current_bar['MAV20']
        rsi_series = df['RSI14']

        # Run the engine!
        result = t25_exit_check(
            position_entry_date=entry_date,
            current_date=today,
            current_time=current_time_str,
            current_bar=current_bar,
            rsi_series=rsi_series,
            mav20=mav20
        )

        price = current_bar['Close']
        rsi = current_bar['RSI14']
        vol_ratio = current_bar['Volume'] / mav20 if mav20 > 0 else 0

        # Format color based on action (if your terminal supports ANSI)
        action_str = result.name
        if "EXIT" in action_str:
            action_str = f"\033[91m{action_str}\033[0m" # Red
        elif "HOLD" in action_str:
            action_str = f"\033[92m{action_str}\033[0m" # Green

        print(f"{ticker:<8} | {price:<8.0f} | {rsi:<8.1f} | {vol_ratio:<11.1f}x | {action_str}")

    print("="*80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_real_t25.py <path_to_tickers.txt>")
        sys.exit(1)
        
    ticker_file_path = sys.argv[1]
    run_real_test(ticker_file_path)
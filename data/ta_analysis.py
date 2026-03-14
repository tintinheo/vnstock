from vnstock import Vnstock
import pandas as pd
import numpy as np

tickers = ['HPG', 'CII', 'TCH', 'HHV']
start_date = '2025-12-01'
end_date = '2026-03-14'

buy_prices = {'HPG': 26.95, 'TCH': 14.475, 'CII': 15.975, 'HHV': 12.40}

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def macd_calc(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histog = macd_line - signal_line
    return macd_line, signal_line, histog

for t in tickers:
    try:
        stock = Vnstock().stock(symbol=t, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date, interval='1D')
        df = df.sort_values('time').reset_index(drop=True)

        df['rsi14'] = rsi(df['close'], 14)
        df['ma10'] = df['close'].rolling(10).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma50'] = df['close'].rolling(50).mean()
        std20 = df['close'].rolling(20).std()
        df['bb_upper'] = df['ma20'] + 2*std20
        df['bb_lower'] = df['ma20'] - 2*std20
        df['macd'], df['signal_l'], df['hist'] = macd_calc(df['close'])
        df['vol_ma10'] = df['volume'].rolling(10).mean()
        df['atr'] = (df['high'] - df['low']).rolling(14).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]

        print('=' * 60)
        ticker_label = t
        close_val = last['close']
        date_val = str(last['time'])[:10]
        print(f"  {ticker_label}  |  Close: {close_val}  |  {date_val}")
        print('=' * 60)

        bp = buy_prices[t]
        pnl = (close_val - bp) / bp * 100
        label = "Co (~mua)" if t == 'HHV' else "Mua"
        print(f"  {label}: {bp}  |  P&L: {pnl:+.2f}%")

        chg = (last['close'] - prev['close']) / prev['close'] * 100
        chg_prev = (prev['close'] - prev2['close']) / prev2['close'] * 100
        vol = int(last['volume'])
        vol_ma = int(last['vol_ma10'])
        vol_ratio = vol / vol_ma
        print(f"  Phien 13/3: {chg:+.2f}%  |  Phien 12/3: {chg_prev:+.2f}%")
        print(f"  Volume: {vol:,}  |  MA10 Vol: {vol_ma:,}  |  Ratio: {vol_ratio:.2f}x")

        r14 = last['rsi14']
        ma10_v = last['ma10']
        ma20_v = last['ma20']
        ma50_v = last['ma50']
        bb_up = last['bb_upper']
        bb_lo = last['bb_lower']
        macd_v = last['macd']
        sig_v = last['signal_l']
        hist_v = last['hist']
        atr_v = last['atr']

        print(f"  RSI(14): {r14:.1f}")
        print(f"  MA10: {ma10_v:.2f}  |  MA20: {ma20_v:.2f}  |  MA50: {ma50_v:.2f}")
        print(f"  BB Upper: {bb_up:.2f}  |  BB Lower: {bb_lo:.2f}")
        print(f"  MACD: {macd_v:.3f}  |  Signal: {sig_v:.3f}  |  Hist: {hist_v:.3f}")
        print(f"  ATR(14): {atr_v:.3f}")

        recent = df.tail(20)
        sup = recent['low'].min()
        res = recent['high'].max()
        print(f"  Support 20D: {sup}  |  Resist 20D: {res}")

        # Recent 5 candles
        print("  --- 5 phien gan nhat ---")
        print(df[['time','open','high','low','close','volume']].tail(5).to_string(index=False))
        print()
    except Exception as e:
        print(t, 'error:', e)

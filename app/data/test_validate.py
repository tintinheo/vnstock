import requests, numpy as np
from datetime import datetime, timedelta

to_ts = int(datetime.now().timestamp())
from_ts = int((datetime.now() - timedelta(days=1095)).timestamp())
url = f'https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?symbol=FCN&resolution=1D&from={from_ts}&to={to_ts}'
r = requests.get(url, timeout=15)
raw = r.json()
t_arr = raw.get('t', [])
c_arr = raw.get('c', [])
print(f'FCN: {len(t_arr)} rows')
print(f'Last close: {c_arr[-1] if c_arr else 0}')
print(f'Last 5 closes: {c_arr[-5:]}')

# Quick RSI calc
cls = np.array(c_arr[-30:])
delta = np.diff(cls)
gain = np.where(delta > 0, delta, 0.0)
loss = np.where(delta < 0, -delta, 0.0)
avg_g = np.mean(gain[-14:])
avg_l = np.mean(loss[-14:])
rs = avg_g / (avg_l + 1e-10)
rsi = 100 - 100 / (1 + rs)
print(f'RSI(14): {rsi:.1f}')

# SMA
sma20 = np.mean(cls[-20:])
c50 = np.array(c_arr[-50:])
sma50 = np.mean(c50)
trend = "bullish" if cls[-1] > sma50 else "bearish"
print(f'SMA20: {sma20:.2f}, SMA50: {sma50:.2f}')
print(f'Trend: {trend} (close={cls[-1]}, sma50={sma50:.2f})')

# 52w range
c252 = np.array(c_arr[-252:])
h52 = np.max(c252)
l52 = np.min(c252)
pos = (cls[-1] - l52) / (h52 - l52) * 100
print(f'52w range: {l52}-{h52}, position: {pos:.0f}%')
print('PASS')

import requests, json
from datetime import datetime, timedelta

to_ts = int(datetime.now().timestamp())
from_ts = int((datetime.now() - timedelta(days=365)).timestamp())

# Test DNSE endpoints
print("=== DNSE Endpoints ===")
for name, url in [
    ("OLD (entrade)", f"https://services.entrade.com.vn/chart-api/v2/ohlcs/stock?symbol=FCN&resolution=D&from={from_ts}&to={to_ts}"),
    ("NEW (api.dnse)", f"https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?symbol=FCN&resolution=1D&from={from_ts}&to={to_ts}"),
]:
    try:
        r = requests.get(url, timeout=10)
        print(f"  {name}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200:
            d = r.json()
            c = d.get('c', [])
            print(f"    rows={len(c)}, last_close={c[-1] if c else 'N/A'}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

# Test TCBS API
print("\n=== TCBS tcanalysis API ===")
tcbs_hdrs = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://tcinvest.tcbs.com.vn/",
    "Origin": "https://tcinvest.tcbs.com.vn",
    "Accept": "application/json",
}
for name, url in [
    ("Overview", "https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/FCN/overview"),
    ("Income", "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/FCN/incomestatement?yearly=0&isAll=0"),
    ("Balance", "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/FCN/balancesheet?yearly=0&isAll=0"),
    ("Ratios", "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/FCN/financialratio?yearly=0&isAll=0"),
]:
    try:
        r = requests.get(url, headers=tcbs_hdrs, timeout=10)
        print(f"  {name}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200:
            d = r.json()
            if isinstance(d, dict):
                print(f"    keys: {list(d.keys())[:15]}")
                for k, v in d.items():
                    if isinstance(v, list):
                        print(f"    {k}: list[{len(v)}]")
                        if v and isinstance(v[0], dict):
                            print(f"      first keys: {list(v[0].keys())[:12]}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

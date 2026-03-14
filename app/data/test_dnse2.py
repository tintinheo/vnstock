import requests, json, re

# Test known DNSE API endpoints
endpoints = [
    ("OHLC", "https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?from=1770000000&to=1772952580&symbol=FCN&resolution=1D"),
    ("Finance", "https://api.dnse.com.vn/api/v1/stock/FCN/finance"),
    ("Stock Info", "https://api.dnse.com.vn/api/v1/stock/FCN"),
    ("Senses API", "https://api.dnse.com.vn/senses/api/stock/FCN"),
    ("Market Info", "https://api.dnse.com.vn/market/api/stock/FCN"),
    ("Insight", "https://api.dnse.com.vn/insight/api/stock/FCN"),
    ("Price Board", "https://api.dnse.com.vn/api/priceboard/FCN"),
]

hdrs = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

for name, url in endpoints:
    try:
        r = requests.get(url, headers=hdrs, timeout=10)
        print(f"{name}: {r.status_code} len={len(r.text)}")
        if r.status_code == 200:
            try:
                d = r.json()
                if isinstance(d, dict):
                    print(f"  Keys: {list(d.keys())[:15]}")
                elif isinstance(d, list) and len(d) > 0:
                    print(f"  List[{len(d)}], first keys: {list(d[0].keys())[:10] if isinstance(d[0],dict) else type(d[0])}")
            except:
                print(f"  Not JSON: {r.text[:100]}")
    except Exception as e:
        print(f"{name}: ERROR {e}")

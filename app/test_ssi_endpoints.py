"""Test SSI iboard API endpoints to understand response structure."""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://iboard.ssi.com.vn/',
    'Origin': 'https://iboard.ssi.com.vn'
}

def test(name, url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"\n{'='*60}")
        print(f"[{name}] status={r.status_code}")
        if r.ok:
            d = r.json()
            if isinstance(d, list):
                print(f"  Type: list, len={len(d)}")
                if d:
                    print(f"  Item[0] keys: {list(d[0].keys())[:15]}")
                    print(f"  Item[0] sample: {json.dumps(d[0], ensure_ascii=False)[:500]}")
            elif isinstance(d, dict):
                print(f"  Type: dict, keys: {list(d.keys())[:15]}")
                inner = d.get('data', None)
                if isinstance(inner, list) and inner:
                    print(f"  inner[0] keys: {list(inner[0].keys())[:15]}")
                    print(f"  inner[0] sample: {json.dumps(inner[0], ensure_ascii=False)[:500]}")
                elif isinstance(inner, dict):
                    print(f"  inner keys: {list(inner.keys())[:15]}")
                    print(f"  inner sample: {json.dumps(inner, ensure_ascii=False)[:500]}")
                else:
                    print(f"  Full: {json.dumps(d, ensure_ascii=False)[:800]}")
        else:
            print(f"  Response: {r.text[:200]}")
    except Exception as e:
        print(f"[{name}] FAIL: {e}")

# Endpoints to test
test("system/time", "https://iboard-query.ssi.com.vn/system/time")
test("stock/FPT boardId=MAIN", "https://iboard-query.ssi.com.vn/stock/FPT?boardId=MAIN")
test("stock/group/VN100", "https://iboard-query.ssi.com.vn/stock/group/VN100")
test("market-stat/exchange/hose", "https://iboard-query.ssi.com.vn/market-stat/exchange/hose")
test("le-table/stock/FPT", "https://iboard-query.ssi.com.vn/le-table/stock/FPT?pageSize=20")
test("charts/symbol?symbol=FPT", "https://iboard-api.ssi.com.vn/statistics/charts/symbol?symbol=FPT")

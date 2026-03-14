import requests, json, re

r = requests.get('https://www.dnse.com.vn/senses/co-phieu-FCN',
                 headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
print('Status:', r.status_code)

# Extract __NEXT_DATA__
nd = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text)
if nd:
    data = json.loads(nd[0])
    props = data.get('props', {}).get('pageProps', {})
    print('pageProps keys:', list(props.keys())[:20])
    for k, v in props.items():
        if isinstance(v, dict):
            print(f'  {k} keys: {list(v.keys())[:15]}')
            for k2, v2 in v.items():
                if isinstance(v2, (int, float, str)):
                    print(f'    {k2}: {str(v2)[:120]}')
                elif isinstance(v2, dict):
                    print(f'    {k2}: dict keys={list(v2.keys())[:10]}')
                elif isinstance(v2, list):
                    print(f'    {k2}: list[{len(v2)}]')
        elif isinstance(v, list):
            print(f'  {k}: list[{len(v)}]')
            if len(v) > 0 and isinstance(v[0], dict):
                print(f'    first item keys: {list(v[0].keys())[:10]}')
                print(f'    first item: {json.dumps(v[0], ensure_ascii=False)[:200]}')
        else:
            print(f'  {k}: {str(v)[:150]}')
else:
    print('No __NEXT_DATA__ found')
    # Look for ld+json
    ld = re.findall(r'application/ld.json.>(.*?)</script>', r.text, re.DOTALL)
    for i, j in enumerate(ld):
        try:
            d = json.loads(j)
            print(f'LD-JSON #{i}: {json.dumps(d, ensure_ascii=False)[:300]}')
        except:
            print(f'LD-JSON #{i}: parse error, len={len(j)}')

"""Phase 3: Sector Map Update - SSI iBoard (no vnstock)

Data sources (verified HTTP 200 in SSI_HARrequestLogs.txt):
  Universe : GET https://iboard-query.ssi.com.vn/stock/group/{HOSE|HNX|VN100}
             Response shape: {"code":"SUCCESS","data":[{"stockSymbol":"ACB","exchange":"hose",...}]}
  Profile  : GET https://iboard-api.ssi.com.vn/statistics/company/ssmi/company-profile?symbol={SYM}&language=vn
             Response shape: {"data":{"industry":"...","exchange":"HOSE",...}}

Strategy:
  1. Primary  - load manually-curated data/sector_map.json.
  2. Fallback - fetch from SSI for every ticker not already in the manual map.
  3. Persist  - write merged result to sector_map.json + SQLite cache.
"""
import json, os, sys, time
import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT_DIR, "src"))

from tradingos.data.cache import Cache
from tradingos.utils.logging import get_logger

log = get_logger("update_sector_map")

JSON_PATH  = os.path.join(ROOT_DIR, "data", "sector_map.json")
_SSI_QUERY = "https://iboard-query.ssi.com.vn"
_SSI_API   = "https://iboard-api.ssi.com.vn"

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradingOS/1.1",
    "Accept":     "application/json, text/plain, */*",
    "Origin":     "https://iboard.ssi.com.vn",
    "Referer":    "https://iboard.ssi.com.vn/",
})


def _get(url, params=None, timeout=15):
    for attempt in range(3):
        try:
            r = _session.get(url, params=params, timeout=timeout)
            if r.status_code == 400:
                return {}
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            log.warning(f"Timeout: {url}")
            return {}
        except Exception as e:
            if attempt == 2:
                log.warning(f"Failed after 3 tries: {url} - {e}")
                return {}
            time.sleep(1.5 ** attempt)
    return {}


def load_existing_map():
    if not os.path.exists(JSON_PATH):
        log.warning("sector_map.json not found, starting with empty map.")
        return {}
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info(f"Loaded {len(data)} tickers from manual map.")
        return data
    except Exception as e:
        log.error(f"Could not load sector_map.json: {e}")
        return {}


def fetch_universe():
    """
    Returns {ticker: exchange} dict for all HOSE+HNX stocks.
    HAR-confirmed key: item["stockSymbol"] for ticker, item["exchange"] for board.
    """
    universe = {}
    for group in ("HOSE", "HNX", "VN100"):
        resp  = _get(f"{_SSI_QUERY}/stock/group/{group}")
        items = resp.get("data", []) if isinstance(resp, dict) else []
        added = 0
        for item in items:
            sym  = item.get("stockSymbol") or item.get("symbol")
            exch = (item.get("exchange") or "UNKNOWN").upper()
            if sym and sym not in universe:
                universe[sym] = exch
                added += 1
        log.info(f"Group {group}: {added} new tickers (total: {len(universe)})")
        time.sleep(0.3)
    log.info(f"Total unique tickers from SSI: {len(universe)}")
    return universe


def fetch_profile(ticker, exchange):
    """
    HAR-confirmed: /company-profile returns HTTP 200.
    Actual response fields (verified by probe):
      industryName : e.g. "Cong nghe Thong tin"  (high-level)
      superSector  : e.g. "Cong nghe Thong tin"
      sector       : e.g. "Phan mem & Dich vu May tinh"  (sub-sector)
      subSector    : e.g. "Dich vu May tinh"
    No 'exchange' field in profile - we use the value from the universe fetch.
    """
    resp  = _get(
        f"{_SSI_API}/statistics/company/ssmi/company-profile",
        params={"symbol": ticker, "language": "vn"},
    )
    inner = resp.get("data") if isinstance(resp, dict) else None
    if not inner:
        return None
    industry    = (inner.get("industryName") or inner.get("superSector") or "").strip()
    sub_sector  = (inner.get("sector") or inner.get("subSector") or "").strip()
    if not industry:
        return None
    return {
        "sector":     exchange.upper(),   # exchange board from universe (HOSE/HNX)
        "industry":   industry,           # high-level: e.g. "Cong nghe Thong tin"
        "sub_sector": sub_sector,         # detail: e.g. "Phan mem & Dich vu May tinh"
    }


def save(sector_map):
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(sector_map, f, ensure_ascii=False, indent=2)
    log.info(f"Wrote {len(sector_map)} tickers to sector_map.json.")
    # SQLite cache schema: ticker, sector, industry only
    records = [
        {"ticker": t, "sector": d["sector"], "industry": d["industry"]}
        for t, d in sector_map.items()
    ]
    Cache().put_sector_map(records)
    log.info(f"Updated SQLite cache with {len(records)} records.")


def update_sector_map():
    log.info("=== Sector map update: Manual (primary) + SSI iBoard (fallback) ===")
    sector_map = load_existing_map()

    universe = fetch_universe()
    if not universe:
        log.error("No tickers retrieved from SSI. Aborting.")
        return False

    missing = {t: exch for t, exch in universe.items() if t not in sector_map}
    log.info(f"{len(missing)} tickers missing - fetching profiles from SSI...")
    for i, (ticker, exchange) in enumerate(missing.items(), 1):
        profile = fetch_profile(ticker, exchange)
        if profile:
            sector_map[ticker] = profile
            log.debug(f"[{i}/{len(missing)}] {ticker}: {profile['industry']}")
        time.sleep(0.2)

    log.info(f"Final map: {len(sector_map)} tickers.")
    save(sector_map)
    log.info("=== Sector map update complete ===")
    return True


if __name__ == "__main__":
    update_sector_map()

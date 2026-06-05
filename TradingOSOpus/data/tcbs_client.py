"""data/tcbs_client.py – Direct TCBS public API client. NO vnstock."""
import requests, time, datetime as dt
import pandas as pd
from config.settings import TCBS_BARS, TCBS_TICKER, TCBS_INTRADAY, TCBS_LISTING

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def fetch_ohlcv(ticker, start="2016-01-01", end=None, resolution="D", max_retries=3):
    if end is None: end = dt.date.today().isoformat()
    ts_from = int(dt.datetime.fromisoformat(start).timestamp())
    ts_to = int(dt.datetime.fromisoformat(end).timestamp())
    params = {"ticker": ticker.upper(), "type": resolution, "from": ts_from,
              "to": ts_to, "resolution": resolution, "countBack": 5000}
    for attempt in range(max_retries):
        try:
            resp = requests.get(TCBS_BARS, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data)
            rm = {"tradingDate": "date", "open": "open", "high": "high",
                  "low": "low", "close": "close", "volume": "volume"}
            df = df.rename(columns={k: v for k, v in rm.items() if k in df.columns})
            for c in ["open", "high", "low", "close"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce") * 1000
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date").reset_index(drop=True)
            return df
        except Exception as e:
            if attempt < max_retries - 1: time.sleep(2 ** attempt)
            else: print(f"[TCBS] Error {ticker}: {e}"); return pd.DataFrame()

def fetch_ticker_overview(ticker):
    try:
        r = requests.get(TCBS_TICKER, params={"ticker": ticker.upper()}, headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json()
    except Exception as e: print(f"[TCBS] Overview: {e}"); return {}

def fetch_listing():
    try:
        r = requests.get(TCBS_LISTING, headers=HEADERS, timeout=15)
        r.raise_for_status(); return pd.DataFrame(r.json().get("data", []))
    except Exception as e: print(f"[TCBS] Listing: {e}"); return pd.DataFrame()

def fetch_intraday(ticker, page=0, size=100):
    try:
        r = requests.get(TCBS_INTRADAY, params={"ticker": ticker.upper(), "page": page, "size": size},
                         headers=HEADERS, timeout=10)
        r.raise_for_status(); return pd.DataFrame(r.json().get("data", []))
    except Exception as e: print(f"[TCBS] Intraday: {e}"); return pd.DataFrame()

def fetch_multiple_tickers(tickers, start="2016-01-01", end=None, delay=0.3):
    result = {}
    for t in tickers:
        df = fetch_ohlcv(t, start=start, end=end)
        if not df.empty: result[t] = df
        time.sleep(delay)
    return result
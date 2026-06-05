"""data/vci_client.py – VCI (Viet Capital) API client."""
import requests, datetime as dt
import pandas as pd
from config.settings import VCI_OHLC, VCI_PRICE_BOARD, VCI_GRAPHQL

HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
_IMAP = {"1D": "ONE_DAY", "1W": "ONE_WEEK", "1M": "ONE_MONTH",
         "1m": "ONE_MINUTE", "5m": "FIVE_MINUTES", "15m": "FIFTEEN_MINUTES", "1h": "ONE_HOUR"}

def fetch_ohlcv_vci(ticker, start="2020-01-01", end=None, interval="1D"):
    if end is None: end = dt.date.today().isoformat()
    payload = {"ticker": ticker.upper(), "from": start.replace("-", ""),
               "to": end.replace("-", ""), "interval": _IMAP.get(interval, "ONE_DAY")}
    try:
        r = requests.post(VCI_OHLC, json=payload, headers=HEADERS, timeout=15)
        r.raise_for_status(); d = r.json()
        if not d or "t" not in d: return pd.DataFrame()
        return pd.DataFrame({"date": pd.to_datetime(d["t"], unit="s"), "open": d["o"],
            "high": d["h"], "low": d["l"], "close": d["c"], "volume": d["v"]
        }).sort_values("date").reset_index(drop=True)
    except Exception as e: print(f"[VCI] Error {ticker}: {e}"); return pd.DataFrame()

def fetch_price_board(tickers):
    try:
        r = requests.post(VCI_PRICE_BOARD, json={"codes": [t.upper() for t in tickers]},
                          headers=HEADERS, timeout=10)
        r.raise_for_status(); return pd.DataFrame(r.json())
    except Exception as e: print(f"[VCI] Board: {e}"); return pd.DataFrame()

def fetch_company_info_graphql(ticker):
    q = """query($t:String!){companyProfile(ticker:$t){
        ticker companyName exchange industry marketCap pe pb eps roe roa debtToEquity}}"""
    try:
        r = requests.post(VCI_GRAPHQL, json={"query": q, "variables": {"t": ticker.upper()}},
                          headers=HEADERS, timeout=10)
        r.raise_for_status(); return r.json().get("data", {}).get("companyProfile", {})
    except Exception as e: print(f"[VCI] GQL: {e}"); return {}
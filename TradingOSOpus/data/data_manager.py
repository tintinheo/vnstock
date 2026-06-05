"""data/data_manager.py – Unified data manager: TCBS -> VCI -> synthetic fallback."""
import os, datetime as dt
import pandas as pd, numpy as np
from config.settings import DATA_DIR, DEFAULT_TICKERS
from data.tcbs_client import fetch_ohlcv, fetch_ticker_overview
from data.vci_client import fetch_ohlcv_vci
from data.news_scraper import scrape_cafef_headlines

class DataManager:
    def __init__(self, cache_dir=DATA_DIR):
        self.cache_dir = cache_dir; os.makedirs(cache_dir, exist_ok=True)

    def _cp(self, t): return os.path.join(self.cache_dir, f"{t.upper()}.csv")
    def _save(self, t, df): df.to_csv(self._cp(t), index=False)
    def _load(self, t):
        p = self._cp(t)
        return pd.read_csv(p, parse_dates=["date"]) if os.path.exists(p) else None

    def get_ohlcv(self, ticker, start="2016-01-01", end=None, use_cache=True):
        if use_cache:
            c = self._load(ticker)
            if c is not None and len(c) > 50: return c
        df = fetch_ohlcv(ticker, start=start, end=end)
        if df.empty:
            print(f"[DM] TCBS failed {ticker}, trying VCI...")
            df = fetch_ohlcv_vci(ticker, start=start, end=end)
        if df.empty:
            print(f"[DM] APIs failed {ticker}, generating synthetic")
            df = self._synthetic(ticker, start, end)
        if not df.empty: self._save(ticker, df)
        return df

    def get_multiple(self, tickers=None, start="2016-01-01", end=None):
        if tickers is None: tickers = DEFAULT_TICKERS
        return {t: self.get_ohlcv(t, start=start, end=end) for t in tickers}

    def get_news(self, pages=3): return scrape_cafef_headlines(pages)
    def get_overview(self, ticker): return fetch_ticker_overview(ticker)

    @staticmethod
    def _synthetic(ticker, start="2016-01-01", end=None):
        if end is None: end = dt.date.today().isoformat()
        dates = pd.bdate_range(start=start, end=end); n = len(dates)
        if n == 0: return pd.DataFrame()
        np.random.seed(hash(ticker) % 2**31)
        s0 = np.random.uniform(10, 150) * 1000
        prices = s0 * np.exp(np.cumsum(np.random.normal(0.0003, 0.018, n)))
        high = prices * (1 + np.abs(np.random.normal(0, 0.008, n)))
        low = prices * (1 - np.abs(np.random.normal(0, 0.008, n)))
        opn = low + (high - low) * np.random.uniform(0.2, 0.8, n)
        vol = np.random.lognormal(13, 1.0, n).astype(int)
        return pd.DataFrame({"date": dates[:n], "open": np.round(opn, -2),
            "high": np.round(high, -2), "low": np.round(low, -2),
            "close": np.round(prices, -2), "volume": vol})
"""data/data_manager.py – KBS(IIS) → CafeF → Cache → Error. No vnstock."""
import pandas as pd
import os, json, logging
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")


class DataUnavailableError(Exception):
    pass


class DataManager:
    CACHE_TTL_HOURS = 24

    def __init__(self, cache_dir="cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._kbs = None
        self._cafef = None

    @property
    def kbs(self):
        if self._kbs is None:
            from data.kbs_client import KBSClient
            self._kbs = KBSClient()
        return self._kbs

    @property
    def cafef(self):
        if self._cafef is None:
            from data.cafef_client import CafeFClient
            self._cafef = CafeFClient()
        return self._cafef

    def get_ohlcv(self, ticker: str, start="2020-01-01", end=None) -> pd.DataFrame:
        ticker = ticker.upper().strip()

        # 1. KBS IIS (primary)
        df = self._try_kbs(ticker, start, end)
        if df is not None and len(df) >= 10:
            self._save_cache(df, ticker)
            return df

        # 2. CafeF scraper (backup)
        df = self._try_cafef(ticker, start)
        if df is not None and len(df) >= 10:
            self._save_cache(df, ticker)
            return df

        # 3. Cache
        df = self._load_cache(ticker)
        if df is not None and len(df) > 0:
            logger.warning(f"[CACHE] Using cached data for {ticker}")
            return df

        raise DataUnavailableError(
            f"Cannot fetch data for '{ticker}'. KBS and CafeF both failed. "
            f"Check internet and that '{ticker}' is valid."
        )

    def _try_kbs(self, ticker, start, end):
        try:
            df = self.kbs.get_ohlcv(ticker, start, end)
            if df is not None and len(df) > 0 and "close" in df.columns:
                last = df["close"].iloc[-1]
                if 500 <= last <= 2_000_000: return df
                logger.warning(f"[KBS] {ticker}: bad price {last:,.0f}")
        except Exception as e:
            logger.warning(f"[KBS] {ticker}: {e}")
        return None

    def _try_cafef(self, ticker, start):
        try:
            df = self.cafef.get_ohlcv(ticker, start=start)
            if df is not None and len(df) > 0 and "close" in df.columns:
                last = df["close"].iloc[-1]
                if 500 <= last <= 2_000_000: return df
        except Exception as e:
            logger.warning(f"[CafeF] {ticker}: {e}")
        return None

    def _save_cache(self, df, ticker):
        try:
            df.to_csv(os.path.join(self.cache_dir, f"{ticker}.csv"), index=False)
            with open(os.path.join(self.cache_dir, f"{ticker}.meta.json"), "w") as f:
                json.dump({"cached_at": datetime.now().isoformat(),
                           "rows": len(df), "last_close": float(df["close"].iloc[-1]),
                           "source": self.get_data_source(df)}, f)
        except Exception as e:
            logger.warning(f"Cache save: {e}")

    def _load_cache(self, ticker):
        dp = os.path.join(self.cache_dir, f"{ticker}.csv")
        mp = os.path.join(self.cache_dir, f"{ticker}.meta.json")
        if not os.path.exists(dp): return None
        try:
            if os.path.exists(mp):
                with open(mp) as f: meta = json.load(f)
                age = (datetime.now() - datetime.fromisoformat(meta["cached_at"])).total_seconds()/3600
                if age > self.CACHE_TTL_HOURS: return None
            df = pd.read_csv(dp); df["date"] = pd.to_datetime(df["date"]); df["_source"] = "CACHE"
            return df
        except: return None

    def get_data_source(self, df) -> str:
        if df is None or len(df) == 0: return "NONE"
        return str(df["_source"].iloc[-1]) if "_source" in df.columns else "UNKNOWN"

    def get_news(self, pages=1): return []

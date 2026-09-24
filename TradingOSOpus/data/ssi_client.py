"""data/ssi_client.py – SSI iBoard API client (backup data source).

Uses SSI's public iBoard API for real-time and historical data.
Endpoint: https://iboard-query.ssi.com.vn
"""
import requests
import pandas as pd
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

BASE_URL = "https://iboard-query.ssi.com.vn"


class SSIClient:
    """SSI iBoard data client – backup source."""

    def __init__(self, timeout=15, max_retries=2):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
            "Accept": "application/json",
            "Referer": "https://iboard.ssi.com.vn/",
        })

    def get_ohlcv(self, ticker: str, start: str = "2020-01-01", end: str = None) -> pd.DataFrame:
        """Fetch OHLCV via SSI. Prices returned in VND."""
        ticker = ticker.upper().strip()

        for attempt in range(self.max_retries):
            try:
                # Try SSI real-time snapshot
                resp = self.session.get(
                    f"{BASE_URL}/v2/stock/type/s/hose/{ticker}",
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, dict):
                        price = data.get("lastPrice") or data.get("matchedPrice")
                        if price:
                            logger.info(f"[SSI] {ticker}: Got snapshot price={price}")
                            now = datetime.now()
                            df = pd.DataFrame([{
                                "date": now,
                                "open": float(data.get("openPrice", price)) * 1000,
                                "high": float(data.get("highestPrice", price)) * 1000,
                                "low": float(data.get("lowestPrice", price)) * 1000,
                                "close": float(price) * 1000,
                                "volume": int(data.get("nmTotalTradedQty", 0)),
                            }])
                            df["_source"] = "SSI"
                            return df

            except Exception as e:
                logger.warning(f"[SSI] Attempt {attempt+1} for {ticker}: {e}")
                time.sleep(1 + attempt)

        logger.error(f"[SSI] ❌ Failed for {ticker}")
        return pd.DataFrame()

    def get_all_tickers(self, exchange="hose"):
        """Get all listed tickers from an exchange."""
        try:
            url = f"{BASE_URL}/stock/type/s/{exchange}/page/1/size/9999"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return [item.get("ss", item.get("stockSymbol", "")) for item in data if item]
            return []
        except Exception as e:
            logger.error(f"[SSI] Failed to get tickers: {e}")
            return []

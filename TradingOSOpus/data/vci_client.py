"""data/vci_client.py – VCI (Vietcap) API client (FIXED: price validation).

VCI API also returns prices in VND. Same validation logic as TCBS.
"""
import requests
import pandas as pd
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

BASE_URL = "https://mt.vietcap.com.vn/api"


class VCIClient:
    """VCI (Vietcap) market data client."""

    def __init__(self, timeout=15, max_retries=3):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0",
            "Accept": "application/json",
        })

    def get_ohlcv(self, ticker, start="2020-01-01", end=None):
        """Fetch OHLCV from VCI API. Returns DataFrame with prices in VND."""
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        url = f"{BASE_URL}/price/symbols/{ticker.upper()}/bars"
        params = {
            "from": start,
            "to": end,
            "resolution": "D",
        }

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 404:
                    logger.warning(f"[VCI] {ticker} not found (404)")
                    return pd.DataFrame()
                resp.raise_for_status()
                data = resp.json()

                # VCI returns different formats depending on endpoint
                if isinstance(data, list):
                    bars = data
                elif isinstance(data, dict):
                    bars = data.get("data", data.get("bars", []))
                else:
                    return pd.DataFrame()

                if not bars:
                    logger.warning(f"[VCI] No data for {ticker}")
                    return pd.DataFrame()

                df = pd.DataFrame(bars)

                # Rename columns
                col_map = {"t": "date", "o": "open", "h": "high",
                           "l": "low", "c": "close", "v": "volume",
                           "time": "date", "tradingDate": "date"}
                df = df.rename(columns=col_map)

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])

                # ═══ PRICE VALIDATION (same logic as TCBS) ═══
                if "close" in df.columns and len(df) > 0:
                    median_price = df["close"].median()
                    if median_price < 100:
                        logger.info(f"[VCI] {ticker}: Converting x1000 → VND")
                        for c in ["open", "high", "low", "close"]:
                            if c in df.columns:
                                df[c] = df[c] * 1000
                    elif median_price > 1_000_000:
                        logger.warning(f"[VCI] {ticker}: Prices too high, dividing by 1000")
                        for c in ["open", "high", "low", "close"]:
                            if c in df.columns:
                                df[c] = df[c] / 1000

                required = ["date", "open", "high", "low", "close", "volume"]
                for col in required:
                    if col not in df.columns:
                        df[col] = 0

                df = df[required].copy()
                df = df.sort_values("date").reset_index(drop=True)
                df["_source"] = "VCI"

                logger.info(f"[VCI] ✅ {ticker}: {len(df)} rows, "
                           f"last close={df['close'].iloc[-1]:,.0f} VND")
                return df

            except requests.exceptions.RequestException as e:
                logger.warning(f"[VCI] Attempt {attempt+1} failed for {ticker}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 + attempt)

        logger.error(f"[VCI] ❌ All attempts failed for {ticker}")
        return pd.DataFrame()

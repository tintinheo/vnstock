"""data/tcbs_client.py – TCBS Public API client.

Endpoint: https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term

IMPORTANT – PRICE UNIT:
  TCBS API returns prices in x1000 VND.
  Example: VCG close = 19.7 means 19,700 VND
           FPT close = 142.5 means 142,500 VND
  → We ALWAYS multiply OHLC by 1000 when median < 500.
"""
import requests
import pandas as pd
from datetime import datetime
import logging
import time
import random

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
]

BASE_URL = "https://apipubaws.tcbs.com.vn"


class TCBSClient:
    """TCBS market data client – returns prices in VND."""

    def __init__(self, timeout=20, max_retries=3):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries

    def _headers(self):
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Origin": "https://tcinvest.tcbs.com.vn",
            "Referer": "https://tcinvest.tcbs.com.vn/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }

    def get_ohlcv(self, ticker: str, start: str = "2020-01-01", end: str = None) -> pd.DataFrame:
        """Fetch daily OHLCV. Returns DataFrame with prices in VND."""
        ticker = ticker.upper().strip()
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        start_ts = int(datetime.strptime(start, "%Y-%m-%d").timestamp())
        end_ts = int(datetime.strptime(end, "%Y-%m-%d").timestamp())

        url = f"{BASE_URL}/stock-insight/v2/stock/bars-long-term"
        params = {
            "ticker": ticker,
            "type": "stock",
            "resolution": "D",
            "from": start_ts,
            "to": end_ts,
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url, params=params, headers=self._headers(), timeout=self.timeout
                )

                if resp.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"[TCBS] Rate limited for {ticker}, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                body = resp.json()

                bars = body.get("data", [])
                if not bars:
                    logger.warning(f"[TCBS] Empty data for {ticker}")
                    return pd.DataFrame()

                df = pd.DataFrame(bars)

                # ─── Column mapping ───
                col_map = {
                    "tradingDate": "date",
                    "open": "open", "high": "high", "low": "low",
                    "close": "close", "volume": "volume",
                }
                df = df.rename(columns=col_map)

                # Ensure columns exist
                for c in ["date", "open", "high", "low", "close", "volume"]:
                    if c not in df.columns:
                        logger.error(f"[TCBS] Missing column '{c}' for {ticker}. Columns: {list(df.columns)}")
                        return pd.DataFrame()

                df["date"] = pd.to_datetime(df["date"])

                # ═══════════════════════════════════════════
                # PRICE CONVERSION: x1000 VND → VND
                #
                # TCBS returns: close=19.7 for VCG (= 19,700 VND)
                #               close=142.5 for FPT (= 142,500 VND)
                #
                # Rule: if median < 500 → multiply by 1000
                #        (all VN stocks trade above 1,000 VND)
                # ═══════════════════════════════════════════
                median_close = df["close"].median()
                if median_close < 500:
                    for c in ["open", "high", "low", "close"]:
                        df[c] = (df[c] * 1000).round(0)
                    logger.info(f"[TCBS] {ticker}: Converted x1000 → VND (median raw={median_close:.2f})")
                else:
                    logger.info(f"[TCBS] {ticker}: Already in VND (median={median_close:,.0f})")

                df = df[["date", "open", "high", "low", "close", "volume"]].copy()
                df = df.sort_values("date").reset_index(drop=True)
                df["_source"] = "TCBS"

                last_close = df["close"].iloc[-1]
                last_date = df["date"].iloc[-1].strftime("%Y-%m-%d")
                logger.info(f"[TCBS] ✅ {ticker}: {len(df)} bars, last={last_close:,.0f} VND ({last_date})")
                return df

            except requests.exceptions.ConnectionError as e:
                last_error = e
                logger.warning(f"[TCBS] Connection error for {ticker} (attempt {attempt+1}): {e}")
                time.sleep(2 ** attempt)
            except requests.exceptions.Timeout as e:
                last_error = e
                logger.warning(f"[TCBS] Timeout for {ticker} (attempt {attempt+1})")
                time.sleep(2 ** attempt)
            except requests.exceptions.HTTPError as e:
                last_error = e
                logger.warning(f"[TCBS] HTTP {resp.status_code} for {ticker}: {e}")
                if resp.status_code >= 500:
                    time.sleep(2 ** attempt)
                else:
                    break
            except Exception as e:
                last_error = e
                logger.error(f"[TCBS] Unexpected error for {ticker}: {e}")
                break

        logger.error(f"[TCBS] ❌ Failed for {ticker} after {self.max_retries} attempts: {last_error}")
        return pd.DataFrame()

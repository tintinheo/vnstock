import aiohttp
import asyncio
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class SSIFetcher:
    def __init__(self, device_id: str):
        self.base_url = "https://iboard-api.ssi.com.vn"
        self.query_url = "https://iboard-query.ssi.com.vn"
        self.headers = {
            "device-id": device_id,
            "origin": "https://iboard.ssi.com.vn",
            "referer": "https://iboard.ssi.com.vn/",
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "accept-language": "vi"
        }

    async def fetch_ohlcv(self, session: aiohttp.ClientSession, ticker: str, resolution: str = "1D") -> pd.DataFrame:
        """EP-1: Fetch Historical Data"""
        # Note: In production, pass actual timestamps for 'from' and 'to'
        url = f"{self.base_url}/statistics/charts/history?resolution={resolution}&symbol={ticker}"
        
        try:
            async with session.get(url, headers=self.headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if not data or 't' not in data:
                        return pd.DataFrame()
                        
                    df = pd.DataFrame({
                        'Date': pd.to_datetime(data['t'], unit='s'),
                        'Open': data['o'],
                        'High': data['h'],
                        'Low': data['l'],
                        'Close': data['c'],
                        'Volume': data['v']
                    })
                    df.set_index('Date', inplace=True)
                    return df
                elif response.status in (429, 503):
                    logger.warning(f"Rate limited on {ticker}. Fallback to DNSE triggered in pipeline.")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Failed fetching OHLCV for {ticker}: {str(e)}")
            return pd.DataFrame()

    async def fetch_batch_ohlcv(self, tickers: List[str], resolution: str = "1D") -> Dict[str, pd.DataFrame]:
        """Fetch multiple tickers concurrently with a connection pool."""
        semaphore = asyncio.Semaphore(10) # SSI limit constraint
        
        async def fetch_with_sem(session, ticker):
            async with semaphore:
                return ticker, await self.fetch_ohlcv(session, ticker, resolution)

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_with_sem(session, ticker) for ticker in tickers]
            results = await asyncio.gather(*tasks)
            return {ticker: df for ticker, df in results if not df.empty}

    async def fetch_order_book(self, session: aiohttp.ClientSession, ticker: str) -> dict:
        """EP-4: Order Book for OFI and Anti-Manipulation checks"""
        url = f"{self.query_url}/le-table/stock/{ticker}?pageSize=50"
        try:
            async with session.get(url, headers=self.headers, timeout=5) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"Order book fetch failed for {ticker}: {str(e)}")
        return {}
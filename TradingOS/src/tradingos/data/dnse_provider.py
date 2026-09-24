"""DNSE LightSpeed intraday data provider.

Uses the DNSE chart API to fetch intraday OHLCV candles.
Requires dnse_api_key (Bearer token) set in config or DNSE_API_KEY env var.
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from ..utils.config import cfg

log = logging.getLogger(__name__)


class DnseProvider:
    """Intraday candle provider backed by the DNSE chart API."""

    def is_configured(self) -> bool:
        return bool(cfg.dnse_api_key)

    def fetch_intraday_candles(
        self,
        ticker: str,
        resolution: str = "1",
    ) -> pd.DataFrame | None:
        """Fetch intraday OHLCV candles from DNSE.

        Args:
            ticker: VN stock ticker, e.g. "HPG".
            resolution: Bar resolution string — "1", "5", "15", "60".

        Returns:
            DataFrame with columns open/high/low/close/volume and DatetimeIndex,
            or None on error / unconfigured.
        """
        if not self.is_configured():
            return None
        try:
            now = int(time.time())
            from_ts = now - 86_400  # ~1 trading day
            url = (
                f"{cfg.dnse_base}/history"
                f"?symbol={ticker}&resolution={resolution}"
                f"&from={from_ts}&to={now}"
            )
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {cfg.dnse_api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("s") != "ok":
                log.debug(f"DNSE API non-ok status for {ticker}: {data.get('s')}")
                return None
            df = pd.DataFrame(
                {
                    "open":   data["o"],
                    "high":   data["h"],
                    "low":    data["l"],
                    "close":  data["c"],
                    "volume": data["v"],
                },
                index=pd.to_datetime(data["t"], unit="s"),
            )
            return df if not df.empty else None
        except Exception as exc:
            log.debug(f"DNSE fetch_intraday_candles failed for {ticker}: {exc}")
            return None


dnse = DnseProvider()

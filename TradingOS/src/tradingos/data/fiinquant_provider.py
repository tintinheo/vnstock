"""FiinQuant realtime data provider.

Wraps the fiinquantx package (https://fiinquant.vn) for snapshot-mode
intraday bar data (1m) with buy/sell aggressor volume (bu/sd fields), and
order book snapshots (BidAsk).

WebSocket streaming is NOT used — Streamlit is single-threaded and requires
snapshot polling only.

Install:
    pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..utils.config import cfg

log = logging.getLogger(__name__)

_FIELDS_1M = ["open", "high", "low", "close", "volume", "bu", "sd", "fn"]


class FiinQuantProvider:
    """Snapshot-mode FiinQuant data provider (credentials from config)."""

    def __init__(self) -> None:
        self._client: Any = None

    def is_configured(self) -> bool:
        """Return True if credentials are present in config."""
        return bool(cfg.fiinquantx_username and cfg.fiinquantx_password)

    def _get_client(self) -> Any | None:
        """Lazy-init FiinSession client. Returns None if package not installed."""
        if self._client is not None:
            return self._client
        try:
            from fiinquantx import FiinSession  # type: ignore[import]

            self._client = FiinSession(
                username=cfg.fiinquantx_username,
                password=cfg.fiinquantx_password,
            ).login()
            return self._client
        except ImportError:
            log.debug("fiinquantx package not installed — FiinQuant provider unavailable")
            return None
        except Exception as exc:
            log.debug(f"FiinQuant login failed: {exc}")
            return None

    def fetch_bars(
        self,
        ticker: str,
        by: str = "1m",
        period: int = 60,
    ) -> pd.DataFrame | None:
        """Fetch intraday OHLCV + buy/sell aggressor volume (bu, sd).

        Args:
            ticker: VN stock ticker, e.g. "HPG".
            by: Bar resolution — "1m", "5m", "15m", etc.
            period: Number of bars to fetch.

        Returns:
            DataFrame with columns open/high/low/close/volume/bu/sd/fn,
            or None on any error.
        """
        if not self.is_configured():
            return None
        client = self._get_client()
        if client is None:
            return None
        try:
            event = client.Fetch_Trading_Data(
                realtime=False,
                tickers=[ticker],
                fields=_FIELDS_1M,
                by=by,
                period=period,
            )
            df: pd.DataFrame = event.get_data()
            if df is None or df.empty:
                return None
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as exc:
            log.debug(f"FiinQuant fetch_bars failed for {ticker}: {exc}")
            return None

    def fetch_orderbook(self, ticker: str) -> pd.DataFrame | None:
        """Fetch bid/ask order book snapshot.

        Returns:
            DataFrame with bid/ask volume levels, or None on any error.
        """
        if not self.is_configured():
            return None
        client = self._get_client()
        if client is None:
            return None
        try:
            bidask = client.BidAsk(tickers=[ticker], callback=None)
            df: pd.DataFrame = bidask.to_dataFrame()
            if df is None or df.empty:
                return None
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as exc:
            log.debug(f"FiinQuant fetch_orderbook failed for {ticker}: {exc}")
            return None


fiin = FiinQuantProvider()

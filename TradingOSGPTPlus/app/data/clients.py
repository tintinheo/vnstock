from io import StringIO
from typing import Callable

import pandas as pd
import requests

from app.config import Settings, get_settings
from app.data.cache import OhlcvCache
from app.data.normalizer import normalize_ohlcv
from app.data.universe import normalize_ticker
from app.errors import DataUnavailableError


class MarketDataClient:
    def __init__(self, settings: Settings | None = None, cache: OhlcvCache | None = None):
        self.settings = settings or get_settings()
        self.cache = cache or OhlcvCache(self.settings)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "VietnamAITradingOS/0.1 decision-support research",
                "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            }
        )

    def get_history(self, ticker: str) -> tuple[pd.DataFrame, dict[str, object]]:
        normalized = normalize_ticker(ticker)
        source_errors: list[str] = []
        for source in self.settings.sources:
            fetcher = self._fetcher_for(source)
            if fetcher is None:
                source_errors.append(f"{source}: adapter not implemented")
                continue
            try:
                frame = fetcher(normalized)
                metadata = {"source": source, "is_cached": False, "source_errors": source_errors.copy()}
                self.cache.put(normalized, frame, metadata)
                return frame, metadata
            except Exception as exc:
                source_errors.append(f"{source}: {exc}")

        cached = self.cache.get_valid(normalized)
        if cached:
            frame, metadata = cached
            metadata["source_errors"] = source_errors
            return frame, metadata
        raise DataUnavailableError(normalized, source_errors)

    def _fetcher_for(self, source: str) -> Callable[[str], pd.DataFrame] | None:
        source_lower = source.lower()
        if source_lower == "kbs":
            return self._fetch_kbs
        if source_lower == "cafef":
            return self._fetch_cafef
        if source_lower in {"vietstock", "fireant", "dnse"}:
            return self._backup_not_enabled(source)
        return None

    def _fetch_kbs(self, ticker: str) -> pd.DataFrame:
        url = f"https://kbbuddywts.kbsec.com.vn/iis-server/investment/stocks/{ticker}/data_day"
        response = self.session.get(url, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        records = _extract_records(payload)
        if not records:
            raise ValueError("empty response")
        raw = pd.DataFrame(records)
        return normalize_ohlcv(raw, ticker=ticker, source="KBS", unit_rule="actual_vnd")

    def _fetch_cafef(self, ticker: str) -> pd.DataFrame:
        url = f"https://s.cafef.vn/Lich-su-giao-dich-{ticker}-1.chn"
        response = self.session.get(url, timeout=self.settings.request_timeout_seconds)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        tables = pd.read_html(StringIO(response.text))
        candidates: list[pd.DataFrame] = []
        for table in tables:
            columns = " ".join(str(col).lower() for col in table.columns)
            if any(token in columns for token in ["ngay", "ngày", "date"]) and any(
                token in columns for token in ["dong", "đóng", "close"]
            ):
                candidates.append(table)
        if not candidates:
            raise ValueError("no historical price table found")
        raw = candidates[0]
        return normalize_ohlcv(raw, ticker=ticker, source="CafeF", unit_rule="thousands_to_vnd")

    def _backup_not_enabled(self, source: str) -> Callable[[str], pd.DataFrame]:
        def fetcher(_: str) -> pd.DataFrame:
            raise ValueError(f"{source} backup requires endpoint/terms validation before enabling")

        return fetcher


def _extract_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ["data", "data_day", "items", "result", "rows"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []


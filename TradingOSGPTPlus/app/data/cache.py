import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings, get_settings
from app.data.universe import normalize_ticker


class OhlcvCache:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_valid(self, ticker: str) -> tuple[pd.DataFrame, dict[str, Any]] | None:
        path = self._path(ticker)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            return None
        frame = pd.DataFrame(payload["data"])
        if frame.empty:
            return None
        frame["date"] = pd.to_datetime(frame["date"]).dt.date
        frame["fetched_at"] = pd.to_datetime(frame["fetched_at"], utc=True)
        for col in ["open", "high", "low", "close", "value"]:
            if col in frame:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype("int64")
        metadata = payload.get("metadata", {})
        metadata["source"] = "cache"
        metadata["is_cached"] = True
        return frame, metadata

    def put(self, ticker: str, frame: pd.DataFrame, metadata: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.settings.cache_ttl_hours)
        serializable = frame.copy()
        serializable["date"] = serializable["date"].astype(str)
        serializable["fetched_at"] = serializable["fetched_at"].astype(str)
        payload = {
            "ticker": normalize_ticker(ticker),
            "cached_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "metadata": metadata,
            "data": serializable.to_dict(orient="records"),
        }
        path = self._path(ticker)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    def _path(self, ticker: str) -> Path:
        return self.settings.cache_dir / f"{normalize_ticker(ticker)}.ohlcv.json"


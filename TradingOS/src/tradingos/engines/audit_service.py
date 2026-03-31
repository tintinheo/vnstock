"""Audit Service — structured event logging + query (SRS §3.5)."""
from __future__ import annotations

import json
from datetime import datetime

import pandas as pd

from ..data.cache import cache
from ..utils.logging import get_logger

log = get_logger("audit_service")


class AuditService:
    def log_event(
        self,
        event_type: str,
        ticker: str,
        action: str,
        mfpm_score: int = 0,
        sms_raw: int = 0,
        confidence: str = "—",
        extra: dict | None = None,
    ) -> None:
        """Write a structured audit record to DuckDB."""
        record = {
            "event_type": event_type,
            "ticker": ticker,
            "action": action,
            "mfpm_score": mfpm_score,
            "sms_raw": sms_raw,
            "confidence": confidence,
        }
        if extra:
            record.update(extra)
        cache.put_audit(record)
        log.info(f"AUDIT [{event_type}] {ticker} {action} score={mfpm_score}")

    def query_events(
        self,
        ticker: str | None = None,
        event_type: str | None = None,
        days_back: int = 30,
        limit: int = 200,
    ) -> pd.DataFrame:
        """Query audit log. Returns DataFrame."""
        return cache.query_audit(
            ticker=ticker,
            event_type=event_type,
            days_back=days_back,
            limit=limit,
        )

    def summary_stats(self, days_back: int = 30) -> dict:
        """Aggregate stats from audit log."""
        df = self.query_events(days_back=days_back)
        if df.empty:
            return {"total_events": 0, "tickers_profiled": 0, "action_breakdown": {}}

        stats = {
            "total_events": len(df),
            "tickers_profiled": df["ticker"].nunique() if "ticker" in df.columns else 0,
            "action_breakdown": {},
        }
        if "action" in df.columns:
            stats["action_breakdown"] = df["action"].value_counts().to_dict()
        return stats

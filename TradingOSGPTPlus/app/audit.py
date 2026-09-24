import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from filelock import FileLock

from app.config import Settings, get_settings
from app.models import AuditEvent
from app.utils import json_safe


class AuditLogger:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.audit_dir.mkdir(parents=True, exist_ok=True)

    def write(self, event: AuditEvent) -> str:
        path = self._path_for(event.ts)
        lock = FileLock(str(path) + ".lock")
        payload = json_safe(event.model_dump())
        with lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return event.id

    def read_latest(self, limit: int = 100) -> list[dict[str, Any]]:
        files = sorted(self.settings.audit_dir.glob("audit-*.jsonl"), reverse=True)
        rows: list[dict[str, Any]] = []
        for path in files:
            with path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
            for line in reversed(lines):
                if line.strip():
                    rows.append(json.loads(line))
                if len(rows) >= limit:
                    return rows
        return rows

    def _path_for(self, ts: datetime) -> Path:
        return self.settings.audit_dir / f"audit-{ts.date().isoformat()}.jsonl"


@contextmanager
def audited(
    action: str,
    ticker: str | None = None,
    params: dict[str, Any] | None = None,
    logger: AuditLogger | None = None,
) -> Iterator[dict[str, Any]]:
    audit_logger = logger or AuditLogger()
    started = time.perf_counter()
    context: dict[str, Any] = {"audit_id": str(uuid.uuid4())}
    try:
        yield context
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        audit_logger.write(
            AuditEvent(
                id=context["audit_id"],
                ts=datetime.now(timezone.utc),
                action=action,
                ticker=ticker,
                params=params or {},
                status="failure",
                duration_ms=elapsed_ms,
                result_summary={"error": str(exc)},
            )
        )
        raise
    else:
        elapsed_ms = (time.perf_counter() - started) * 1000
        audit_logger.write(
            AuditEvent(
                id=context["audit_id"],
                ts=datetime.now(timezone.utc),
                action=action,
                ticker=ticker,
                params=params or {},
                status=context.get("status", "success"),
                duration_ms=elapsed_ms,
                data_source=context.get("data_source"),
                signal=context.get("signal"),
                confidence=context.get("confidence"),
                result_summary=context.get("result_summary"),
            )
        )


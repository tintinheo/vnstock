"""Fail CI when the requirement traceability ledger is incomplete or stale."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "traceability" / "requirements.v1.json"
FIELDS = {"id", "requirement", "module", "test", "evidence", "status"}
STATUSES = {"PLANNED", "IMPLEMENTED", "TESTED_OFFLINE", "IMPLEMENTED_NOT_LIVE_VALIDATED", "VALIDATED_LIVE", "BLOCKED"}


def validate_traceability(root: Path = ROOT, ledger_path: Path = LEDGER) -> list[str]:
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("unsupported traceability schema_version")
    seen: set[str] = set()
    for index, item in enumerate(data.get("requirements", [])):
        label = item.get("id", f"row {index}")
        missing = FIELDS - item.keys()
        if missing:
            errors.append(f"{label}: missing fields {sorted(missing)}")
            continue
        if label in seen:
            errors.append(f"{label}: duplicate requirement id")
        seen.add(label)
        if item["status"] not in STATUSES:
            errors.append(f"{label}: invalid status {item['status']}")
        for field in ("module", "test", "evidence"):
            target = root / item[field].split("#", 1)[0]
            if not target.is_file():
                errors.append(f"{label}: {field} does not exist: {item[field]}")
    if not data.get("requirements"):
        errors.append("traceability ledger has no requirements")
    return errors


if __name__ == "__main__":
    problems = validate_traceability()
    if problems:
        raise SystemExit("Traceability check failed:\n" + "\n".join(f"- {p}" for p in problems))
    print("Traceability check passed")

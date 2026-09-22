"""Shared data-quality publication gate for all recommendation engines."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..data.schemas import ActionabilityStatus, CapabilityStatus, DataContext

_BLOCKING = {
    CapabilityStatus.MISSING,
    CapabilityStatus.FETCH_FAILED,
    CapabilityStatus.NOT_CONFIGURED,
    CapabilityStatus.DQ_FAILED,
}


def apply_publication_gate(
    proposed_action: str,
    contexts: list[DataContext],
    *,
    required_capabilities: tuple[str, ...] = ("OHLCV",),
    max_staleness: timedelta = timedelta(hours=24),
    now: datetime | None = None,
) -> tuple[str, ActionabilityStatus]:
    """Prevent an actionable recommendation when required evidence is unsafe.

    The proposed score is retained by callers, but the public action is replaced
    with ``NO_RECOMMENDATION``.  This makes provider failures observable instead
    of silently converting them into neutral market evidence.
    """
    now = now or datetime.now(timezone.utc)
    by_capability = {context.capability: context for context in contexts}
    reasons: list[str] = []

    for capability in required_capabilities:
        context = by_capability.get(capability)
        if context is None:
            reasons.append(f"{capability}: capability missing")
            continue
        if context.status in _BLOCKING:
            reasons.append(f"{capability}: {context.status.value}")
        if capability == "OHLCV" and not context.raw_snapshot_hash:
            reasons.append("OHLCV: raw snapshot hash missing")
        if context.status == CapabilityStatus.STALE_CACHE:
            age = now - context.fetched_at if context.fetched_at else None
            if age is None or age > max_staleness:
                reasons.append("OHLCV: stale beyond policy")
        if context.dq_status == "FAILED":
            reasons.append(f"{capability}: DQ_FAILED")

    actionable = not reasons
    published_action = proposed_action if actionable else "NO_RECOMMENDATION"
    return published_action, ActionabilityStatus(
        actionable=actionable,
        action="PUBLISHED" if actionable else "NO_RECOMMENDATION",
        reasons=list(dict.fromkeys(reasons)),
    )

"""Safety invariants for data-lineage-aware recommendation publication."""
from datetime import datetime, timedelta, timezone

import pytest

from tradingos.data.schemas import CapabilityStatus, DataContext
from tradingos.engines.publication_gate import apply_publication_gate


def _context(status: CapabilityStatus, **overrides) -> DataContext:
    now = datetime.now(timezone.utc)
    values = {
        "provider": "TEST",
        "capability": "OHLCV",
        "requested_at": now,
        "fetched_at": now,
        "data_as_of": now,
        "freshness_status": "FRESH",
        "raw_snapshot_hash": "abc123",
        "canonical_revision": "ohlcv-v1",
        "dq_status": "PASSED",
        "status": status,
    }
    values.update(overrides)
    return DataContext(**values)


@pytest.mark.parametrize("proposed", ["BUY", "STRONG_BUY"])
def test_stale_beyond_policy_cannot_publish_buy(proposed):
    context = _context(
        CapabilityStatus.STALE_CACHE,
        fetched_at=datetime.now(timezone.utc) - timedelta(days=2),
        freshness_status="STALE",
    )
    action, status = apply_publication_gate(
        proposed, [context], max_staleness=timedelta(hours=24)
    )
    assert action == "NO_RECOMMENDATION"
    assert not status.actionable


@pytest.mark.parametrize("provider_status", [CapabilityStatus.FETCH_FAILED])
def test_fetch_failure_cannot_publish_buy(provider_status):
    action, status = apply_publication_gate("BUY", [_context(provider_status)])
    assert action == "NO_RECOMMENDATION"
    assert "FETCH_FAILED" in " ".join(status.reasons)


def test_missing_raw_hash_cannot_publish_strong_buy():
    action, status = apply_publication_gate(
        "STRONG_BUY", [_context(CapabilityStatus.SUCCESS, raw_snapshot_hash=None)]
    )
    assert action == "NO_RECOMMENDATION"
    assert not status.actionable


def test_dq_failure_cannot_publish_buy():
    action, status = apply_publication_gate(
        "BUY", [_context(CapabilityStatus.DQ_FAILED, dq_status="FAILED")]
    )
    assert action == "NO_RECOMMENDATION"
    assert not status.actionable


def test_valid_lineage_preserves_buy():
    action, status = apply_publication_gate(
        "BUY", [_context(CapabilityStatus.SUCCESS)]
    )
    assert action == "BUY"
    assert status.actionable

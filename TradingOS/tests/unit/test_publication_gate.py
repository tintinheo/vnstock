"""Safety invariants for data-lineage-aware recommendation publication."""
from datetime import datetime, timedelta, timezone

import pytest
import pandas as pd

from tradingos.data.fetcher import _ohlcv_result
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


def test_fetch_result_preserves_dq_failure_and_original_data():
    frame = pd.DataFrame({
        "date": [datetime.now(timezone.utc).date()],
        "open": [10.0], "high": [9.0], "low": [11.0], "close": [10.0],
        "volume": [100],
    })
    result = _ohlcv_result(
        frame, "TEST", CapabilityStatus.SUCCESS, datetime.now(timezone.utc)
    )
    assert result.context.status == CapabilityStatus.DQ_FAILED
    assert result.context.dq_status == "FAILED"
    pd.testing.assert_frame_equal(result.data, frame)


def test_empty_provider_response_is_missing_not_neutral_data(monkeypatch):
    from tradingos.data import fetcher

    monkeypatch.setattr(fetcher.cache, "get_ohlcv", lambda *args: pd.DataFrame())
    monkeypatch.setattr(fetcher, "_fetch_ohlcv_ssi", lambda *args: pd.DataFrame())
    monkeypatch.setattr(fetcher, "_fetch_ohlcv_dnse", lambda *args: pd.DataFrame())
    result = fetcher.fetch_ohlcv("VCB", use_cache=False)
    assert result.context.status == CapabilityStatus.MISSING
    assert result.data.empty


def test_provider_exception_is_fetch_failed(monkeypatch):
    from tradingos.data import fetcher

    def fail(*args):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(fetcher, "_fetch_ohlcv_ssi", fail)
    monkeypatch.setattr(fetcher, "_fetch_ohlcv_dnse", fail)
    result = fetcher.fetch_ohlcv("VCB", use_cache=False)
    assert result.context.status == CapabilityStatus.FETCH_FAILED
    assert "provider unavailable" in " ".join(result.context.degraded_reasons)

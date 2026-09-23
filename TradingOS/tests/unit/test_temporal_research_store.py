"""Temporal leakage tests for governed research inputs."""
from datetime import date, datetime, timedelta, timezone

import pytest

from tradingos.data.research_store import ResearchStore
from tradingos.data.schemas import (
    CorporateAction,
    FinancialObservation,
    OfficialIndexObservation,
    ProviderLineage,
    UniverseMembership,
)

NOW = datetime(2026, 1, 20, tzinfo=timezone.utc)
LINEAGE = ProviderLineage(
    provider_id="official", provider_revision="p1",
    source_snapshot_id="sha256:snapshot", raw_hash="sha256:raw",
)


def test_late_membership_cannot_enter_features():
    store = ResearchStore()
    store.append("universe_membership", UniverseMembership(
        index_code="VN100", symbol="AAA", effective_from=NOW - timedelta(days=20),
        effective_to=None, review_source="HOSE review", raw_hash="h",
        ingested_at=NOW + timedelta(minutes=1), revision_id="u1",
    ))
    view = store.begin_run(NOW, {"universe_membership": "u1"})
    assert view.membership("VN100") == ()


def test_later_report_revision_cannot_enter_features():
    store = ResearchStore()
    common = dict(symbol="AAA", metric="revenue", value=10, period_end=date(2025, 12, 31),
                  lineage=LINEAGE)
    store.append("financials", FinancialObservation(
        **common, publication_time=NOW - timedelta(days=1), ingested_at=NOW - timedelta(hours=1),
        revision_id="f1",
    ))
    store.append("financials", FinancialObservation(
        **{**common, "value": 99}, publication_time=NOW + timedelta(days=1),
        ingested_at=NOW + timedelta(days=1), revision_id="f2",
    ))
    view = store.begin_run(NOW, {"financials": "f1"})
    view.coverage(["AAA"], ["financials"])
    assert [row.value for row in view.feature_rows("financials")] == [10]


def test_late_corporate_action_cannot_enter_features():
    store = ResearchStore()
    store.append("corporate_actions", CorporateAction(
        symbol="AAA", ex_date=date(2026, 1, 21), announced_at=NOW + timedelta(seconds=1),
        action_type="DIVIDEND", review_source="VSDC", raw_hash="h",
        ingested_at=NOW + timedelta(seconds=2), revision_id="c1",
    ))
    view = store.begin_run(NOW, {"corporate_actions": "c1"})
    assert view.corporate_actions() == ()


def test_proxy_index_requires_explicit_degraded_status():
    store = ResearchStore()
    row = OfficialIndexObservation(
        index_code="VNINDEX", observed_at=NOW, value=1200, ingested_at=NOW,
        revision_id="i1", lineage=LINEAGE, is_official=False,
    )
    with pytest.raises(ValueError, match="degraded_status"):
        store.append_market_index(row)


def test_features_require_prior_coverage_report_and_revision_is_immutable():
    store = ResearchStore()
    view = store.begin_run(NOW, {"financials": "f1"})
    with pytest.raises(RuntimeError, match="coverage"):
        view.feature_rows("financials")
    with pytest.raises(TypeError):
        view.revision.capability_revisions["financials"] = "f2"
    report = view.coverage(["AAA"], ["financials"])
    assert report.has_blocking_gaps
    assert report.to_frame().iloc[0]["status"] == "MISSING"

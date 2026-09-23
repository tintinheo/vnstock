"""Point-in-time research data store and immutable run revisions.

The store deliberately keeps all revisions.  A research run first obtains a
``CanonicalRevision`` and all subsequent reads must go through the resulting
``RevisionView``.  This makes accidental "latest data" reads during a backtest
impossible at the API boundary.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from .schemas import CorporateAction, FinancialObservation, OfficialIndexObservation


@dataclass(frozen=True)
class CanonicalRevision:
    """Content-addressed, immutable input manifest for one research run."""

    revision_id: str
    created_at: datetime
    decision_time: datetime
    capability_revisions: Mapping[str, str]

    @classmethod
    def create(
        cls, decision_time: datetime, capability_revisions: Mapping[str, str]
    ) -> "CanonicalRevision":
        if decision_time.tzinfo is None:
            raise ValueError("decision_time must be timezone-aware")
        manifest = dict(sorted(capability_revisions.items()))
        if not manifest or any(not key or not value for key, value in manifest.items()):
            raise ValueError("every research capability must pin a revision")
        payload = json.dumps(
            {"decision_time": decision_time.isoformat(), "revisions": manifest},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return cls(
            revision_id=hashlib.sha256(payload).hexdigest(),
            created_at=datetime.now(timezone.utc),
            decision_time=decision_time,
            capability_revisions=MappingProxyType(manifest),
        )


@dataclass(frozen=True)
class CoverageReport:
    revision_id: str
    generated_at: datetime
    rows: tuple[Mapping[str, Any], ...]

    @property
    def has_blocking_gaps(self) -> bool:
        return any(row["status"] == "MISSING" for row in self.rows)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


class ResearchStore:
    """Append-only in-memory canonical store suitable for tests and pipelines."""

    def __init__(self) -> None:
        self._rows: dict[str, list[Any]] = {}

    def append(self, capability: str, row: Any) -> None:
        if not getattr(row, "revision_id", None):
            raise ValueError("canonical rows require revision_id")
        self._rows.setdefault(capability, []).append(row)

    def append_market_index(self, row: OfficialIndexObservation) -> None:
        if not row.is_official and not row.degraded_status:
            raise ValueError("proxy market series must carry degraded_status")
        self.append("market_index", row)

    def begin_run(
        self, decision_time: datetime, capability_revisions: Mapping[str, str]
    ) -> "RevisionView":
        revision = CanonicalRevision.create(decision_time, capability_revisions)
        return RevisionView(self, revision)


class RevisionView:
    """The only supported feature-input reader; fixed to a canonical revision."""

    def __init__(self, store: ResearchStore, revision: CanonicalRevision) -> None:
        self._store = store
        self.revision = revision
        self._coverage_report: CoverageReport | None = None

    def _visible(self, capability: str) -> list[Any]:
        pinned = self.revision.capability_revisions.get(capability)
        if pinned is None:
            raise KeyError(f"capability {capability!r} is not pinned by this run")
        decision = self.revision.decision_time
        visible = []
        for row in self._store._rows.get(capability, ()):
            if row.revision_id != pinned or row.ingested_at > decision:
                continue
            publication = getattr(row, "publication_time", None)
            announcement = getattr(row, "announced_at", None)
            if publication is not None and publication > decision:
                continue
            if announcement is not None and announcement > decision:
                continue
            visible.append(row)
        return visible

    def financials(self) -> tuple[FinancialObservation, ...]:
        return tuple(self._visible("financials"))

    def corporate_actions(self) -> tuple[CorporateAction, ...]:
        return tuple(self._visible("corporate_actions"))

    def membership(self, index_code: str) -> tuple[Any, ...]:
        decision = self.revision.decision_time
        return tuple(
            row for row in self._visible("universe_membership")
            if row.index_code == index_code
            and row.effective_from <= decision
            and (row.effective_to is None or decision < row.effective_to)
        )

    def coverage(self, symbols: Sequence[str], capabilities: Iterable[str]) -> CoverageReport:
        rows: list[Mapping[str, Any]] = []
        for capability in capabilities:
            available = self._visible(capability)
            for symbol in symbols:
                observations = [r for r in available if getattr(r, "symbol", symbol) == symbol]
                times = [
                    getattr(r, "period_end", getattr(r, "observed_at", None))
                    for r in observations
                ]
                rows.append(MappingProxyType({
                    "symbol": symbol,
                    "capability": capability,
                    "from": min(times) if times else None,
                    "to": max(times) if times else None,
                    "observation_count": len(observations),
                    "missing": len(observations) == 0,
                    "status": "AVAILABLE" if observations else "MISSING",
                }))
        report = CoverageReport(
            self.revision.revision_id, datetime.now(timezone.utc), tuple(rows)
        )
        self._coverage_report = report
        return report

    def feature_rows(self, capability: str) -> tuple[Any, ...]:
        """Return pinned PIT input only after coverage has been published."""
        if self._coverage_report is None:
            raise RuntimeError("coverage/missingness report must run before feature computation")
        covered = {row["capability"] for row in self._coverage_report.rows}
        if capability not in covered:
            raise RuntimeError(f"coverage/missingness was not reported for {capability!r}")
        return tuple(self._visible(capability))

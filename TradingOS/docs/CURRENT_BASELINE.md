# TradingOS current baseline

**Baseline ID:** `tradingos-governed-providers-v1`
**Effective date:** 2026-09-22
**Status:** active; this is the single baseline decision record.

## Maintained package decision

`src/tradingos` is the only maintained Python package in this repository.
`src/vnquant` is not present and is neither a delivery target nor an alternative
package name. Historical BRD/SRD entries that describe `src/vnquant`, its tests,
or an “SSI-free” implementation are superseded and are not current evidence.

## Provider baseline

SSI is retained as a market-data provider. It is not described as removed or as
making the system “SSI-free”. Provider selection is governed by the versioned
registry at `config/providers.v1.json`; being implemented or returning HTTP 200
does not constitute admission. The registry records provider role, capabilities,
admission status, and an evidence reference.

The current runtime in `src/tradingos/data/fetcher.py` attempts SSI for daily
OHLCV and DNSE as fallback. This behavior predates the registry and has not been
validated against live provider contracts in this repository. Consequently all
automated providers remain `CANDIDATE`, and runtime data must not be represented
as contract-approved or production-validated merely because a fetch succeeds.

## Governance artifacts

| Artifact | Authority |
|---|---|
| `docs/CURRENT_BASELINE.md` | Package and architecture baseline (this file) |
| `config/providers.v1.json` | Machine-readable provider admission registry |
| `docs/PROVIDER-VALIDATION.md` | Provider contract, rights, credentials, retention, and actual validation evidence |
| `traceability/requirements.v1.json` | Requirement → module → test → evidence → status ledger |

Changes to package identity, provider admission, or validation status must update
these artifacts and pass `python scripts/check_traceability.py` in the same commit.

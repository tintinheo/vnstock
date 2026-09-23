# Provider validation evidence

**Evidence version:** 1.0 · **assessed:** 2026-09-22

This record states what the repository actually proves. No live-provider or
contract validation was performed for this baseline.

| Provider | Contract / data-use rights | Credential policy | Retention policy | Actual validation |
|---|---|---|---|---|
| SSI iBoard | Contract and authorization for automated access, derived storage, redistribution, and commercial use are **not evidenced**. Candidate use is limited to evaluation pending written authorization. | Device IDs/tokens must come from environment variables or an approved secret store; never commit, log, persist in cache metadata, or place in URLs. Least privilege and rotation are required. | **Not approved.** Retain no raw response beyond transient processing until written terms define permitted fields and duration; canonical cache is evaluation-only and must be purgeable. | Adapter exists and tests may mock it; **no live contract, schema, rights, or accuracy validation evidence is committed**. `CANDIDATE`. |
| DNSE | Public/API availability does not establish storage or redistribution rights. Authorized terms and capability semantics are **not evidenced**. | Bearer keys come from environment variables or an approved secret store and must be redacted from logs/errors. Read-only market-data scope only. | **Not approved.** Raw/canonical retention awaits written terms; evaluation data must be purgeable. | Adapter exists; **no committed live connectivity, reconciliation, or rights validation**. `CANDIDATE`. |
| FiinQuant | Use requires the applicable account/subscription terms; storage, derived-use, and redistribution rights are **not evidenced** here. | Username/password come from environment variables or an approved secret store; never commit or log them. | **Not approved.** Snapshot data is transient until subscription terms are recorded. | Optional adapter exists; package/login/live payload are **not validated in repository evidence**. `CANDIDATE`. |
| CafeF | Public visibility is not permission for automated collection or redistribution. No production API contract is evidenced. | No credential is currently defined; adding one requires secret-store handling. | **Not approved** for automated raw retention. | Configuration reference only; no governed production adapter validation. `REFERENCE_ONLY`. |

## Admission contract

A provider may move to `ADMITTED` only when evidence records: authorized access
and endpoint contract; field/unit/time-zone/corporate-action semantics; allowed
purposes and redistribution; raw and derived retention/deletion periods;
credential owner, scope, rotation and revocation; live schema samples; DQ and
cross-source reconciliation; and an approver/date. Missing evidence fails closed.

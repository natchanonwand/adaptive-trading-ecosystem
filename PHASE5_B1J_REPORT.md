# Phase 5B.1J - Reconciled result publication and functional acceptance closure

Status: COMPLETE / PASS. Phase 5B functional acceptance: CLOSED.

## Prerequisites and preserved semantics

Frozen baseline phase5b-tooling-v0.1.12 resolves to
657f0236d5b3e88db36848efb279b06047d09eb8. HEAD and origin/main matched,
the tree was clean before implementation, all prior tags remain unchanged.

Original BaselineRun: aebb719c-6738-4b1a-a323-3f405ed512fe.
Original immutable execution outcome: BLOCKED_REAL_TICKS_UNAVAILABLE.
Reconciliation: REAL_TICK_COVERAGE_VERIFIED_100; 100% real ticks,
53,200,842 ticks, 34,651 bars; no generated-tick fallback observed.
No native rerun, no new BaselineRun, no BaselineResult insertion.
Gold Scalper native executions remain exactly one. There are three historical
BaselineRuns in the database in total, including exactly one real Gold Scalper
acceptance run. All seven pre-existing application tables compare unchanged.

## Publication architecture

New workbench.reconciled_results is separate from baseline_results.
The additive 0003_reconciled_results migration creates a unique run reference.
An offline publish operation locks the original run, independently recomputes
the assessment from preserved evidence, requires 100% real-tick coverage and
successful parser validation, and inserts one publication. It never transitions
the run or calls a native process. Repeating publication compares and returns
the same persisted record. A conflicting publication fails closed.

The canonical content hash includes semantic schema, normalized metrics,
provenance and parser source identity; no publication timestamp, process ID or
temporary path is introduced. A UUIDv5 derives from this content identity.
Readback independently verifies identity. Existing BaselineResult invariants
remain intact. The API returns separate run, result and publication fields.

Publication ID: b6a9c561-e67d-5f5e-9cff-c58c8ca3925e

Publication identity: e1d01c152831d1fe7f3a0b9736339cba0e961dbcd7130ea7d57967c6f13a5cf2

Publication state: PUBLISHED; provenance: POST_RUN_RECONCILIATION.

## Immutable provenance

| Link | Identity |
| --- | --- |
| Candidate | d5508913-c5d6-4f97-99e2-0be7e859b84a |
| BaselineConfiguration | 4a6d8cc7-59ef-474e-8eff-feec6d1658de |
| Configuration identity | 2e31959d4f4b4e63151c2b1e7be1c3eb4058a06348b163a89d2950f4d271edfc |
| Execution plan | 6178e755b74ff71da2eca2f8af2333ee867e27378b689edb3931e1d2c5c8de35 |
| Original run manifest | 0e75aef15a1b9ee72d70b39a7593e0a49937e237fa05b0d0ae296c3e4e92ea7e |
| Reconciliation | b4fe6d5c7b8d05c19d1f79acbf2f1f413c44967c793ca28ea99128144cac9d64 |
| Parser source | a0318ee699ae2e1905424ba90c8a962eb656654e7e2c3177270997b497c0b04f |
| Original parsed result | 1d63190e84549d2083cd863a7ffbf082946e495b0e9c95d88a8108a3339712f4 |
| Native source report | eb855831763c4b45a5463518b2e22f743146a9808b9b6ff4d67178c56516bc42 |
| Stored UTF-8 report | d36024464fcd14606c243c8a29441898fa4543f2b09f2af5ec51295658496eed |

Native-source identity is supported by the immutable manifest provenance.
Original native report encoding bytes were NOT retained byte-for-byte and
cannot be independently rehashed now. The retained UTF-8 report is separately
hashed and unchanged. The publication and UI explicitly retain this distinction.

## Supported observations

| Metric | Published value |
| --- | --- |
| Trades | 0 |
| Net profit | 0.00 USD |
| Balance drawdown | 0.00 (0.00%) |
| Equity drawdown | 0.00 (0.00%) |
| Win rate | null |
| Profit factor / expected payoff / trade averages | null (zero denominator) |

The drawdown fields retain the existing parser's amount/percentage representation.
Zero trades is valid, not a parser/tester failure or performance judgment.
Undefined ratios and averages remain null rather than zero; no absent metric
is invented. The original parsed representation is preserved separately.

## API and Workbench

Readback and Workbench verification PASS. The original blocked execution outcome
is displayed separately from the 100% real-tick reconciliation and PUBLISHED
post-run result. Null values display as an em dash, not 0%.
Execution strategy INSTALLED_PROFILE_REFERENCE and full original started_at /
completed_at timestamps are visible. No broad redesign was performed.
No readiness check, tester launch, new attempt, or configuration edit was triggered.

## Validation

| Gate | Result |
| --- | --- |
| Backend | PASS: 1438 |
| PostgreSQL/integration (included in backend) | PASS: 289 |
| Frontend | PASS: 106 |
| Ruff / formatting / strict mypy / secrets | PASS |
| Frontend typecheck / lint / format / production build | PASS |
| Additive migrations / scope / Git-ignore / frozen lineage | PASS |
| Frozen evidence | PASS: 1,044 byte-identical files |
| Historical/acceptance/reconciliation preservation | PASS: 1,603 files unchanged |
| Seven historical DB tables / original run / configuration | PASS: unchanged |
| Publication repeated in separate transactions | PASS: same ID/content, one row |
| Publication independent readback / Workbench | PASS |
| git diff --check | PASS |

Six new integration cases cover full/partial/unknown proof, zero/nonzero trades,
immutable history and evidence, no native execution/new run, exact provenance,
idempotency, rejection of altered assessment, and actual HTTP readback.
One new frontend case covers blocked-versus-reconciled display, zero/null values,
strategy, timestamps and no launch. Existing migration test only advances its
expected baseline schema revision; assertions are retained.

Gate log: .local/phase5_b1j/full-gate.log
Gate SHA-256: 54c3c6000eab0c0df865bc255d1ddb23611b8271e118074b21d632ace4bb4175
Runtime audit: .local/phase5_b1j/publication-readback.json,
preservation-after.json, workbench-verification.json, final-verification.json.
These are Git-ignored; raw reports, account material and runtime files are not tracked.

## Files changed (10)

- PHASE5_B1J_REPORT.md
- dashboard/src/workbench/BaselinePanel.tsx
- dashboard/tests/baseline.test.tsx
- migrations/baseline/versions/0003_reconciled_results.py
- scripts/verify_phase5_b_scope.py
- src/trading_ecosystem/tester/api.py
- src/trading_ecosystem/tester/checkpoint.py
- src/trading_ecosystem/tester/publication.py
- tests/integration/test_baseline.py
- tests/integration/test_publication.py

## Limits and deviations

No scope deviations. The first test invocation used the wrong database target
and was rejected by the test safety guard before fixtures ran; corrected to the
local maintenance database. Intermediate checks found a test import typing issue,
new UI punctuation encoding, and Git SHA annotation placement; all corrected.
A standalone frontend format check without the frozen Windows newline option
flagged existing CRLF files; no frozen files were rewritten. Final verification
uses the unchanged gate's existing newline-aware configuration.

Native report byte-retention limitation remains explicit. Acceptance closure is
for execution/evidence publication only, not strategy quality, licensing rights
beyond recorded evidence, optimization, or live-trading qualification.
No Phase 5C, rerun, commit, tag or push. HEAD remains the required frozen baseline.

# Phase 5B.1F — External candidate qualification and safe adapter readiness

Required baseline: `phase5b-tooling-v0.1.8` at
`55071a4f8be825f5aef9d920d3182ef241f2b158`.
The preceding Phase 5B.1E freeze committed exactly its six authorized files and was pushed.
Its annotated tag object is `ee92d9a1c9f415f9477f36c965e08bf7a6924a7b`.
All 19 earlier tag objects, 1,044 frozen evidence files, 1,483 historical evidence files,
two BaselineConfigurations and two BaselineRuns were verified unchanged after that freeze.

## Qualification outcome

Candidate status: **BLOCKED_CANDIDATE_INGESTION_MODEL**.
Qualification implementation: **COMPLETE** (precise blocker established).
Complete Phase 5B verification gate: **PASS**.
Native candidate attempts: **0**. Infrastructure probes: **0**.
No BaselineRun or BaselineResult was created. MT5 was not launched.

| Layer | Observed result |
| --- | --- |
| Existing project | Gold Scalper PRO Acceptance |
| Project ID | 1b55ae30-d498-4e75-aa4e-74fb97bf62e9 |
| Candidate ID | d5508913-c5d6-4f97-99e2-0be7e859b84a |
| Artifact ID | a8d06843-bb35-4471-9b46-66746cda30cf |
| Source/authorization | VERIFIED_USER_ATTESTATION; MARKETPLACE_AUTHORIZED |
| Authorization event | 5593e28a-796e-45cc-8093-3c65c169e9ef, revision 1, reused |
| Artifact verification | VERIFIED; recomputed uploaded and installed file hashes match persisted SHA-256 |
| Ingestion mode | AUTHORIZED_MT5_INSTALLED_EA |
| Installed representation | Market\Gold Scalper for MT5 EA.ex5, in the pinned profile |
| Research environment | BOOTSTRAP_READY_AS_OBSERVED from immutable Phase 5B.1E evidence |
| Account environment | DEMO; Exness-MT5Trial14; build 6230 |
| BaselineConfiguration | 4a6d8cc7-59ef-474e-8eff-feec6d1658de, reused unchanged |
| Declared license | UNKNOWN |
| Declared tester access | UNKNOWN |
| Observed tester access | UNKNOWN |
| Current-phase execution result | NOT_EXECUTED |
| Candidate execution readiness | BLOCKED_CANDIDATE_INGESTION_MODEL |

Authorization was read from the Workbench database, not inferred from filename/hash or an
installed file. It remains a user attestation, not vendor verification. Both pre-existing
initialization-failed runs remain historical observations; they do not prove license denial.

## Precise adapter boundary

The existing execution adapter writes candidate bytes into a new portable runtime and invokes
that portable terminal. Its environment loader remains fail-closed. It does not support an
installed Marketplace Expert reference in the pinned authenticated profile, nor consume the
verified research account binding. Passing the protected candidate through the upload/copy
route would not establish the required execution representation.

The qualification therefore preserves this specific blocker:
`INSTALLED_EA_REFERENCE_AND_VERIFIED_ACCOUNT_BINDING_NOT_SUPPORTED_BY_EXECUTION_ADAPTER`.
No protected file was copied, decrypted, patched, normalized, installed, or executed.
The artifact was only read to recompute its hash. UNKNOWN declarations did not cause the blocker.

## Exact binding and config dry-run

The immutable proposal binds the current project/candidate/artifact, the exact authorization
attestation, persisted configuration identity, terminal executable/profile/hash, verified DEMO
account binding, frozen probe identity/hash, ingestion representation, report/evidence paths,
native configuration hash and fixed lifecycle. Its canonical SHA-256 is in ignored
`.local/phase5_b1f/qualification.json`.

Requalification from the database/files with the same qualification namespace returned the
identical binding. A changed candidate, artifact, configuration, account/environment or path
changes the binding and is rejected by binding verification. A saved binding is a proposal,
not a bearer capability or permission to execute.

The native configuration dry-run is stored as `.local/phase5_b1f/candidate-config.dry-run.txt`.
It validates the installed Expert relative path and these unchanged inputs:

| Field | Value |
| --- | --- |
| Symbol / Period / Model | XAUUSDm / M5 / 4 (real ticks) |
| From / To | 2026-01-01 / 2026-06-30 |
| Deposit / Currency / Leverage | 300 / USD / 1:100 |
| Inputs | TESTER_DEFAULTS; no SET file |
| Optimization / Forward / Remote / Cloud | Disabled |
| AutoTrading / DLL imports / startup Expert | Disabled / disabled / empty |
| Timeout | 600 seconds; fixed owned-process lifecycle, no adaptive retry |
| Report | Unique qualification-UUID .htm under the pinned native data root; not created |
| Persisted qualification evidence | Git-ignored .local/phase5_b1f |

Dry-run status is **RENDERED_NOT_EXECUTABLE_QUALIFICATION_ONLY**: required tester fields are
rendered, but production adapter/account materialization is deliberately not enabled.
No login or credentials appear in this file. A later authorized execution must revalidate the
current account/environment and safely materialize its identifier; historical bootstrap evidence
does not prove the current session or full-period tick coverage. No new configuration was saved.

## Validation and preservation

New tests cover authorization reuse/missing provenance, hash mismatch, supported/unsupported
ingestion, installed artifact identity, no protected copy, project/candidate mismatch, missing
configuration, wrong terminal, non-DEMO proof, immutable binding, exact dry-run fields, path/INI
injection rejection, UNKNOWN declarations, and zero native calls/database or artifact mutations.
The actual source candidate and all Workbench database records were re-read before qualification.

| Verification | Result |
| --- | --- |
| Backend | PASS — 1,339 tests |
| PostgreSQL/integration and migrations | PASS — 243 tests included in backend total |
| New qualification tests | PASS — 27 (15 unit, 12 PostgreSQL/integration) |
| Frontend | PASS — 100 tests across 11 files |
| Ruff / format / strict mypy | PASS — 286 source files checked by mypy |
| Secret scan | PASS — 427 project files |
| Frontend typecheck / lint / format / production build | PASS |
| Scope / Git-ignore / registry / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 files byte-identical |
| Historical probe/run evidence | PASS — 1,483 files byte-identical; both prior run manifests valid |
| All persisted Workbench records | Unchanged; 2 configurations, 2 runs, 0 results |
| Tags / HEAD | All 20 existing tags unchanged; HEAD remains v0.1.8 |
| git diff --check | PASS |

Full log: `test-results/phase5_b1f-final-gate.log`. Qualification evidence and the native dry-run
remain Git-ignored. No new production database row or native candidate artifact was created.

Changed files:

- src/trading_ecosystem/tester/qualification.py
- src/trading_ecosystem/tester/checkpoint.py
- scripts/verify_phase5_b_scope.py
- tests/test_phase5b_qualification.py
- tests/integration/test_candidate_qualification.py
- PHASE5_B1F_REPORT.md

## Stop and limitations

ONE real Gold Scalper acceptance run **may not start yet**: the installed-candidate/account
adapter boundary remains unresolved. No candidate license/access/initialization/trading or
profitability inference follows from this preflight. Full-period real ticks remain UNKNOWN.

The existing candidate/project, both configurations, both previous runs, their reports and all
previous probes were retained. No second candidate, replacement configuration, native candidate
attempt, infrastructure probe, forward trade, optimization, or Phase 5C work occurred.
Phase 5B.1F changes are intentionally uncommitted; no Phase 5B.1F tag or push was made.

Deviation: none from the Phase 5B.1F definition of done, which explicitly permits a precise
candidate-layer blocker. The adapter was not weakened to turn this blocker into READY.

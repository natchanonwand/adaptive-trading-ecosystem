# Phase 5B.1G - Authorized installed Marketplace EA adapter

**IMPLEMENTATION COMPLETE / PASS.** Final complete Phase 5B gate: **PASS**.
Candidate: **CANDIDATE_EXECUTION_READY**, a non-executing qualification.

Frozen baseline: phase5b-tooling-v0.1.9 at
6b9567a9ad76f27e63f98aeeae98350bcc1700fd.
Before implementation, HEAD, origin/main and the tag matched and the working tree was clean.
All 21 existing tags remain unchanged. No commit, tag or push was performed.

## Candidate and readiness

| Layer | Verified result |
| --- | --- |
| Project | Gold Scalper PRO Acceptance; 1b55ae30-d498-4e75-aa4e-74fb97bf62e9 |
| Candidate | d5508913-c5d6-4f97-99e2-0be7e859b84a; Gold Scalper for MT5 EA |
| Artifact | a8d06843-bb35-4471-9b46-66746cda30cf; 33,746 bytes |
| Authorization | VERIFIED_USER_ATTESTATION; MARKETPLACE_AUTHORIZED |
| Existing authorization event | 5593e28a-796e-45cc-8093-3c65c169e9ef; revision 1, unchanged |
| Persisted / installed SHA-256 | ea21fcd96c9c5683aaf39fc20cf91cc29234f72ac22f202f726fe30e9d028ce4; exact match |
| Execution strategy | INSTALLED_PROFILE_REFERENCE |
| Expert representation | Market\Gold Scalper for MT5 EA.ex5 |
| Profile binding | VERIFIED; original pinned profile, no arbitrary profile search |
| Path safety | VERIFIED; canonical Experts/Market path; traversal, absolute references and symlink/junction parents rejected |
| Terminal | Original pinned executable/hash; build 6230 |
| Terminal binding | 0b14ea86-61b9-4f0f-b9dd-ac766c6166df |
| Account binding | 1d53cf50-0f8c-4520-80f8-4b17cad594e6 |
| Account / broker | DEMO; Exness Technologies Ltd; Exness-MT5Trial14 |
| Environment | READY_AS_OBSERVED from immutable successful Phase 5B.1E proof |
| Observation scope | Historical 2026-10-02; fresh identity/account checks required before later execution |
| BaselineConfiguration | 4a6d8cc7-59ef-474e-8eff-feec6d1658de; reused unchanged |
| Configuration identity | 2e31959d4f4b4e63151c2b1e7be1c3eb4058a06348b163a89d2950f4d271edfc |
| Native config | VERIFIED_DRY_RUN_NO_LAUNCH |
| Declared license | UNKNOWN |
| Declared tester access | UNKNOWN |
| Observed tester access | UNKNOWN |
| Candidate execution readiness | CANDIDATE_EXECUTION_READY |
| Actual execution | NOT_EXECUTED; execution_available=false |

Authorization is a preserved user attestation, not vendor verification. No Marketplace license
acceptance, tester permission, OnInit, trades, history completeness or performance is inferred.

## Adapter and immutable configuration

A separate installed-profile adapter consumes the database-qualified binding and checks the
candidate, authorization, exact installed bytes, profile identity, original executable and
historical DEMO account evidence. Same-name files in another profile are never selected.
Marketplace material is referenced in place: no copy, patch, rename, relocation, unpacking,
decryption, decompilation, signing, or license-storage inspection occurs.

The original portable adapter and its fail-closed environment loader remain unchanged.
User-supplied material retains PORTABLE_ARTIFACT and its existing portable/account limitation.
Marketplace candidates are not sent through that path. The new adapter prepares a dry-run;
it does not add an executable HTTP capability or enable the existing execution service.

The persisted configuration is rendered without changing or replacing it:

| Native field | Value |
| --- | --- |
| Symbol / Period / Model | XAUUSDm / M5 / 4 (EVERY_TICK_BASED_ON_REAL_TICKS) |
| From / To | 2026-01-01 / 2026-06-30 |
| Deposit / Currency / Leverage | 300 / USD / 1:100 |
| Input provenance | TESTER_DEFAULTS; no SET file created |
| Timeout | 600 seconds |
| Optimization / Forward / Remote / Cloud | Disabled |
| AutoTrading / DLL import / Startup Expert / Script | Disabled / disabled / empty / empty |
| Report | Qualification UUID .htm in pinned native data root; not created |

The adapter rejects a pre-existing implicit candidate SET preset that could replace requested
defaults. No existing preset is deleted or modified. Exact default input values remain unknown
before initialization.

Native Expert syntax was grounded in read-only inspection of native-generated build-6230
presets in the single pinned profile, including Expert=Market\Aot.ex5 and
Expert=Market\Atherion Zenith AI EA.ex5. Only Expert lines were exposed. The
[official MT5 configuration documentation](https://www.metatrader5.com/en/terminal/help/start_advanced/start)
also documents nested Experts-relative Tester.Expert references. The previous successful
no-trade probe established main-mode /config behavior in this installation. No new native
syntax probe or candidate initialization occurred.

The dry-run contains exact candidate tester fields but excludes private Common.Login material.
A later authorized acceptance must freshly verify the same DEMO context, transiently materialize
its account identifier and consume the plan using the original terminal in main mode, never
/portable. No saved digest is a bearer capability or permission to launch.

## Workbench and evidence

Workbench exposes a GET-only, same-origin dry-run endpoint with an allowlisted summary.
It never returns protected Marketplace paths, account material or full native configuration.
Select the existing configuration under Baseline, then use Check candidate readiness (dry run).
Earlier probe diagnostics remain historical; the new selected-candidate panel explicitly
labels its successful environment proof READY_AS_OBSERVED.

The real HTTP endpoint and browser UI were independently checked after a controlled Workbench
reload. Both displayed CANDIDATE_EXECUTION_READY, INSTALLED_PROFILE_REFERENCE, verified profile
binding and UNKNOWN license/tester access. Run Baseline remained disabled. No configuration
save or execution action was submitted. The HTTP regression covers relative server-root
resolution to canonical absolute proof paths.

New Git-ignored qualification evidence is in .local/phase5_b1g/:

- qualification.json
- candidate-config.dry-run.txt
- summary.json
- files.json (hashes of those three outputs)
- http-readback.json (actual local GET result)
- preservation snapshots and final completion metadata

Qualification namespace: e2574567-56af-4685-972c-4b478f4cba88; this is not a BaselineRun.
Binding SHA-256: 13d6c3cdfc4961863fa09f3c04e831e7fcce7782fd3c0b162de9a5e49bdeefb8.
Independent requalification from DB/files returned the identical binding and native config.
Operational Workbench server logs are not immutable qualification artifacts.

## Verification and preservation

| Check | Result |
| --- | --- |
| Backend regression | PASS - 1,377 tests |
| PostgreSQL/integration | PASS - 256 tests included in backend total |
| New backend coverage | PASS - 38 cases: 25 unit, 13 integration |
| Frontend | PASS - 105 tests across 12 files; 5 new cases |
| Ruff / format | PASS |
| Strict mypy | PASS - 288 source files |
| Secret scan | PASS - 432 project files |
| Frontend typecheck / lint / format / build | PASS |
| Migrations / scope / Git-ignore / registry / frozen lineage | PASS |
| Frozen evidence | PASS - 1,044 files byte-identical before and after gate |
| Historical evidence | PASS - 1,495 prior files unchanged, including all 1,483 required historical files |
| Previous Phase 5B run manifests | PASS - both independently verified |
| Production Workbench records | Unchanged: 2 configurations, 2 runs, 0 results |
| Prior tags / HEAD | All 21 tags unchanged; HEAD remains frozen v0.1.9 |
| git diff --check | PASS |
| Real HTTP and browser dry-run | PASS; no execution enabled or submitted |

Final complete gate log: test-results/phase5_b1g-final-gate-2.log.

Tests cover authorization, installed identity and same-name substitution, wrong profile,
terminal/account/build mismatch, LIVE rejection, path traversal, absolute paths and linked
parents, implicit presets, proof tampering, exact config rendering, stable bindings, immutable
configuration reuse, UNKNOWN declarations and retained portable behavior. File-read guards
reject unexpected license/account storage access; copy/native/SDK operations are forbidden.
PostgreSQL before/after comparisons verify zero mutations or new runs/results. HTTP tests check
GET-only qualification, duplicate-query and cross-origin rejection and sanitized output.
Frontend tests cover selection, UNKNOWN, precise blockers, unavailable proof and no execution
controls in the dry-run component.

## Changed files

Exactly 11 files; all changes remain uncommitted and unstaged:

- src/trading_ecosystem/tester/installed_profile.py
- src/trading_ecosystem/tester/qualification.py
- src/trading_ecosystem/tester/api.py
- src/trading_ecosystem/tester/checkpoint.py
- scripts/verify_phase5_b_scope.py
- tests/test_phase5b_installed_profile.py
- tests/integration/test_candidate_qualification.py
- dashboard/src/workbench/CandidateReadiness.tsx
- dashboard/src/workbench/ReadinessPanel.tsx
- dashboard/tests/candidate-readiness.test.tsx
- PHASE5_B1G_REPORT.md

## Strict stop and limitations

The candidate-layer ingestion blocker is resolved by the installed-profile preparation strategy.
Exactly ONE real Gold Scalper acceptance attempt may be considered in a later explicitly
authorized workflow, subject to fresh account/profile/artifact validation and controlled
consumption of this plan. This phase does not enable or perform that attempt; the existing
production service remains fail-closed. License/access/init/trading/complete real-tick coverage
and performance remain unverified. Fresh account materialization has not been performed.

Native MT5 launches: 0. Gold Scalper executions: 0. Infrastructure probes: 0.
New production BaselineRuns/BaselineResults: 0. BaselineConfiguration changes: 0.
No optimization, forward trading, Phase 5C, commit, tag or push occurred.

Deviations: none from the authorized non-executing scope. All remaining runtime checks are
explicitly deferred to a later separately authorized acceptance, not represented as completed.

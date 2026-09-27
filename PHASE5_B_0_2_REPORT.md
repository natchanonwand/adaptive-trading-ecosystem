# Phase 5B.0.2 — Real Acceptance Readiness Reconciliation

Status: IMPLEMENTATION COMPLETE / PASS. Real acceptance remains NOT READY; no real execution was performed.

## Root cause and checkpoint contract

The old verifier required HEAD and origin/main to equal Phase 5B tooling v0.1.0,
so the legitimate frozen v0.1.1 checkpoint failed before acceptance execution.
The new explicit checkpoint contract pins the annotated tag objects and resolved
commits of both Phase 5A tags and both Phase 5B tooling tags, verifies their ordered
ancestry, and requires current work and origin/main to derive from v0.1.1.
An explicit immediate-checkpoint change allowlist restricts this correction.
The historical Phase 5B.1 stopped report is separately strict byte-hash pinned.
No tag, commit, history or frozen generated evidence was rewritten.

## Contracts and UX

- Authorization provenance: UNKNOWN, USER_SUPPLIED_AUTHORIZED,
  FREE_VENDOR_DISTRIBUTION, MARKETPLACE_AUTHORIZED, VENDOR_TRIAL_AUTHORIZED,
  OTHER_EXPLICIT_AUTHORIZATION, PROHIBITED_OR_UNVERIFIED.
- Supporting source label/reference and authorization basis are mandatory for
  an affirmative attestation. The server records time, revision, candidate UUID,
  event UUID and preceding event UUID. Updates append history and reject stale edits.
  Values are explicitly user-attested, never represented as vendor verification.
  Original license/tester declarations are not overwritten.
- Evidence → Source & Authorization captures these declarations through the
  same-origin local Workbench API. Artifact verification is displayed separately.
- Baseline → Save BaselineConfiguration stores an immutable, independently hashed
  specification with its own UUID, project/candidate/artifact association and
  explicitly confirmed validated inputs. Saving does not create a run or process.
- The separate Run Baseline action uses the selected configuration and explicit
  confirmation. The backend rejects missing/unknown/prohibited authorization and
  absent/mismatched configuration. It checks authorization again at start/preflight.
  Existing attempts, observations, results and cancellation remain accessible.
- Inputs distinguish TESTER_DEFAULTS, VENDOR_DOCUMENTED_DEFAULTS,
  USER_SUPPLIED_SET and USER_CONFIRMED_VALUES. Opaque defaults are explicitly
  marked not exactly known before initialization; documented defaults need a reference.
  Exact supplied values are validated without optimization.
- Onboarding readiness is distinct from acceptance execution readiness. UNKNOWN
  license/tester declarations do not block; UNKNOWN authorization does.

## Current real project

Gold Scalper PRO Acceptance; project UUID
`1b55ae30-d498-4e75-aa4e-74fb97bf62e9`.


Verified post-migration readback is recorded below. No metadata was fabricated.

## Changed files

Modified:
- dashboard/src/workbench/BaselinePanel.tsx
- dashboard/src/workbench/Workbench.tsx
- dashboard/src/workbench/api.ts
- docs/PHASE5_B_AUTOMATED_BASELINE.md
- scripts/verify_phase5_b_scope.py
- src/trading_ecosystem/tester/adapter.py
- src/trading_ecosystem/tester/api.py
- src/trading_ecosystem/tester/contracts.py
- src/trading_ecosystem/tester/service.py
- src/trading_ecosystem/tester/store.py
- tests/integration/test_baseline.py

Added:
- PHASE5_B_0_2_REPORT.md
- dashboard/src/workbench/ReadinessPanel.tsx
- dashboard/tests/readiness.test.tsx
- migrations/baseline/versions/0002_readiness.py
- src/trading_ecosystem/tester/checkpoint.py
- src/trading_ecosystem/tester/readiness.py
- tests/integration/test_baseline_readiness.py
- tests/test_phase5b_readiness.py

Pre-existing untracked PHASE5_B1_ACCEPTANCE_REPORT.md is preserved, not modified.
Operational logs and database readback hashes are under Git-ignored test-results/
and .local/phase5_b_0_2/. No binary EA is added to Git.

## Remaining user confirmations

1. In Evidence → Source & Authorization, choose the accurate provenance category
   and supply source label/reference and the explicit authorization basis. Confirm
   the declaration without entering credentials or license secrets.
2. In Baseline, choose the historical from/to dates (at most 366 days), review
   deposit and leverage, USD currency and timeout, and confirm the existing
   XAUUSD/XAUUSDm/M5 DEMO binding and fixed real-tick tester model.
3. Choose input provenance; supply the vendor reference or exact permitted .set
   values when applicable, or acknowledge opaque tester defaults. Review and save.
4. Actual EA/Strategy Tester execution remains outside this phase and requires
   a later authorized acceptance workflow. No Run Baseline action is taken here.

Limitations: user attestation is not independent vendor/license verification;
opaque defaults cannot establish exact input values before initialization;
readiness is not a completed acceptance result or proof of tester access.

Deviations: none. No optimization, Phase 5C, broker writes, live trading,
license bypass, real execution attempt, commit, tag or push is performed.



## Verified current project and complete gate

| Current field | Observed value |
| --- | --- |
| Artifact | VERIFIED |
| Authorization provenance | UNKNOWN; zero attestation events |
| License / tester declarations | UNKNOWN / UNKNOWN, preserved |
| Explicit binding | Exness DEMO; XAUUSD / XAUUSDm / M5; confirmed |
| Persisted configurations | 0 |
| Real execution attempts / results | 0 / 0 |
| Onboarding status | BASELINE_READY |
| Acceptance execution | NOT_READY |
| Reasons | BLOCKED_AUTHORIZATION_PROVENANCE; BASELINE_CONFIGURATION_REQUIRED |

The additive migration reached `0002_readiness`. All five pre-existing Workbench
 table content hashes remained identical: artifacts, candidates, projects,
baseline_runs and baseline_results. The refreshed Workbench returned HTTP 200.
Readback: `.local/phase5_b_0_2/gold-project-after.json`. Before/after database
snapshots: `.local/phase5_b_0_2/database-before.json` and `database-after.json`.

`./scripts/verify_phase5_b.ps1` completed successfully. Full log:
`test-results/phase5_b_0_2-gate.log`; backend JUnit: `test-results/phase5_a.xml`.

| Check | Result |
| --- | --- |
| Backend regression | PASS — 1,233 tests |
| PostgreSQL/integration, including migrations | PASS — 231 tests, included in backend count |
| Frontend regression | PASS — 99 tests across 11 files |
| Ruff / Ruff format | PASS — 321 Python files formatted |
| Strict mypy | PASS — 273 source files |
| Secret scan | PASS |
| Frontend typecheck / lint / format / production build | PASS |
| Frozen lineage / scope / Git-ignore checks | PASS |
| Strict frozen evidence byte verification | PASS — 1,044 files |
| Prior Phase 5B snapshot | PASS — 363 unchanged files |
| Stopped Phase 5B.1 report | PASS — original SHA-256 preserved |
| git diff --check | PASS |

New coverage adds 17 backend tests and 2 frontend tests. Existing simulated-run
fixtures now persist explicit synthetic authorization and configuration first;
prior assertions remain in place. Coverage includes checkpoint lineage failures,
invalid configurations, immutable readback, authorization audit and stale edits,
revoked rights blocking start, same-origin restrictions and saving without execution.
Older evidence-reconciliation tests still reject normalization of generated evidence.
Zero finalized real Phase 5B manifests were found; zero is not real acceptance success.
Final documentation-only edits received an additional scope/secret/format/diff check.

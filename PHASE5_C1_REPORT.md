# Phase 5C.1 — Controlled experiment runner

Status: COMPLETE / PASS. No real campaign has executed.
Final verification completed on 2026-10-12 (Asia/Bangkok).

## Baselines and preceding UI-1 freeze

UI-1 was frozen and pushed before this implementation:

- Commit / HEAD / origin/main / `ui-retro-v0.2.0`:
  `efdf23b4c41fab1f990b414e222d7bf4e75b2812`.
- Annotated UI-1 tag object: `9de78eacf518633d12cacec2a04935b9d19a8918`.
- Ten UI-1 files committed, clean tree verified at that checkpoint; all prior tags preserved.
- Required research baseline `phase5c-contract-v0.1.0` remains
  `f6e3621973c55bc479c7be0b9d8833de0436c6f4`.
- Phase 5C.1 changes are uncommitted. No Phase 5C.1 tag or push was performed.

The ten UI-1 freeze files were `UI1_REPORT.md`,
`dashboard/src/workbench/BaselinePanel.tsx`,
`dashboard/src/workbench/ResearchSurfaces.tsx`,
`dashboard/src/workbench/Workbench.tsx`,
`dashboard/src/workbench/workbench.css`,
`dashboard/tests/baseline.test.tsx`,
`dashboard/tests/research-surfaces.test.tsx`,
`docs/UI1_RESEARCH_SURFACES.md`, `scripts/verify_ui1.py` and
`scripts/verify_ui1.ps1`. That freeze preserved Phase 5B/5C state and zero experiment
executions. The subsequent Phase 5C.1 work began only after the verified freeze,
as separately requested by the operator.

## Implementation and results

| Area | Implemented behavior |
| --- | --- |
| Contracts | Only FROZEN definitions, with definition/baseline/component identities checked |
| Candidates | Deterministic GRID and RANDOM_SEEDED; numeric canonicalization; deterministic duplicate collapse |
| Budgets | Configuration slots, conservative native reservations, persisted wall-time deadline, concurrency 1 |
| Development | Declared constraints before declared objective; execution failure distinct from rejection |
| Selection | All lexicographic ties or Pareto front in original candidate order; immutable selection digest |
| Validation | Only development-selected candidates; no feedback into generation or selection |
| LOCKED_OOS | Scheduler and boundary exclusion; denied/audited API actions; no UI control |
| Recovery | Persisted run IDs and order; recover reserved work without relaunch; never reset budgets |
| Cancellation | Stop scheduling; signal only owned Phase 5B execution; retain evidence and consumption |
| Execution reuse | Existing Phase 5B Service, artifact/account safety, adapter, parser and evidence infrastructure |
| Persistence | One additive campaign ledger and separate migration version table; no frozen migration changes |
| API/UI | Explicit create/inspect/start/resume/cancel; minimal Retro campaign panel; no automatic execution |

The ledger binds versioned policies into the plan identity. Duplicate samples do not
replenish configuration slots. Budget is conservatively charged before handoff even
when preparation prevents a native launch. Failure policy continues within budget
without retry. An interrupted reservation is reconciled by ID; uncertain active
execution requires ownership reconciliation instead of a second launch.

Zero trades remains a valid observation. Undefined denominator metrics remain null.
No synthetic metrics are inserted into the production database. Test fixture values
are clearly synthetic and exist only in isolated disposable databases.

## Tests and browser review

Added 39 backend cases: 23 unit and 16 PostgreSQL/integration cases. They cover
determinism, conditional domains, duplicate collapse, frozen identity rejection,
budget/resume, deadline persistence, constraint/objective ordering, validation
isolation, OOS denial, zero/null, failures, invalid results, cancellation, concurrency,
ledger tampering, HTTP safety, and the existing Phase 5B Service/parser through a
synthetic native callback. No actual terminal executable is launched.

Added eight frontend tests for explicit inspection/creation/start, cancellation,
budget and selection display, zero/null and failure display, unavailable storage,
and read-only refresh. All pre-existing tests remain unchanged.

Browser review used the built Workbench with an isolated synthetic PostgreSQL
database on port 8786. It displayed three candidates, six consumed reservations,
three DEVELOPMENT and three VALIDATION observations, frozen development selection,
zero trade counts and null profit factors. Desktop and 390px review passed without
document horizontal overflow or console errors; wide tables scroll inside their
own regions. No OOS control was present. The fixture server and disposable database
were removed after review. Screenshots remain Git-ignored under `.local/phase5_c1/`.

The additive campaign migration was applied to the local Workbench database. Only
the verified Workbench server was restarted to load the new routes. No real
experiment or campaign records were created, and existing Phase 5B tables remained
unchanged. No native tester or infrastructure probe was started.

## Gate evidence

Final complete gate: PASS (exit code 0). Evidence is retained in
`.local/phase5_c1/completion-gate.log` and `test-results/phase5_c1.xml`.

| Verification | Result |
| --- | --- |
| Backend regression | 1,517 PASS; no skips/failures |
| PostgreSQL/integration | 311 PASS, included in backend total |
| Frontend | 152 PASS across 16 test files |
| New tests | 39 backend + 8 frontend; existing tests unchanged |
| Ruff / Python format | PASS; 389 files formatted |
| Strict mypy | PASS; 322 source files |
| Secret scan | PASS; 490 project files, no findings |
| Frontend typecheck / lint / format / production build | PASS |
| Fresh migrations and idempotent campaign migration | PASS |
| Scope / Git-ignore / frozen lineage / registry | PASS |
| Frozen evidence | 1,044 byte-identical |
| Historical evidence | 1,621 byte-identical |
| Phase 5B database / publication / finalized manifests | PASS, unchanged |
| Production experiment/campaign execution count | 0 |
| Browser desktop / 390px review | PASS, synthetic fixture only |
| git diff --check | PASS |

The first complete attempt passed all 1,517 backend cases, then detected mixed line
endings in the new Workbench entry-point wiring. Formatting was corrected without a
behavior change; the complete gate was restarted. No existing test was weakened.
The subsequent frontend regression identified a legacy assertion requiring the
Phase 5C.0 definition-section label. The new explanatory text now retains that
label while explicitly distinguishing the Phase 5C.1 campaign panel. The unchanged
seven-test Workbench suite passed after this copy correction; the subsequent fresh
complete gate passed all checks above. Earlier failed gate logs remain available locally.

## Preservation and scope

Required checks verify 1,044 frozen evidence files and 1,621 historical files
byte-for-byte, the historical eight Phase 5B tables, three finalized run manifests,
the original blocked acceptance outcome, its derived publication and all Git tags.
The production state remains three BaselineRuns, zero BaselineResults, one derived
publication, one historical Gold Scalper native execution and zero real experiment
or campaign executions. No original BaselineConfiguration was modified.

## Actual Phase 5C.1 change set

20 files: two existing integration points and 18 new files.

1. `src/trading_ecosystem/workbench/__main__.py`
2. `dashboard/src/workbench/ExperimentsPanel.tsx`
3. `src/trading_ecosystem/experiments/campaigns.py`
4. `src/trading_ecosystem/experiments/campaign_store.py`
5. `src/trading_ecosystem/experiments/campaign_runner.py`
6. `src/trading_ecosystem/experiments/baseline_boundary.py`
7. `src/trading_ecosystem/experiments/campaign_api.py`
8. `alembic-campaigns.ini`
9. `migrations/campaigns/__init__.py`
10. `migrations/campaigns/env.py`
11. `migrations/campaigns/versions/__init__.py`
12. `migrations/campaigns/versions/0001_campaigns.py`
13. `dashboard/src/workbench/CampaignPanel.tsx`
14. `dashboard/tests/campaigns.test.tsx`
15. `tests/test_campaigns.py`
16. `tests/integration/test_experiment_campaigns.py`
17. `scripts/verify_phase5_c1.py`
18. `scripts/verify_phase5_c1.ps1`
19. `docs/PHASE5_C1_CONTROLLED_RUNNER.md`
20. `PHASE5_C1_REPORT.md`

No runtime outputs, EX5 binaries, screenshots, credentials or database files are
included in this change set. Existing observer campaign tests were preserved; the
new experiment campaign integration tests use a distinct filename.

## Limitations and next-phase boundary

The qualified native observation adapter exposes NET_PROFIT, TRADE_COUNT and
PROFIT_FACTOR for EXPLORATORY_GROSS. Unsupported declared metrics and cost-modeled
definitions produce typed pre-launch blockers; formulas are not invented from
descriptive contract prose. They need separately qualified extractors before use
in a real campaign. Domain selection can consume any validated, explicitly
declared metric supplied by a qualified boundary.

The runner is conservatively serial. It never retries uncertain native ownership.
Wall-time enforcement requests cancellation through the existing bounded process
lifecycle; termination/cleanup can finish after the scheduling deadline. No new
run starts after the deadline. Interrupted workers require explicit resume and
retain their audit trail; service startup does not automatically resume them.

Phase 5C.2 cannot begin under this authorization. A separate frozen checkpoint,
explicit real-campaign authorization and a reviewed supported frozen experiment
contract are required. No UI-2, champion selection, adaptive optimization, forward
test or OOS execution was started.

Design choices within scope: separate additive migration lineage preserves frozen
migration tests; tied lexicographic/Pareto selections and conservative reservation
accounting are explicitly versioned. No scope deviation authorizes real execution.

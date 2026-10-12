# UI-2 — Retro Experiment Lab

Status: COMPLETE / PASS. Presentation only; no real campaign or native execution.

## Frozen prerequisite

Phase 5C.1 was committed and pushed before UI-2 began:

- Commit: `928ef6fbddccd999f79cbb19cbcb3ba99438457f`
- Annotated tag object: `c9962e28fe64a112d6a386e4fd33957c7dc4e815`
- Tag: `phase5c-runner-v0.1.0`; HEAD and origin/main resolve to that commit.
- Exact 20-file Phase 5C.1 set matched its completion receipt. Earlier tags unchanged.
- Working tree was clean after freeze; UI-2 changes are deliberately uncommitted.
- Freeze receipt: `.local/ui2/phase5c1-freeze.json` (ignored).

## Presentation contract

`ExperimentLab` composes the existing RetroPanel, status, identity and table primitives.
The dossier exposes hypothesis, candidate, immutable definition identity and classification.
The protocol shows DEVELOPMENT, SELECTION FROZEN, VALIDATION and sealed LOCKED_OOS,
with actual half-open date boundaries. It explicitly describes protocol, not live progress.
OOS has no performance preview, unlock or run action.

The parameter register shows native key, type, baseline, domain/choices, provenance,
source reference and condition. Draft editing and explicit freeze confirmation remain;
frozen fields are disabled inside an inspection disclosure. Revisions retain new identities.

Budget meters show used / remaining / maximum only from persisted campaign observations.
Unloaded usage is unavailable, not zero. Unique candidate counts do not imply replenishing
duplicate sampling slots. Remaining capacity is a limit, not encouragement to execute.
Campaign tables join configuration identities to recorded DEVELOPMENT/VALIDATION states,
decisions and observed metrics. Existing run-level provenance remains available.

Only NET_PROFIT, TRADE_COUNT and PROFIT_FACTOR are offered for new metric declarations,
with EXPLORATORY_GROSS classification. Stored unsupported declarations remain visible and
preserved as unqualified; no automatic migration or reinterpretation occurs.
Measured zero remains `0`; null/unavailable remains an em dash. No synthetic production metrics.

The current API lacks an authoritative campaign execution authorization field. UI-2 therefore
offers no enabled start/resume action and sends no start request. Existing explicit plan creation,
inspection and cancellation contracts are unchanged. No plan was created in production.

## Verification

| Check | Result |
| --- | --- |
| Frontend regression | PASS: 172 tests, 17 files |
| New UI-2 tests | 20; one existing start-control test updated for disabled UI-2 authorization |
| Typecheck / lint / Prettier / production build | PASS |
| Ruff / Python format / strict mypy / secret scan | PASS |
| Scope / lineage / Git-ignore / diff check | PASS |
| Frozen evidence | 1,044 files byte-identical |
| Historical evidence | 1,621 files byte-identical |
| Phase 5B database | Eight tables unchanged; 3 runs, 0 results, 1 publication |
| Phase 5B manifest readback | Three finalized manifests independently verified |
| Real experiment definitions / campaigns | 0 / 0 |
| Gold Scalper native executions | Remains 1; none in UI-2 |
| Browser desktop / 390px | PASS |

Full UI-2 gate: `scripts/verify_ui2.ps1`; log `.local/ui2/full-gate.log`.
Backend and integration sources remain frozen byte-for-byte relative to the runner baseline.
The associated Phase 5C.1 backend result is 1,517 passed, including 311 integration tests;
UI-2 reran frontend and preservation gates, not the backend regression suite.

Tests cover dossier identity/state, immutable fields, protocol/OOS, unknown and measured budgets,
qualified metric options, preservation of unsupported declarations, zero/null, empty campaign,
candidate/run joins, and absence of a start request. Existing navigation/freeze tests pass.

Browser review used the actual compiled Workbench with an isolated disposable PostgreSQL
fixture: saved DRAFT, FROZEN without campaign, and synthetic completed campaign.
Native execution was prohibited in the fixture. Production state was not populated for screenshots.
The disposable database was removed after review. Desktop 1280px and mobile 390px were inspected;
mobile document scroll width was 375px, with table-local overflow rather than page overflow.
Semantic headings, labeled controls/meters, keyboard-focusable table regions, explicit disabled
controls and inherited focus/reduced-motion styling remain. No browser console errors observed.
Proof images: `.local/ui2/desktop.png`, `.local/ui2/mobile.png` (synthetic, ignored).

## Actual changed files (11)

- `dashboard/src/workbench/ExperimentLab.tsx`
- `dashboard/src/workbench/experiment-lab.css`
- `dashboard/src/workbench/ExperimentsPanel.tsx`
- `dashboard/src/workbench/CampaignPanel.tsx`
- `dashboard/tests/experiment-lab.test.tsx`
- `dashboard/tests/experiments.test.tsx`
- `dashboard/tests/campaigns.test.tsx`
- `scripts/verify_ui2.py`
- `scripts/verify_ui2.ps1`
- `docs/UI2_EXPERIMENT_LAB.md`
- `UI2_REPORT.md`

## Limits and next step

No implementation blocker remains. Execution authorization is not exposed by the existing API,
so start/resume stays unavailable. Per-run constraint evaluations or objective ranking are not
invented from aggregate decisions. Any new API fields require separate authorization.
Manual accessibility review is not a complete assistive-technology audit.

Review UI-2 and authorize its freeze separately. Phase 5C.2 and UI-3 have not started.
No OOS access, tuning, new metric qualification, native execution or backend contract change.
No UI-2 commit, tag or push. Deviations: none; synthetic browser fixtures were isolated and removed.

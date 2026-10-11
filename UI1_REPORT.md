# UI-1 — Retro research run, evidence and publication surfaces

Status: COMPLETE / PASS.

## Frozen starting point

UI-0 was frozen and pushed before UI-1 began:

- Commit / origin/main / `ui-retro-v0.1.0`: `d75ce607d3c4e5b98aad9d24c4d4127ca76af20c`.
- Annotated tag object: `589846188f697a1c69ec1cf1e5ea9534b8902d8f`.
- Eight UI-0 files committed; clean tree verified at that checkpoint.
- All preceding tags preserved. UI-1 itself is not committed, tagged or pushed.

## Presentation changes

- Baseline register: semantic compact table, status badges, abbreviated IDs with full accessible
  values, explicit inspect actions, configuration/environment/timing and result availability.
  The existing saved-run selector and execution confirmation behavior remain available.
- Run detail: identity, execution, full timestamps including timezone, elapsed seconds,
  native exit code, observed status, immutable configuration and evidence.
- Publication: three separate execution-time outcome, later reconciliation and publication
  sections. The original blocked run is never visually changed to COMPLETE.
- Metrics: compact UI-0 strips for primary metrics; numeric-aligned table for all additional
  reported metrics. Measured zero retains precision; null remains an em dash, never 0%.
- Evidence: grouped ordered provenance table for authorization, artifact, configuration,
  execution plan, native report, reconciliation and publication. Full hashes remain selectable;
  labeled copy buttons provide non-obscuring success/failure feedback.
- Evidence page reuses these surfaces and the existing authorization UI. The legacy fallback
  for projects without readiness metadata is read-only. Existing authorization controls are
  preserved, not invoked during review.
- Tables have sticky headers, focusable contained scrolling and focus/hover treatment.
  Full timestamps remain available; research table bodies use the UI-0 operational/body fonts.
  Long attestation URLs now wrap within generic panels at narrow widths.

## Research preservation

Acceptance run: `aebb719c-6738-4b1a-a323-3f405ed512fe`.
Execution outcome: `BLOCKED_REAL_TICKS_UNAVAILABLE` (unchanged).
Reconciliation: `REAL_TICK_COVERAGE_VERIFIED_100`.
Publication: `PUBLISHED / POST_RUN_RECONCILIATION`.
Publication ID: `b6a9c561-e67d-5f5e-9cff-c58c8ca3925e`.
Publication identity:
`e1d01c152831d1fe7f3a0b9736339cba0e961dbcd7130ea7d57967c6f13a5cf2`.

Native exit code 0 is displayed independently from the historical validator outcome.
The original-native-report hash remains manifest provenance only; original encoding bytes
were not retained. The verified stored UTF-8 report identity is separately identified.
Zero trades is not interpreted as strategy quality.

No backend/API/experiment contracts changed. No new execution, BaselineRun, result,
publication, experiment, tuning campaign or configuration mutation was authorized or performed.

## Verification

Full UI-1 gate: `scripts/verify_ui1.ps1`; ignored logs under `.local/ui1/`.

| Check | Result |
| --- | --- |
| Frontend regression | 144 PASS across 15 files; 8 new tests |
| Typecheck / lint / format / production build | PASS |
| Ruff / Python format / strict mypy / secret scan | PASS |
| UI-only scope / frozen checkpoint / all tag refs / diff check | PASS |
| Frozen evidence | 1,044 files byte-identical |
| Historical evidence | 1,621 files byte-identical |
| Phase 5B persisted state | Eight tables unchanged; 3 runs, 0 results, 1 publication |
| Finalized run evidence | Three manifests independently verified |
| Phase 5C | Contracts unchanged; zero real experiment records |

Backend tests were not rerun for this presentation-only rollout. Backend/API source is
strictly unchanged from the frozen checkpoint; the live read-only preservation checks above
were run. Previously frozen backend total is 1,478, including 295 PostgreSQL/integration tests;
these are historical totals, not new UI-1 test results.

Tests cover register/status/strategy, keyboard inspection, full timestamps and native exit,
immutable outcome versus reconciliation/publication, zero/null metrics, evidence categories,
full identity copy and denied clipboard access, absent identities, and read-only fallback.
Existing navigation, execution confirmation, cancellation and experiment tests remain passing.

## Files changed (10)

1. `dashboard/src/workbench/BaselinePanel.tsx`
2. `dashboard/src/workbench/ResearchSurfaces.tsx`
3. `dashboard/src/workbench/Workbench.tsx`
4. `dashboard/src/workbench/workbench.css`
5. `dashboard/tests/baseline.test.tsx`
6. `dashboard/tests/research-surfaces.test.tsx`
7. `docs/UI1_RESEARCH_SURFACES.md`
8. `scripts/verify_ui1.py`
9. `scripts/verify_ui1.ps1`
10. `UI1_REPORT.md`

## Browser review

Reviewed the real local Workbench, existing acceptance run, Baseline register/detail,
Evidence and published reconciliation at 1365×1000 and 390×844. Read-only navigation,
keyboard focus, copy feedback and full timestamps were exercised. No save, readiness probe,
start, cancel or experiment action was invoked.

Desktop document client/scroll widths were both 1350px. At 390px (15px scrollbar), both
were 375px after fixing the long attestation URL wrapping. Tables remained horizontally
scrollable inside their focusable regions. No status/metric overlap was observed. Existing
UI-0 contrast/focus tokens and reduced-motion rules remain in force. Keyboard copy behavior
and clipboard failure are additionally covered by tests.

Screenshots are ignored runtime artifacts under `.local/ui1/`, including
`runs-desktop.jpg`, `run-narrow.jpg`, `publication-desktop.jpg` and `evidence-390.jpg`.
The production build is served by the existing local Workbench; no server/native-probe
restart was needed. Remaining design-system limitation: large datasets still use contained
scrolling rather than pagination/virtualization; neither is introduced in UI-1.

## API limits and remaining scope

The run-list payload has no publication or execution-strategy field. Inspecting a run uses
the existing detail endpoint to reveal the publication and its strategy. Uninspected rows
explicitly say to inspect; older runs without publications do not acquire inferred strategies
or execution-plan hashes. These are optional data-availability limits, not fabricated values.

No API exposure was added. The existing API provides the full required acceptance-run
publication/provenance fields. No broad Experiments redesign, UI-2 or Phase 5C.1 work started.
Next UI work requires separate authorization; a focused review of remaining unconverted
surfaces is appropriate before any further rollout. No scope deviation.

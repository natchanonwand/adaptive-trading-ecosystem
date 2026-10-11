# UI-0 report

Status: COMPLETE / PASS. Verified 2026-10-11 (Asia/Bangkok).
Frozen baseline: `phase5c-contract-v0.1.0`,
`f6e3621973c55bc479c7be0b9d8833de0436c6f4`.

## Delivered presentation system

Dark navy canvas, square panels/windows, cyan primary accent, violet secondary accents,
amber warning/focus and coral failure states, restrained grid and hard shadows. Brand uses
local terminal/raster display-font fallbacks; body, forms, dense data, numbers and hashes
retain readable sans/mono roles. No external fonts, textures, binaries or dependencies.
Semantic background/border/text/accent/state/interaction tokens live in Workbench-only CSS.
The separate monitoring dashboard theme is unchanged.

Reusable foundation: RetroPanel/RetroWindow, SectionHeader, Button, StatusBadge, Field,
Select, Checkbox, Tabs, MetricCard/MetricStrip, DataTable, Callout, EmptyState and
IdentityField/MonoValue. Progress and delta displays are deferred because no applicable
experiment results exist. No fictitious metrics or activity are introduced.

The shell has a desktop navigation rail that wraps on smaller screens. Overview is the
single representative conversion: project dossier, actual registered artifact sizes and
configuration count, full identity register, explicit metadata/readiness status and research
context callout. Experiments retains its original implementation/layout and only inherits
shared presentation. Baseline execution and publication components are unmodified.

## Verification

| Check | Result |
|---|---|
| Frontend regression | PASS: 136 tests / 14 files, including all prior 117 tests |
| New UI-0 tests | PASS: 19 cases; no prior test changed |
| Frontend typecheck / lint / format | PASS |
| Production build | PASS |
| Ruff / Python format / strict mypy / secret scan | PASS |
| Scope / Git-ignore / frozen lineage / whitespace | PASS |
| Phase 5B run manifest verification | PASS: 3 finalized manifests |
| Phase 5B database/publication readback | PASS: 8 tables unchanged |
| Frozen evidence | PASS: 1,044 byte-identical |
| Historical evidence | PASS: 1,621 byte-identical |
| Phase 5C contracts/API/backend | Unchanged from frozen baseline |
| Real experiment records/executions | 0; no campaign or tuning |

Gate: `scripts/verify_ui0.ps1`; log: `.local/ui0/gate.log` (ignored).
Backend/PostgreSQL regression was not rerun for this presentation-only phase: the frozen
1,478/295 baseline is preserved through the strict changed-file boundary. Fresh database,
publication, run-manifest and evidence-hash checks were run instead. No migration changed.

Tests cover explicit status text, unknown/blocker distinction, keyboard activation and
disabled buttons, native labeled/read-only/error form controls, null versus numeric/decimal
zero, named table scrolling, mono identities, panel slots, navigation and real Overview data.
Initial failures were presentation/test-integration issues, corrected without weakening any
prior test: retain the existing project-badge class and avoid duplicate verification badges.

## Accessibility and browser review

Real Workbench restarted with new ignored logs in `.local/ui0/`; previous logs preserved.
Overview inspected at 1365px desktop and 390px narrow viewport. Navigation wraps sensibly;
readable metadata and full identities remain available. Narrow document client/scroll widths
both measured 375px (scrollbar excluded): no horizontal page overflow. Temporary viewport
override was reset after review.

Keyboard traversal verified in the real browser; focused Baseline navigation had computed
outline `rgb(255, 240, 165) solid 3px`. Button hover/pressed/disabled rules are explicit;
keyboard/disabled behavior is covered by tests. Reduced-motion CSS removes animations,
transitions and press displacement; there is no continuous animation. Declared operational
text/state tokens against panel backgrounds have a minimum contrast ratio of 6.44:1.
This is targeted accessibility review, not a complete external accessibility certification.

Baseline navigation and original acceptance readback were checked: immutable execution
outcome BLOCKED_REAL_TICKS_UNAVAILABLE remains visible alongside the separately published
reconciliation. Zero trades/profit and unavailable win rate remain distinct. Experiments
shows LOCKED_OOS and definition-only functionality; no form was submitted or run started.

Review screenshots (ignored, not committed): `.local/ui0/overview-desktop.jpg` and
`.local/ui0/overview-narrow.jpg`.

## Exact changed file set

- `dashboard/src/workbench/Workbench.tsx`
- `dashboard/src/workbench/workbench.css`
- `dashboard/src/workbench/retro.tsx`
- `dashboard/tests/retro.test.tsx`
- `docs/UI_RETRO_DESIGN_SYSTEM.md`
- `UI0_REPORT.md`
- `scripts/verify_ui0.py`
- `scripts/verify_ui0.ps1`

Design documentation: `docs/UI_RETRO_DESIGN_SYSTEM.md` contains principles, tokens,
typography, spacing, component inventory, states, null semantics, accessibility, motion,
examples and rollout guidance.

Recommended UI-1, only after new authorization: adopt primitives in evidence/run tables and
publication readback, then review complex forms separately. Do not tie presentation rollout
to Phase 5C.1 or execution capability.

Blockers: none. Deviations: no scope deviations; browser tooling briefly timed out and was
reconnected. No API/business semantics, database values or frozen research files changed.
No Phase 5C.1, UI-1, experiment execution, tuning, commit, tag or push.
